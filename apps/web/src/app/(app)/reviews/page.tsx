'use client';

import Link from 'next/link';
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  ClipboardCheck,
  MessageSquare,
  Users
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { LiveSyncStatus } from '@/components/bidpilot/live-sync-status';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { ProjectPicker } from '@/components/bidpilot/project-picker';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { useProjectSelection } from '@/hooks/use-project-selection';
import { listProjects, getCollaborationBoard } from '@/lib/bidpilot-api';

export default function ReviewsPage() {
  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const { projectId, onChange: setSelectedProjectId } = useProjectSelection(projects.data);
  const board = useQuery({
    queryKey: ['collaboration-board', projectId],
    queryFn: () => getCollaborationBoard(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 15_000,
    refetchOnWindowFocus: true
  });
  return (
    <>
      <PageHeader
        eyebrow='投标工作流'
        title='评审'
        description='从同一份项目看板跟踪审核、分配和待处理风险。'
        action={
          projects.data?.length ? (
            <div className='flex flex-wrap items-center justify-end gap-2'>
              <LiveSyncStatus
                active={Boolean(board.data)}
                dataUpdatedAt={Math.max(projects.dataUpdatedAt, board.dataUpdatedAt)}
                intervalLabel='每 15 秒'
                isFetching={projects.isFetching || board.isFetching}
                onRefresh={() => void Promise.all([projects.refetch(), board.refetch()])}
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
      <div className='flex flex-1 flex-col gap-6 px-5 py-6 lg:px-8'>
        {projects.isPending || board.isPending ? (
          <QuerySkeleton rows={5} />
        ) : projects.error || board.error ? (
          <QueryError
            message={
              (projects.error || board.error) instanceof Error
                ? (projects.error || board.error)?.message
                : undefined
            }
          />
        ) : !projects.data?.length || !board.data ? (
          <EmptyState
            title='还没有可评审项目'
            description='创建项目并生成需求、章节后，协作看板会显示在这里。'
          />
        ) : (
          <>
            <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-5'>
              <ReviewMetric
                icon={<ClipboardCheck />}
                label='待分配'
                value={board.data.unassigned_requirement_count}
              />
              <ReviewMetric
                icon={<AlertTriangle />}
                label='逾期'
                value={board.data.overdue_requirement_count}
              />
              <ReviewMetric
                icon={<MessageSquare />}
                label='待回复讨论'
                value={board.data.open_review_thread_count}
              />
              <ReviewMetric
                icon={<Users />}
                label='活跃运行'
                value={board.data.active_workflow_count}
              />
              <ReviewMetric
                icon={<CheckCircle2 />}
                label='需评审'
                value={board.data.review_required_count}
              />
            </div>
            <Card>
              <CardHeader className='flex flex-col gap-3 border-b sm:flex-row sm:items-start sm:justify-between'>
                <div>
                  <h2 className='font-medium'>需求审核队列</h2>
                  <p className='text-muted-foreground mt-1 text-sm'>
                    按当前项目返回的真实协作看板。
                  </p>
                </div>
                <Link
                  className={buttonVariants({ size: 'sm', variant: 'outline' })}
                  href={`/projects/${projectId}?tab=response`}
                >
                  审核响应章节 <ArrowUpRight data-icon='inline-end' />
                </Link>
              </CardHeader>
              <CardContent className='p-0'>
                {board.data.requirement_items.length ? (
                  <div className='divide-y'>
                    {board.data.requirement_items.map((item) => (
                      <div
                        className='flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-start'
                        key={item.requirement_id}
                      >
                        <div className='min-w-0 flex-1'>
                          <p className='text-sm font-medium'>{item.requirement_text}</p>
                          <p className='text-muted-foreground mt-1 text-xs'>
                            {item.section_key} · {item.owner_display_name || '未分配'}
                            {item.reviewer_display_name
                              ? ` · 审核：${item.reviewer_display_name}`
                              : ''}
                          </p>
                        </div>
                        <div className='flex shrink-0 gap-2'>
                          <Badge variant={item.overdue ? 'destructive' : 'outline'}>
                            {item.overdue ? '已逾期' : item.status}
                          </Badge>
                          <Badge variant='outline'>{item.verification_status}</Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className='p-5'>
                    <EmptyState title='没有审核条目' description='项目当前没有返回需求协作条目。' />
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </>
  );
}

function ReviewMetric({
  icon,
  label,
  value
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <Card>
      <CardContent className='flex items-center gap-3 p-4'>
        <span className='bg-primary/10 text-primary flex size-8 items-center justify-center rounded-lg [&_svg]:size-4'>
          {icon}
        </span>
        <span className='min-w-0'>
          <span className='text-muted-foreground block truncate text-xs'>{label}</span>
          <span className='mt-1 block text-lg font-semibold tabular-nums'>{value}</span>
        </span>
      </CardContent>
    </Card>
  );
}
