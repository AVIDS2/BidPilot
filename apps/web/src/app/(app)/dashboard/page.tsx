'use client';

import Link from 'next/link';
import { ArrowUpRight, FolderKanban, ListChecks, PlayCircle, TriangleAlert } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { getRuntimeSummary, listProjects, listRuntimeRuns } from '@/lib/bidpilot-api';

export default function DashboardPage() {
  const projects = useQuery({ queryKey: ['projects'], queryFn: listProjects });
  const runtime = useQuery({
    queryKey: ['runtime-summary'],
    queryFn: getRuntimeSummary,
    refetchInterval: 30_000
  });
  const runs = useQuery({
    queryKey: ['runtime-runs', 'dashboard'],
    queryFn: () => listRuntimeRuns(8)
  });
  const loading = projects.isPending || runtime.isPending || runs.isPending;
  const error = projects.error || runtime.error || runs.error;

  return (
    <>
      <PageHeader
        eyebrow='BidPilot 工作台'
        title='总览'
        description='从这里查看项目进度、Agent 运行和响应准备度。'
        action={
          <Link className={buttonVariants()} href='/projects'>
            查看项目 <ArrowUpRight data-icon='inline-end' />
          </Link>
        }
      />
      <div className='flex flex-1 flex-col gap-6 px-5 py-6 lg:px-8'>
        {loading ? (
          <QuerySkeleton rows={5} />
        ) : error ? (
          <QueryError message={error instanceof Error ? error.message : undefined} />
        ) : (
          <>
            <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
              <MetricCard
                icon={<FolderKanban />}
                label='项目'
                value={projects.data?.length}
                href='/projects'
              />
              <MetricCard
                icon={<PlayCircle />}
                label='队列中的运行'
                value={runtime.data?.queue_depth}
                href='/runs'
              />
              <MetricCard
                icon={<TriangleAlert />}
                label='失败运行'
                value={runtime.data?.failed_runs}
                href='/runs'
                tone={runtime.data?.failed_runs ? 'danger' : 'default'}
              />
              <MetricCard
                icon={<ListChecks />}
                label='起草成功率'
                value={
                  runtime.data ? `${Math.round(runtime.data.draft_success_rate * 100)}%` : undefined
                }
                href='/deliverables'
              />
            </div>
            <div className='grid gap-6 xl:grid-cols-[1.2fr_0.8fr]'>
              <Card>
                <CardHeader className='flex flex-row items-center justify-between gap-3 border-b'>
                  <div>
                    <h2 className='font-medium'>最近项目</h2>
                    <p className='text-muted-foreground mt-1 text-sm'>
                      从项目进入资料、需求和响应工作流。
                    </p>
                  </div>
                  <Link
                    className={buttonVariants({ size: 'sm', variant: 'ghost' })}
                    href='/projects'
                  >
                    全部项目 <ArrowUpRight data-icon='inline-end' />
                  </Link>
                </CardHeader>
                <CardContent className='p-0'>
                  {projects.data?.length ? (
                    <div className='divide-y'>
                      {projects.data.slice(0, 6).map((project) => (
                        <Link
                          className='hover:bg-muted/40 flex items-center gap-4 px-5 py-4 transition-colors'
                          href={`/projects/${project.id}`}
                          key={project.id}
                        >
                          <div className='bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-lg'>
                            <FolderKanban className='size-4' />
                          </div>
                          <div className='min-w-0 flex-1'>
                            <p className='truncate text-sm font-medium'>{project.name}</p>
                            <p className='text-muted-foreground mt-1 truncate text-xs'>
                              {project.scenario_package} · {project.slug}
                            </p>
                          </div>
                          <StatusBadge value={project.status} />
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <div className='p-5'>
                      <EmptyState
                        title='还没有项目'
                        description='创建第一个投标项目后，资料和响应进度会显示在这里。'
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className='border-b'>
                  <h2 className='font-medium'>最近运行</h2>
                  <p className='text-muted-foreground mt-1 text-sm'>
                    真实 Pi/工作流运行的最新状态。
                  </p>
                </CardHeader>
                <CardContent className='p-0'>
                  {runs.data?.length ? (
                    <div className='divide-y'>
                      {runs.data.slice(0, 6).map((run) => (
                        <Link
                          className='hover:bg-muted/40 block px-5 py-4 transition-colors'
                          href={
                            run.project_id
                              ? `/projects/${run.project_id}?run=${run.id}`
                              : `/runs?run=${run.id}`
                          }
                          key={run.id}
                        >
                          <div className='flex items-center gap-3'>
                            <span className='min-w-0 flex-1 truncate text-sm'>
                              {run.latest_event_summary || run.kind}
                            </span>
                            <StatusBadge value={run.status} />
                          </div>
                          <p className='text-muted-foreground mt-1 truncate text-xs'>
                            {run.project_name || '未关联项目'} · {formatDate(run.created_at)}
                          </p>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <div className='p-5'>
                      <EmptyState
                        title='还没有运行记录'
                        description='当 Agent 开始处理项目任务后，运行状态会出现在这里。'
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>
    </>
  );
}

function MetricCard({
  icon,
  label,
  value,
  href,
  tone = 'default'
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string | undefined;
  href: string;
  tone?: 'default' | 'danger';
}) {
  return (
    <Link href={href} aria-label={label}>
      <Card className='h-full transition-colors hover:border-primary/40'>
        <CardContent className='flex items-start gap-4 p-5'>
          <div
            className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${tone === 'danger' ? 'bg-destructive/10 text-destructive' : 'bg-primary/10 text-primary'} [&_svg]:size-4`}
          >
            {icon}
          </div>
          <div className='min-w-0'>
            <p className='text-muted-foreground truncate text-sm'>{label}</p>
            <p className='mt-2 text-2xl font-semibold tabular-nums'>{value ?? '—'}</p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const variant = ['failed', 'error', 'cancelled'].includes(normalized)
    ? 'destructive'
    : normalized === 'completed' || normalized === 'succeeded'
      ? 'secondary'
      : 'outline';
  return <Badge variant={variant}>{statusLabel(normalized)}</Badge>;
}

function statusLabel(value: string) {
  return (
    (
      {
        active: '进行中',
        running: '运行中',
        queued: '排队中',
        pending: '等待中',
        completed: '已完成',
        succeeded: '已完成',
        failed: '失败',
        cancelled: '已取消',
        draft: '草稿'
      } as Record<string, string>
    )[value] || value
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value));
}
