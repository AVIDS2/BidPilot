'use client';

import Link from 'next/link';
import { ArrowUpRight, ListChecks, Search } from 'lucide-react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LiveSyncStatus } from '@/components/bidpilot/live-sync-status';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { ProjectPicker } from '@/components/bidpilot/project-picker';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useProjectSelection } from '@/hooks/use-project-selection';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { listProjects, listRequirements } from '@/lib/bidpilot-api';

export default function RequirementsPage() {
  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const { projectId, onChange: setSelectedProjectId } = useProjectSelection(projects.data);
  const [search, setSearch] = useState('');
  const requirements = useQuery({
    queryKey: ['requirements', projectId],
    queryFn: () => listRequirements(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 15_000,
    refetchOnWindowFocus: true
  });
  const rows =
    requirements.data?.filter((item) =>
      `${item.requirement_text} ${item.section_key}`.toLowerCase().includes(search.toLowerCase())
    ) ?? [];
  return (
    <>
      <PageHeader
        eyebrow='投标工作流'
        title='需求清单'
        description='把招标要求作为可分配、可验证和可审计的工作项管理。'
        action={
          projects.data?.length ? (
            <div className='flex flex-wrap items-center justify-end gap-2'>
              <LiveSyncStatus
                active={Boolean(requirements.data)}
                dataUpdatedAt={Math.max(projects.dataUpdatedAt, requirements.dataUpdatedAt)}
                intervalLabel='每 15 秒'
                isFetching={projects.isFetching || requirements.isFetching}
                onRefresh={() => void Promise.all([projects.refetch(), requirements.refetch()])}
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
        {projects.isPending ? (
          <QuerySkeleton rows={4} />
        ) : projects.error ? (
          <QueryError
            message={projects.error instanceof Error ? projects.error.message : undefined}
          />
        ) : !projects.data?.length ? (
          <EmptyState
            title='还没有项目'
            description='创建项目并上传资料后，需求清单才会有可追踪的条目。'
          />
        ) : !projectId || requirements.isPending ? (
          <QuerySkeleton rows={5} />
        ) : requirements.error ? (
          <QueryError
            message={requirements.error instanceof Error ? requirements.error.message : undefined}
          />
        ) : (
          <Card>
            <CardContent className='p-0'>
              <div className='flex flex-col gap-3 border-b p-4 sm:flex-row sm:items-center sm:justify-between'>
                <div className='relative w-full max-w-sm'>
                  <Search className='text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2' />
                  <Input
                    className='pl-8'
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder='搜索需求'
                    aria-label='搜索需求'
                  />
                </div>
                <span className='text-muted-foreground text-sm'>
                  {requirements.data?.length ?? 0} 条需求
                </span>
              </div>
              {rows.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>需求</TableHead>
                      <TableHead>章节</TableHead>
                      <TableHead>优先级</TableHead>
                      <TableHead>验证</TableHead>
                      <TableHead className='text-right'>来源</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className='max-w-xl whitespace-normal'>
                          <div className='flex items-start gap-3'>
                            <ListChecks className='text-primary mt-0.5 size-4 shrink-0' />
                            <span className='text-sm leading-6'>{item.requirement_text}</span>
                          </div>
                        </TableCell>
                        <TableCell className='text-muted-foreground'>{item.section_key}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              item.priority === 'critical' || item.priority === 'high'
                                ? 'destructive'
                                : 'outline'
                            }
                          >
                            {item.priority}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant='outline'>{item.verification_status}</Badge>
                        </TableCell>
                        <TableCell className='text-right'>
                          {item.source_document_id ? (
                            <Link
                              className={buttonVariants({ size: 'sm', variant: 'ghost' })}
                              href={`/knowledge?project_id=${item.project_id}`}
                            >
                              查看 <ArrowUpRight data-icon='inline-end' />
                            </Link>
                          ) : (
                            <span className='text-muted-foreground'>—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className='p-5'>
                  <EmptyState
                    title='没有匹配需求'
                    description='换一个搜索词，或等待项目资料解析完成。'
                  />
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </>
  );
}
