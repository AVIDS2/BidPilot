'use client';

import Link from 'next/link';
import { ArrowUpRight, FileCheck2, FileDown } from 'lucide-react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { LiveSyncStatus } from '@/components/bidpilot/live-sync-status';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { ProjectPicker } from '@/components/bidpilot/project-picker';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { LoadingButton } from '@/components/ui/loading-button';
import { useProjectSelection } from '@/hooks/use-project-selection';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import {
  exportDeliverableDocx,
  exportDeliverablePdf,
  listDeliverables,
  listProjects
} from '@/lib/bidpilot-api';
import { toast } from 'sonner';

export default function DeliverablesPage() {
  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const { projectId, onChange: setSelectedProjectId } = useProjectSelection(projects.data);
  const query = useQuery({
    queryKey: ['deliverables', projectId],
    queryFn: () => listDeliverables(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  return (
    <>
      <PageHeader
        eyebrow='投标工作流'
        title='交付物'
        description='查看响应文档、版本状态和可下载的最终交付结果。'
        action={
          projects.data?.length ? (
            <div className='flex flex-wrap items-center justify-end gap-2'>
              <LiveSyncStatus
                active={Boolean(query.data)}
                dataUpdatedAt={Math.max(projects.dataUpdatedAt, query.dataUpdatedAt)}
                intervalLabel='每 30 秒'
                isFetching={projects.isFetching || query.isFetching}
                onRefresh={() => void Promise.all([projects.refetch(), query.refetch()])}
              />
              <ProjectPicker
                projects={projects.data}
                value={projectId}
                onChange={setSelectedProjectId}
              />
            </div>
          ) : undefined
        }
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {projects.isPending || query.isPending ? (
          <QuerySkeleton rows={5} />
        ) : projects.error || query.error ? (
          <QueryError
            message={
              (projects.error || query.error) instanceof Error
                ? (projects.error || query.error)?.message
                : undefined
            }
          />
        ) : !projects.data?.length ? (
          <EmptyState title='还没有项目' description='先创建项目并完成一次响应流程。' />
        ) : !query.data?.length ? (
          <EmptyState
            title='还没有交付物'
            description='Agent 完成章节起草和审核后，交付物会出现在这里。'
          />
        ) : (
          <Card>
            <CardContent className='overflow-x-auto p-0'>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>交付物</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>导出</TableHead>
                    <TableHead className='text-right'>打开</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <div className='flex items-center gap-3'>
                          <span className='bg-primary/10 text-primary flex size-8 items-center justify-center rounded-md'>
                            <FileCheck2 className='size-4' />
                          </span>
                          <span className='font-medium'>{item.title}</span>
                        </div>
                      </TableCell>
                      <TableCell className='text-muted-foreground'>{item.type}</TableCell>
                      <TableCell>
                        <Badge variant='outline'>{item.status}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className='flex flex-wrap items-center gap-1'>
                          <span className='text-muted-foreground mr-1 inline-flex items-center gap-1.5 text-xs'>
                            <FileDown className='size-3.5' />
                            {item.export_status}
                          </span>
                          <DeliverableExportActions deliverableId={item.id} />
                        </div>
                      </TableCell>
                      <TableCell className='text-right'>
                        <Link
                          className={buttonVariants({ size: 'sm', variant: 'ghost' })}
                          href={`/projects/${item.project_id}?tab=response&deliverable=${item.id}`}
                          aria-label='查看交付物'
                        >
                          查看 <ArrowUpRight data-icon='inline-end' />
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  );
}

function DeliverableExportActions({ deliverableId }: { deliverableId: string }) {
  const mutation = useMutation({
    mutationFn: (format: 'docx' | 'pdf') =>
      format === 'docx'
        ? exportDeliverableDocx(deliverableId)
        : exportDeliverablePdf(deliverableId),
    onSuccess: (_, format) => toast.success(`${format.toUpperCase()} 文件已开始下载。`),
    onError: () => toast.error('导出失败，请先通过至少一个章节版本。')
  });

  return (
    <div className='flex items-center gap-1'>
      <LoadingButton
        aria-label='导出 DOCX'
        loading={mutation.isPending && mutation.variables === 'docx'}
        loadingLabel='正在生成 DOCX'
        onClick={() => mutation.mutate('docx')}
        size='xs'
        variant='ghost'
      >
        DOCX
      </LoadingButton>
      <LoadingButton
        aria-label='导出 PDF'
        loading={mutation.isPending && mutation.variables === 'pdf'}
        loadingLabel='正在生成 PDF'
        onClick={() => mutation.mutate('pdf')}
        size='xs'
        variant='ghost'
      >
        PDF
      </LoadingButton>
    </div>
  );
}
