'use client';

import Link from 'next/link';
import { ArrowUpRight, FileCheck2, FileDown } from 'lucide-react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { ProjectPicker } from '@/components/bidpilot/project-picker';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { listDeliverables, listProjects } from '@/lib/bidpilot-api';

export default function DeliverablesPage() {
  const projects = useQuery({ queryKey: ['projects'], queryFn: listProjects });
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const projectId = selectedProjectId || projects.data?.[0]?.id || '';
  const query = useQuery({
    queryKey: ['deliverables', projectId],
    queryFn: () => listDeliverables(projectId),
    enabled: Boolean(projectId)
  });
  return (
    <>
      <PageHeader
        eyebrow='投标工作流'
        title='交付物'
        description='查看响应文档、版本状态和可下载的最终交付结果。'
        action={
          projects.data?.length ? (
            <ProjectPicker
              projects={projects.data}
              value={projectId}
              onChange={setSelectedProjectId}
            />
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
            <CardContent className='p-0'>
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
                        <span className='text-muted-foreground inline-flex items-center gap-1.5 text-xs'>
                          <FileDown className='size-3.5' />
                          {item.export_status}
                        </span>
                      </TableCell>
                      <TableCell className='text-right'>
                        <Link
                          className={buttonVariants({ size: 'sm', variant: 'ghost' })}
                          href={`/projects/${item.project_id}?deliverable=${item.id}`}
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
