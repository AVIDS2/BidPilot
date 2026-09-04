'use client';

import Link from 'next/link';
import { ArrowUpRight, FolderKanban, ListChecks, PlayCircle, TriangleAlert } from 'lucide-react';
import { useQueries, useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth';
import { LiveSyncStatus } from '@/components/bidpilot/live-sync-status';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig
} from '@/components/ui/chart';
import {
  getReadinessSummary,
  getRuntimeSummary,
  listProjects,
  listRuntimeRuns
} from '@/lib/bidpilot-api';
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts';

const runChartConfig = {
  count: { label: '任务数', color: 'var(--primary)' }
} satisfies ChartConfig;

export default function DashboardPage() {
  const { user } = useAuth();
  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const runtime = useQuery({
    queryKey: ['runtime-summary'],
    queryFn: getRuntimeSummary,
    refetchInterval: 30_000,
    retry: false,
    enabled: user?.role === 'admin'
  });
  const runs = useQuery({
    queryKey: ['runtime-runs', 'dashboard'],
    queryFn: () => listRuntimeRuns(8, null, undefined, true),
    retry: false,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true
  });
  const readinessQueries = useQueries({
    queries: (projects.data ?? []).map((project) => ({
      queryKey: ['readiness-summary', project.id],
      queryFn: () => getReadinessSummary(project.id),
      staleTime: 30_000,
      retry: false,
      refetchInterval: 30_000,
      refetchOnWindowFocus: true
    }))
  });
  // Child agents belong to the current Copilot turn. They are presented in
  // the Agent collaboration surface, not as separate user tasks here.
  const rootRuns = (runs.data ?? []).filter((run) => !run.parent_run_id);
  // Runtime summary is an administrator-only aggregate. It must not block the
  // member dashboard when the scoped project/run queries are available.
  const loading = projects.isPending || runs.isPending;
  const error = projects.error || runs.error;
  const readinessLoading = projects.isPending || readinessQueries.some((query) => query.isPending);
  const readinessChartData = (projects.data ?? [])
    .map((project, index) => ({
      project: project.name.slice(0, 10),
      readiness: Math.round(readinessQueries[index]?.data?.readiness_score ?? 0)
    }))
    .filter((_, index) => Boolean(readinessQueries[index]?.data))
    .slice(0, 6);
  const finishedRuns = rootRuns.filter((run) =>
    ['completed', 'succeeded', 'failed', 'error'].includes(run.status)
  );
  const successfulRuns = finishedRuns.filter((run) =>
    ['completed', 'succeeded'].includes(run.status)
  );
  const runChartData = [
    {
      status: '处理中',
      count: rootRuns.filter((run) => ['running', 'queued', 'pending'].includes(run.status)).length
    },
    {
      status: '待审批',
      count: rootRuns.filter((run) => run.status === 'awaiting_approval').length
    },
    {
      status: '已完成',
      count: rootRuns.filter((run) => ['completed', 'succeeded'].includes(run.status)).length
    },
    {
      status: '失败',
      count: rootRuns.filter((run) => ['failed', 'error'].includes(run.status)).length
    }
  ];
  const isRefreshing =
    projects.isFetching ||
    runs.isFetching ||
    runtime.isFetching ||
    readinessQueries.some((query) => query.isFetching);
  const dataUpdatedAt = Math.max(
    projects.dataUpdatedAt,
    runs.dataUpdatedAt,
    runtime.dataUpdatedAt,
    ...readinessQueries.map((query) => query.dataUpdatedAt)
  );
  const refreshAll = () => {
    void Promise.all([
      projects.refetch(),
      runs.refetch(),
      ...(user?.role === 'admin' ? [runtime.refetch()] : []),
      ...readinessQueries.map((query) => query.refetch())
    ]);
  };

  return (
    <>
      <PageHeader
        eyebrow='BidPilot 工作台'
        title='总览'
        description='从这里查看项目进度、Agent 任务和响应准备度。'
        action={
          <div className='flex flex-wrap items-center justify-end gap-2'>
            <LiveSyncStatus
              active={Boolean(projects.data || runs.data)}
              dataUpdatedAt={dataUpdatedAt}
              intervalLabel='每 15 秒'
              isFetching={isRefreshing}
              onRefresh={refreshAll}
            />
            <Link className={buttonVariants()} href='/projects'>
              查看项目 <ArrowUpRight data-icon='inline-end' />
            </Link>
          </div>
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
                label='待处理任务'
                value={
                  runtime.data?.queue_depth ??
                  rootRuns.filter((run) => run.status === 'queued').length
                }
                href='/my-work'
              />
              <MetricCard
                icon={<TriangleAlert />}
                label='需要关注'
                value={
                  runtime.data?.failed_runs ??
                  rootRuns.filter((run) => ['failed', 'error'].includes(run.status)).length
                }
                href='/my-work'
                tone={
                  (runtime.data?.failed_runs ??
                    rootRuns.filter((run) => ['failed', 'error'].includes(run.status)).length ??
                    0) > 0
                    ? 'danger'
                    : 'default'
                }
              />
              <MetricCard
                icon={<ListChecks />}
                label='起草成功率'
                value={
                  runtime.data
                    ? `${Math.round(runtime.data.draft_success_rate * 100)}%`
                    : finishedRuns.length
                      ? `${Math.round((successfulRuns.length / finishedRuns.length) * 100)}%`
                      : undefined
                }
                href='/deliverables'
              />
            </div>
            <div className='grid gap-6 xl:grid-cols-[0.8fr_1.2fr]'>
              <Card>
                <CardHeader className='border-b'>
                  <h2 className='font-medium'>任务状态分布</h2>
                  <p className='text-muted-foreground mt-1 text-sm'>
                    当前账户可见任务的真实状态，不包含管理员全局统计。
                  </p>
                </CardHeader>
                <CardContent className='p-5'>
                  {rootRuns.length ? (
                    <ChartContainer className='h-56 w-full' config={runChartConfig}>
                      <BarChart accessibilityLayer data={runChartData}>
                        <CartesianGrid vertical={false} />
                        <XAxis axisLine={false} dataKey='status' tickLine={false} />
                        <YAxis allowDecimals={false} axisLine={false} tickLine={false} width={28} />
                        <ChartTooltip content={<ChartTooltipContent />} />
                        <Bar
                          animationDuration={550}
                          animationEasing='ease-out'
                          dataKey='count'
                          fill='var(--color-count)'
                          isAnimationActive
                          radius={4}
                        />
                      </BarChart>
                    </ChartContainer>
                  ) : (
                    <EmptyState
                      title='还没有运行数据'
                      description='从助手发起一次项目任务后，这里会根据真实运行状态绘制。'
                    />
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className='border-b'>
                  <h2 className='font-medium'>最近项目</h2>
                  <p className='text-muted-foreground mt-1 text-sm'>
                    从项目进入资料、需求和响应工作流。
                  </p>
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
            </div>
            <div className='grid gap-6 xl:grid-cols-[1.2fr_0.8fr]'>
              <Card>
                <CardHeader className='border-b'>
                  <div className='flex items-center justify-between gap-3'>
                    <div>
                      <h2 className='font-medium'>最近任务</h2>
                      <p className='text-muted-foreground mt-1 text-sm'>
                        真实 Pi/工作流运行的最新状态。
                      </p>
                    </div>
                    <Link
                      className={buttonVariants({ size: 'sm', variant: 'ghost' })}
                      href='/my-work'
                    >
                      查看我的工作 <ArrowUpRight data-icon='inline-end' />
                    </Link>
                  </div>
                </CardHeader>
                <CardContent className='p-0'>
                  {rootRuns.length ? (
                    <div className='divide-y'>
                      {rootRuns.slice(0, 6).map((run) => (
                        <Link
                          className='hover:bg-muted/40 block px-5 py-4 transition-colors'
                          href={
                            run.project_id
                              ? `/projects/${run.project_id}?run=${run.id}`
                              : run.conversation_id
                                ? `/agent?conversation=${run.conversation_id}`
                                : '/my-work'
                          }
                          key={run.id}
                        >
                          <div className='flex items-center gap-3'>
                            <span className='min-w-0 flex-1 truncate text-sm'>
                              {run.latest_event_summary || runKindLabel(run.kind)}
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
                        title='还没有最近任务'
                        description='当 Agent 开始处理项目任务后，进展会出现在这里。'
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className='border-b'>
                  <h2 className='font-medium'>项目就绪度</h2>
                  <p className='text-muted-foreground mt-1 text-sm'>
                    来自真实要求、证据和核验状态。
                  </p>
                </CardHeader>
                <CardContent className='p-5'>
                  {readinessLoading ? (
                    <QuerySkeleton rows={3} />
                  ) : readinessChartData.length ? (
                    <ChartContainer
                      className='h-56 w-full'
                      config={{ readiness: { label: '就绪度', color: 'var(--primary)' } }}
                    >
                      <BarChart
                        accessibilityLayer
                        data={readinessChartData}
                        margin={{ top: 12, right: 6, left: -18, bottom: 0 }}
                      >
                        <CartesianGrid vertical={false} />
                        <XAxis axisLine={false} dataKey='project' tickLine={false} tickMargin={8} />
                        <YAxis
                          axisLine={false}
                          domain={[0, 100]}
                          tickFormatter={(value) => `${value}%`}
                          tickLine={false}
                          width={42}
                        />
                        <ChartTooltip
                          content={
                            <ChartTooltipContent formatter={(value) => [`${value}%`, '就绪度']} />
                          }
                        />
                        <Bar
                          animationDuration={650}
                          animationEasing='ease-out'
                          dataKey='readiness'
                          fill='var(--color-readiness)'
                          isAnimationActive
                          radius={4}
                        />
                      </BarChart>
                    </ChartContainer>
                  ) : (
                    <EmptyState
                      title='还没有就绪度基线'
                      description='完成项目资料解析和要求识别后，这里会绘制真实结果。'
                    />
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
        awaiting_approval: '等待审批',
        awaiting_input: '需要补充信息',
        cancel_requested: '停止中',
        completed: '已完成',
        succeeded: '已完成',
        failed: '失败',
        error: '失败',
        cancelled: '已取消',
        expired: '已过期',
        draft: '草稿'
      } as Record<string, string>
    )[value] || value
  );
}

function runKindLabel(value: string) {
  return (
    (
      {
        assistant_turn: 'Agent 任务',
        workflow_bridge: '响应工作流',
        subagent: '后台协作任务',
        deep_research: '深度调研',
        remote_import: '资料导入'
      } as Record<string, string>
    )[value] || '工作流任务'
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
