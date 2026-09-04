'use client';

import Link from 'next/link';
import { useMemo, useState, type ComponentType } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  ArrowUpRight,
  Bell,
  BriefcaseBusiness,
  CalendarClock,
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileSearch,
  FolderKanban,
  ListChecks,
  Plus,
  Radar,
  RefreshCw,
  Rss,
  Search,
  ShieldCheck,
  Sparkles,
  Square,
  Target,
  Users,
  Webhook
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth';
import { LiveSyncStatus } from '@/components/bidpilot/live-sync-status';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { AdminGuard } from '@/components/auth/admin-guard';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig
} from '@/components/ui/chart';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import {
  convertRadarNoticeToProject,
  createRadarSource,
  createRadarSubscription,
  getBillingSummary,
  getOrganizationEntitlements,
  getPiRuntimeContract,
  getRadarOverview,
  getReadinessSummary,
  getRuntimeSummary,
  listOrganizationMembers,
  listProjects,
  listRuntimeRuns,
  pollRadarSource,
  updateRadarNoticeStatus,
  type RadarNoticeRead,
  type RadarOverviewView,
  type ReadinessRequirementRead
} from '@/lib/bidpilot-api';
import { cancelRuntimeWorkflow } from '@/lib/bidpilot-api';

type RunFilter = 'all' | 'active' | 'approval' | 'failed' | 'completed';

const ACTIVE_RUN_STATUSES = new Set([
  'queued',
  'running',
  'awaiting_approval',
  'awaiting_input',
  'cancel_requested'
]);
const COMPLETED_RUN_STATUSES = new Set(['succeeded', 'cancelled', 'expired']);

function formatDate(
  value: string | null,
  options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' }
) {
  if (!value) return '未提供';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '未提供';
  return new Intl.DateTimeFormat('zh-CN', options).format(date);
}

function statusLabel(value: string) {
  return (
    (
      {
        queued: '排队中',
        running: '运行中',
        awaiting_approval: '等待审批',
        awaiting_input: '需要补充信息',
        cancel_requested: '停止中',
        succeeded: '已完成',
        completed: '已完成',
        cancelled: '已停止',
        expired: '已过期',
        failed: '失败',
        error: '失败'
      } as Record<string, string>
    )[value] || value
  );
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const variant = ['failed', 'error'].includes(normalized)
    ? 'destructive'
    : ['succeeded', 'completed'].includes(normalized)
      ? 'secondary'
      : 'outline';
  return <Badge variant={variant}>{statusLabel(normalized)}</Badge>;
}

function sourceKindLabel(value: string) {
  return (
    (
      {
        rss: 'RSS 来源',
        json_feed: 'JSON Feed 来源',
        webhook: 'Webhook 来源'
      } as Record<string, string>
    )[value] || '公开来源'
  );
}

function RunIcon({ status }: { status: string }) {
  if (['failed', 'error'].includes(status)) return <AlertCircle className='text-destructive' />;
  if (['succeeded', 'completed'].includes(status)) return <CheckCircle2 className='text-primary' />;
  return <Clock3 className='text-primary' />;
}

function SummaryStat({
  icon: Icon,
  label,
  value,
  detail
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  detail: string;
}) {
  return (
    <Card>
      <CardContent className='flex items-start gap-4 p-5'>
        <span className='bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-lg'>
          <Icon className='size-4' />
        </span>
        <div className='min-w-0'>
          <p className='text-muted-foreground text-xs'>{label}</p>
          <p className='mt-1 text-2xl font-semibold tabular-nums'>{value}</p>
          <p className='text-muted-foreground mt-1 truncate text-xs'>{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function RuntimeMetric({
  icon: Icon,
  label,
  value,
  detail
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  detail: string;
}) {
  return (
    <div className='flex items-start gap-3 rounded-lg border p-4'>
      <span className='bg-muted text-primary flex size-8 shrink-0 items-center justify-center rounded-lg'>
        <Icon className='size-4' />
      </span>
      <div className='min-w-0'>
        <p className='text-muted-foreground text-xs'>{label}</p>
        <p className='mt-1 text-xl font-semibold tabular-nums'>{value}</p>
        <p className='text-muted-foreground mt-1 truncate text-xs'>{detail}</p>
      </div>
    </div>
  );
}

export function InboxPage() {
  const router = useRouter();
  const client = useQueryClient();
  const [filter, setFilter] = useState<RunFilter>('all');
  const runs = useQuery({
    queryKey: ['runtime-runs', 'inbox'],
    queryFn: () => listRuntimeRuns(50, null, undefined, true),
    staleTime: 10_000,
    retry: false
  });
  const cancel = useMutation({
    mutationFn: cancelRuntimeWorkflow,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['runtime-runs'] });
      toast.success('已请求停止运行，终态会由服务端事件确认。');
    },
    onError: () => toast.error('当前任务无法停止，请稍后重试。')
  });
  const visibleRuns = useMemo(() => {
    // Child agents are shown in the Agent collaboration panel. Keeping them
    // out of the inbox prevents a user from opening a synthetic second chat.
    const all = (runs.data ?? []).filter((run) => !run.parent_run_id);
    if (filter === 'active') return all.filter((run) => ACTIVE_RUN_STATUSES.has(run.status));
    if (filter === 'approval') return all.filter((run) => run.status === 'awaiting_approval');
    if (filter === 'failed') return all.filter((run) => ['failed', 'error'].includes(run.status));
    if (filter === 'completed') return all.filter((run) => COMPLETED_RUN_STATUSES.has(run.status));
    return all;
  }, [filter, runs.data]);

  return (
    <>
      <PageHeader
        eyebrow='工作流运营'
        title='收件箱'
        description='把需要你处理的 Agent 运行、审批和失败事项集中在一处。'
        action={
          <Link className={buttonVariants({ variant: 'outline' })} href='/my-work'>
            查看我的工作 <ArrowUpRight data-icon='inline-end' />
          </Link>
        }
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        <Card>
          <CardHeader className='gap-4 border-b sm:flex-row sm:items-center sm:justify-between'>
            <div>
              <CardTitle>处理队列</CardTitle>
              <CardDescription>只显示当前账户有权限查看的真实运行。</CardDescription>
            </div>
            <Tabs value={filter} onValueChange={(value) => setFilter(value as RunFilter)}>
              <TabsList className='max-w-full overflow-x-auto' variant='line'>
                <TabsTrigger value='all'>全部</TabsTrigger>
                <TabsTrigger value='active'>进行中</TabsTrigger>
                <TabsTrigger value='approval'>待审批</TabsTrigger>
                <TabsTrigger value='failed'>失败</TabsTrigger>
                <TabsTrigger value='completed'>已结束</TabsTrigger>
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent className='p-0'>
            {runs.isPending ? (
              <div className='p-5'>
                <QuerySkeleton rows={5} />
              </div>
            ) : runs.error ? (
              <div className='p-5'>
                <QueryError
                  message={runs.error instanceof Error ? runs.error.message : undefined}
                />
              </div>
            ) : !visibleRuns.length ? (
              <div className='p-5'>
                <EmptyState
                  title={filter === 'all' ? '收件箱是空的' : '没有匹配事项'}
                  description='新的 Agent 运行、审批或失败状态会在服务端产生后出现在这里。'
                />
              </div>
            ) : (
              <div className='divide-y'>
                {visibleRuns.map((run) => {
                  const isActive = ACTIVE_RUN_STATUSES.has(run.status);
                  return (
                    <div className='flex items-center gap-3 px-5 py-4' key={run.id}>
                      <RunIcon status={run.status} />
                      <Link
                        className='min-w-0 flex-1'
                        href={
                          run.project_id
                            ? `/projects/${run.project_id}`
                            : run.conversation_id
                              ? `/agent?conversation=${run.conversation_id}`
                              : '/my-work'
                        }
                      >
                        <p className='truncate text-sm font-medium'>
                          {run.latest_event_summary || 'Agent 任务'}
                        </p>
                        <p className='text-muted-foreground mt-1 truncate text-xs'>
                          {run.project_name || '未关联项目'} · {formatDate(run.created_at)}
                        </p>
                      </Link>
                      <StatusBadge value={run.status} />
                      {isActive ? (
                        <Button
                          aria-label='停止运行'
                          disabled={cancel.isPending}
                          onClick={() => cancel.mutate(run.id)}
                          size='icon-sm'
                          title='停止运行'
                          type='button'
                          variant='destructive'
                        >
                          <Square />
                        </Button>
                      ) : (
                        <Button
                          aria-label='查看任务'
                          onClick={() =>
                            router.push(
                              run.project_id
                                ? `/projects/${run.project_id}`
                                : run.conversation_id
                                  ? `/agent?conversation=${run.conversation_id}`
                                  : '/my-work'
                            )
                          }
                          size='icon-sm'
                          title='查看任务'
                          type='button'
                          variant='ghost'
                        >
                          <ArrowUpRight />
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

export function MyWorkPage() {
  const router = useRouter();
  const [scope, setScope] = useState<'all' | 'compliance' | 'approval'>('all');
  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
    staleTime: 30_000,
    retry: false,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const runs = useQuery({
    queryKey: ['runtime-runs', 'my-work'],
    queryFn: () => listRuntimeRuns(50, null, undefined, true),
    staleTime: 10_000,
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
  const workItems = useMemo(() => {
    const items: Array<{
      id: string;
      projectId: string;
      projectName: string;
      title: string;
      detail: string;
      tone: 'destructive' | 'outline';
      kind: 'compliance' | 'approval';
    }> = [];
    (projects.data ?? []).forEach((project, index) => {
      const summary = readinessQueries[index]?.data;
      if (!summary) return;
      const gaps: Array<[string, ReadinessRequirementRead[]]> = [
        ['硬性要求缺口', summary.mandatory_gaps],
        ['证据缺口', summary.evidence_gaps],
        ['矛盾待核验', summary.contradictions]
      ];
      gaps.forEach(([label, requirements]) => {
        requirements.slice(0, 8).forEach((requirement) => {
          items.push({
            id: `${project.id}-${label}-${requirement.id}`,
            projectId: project.id,
            projectName: project.name,
            title: requirement.requirement_text,
            detail: `${label} · ${requirement.section_key}`,
            tone: 'destructive',
            kind: 'compliance'
          });
        });
      });
    });
    (runs.data ?? [])
      .filter((run) => !run.parent_run_id)
      .filter((run) => ['awaiting_approval', 'failed'].includes(run.status))
      .forEach((run) => {
        items.push({
          id: run.id,
          projectId: run.project_id || '',
          projectName: run.project_name || '未关联项目',
          title: run.latest_event_summary || '运行需要处理',
          detail: `${statusLabel(run.status)} · ${formatDate(run.created_at)}`,
          tone: run.status === 'failed' ? 'destructive' : 'outline',
          kind: 'approval'
        });
      });
    return items;
  }, [projects.data, readinessQueries, runs.data]);
  const visibleItems =
    scope === 'all' ? workItems : workItems.filter((item) => item.kind === scope);
  const loading =
    projects.isPending || runs.isPending || readinessQueries.some((query) => query.isPending);
  const error = projects.error || runs.error;
  const chartData = useMemo(() => {
    const projectsWithSummary = (projects.data ?? [])
      .map((project, index) => ({
        name: project.name.slice(0, 10),
        readiness: Math.round(readinessQueries[index]?.data?.readiness_score ?? 0)
      }))
      .filter(
        (item, index) => !readinessQueries[index]?.isPending && readinessQueries[index]?.data
      );
    return projectsWithSummary.slice(0, 6);
  }, [projects.data, readinessQueries]);
  const chartConfig = {
    readiness: { label: '就绪度', color: 'var(--primary)' }
  } satisfies ChartConfig;
  const isRefreshing =
    projects.isFetching || runs.isFetching || readinessQueries.some((query) => query.isFetching);
  const dataUpdatedAt = Math.max(
    projects.dataUpdatedAt,
    runs.dataUpdatedAt,
    ...readinessQueries.map((query) => query.dataUpdatedAt)
  );
  const refreshAll = () => {
    void Promise.all([
      projects.refetch(),
      runs.refetch(),
      ...readinessQueries.map((query) => query.refetch())
    ]);
  };

  return (
    <>
      <PageHeader
        eyebrow='工作流运营'
        title='我的工作'
        description='从项目事实和真实运行状态中汇总下一步需要你决定的事项。'
        action={
          <div className='flex flex-wrap items-center justify-end gap-2'>
            <LiveSyncStatus
              active={Boolean(projects.data || runs.data)}
              dataUpdatedAt={dataUpdatedAt}
              intervalLabel='每 15 秒'
              isFetching={isRefreshing}
              onRefresh={refreshAll}
            />
            <Link className={buttonVariants({ variant: 'outline' })} href='/projects'>
              查看项目 <ArrowUpRight data-icon='inline-end' />
            </Link>
          </div>
        }
      />
      <div className='flex flex-1 flex-col gap-6 px-5 py-6 lg:px-8'>
        {loading ? (
          <QuerySkeleton rows={6} />
        ) : error ? (
          <QueryError message={error instanceof Error ? error.message : undefined} />
        ) : (
          <>
            <div className='grid gap-4 sm:grid-cols-3'>
              <SummaryStat
                icon={ListChecks}
                label='待处理事项'
                value={workItems.length}
                detail='来自项目缺口和运行状态'
              />
              <SummaryStat
                icon={ShieldCheck}
                label='资料就绪项目'
                value={
                  (projects.data ?? []).filter(
                    (_, index) => (readinessQueries[index]?.data?.readiness_score ?? 0) >= 80
                  ).length
                }
                detail='就绪度达到 80% 的项目'
              />
              <SummaryStat
                icon={Bell}
                label='等待决定'
                value={workItems.filter((item) => item.kind === 'approval').length}
                detail='审批或失败运行'
              />
            </div>
            <div className='grid gap-6 xl:grid-cols-[1.1fr_0.9fr]'>
              <Card>
                <CardHeader className='gap-4 border-b sm:flex-row sm:items-center sm:justify-between'>
                  <div>
                    <CardTitle>下一步</CardTitle>
                    <CardDescription>
                      点击事项回到对应项目，所有状态均由服务端数据计算。
                    </CardDescription>
                  </div>
                  <Tabs value={scope} onValueChange={(value) => setScope(value as typeof scope)}>
                    <TabsList variant='line'>
                      <TabsTrigger value='all'>全部</TabsTrigger>
                      <TabsTrigger value='compliance'>资料缺口</TabsTrigger>
                      <TabsTrigger value='approval'>运行决定</TabsTrigger>
                    </TabsList>
                  </Tabs>
                </CardHeader>
                <CardContent className='p-0'>
                  {visibleItems.length ? (
                    <div className='divide-y'>
                      {visibleItems.slice(0, 30).map((item) => (
                        <Link
                          className='hover:bg-muted/40 flex items-center gap-3 px-5 py-4 transition-colors'
                          href={item.projectId ? `/projects/${item.projectId}` : '/my-work'}
                          key={item.id}
                        >
                          <span className='bg-muted flex size-8 shrink-0 items-center justify-center rounded-lg'>
                            {item.kind === 'approval' ? <Bell /> : <FileSearch />}
                          </span>
                          <span className='min-w-0 flex-1'>
                            <span className='block truncate text-sm font-medium'>{item.title}</span>
                            <span className='text-muted-foreground mt-1 block truncate text-xs'>
                              {item.projectName} · {item.detail}
                            </span>
                          </span>
                          <Badge variant={item.tone}>
                            {item.kind === 'approval' ? '查看任务' : '处理缺口'}
                          </Badge>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <div className='p-5'>
                      <EmptyState
                        title='目前没有待办'
                        description='当项目要求出现缺口或运行需要决定时，会在这里汇总。'
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className='border-b'>
                  <CardTitle>项目就绪度</CardTitle>
                  <CardDescription>来自已识别要求、证据和核验状态的真实聚合。</CardDescription>
                </CardHeader>
                <CardContent className='p-5'>
                  {chartData.length ? (
                    <ChartContainer className='h-64 w-full' config={chartConfig}>
                      <BarChart
                        accessibilityLayer
                        data={chartData}
                        margin={{ top: 12, right: 6, left: -18, bottom: 0 }}
                      >
                        <CartesianGrid vertical={false} />
                        <XAxis axisLine={false} dataKey='name' tickLine={false} tickMargin={8} />
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
                      title='还没有可绘制的基线'
                      description='完成资料解析和要求识别后，项目就绪度会出现在这里。'
                    />
                  )}
                </CardContent>
                <CardFooter className='justify-end'>
                  <Button onClick={() => router.push('/requirements')} size='sm' variant='ghost'>
                    查看要求清单 <ArrowUpRight data-icon='inline-end' />
                  </Button>
                </CardFooter>
              </Card>
            </div>
          </>
        )}
      </div>
    </>
  );
}

const radarChartConfig = {
  notices: { label: '新增公告', color: 'var(--primary)' }
} satisfies ChartConfig;
const radarViews: Array<{ value: RadarOverviewView; label: string }> = [
  { value: 'recommended', label: '推荐' },
  { value: 'all', label: '全部' },
  { value: 'intent', label: '采购意向' },
  { value: 'tender', label: '招标公告' },
  { value: 'saved', label: '已保存' },
  { value: 'ignored', label: '已忽略' }
];

function splitTerms(value: string) {
  return value
    .split(/[，,\n]/)
    .map((term) => term.trim())
    .filter(Boolean);
}

function noticeTypeLabel(type: RadarNoticeRead['notice_type']) {
  return (
    {
      intent: '采购意向',
      tender: '招标公告',
      prequalification: '资格预审',
      rfi: '需求征询',
      other: '其他公告'
    } as Record<string, string>
  )[type];
}

function noticeStatusLabel(status: RadarNoticeRead['status']) {
  return (
    { new: '待研判', saved: '已保存', ignored: '已忽略', converted: '已转项目' } as Record<
      string,
      string
    >
  )[status];
}

function safeExternalUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : undefined;
  } catch {
    return undefined;
  }
}

export function RadarPage() {
  const router = useRouter();
  const client = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [view, setView] = useState<RadarOverviewView>('recommended');
  const [queryText, setQueryText] = useState('');
  const [sourceOpen, setSourceOpen] = useState(false);
  const [subscriptionOpen, setSubscriptionOpen] = useState(false);
  const [sourceName, setSourceName] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceKind, setSourceKind] = useState<'rss' | 'json_feed'>('rss');
  const [pollingMinutes, setPollingMinutes] = useState('60');
  const [subscriptionName, setSubscriptionName] = useState('');
  const [keywords, setKeywords] = useState('');
  const [regions, setRegions] = useState('');
  const [categories, setCategories] = useState('');
  const overviewQuery = useQuery({
    queryKey: ['radar-overview', view, queryText],
    queryFn: () => getRadarOverview({ view, query: queryText }),
    placeholderData: (previousData) => previousData,
    staleTime: 15_000,
    retry: false,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true
  });
  const overview = overviewQuery.data;
  const invalidate = () => client.invalidateQueries({ queryKey: ['radar-overview'] });
  const sourceMutation = useMutation({
    mutationFn: createRadarSource,
    onSuccess: () => {
      setSourceOpen(false);
      setSourceName('');
      setSourceUrl('');
      void invalidate();
      toast.success('公开来源已接入。');
    },
    onError: () => toast.error('来源未能接入，请检查地址和管理员权限。')
  });
  const subscriptionMutation = useMutation({
    mutationFn: createRadarSubscription,
    onSuccess: () => {
      setSubscriptionOpen(false);
      setSubscriptionName('');
      setKeywords('');
      setRegions('');
      setCategories('');
      void invalidate();
      toast.success('订阅已创建，匹配理由会随公告显示。');
    },
    onError: () => toast.error('订阅未能创建，请检查名称和筛选条件。')
  });
  const pollMutation = useMutation({
    mutationFn: pollRadarSource,
    onSuccess: (result) => {
      void invalidate();
      toast[result.status === 'succeeded' ? 'success' : 'error'](
        result.status === 'succeeded'
          ? `来源已刷新，新增 ${result.created_count} 条公告。`
          : '来源刷新失败，请检查公开地址。'
      );
    },
    onError: () => toast.error('来源暂时无法刷新。')
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'new' | 'saved' | 'ignored' }) =>
      updateRadarNoticeStatus(id, status),
    onSuccess: () => void invalidate(),
    onError: () => toast.error('公告状态未能更新。')
  });
  const convertMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name?: string }) =>
      convertRadarNoticeToProject(id, name),
    onSuccess: (result) => {
      void invalidate();
      toast.success('公告已转换为投标项目。');
      router.push(`/projects/${result.project_id}`);
    },
    onError: () => toast.error('公告暂时无法转换为项目。')
  });
  const summary = overview?.summary;
  const chartData = overview?.summary.trends ?? [];

  return (
    <>
      <PageHeader
        eyebrow='Opportunity intelligence'
        title='招采雷达'
        description='把公开来源、团队关注方向和机会研判放到同一条可追溯的工作路径上。'
        action={
          <div className='flex flex-wrap items-center justify-end gap-2'>
            <LiveSyncStatus
              active={Boolean(summary?.active_source_count)}
              dataUpdatedAt={overviewQuery.dataUpdatedAt}
              intervalLabel='每 30 秒'
              isFetching={overviewQuery.isFetching}
              onRefresh={() => void overviewQuery.refetch()}
            />
            <Button onClick={() => setSubscriptionOpen(true)} size='sm'>
              <Plus data-icon='inline-start' />
              新建订阅
            </Button>
            {isAdmin && (
              <Button onClick={() => setSourceOpen(true)} size='sm' variant='outline'>
                <Rss data-icon='inline-start' />
                管理来源
              </Button>
            )}
          </div>
        }
      />
      <div className='flex flex-1 flex-col gap-6 px-5 py-6 lg:px-8'>
        {overviewQuery.isPending ? (
          <QuerySkeleton rows={8} />
        ) : overviewQuery.error ? (
          <QueryError
            message={overviewQuery.error instanceof Error ? overviewQuery.error.message : undefined}
          />
        ) : overview ? (
          <>
            <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
              <SummaryStat
                icon={Rss}
                label='采集来源'
                value={summary?.active_source_count ?? 0}
                detail={
                  summary?.source_attention_count
                    ? `${summary.source_attention_count} 个需要处理`
                    : '按来源频率持续采集'
                }
              />
              <SummaryStat
                icon={Target}
                label='生效订阅'
                value={summary?.active_subscription_count ?? 0}
                detail='关键词、区域和品类意图'
              />
              <SummaryStat
                icon={Bell}
                label='推荐机会'
                value={summary?.recommended_count ?? 0}
                detail='已有订阅匹配依据'
              />
              <SummaryStat
                icon={CalendarClock}
                label='近期截止'
                value={summary?.due_soon_count ?? 0}
                detail='未来 14 天需要研判'
              />
            </div>
            <div className='grid gap-6 xl:grid-cols-[0.9fr_1.1fr]'>
              <Card>
                <CardHeader className='border-b'>
                  <CardTitle className='flex items-center gap-2'>
                    <Radar className={overviewQuery.isFetching ? 'motion-safe:animate-spin' : ''} />
                    来源信号
                  </CardTitle>
                  <CardDescription>只显示服务端已接入的公开来源。</CardDescription>
                </CardHeader>
                <CardContent className='flex flex-col gap-4 p-5'>
                  {overview.sources.length ? (
                    overview.sources.map((source) => (
                      <div className='flex items-center gap-3' key={source.id}>
                        <span
                          className={
                            source.is_active
                              ? 'bg-primary motion-safe:animate-pulse size-2 rounded-full'
                              : 'bg-muted-foreground size-2 rounded-full'
                          }
                        />
                        <span className='min-w-0 flex-1'>
                          <span className='block truncate text-sm font-medium'>{source.name}</span>
                          <span className='text-muted-foreground block truncate text-xs'>
                            {sourceKindLabel(source.kind)} · {source.notice_count} 条公告
                          </span>
                          <span className='text-muted-foreground/80 block truncate text-[11px]'>
                            {source.last_success_at
                              ? `最近成功 ${formatDate(source.last_success_at, {
                                  month: 'short',
                                  day: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit'
                                })}`
                              : source.last_polled_at
                                ? '最近刷新未成功'
                                : '尚未刷新'}
                            {source.last_error_code ? ' · 需要处理' : ''}
                          </span>
                        </span>
                        {isAdmin && ['rss', 'json_feed'].includes(source.kind) && (
                          <Button
                            aria-label={`刷新 ${source.name}`}
                            disabled={pollMutation.isPending || !source.is_active}
                            onClick={() => pollMutation.mutate(source.id)}
                            size='icon-sm'
                            title='刷新来源'
                            type='button'
                            variant='ghost'
                          >
                            <RefreshCw />
                          </Button>
                        )}
                      </div>
                    ))
                  ) : (
                    <EmptyState
                      title='尚未接入来源'
                      description={
                        isAdmin
                          ? '接入 RSS 或 JSON Feed 后，雷达会开始采集真实公告。'
                          : '请联系工作区管理员接入公开公告来源。'
                      }
                    />
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className='flex flex-row items-start justify-between gap-4 border-b'>
                  <div>
                    <CardTitle>新增机会趋势</CardTitle>
                    <CardDescription>最近 14 天已接入来源采集到的公告数量。</CardDescription>
                  </div>
                  <Badge variant='outline'>
                    {chartData.reduce((total, point) => total + point.notice_count, 0)} 条
                  </Badge>
                </CardHeader>
                <CardContent className='p-5'>
                  {chartData.some((point) => point.notice_count > 0) ? (
                    <ChartContainer className='h-64 w-full' config={radarChartConfig}>
                      <AreaChart
                        accessibilityLayer
                        data={chartData}
                        margin={{ top: 12, right: 6, left: -18, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient id='radar-notices-fill' x1='0' x2='0' y1='0' y2='1'>
                            <stop offset='5%' stopColor='var(--color-notices)' stopOpacity={0.24} />
                            <stop
                              offset='95%'
                              stopColor='var(--color-notices)'
                              stopOpacity={0.02}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid vertical={false} />
                        <XAxis
                          axisLine={false}
                          dataKey='day'
                          tickFormatter={(value) => formatDate(`${value}T00:00:00`)}
                          tickLine={false}
                          tickMargin={8}
                        />
                        <YAxis allowDecimals={false} axisLine={false} tickLine={false} width={30} />
                        <ChartTooltip content={<ChartTooltipContent />} />
                        <Area
                          animationDuration={700}
                          animationEasing='ease-out'
                          dataKey='notice_count'
                          fill='url(#radar-notices-fill)'
                          isAnimationActive
                          name='新增公告'
                          stroke='var(--color-notices)'
                          strokeWidth={2}
                          type='monotone'
                        />
                      </AreaChart>
                    </ChartContainer>
                  ) : (
                    <EmptyState
                      title='暂无真实采集数据'
                      description='来源完成首次刷新后，这里显示每日新增公告。'
                    />
                  )}
                </CardContent>
              </Card>
            </div>
            <Card>
              <CardHeader className='gap-4 border-b'>
                <div className='flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between'>
                  <div>
                    <CardTitle>机会队列</CardTitle>
                    <CardDescription>每条机会都保留来源、匹配理由和后续动作。</CardDescription>
                  </div>
                  <div className='relative w-full sm:max-w-xs'>
                    <Search className='text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2' />
                    <Input
                      aria-label='搜索公告'
                      className='pl-8'
                      onChange={(event) => setQueryText(event.target.value)}
                      placeholder='搜索公告、采购方或区域'
                      value={queryText}
                    />
                  </div>
                </div>
                <Tabs value={view} onValueChange={(value) => setView(value as RadarOverviewView)}>
                  <TabsList className='max-w-full overflow-x-auto' variant='line'>
                    {radarViews.map((item) => (
                      <TabsTrigger key={item.value} value={item.value}>
                        {item.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
              </CardHeader>
              <CardContent className='p-0'>
                {overview.notices.length ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>公告</TableHead>
                        <TableHead>来源</TableHead>
                        <TableHead>截止</TableHead>
                        <TableHead>状态</TableHead>
                        <TableHead className='text-right'>动作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {overview.notices.map((notice) => {
                        const href = safeExternalUrl(notice.source_url);
                        return (
                          <TableRow key={notice.id}>
                            <TableCell className='min-w-[18rem] max-w-[34rem] whitespace-normal'>
                              <div className='flex items-start gap-3'>
                                <span className='bg-primary/10 text-primary mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md'>
                                  <FileSearch />
                                </span>
                                <div className='min-w-0'>
                                  <p className='font-medium'>{notice.title}</p>
                                  <p className='text-muted-foreground mt-1 text-xs'>
                                    {notice.buyer_name || '采购方待补充'} ·{' '}
                                    {noticeTypeLabel(notice.notice_type)}
                                    {notice.region ? ` · ${notice.region}` : ''}
                                  </p>
                                  {notice.matches.length ? (
                                    <div className='mt-2 flex flex-wrap gap-1'>
                                      {notice.matches.slice(0, 2).map((match) => (
                                        <Badge key={match.subscription_id} variant='secondary'>
                                          {match.subscription_name} {Math.round(match.score)}%
                                        </Badge>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell className='text-muted-foreground'>
                              {notice.source_name}
                            </TableCell>
                            <TableCell>
                              {notice.deadline_at ? (
                                <span className='inline-flex items-center gap-1.5 text-xs'>
                                  <CalendarClock />
                                  {formatDate(notice.deadline_at)}
                                </span>
                              ) : (
                                '待补充'
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={
                                  notice.status === 'ignored'
                                    ? 'outline'
                                    : notice.status === 'saved'
                                      ? 'secondary'
                                      : 'default'
                                }
                              >
                                {noticeStatusLabel(notice.status)}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <div className='flex justify-end gap-1'>
                                <Button
                                  aria-label='保存公告'
                                  disabled={statusMutation.isPending || notice.status === 'saved'}
                                  onClick={() =>
                                    statusMutation.mutate({ id: notice.id, status: 'saved' })
                                  }
                                  size='icon-sm'
                                  title='保存公告'
                                  type='button'
                                  variant='ghost'
                                >
                                  <Target />
                                </Button>
                                <Button
                                  aria-label='转为项目'
                                  disabled={
                                    convertMutation.isPending || notice.status === 'converted'
                                  }
                                  onClick={() => convertMutation.mutate({ id: notice.id })}
                                  size='icon-sm'
                                  title='转为投标项目'
                                  type='button'
                                  variant='ghost'
                                >
                                  <FolderKanban />
                                </Button>
                                {href ? (
                                  <a
                                    aria-label='打开来源'
                                    className={buttonVariants({
                                      size: 'icon-sm',
                                      variant: 'ghost'
                                    })}
                                    href={href}
                                    title='打开来源'
                                    rel='noreferrer'
                                    target='_blank'
                                  >
                                    <ExternalLink />
                                  </a>
                                ) : null}
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                ) : (
                  <div className='p-5'>
                    <EmptyState
                      title='暂无匹配机会'
                      description='接入来源并创建订阅后，符合条件的公告会出现在这里。'
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        ) : null}
      </div>
      <Dialog onOpenChange={setSourceOpen} open={sourceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>接入公开来源</DialogTitle>
            <DialogDescription>来源地址由服务端定时采集，页面不会填充演示公告。</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor='radar-source-name'>来源名称</FieldLabel>
              <Input
                id='radar-source-name'
                onChange={(event) => setSourceName(event.target.value)}
                placeholder='例如：中国政府采购网'
                value={sourceName}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor='radar-source-url'>Feed 地址</FieldLabel>
              <Input
                id='radar-source-url'
                onChange={(event) => setSourceUrl(event.target.value)}
                placeholder='https://example.com/feed.xml'
                type='url'
                value={sourceUrl}
              />
              <FieldDescription>需要是公开可访问的 HTTP(S) 地址。</FieldDescription>
            </Field>
            <Field>
              <FieldLabel>来源格式</FieldLabel>
              <Select
                onValueChange={(value) => value && setSourceKind(value as 'rss' | 'json_feed')}
                value={sourceKind}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value='rss'>RSS Feed</SelectItem>
                    <SelectItem value='json_feed'>JSON Feed</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor='radar-polling'>采集间隔（分钟）</FieldLabel>
              <Input
                id='radar-polling'
                min='5'
                onChange={(event) => setPollingMinutes(event.target.value)}
                type='number'
                value={pollingMinutes}
              />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => setSourceOpen(false)} type='button' variant='outline'>
              取消
            </Button>
            <Button
              disabled={sourceMutation.isPending || !sourceName.trim() || !sourceUrl.trim()}
              onClick={() =>
                sourceMutation.mutate({
                  name: sourceName.trim(),
                  kind: sourceKind,
                  endpoint_url: sourceUrl.trim(),
                  polling_interval_minutes: Number(pollingMinutes)
                })
              }
              type='button'
            >
              保存来源
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog onOpenChange={setSubscriptionOpen} open={subscriptionOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建机会订阅</DialogTitle>
            <DialogDescription>
              使用逗号或换行分隔多个关键词，公告匹配后会保留命中理由。
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor='radar-subscription-name'>订阅名称</FieldLabel>
              <Input
                id='radar-subscription-name'
                onChange={(event) => setSubscriptionName(event.target.value)}
                placeholder='例如：医疗设备维保'
                value={subscriptionName}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor='radar-keywords'>关键词</FieldLabel>
              <Input
                id='radar-keywords'
                onChange={(event) => setKeywords(event.target.value)}
                placeholder='内窥镜，维保，医院'
                value={keywords}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor='radar-regions'>区域</FieldLabel>
              <Input
                id='radar-regions'
                onChange={(event) => setRegions(event.target.value)}
                placeholder='北京，江苏，四川'
                value={regions}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor='radar-categories'>品类</FieldLabel>
              <Input
                id='radar-categories'
                onChange={(event) => setCategories(event.target.value)}
                placeholder='医疗器械，服务'
                value={categories}
              />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => setSubscriptionOpen(false)} type='button' variant='outline'>
              取消
            </Button>
            <Button
              disabled={subscriptionMutation.isPending || !subscriptionName.trim()}
              onClick={() =>
                subscriptionMutation.mutate({
                  name: subscriptionName.trim(),
                  keywords: splitTerms(keywords),
                  regions: splitTerms(regions),
                  categories: splitTerms(categories)
                })
              }
              type='button'
            >
              创建订阅
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function AdministrationPage() {
  return (
    <AdminGuard>
      <AdministrationContent />
    </AdminGuard>
  );
}

function AdministrationContent() {
  const entitlements = useQuery({
    queryKey: ['organization-entitlements'],
    queryFn: getOrganizationEntitlements,
    staleTime: 30_000,
    retry: false
  });
  const billing = useQuery({
    queryKey: ['billing-summary'],
    queryFn: getBillingSummary,
    staleTime: 30_000,
    retry: false
  });
  const runtimeSummary = useQuery({
    queryKey: ['runtime-summary'],
    queryFn: getRuntimeSummary,
    staleTime: 15_000,
    retry: false
  });
  const runtimeContract = useQuery({
    queryKey: ['pi-runtime-contract'],
    queryFn: getPiRuntimeContract,
    staleTime: 60_000,
    retry: false
  });
  const members = useQuery({
    queryKey: ['organization-members'],
    queryFn: listOrganizationMembers,
    staleTime: 30_000,
    retry: false
  });
  const loading =
    entitlements.isPending ||
    billing.isPending ||
    members.isPending ||
    runtimeSummary.isPending ||
    runtimeContract.isPending;
  const error =
    entitlements.error ||
    billing.error ||
    members.error ||
    runtimeSummary.error ||
    runtimeContract.error;
  return (
    <>
      <PageHeader
        eyebrow='管理员'
        title='工作区管理'
        description='查看当前组织的容量、成员和外部集成入口。管理员控制与普通用户工作流分开。'
      />
      <div className='flex flex-1 flex-col gap-6 px-5 py-6 lg:px-8'>
        {loading ? (
          <QuerySkeleton rows={7} />
        ) : error ? (
          <QueryError message={error instanceof Error ? error.message : undefined} />
        ) : (
          <>
            <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
              <SummaryStat
                icon={Users}
                label='工作区成员'
                value={members.data?.length ?? 0}
                detail={`席位上限 ${entitlements.data?.seat_limit ?? '—'}`}
              />
              <SummaryStat
                icon={FolderKanban}
                label='项目容量'
                value={
                  entitlements.data?.project_limit === -1
                    ? '不限'
                    : (entitlements.data?.project_limit ?? '—')
                }
                detail={`当前计划 ${billing.data?.data.plan ?? '—'}`}
              />
              <SummaryStat
                icon={BriefcaseBusiness}
                label='工作流额度'
                value={
                  entitlements.data?.monthly_workflow_limit === -1
                    ? '不限'
                    : (entitlements.data?.monthly_workflow_limit ?? '—')
                }
                detail='按工作区月度计算'
              />
              <SummaryStat
                icon={Webhook}
                label='组织状态'
                value={billing.data?.data.status ?? '—'}
                detail={entitlements.data?.capacity_enforced ? '容量策略已启用' : '容量策略未启用'}
              />
            </div>
            <div className='grid gap-6 lg:grid-cols-2'>
              <Card>
                <CardHeader>
                  <CardTitle>成员与权限</CardTitle>
                  <CardDescription>
                    成员查看属于工作区协作，角色和邀请变更只在管理员区域开放。
                  </CardDescription>
                </CardHeader>
                <CardContent className='flex flex-col gap-3'>
                  <Link className={buttonVariants({ variant: 'outline' })} href='/members'>
                    查看成员列表 <ArrowUpRight data-icon='inline-end' />
                  </Link>
                  <Link className={buttonVariants({ variant: 'outline' })} href='/admin/users'>
                    管理用户角色 <ArrowUpRight data-icon='inline-end' />
                  </Link>
                  <Link className={buttonVariants({ variant: 'outline' })} href='/admin/teams'>
                    管理响应团队 <ArrowUpRight data-icon='inline-end' />
                  </Link>
                  <Link
                    className={buttonVariants({ variant: 'outline' })}
                    href='/admin/invitations'
                  >
                    管理邀请 <ArrowUpRight data-icon='inline-end' />
                  </Link>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>集成与容量</CardTitle>
                  <CardDescription>
                    这里不显示 Pi 私有提示词、原始工具参数或供应商密钥。
                  </CardDescription>
                </CardHeader>
                <CardContent className='flex flex-col gap-3'>
                  <Link
                    className={buttonVariants({ variant: 'outline' })}
                    href='/settings/providers'
                  >
                    模型供应商配置 <ArrowUpRight data-icon='inline-end' />
                  </Link>
                  <Link
                    className={buttonVariants({ variant: 'outline' })}
                    href='/settings/webhooks'
                  >
                    Webhook 端点 <ArrowUpRight data-icon='inline-end' />
                  </Link>
                  <Link className={buttonVariants({ variant: 'outline' })} href='/runs'>
                    运行记录 <ArrowUpRight data-icon='inline-end' />
                  </Link>
                </CardContent>
              </Card>
            </div>
            <Card>
              <CardHeader>
                <CardTitle>Pi 运行状态</CardTitle>
                <CardDescription>
                  仅管理员可见的服务端运行时摘要；这里不暴露提示词、原始工具参数或租户密钥。
                </CardDescription>
              </CardHeader>
              <CardContent className='grid gap-4 sm:grid-cols-3'>
                <RuntimeMetric
                  icon={Clock3}
                  label='排队运行'
                  value={runtimeSummary.data?.queue_depth ?? '—'}
                  detail='服务端队列中的任务'
                />
                <RuntimeMetric
                  icon={AlertCircle}
                  label='失败运行'
                  value={runtimeSummary.data?.failed_runs ?? '—'}
                  detail='需要管理员关注的终态'
                />
                <RuntimeMetric
                  icon={Sparkles}
                  label='Pi 能力'
                  value={runtimeContract.data?.data.extensions.length ?? '—'}
                  detail={`${runtimeContract.data?.data.skills.length ?? '—'} 项受信技能`}
                />
              </CardContent>
            </Card>
            <Alert>
              <ShieldCheck />
              <AlertTitle>服务端仍是权限和业务事实的唯一裁决点</AlertTitle>
              <AlertDescription>
                页面角色过滤只负责减少误触和信息暴露；每个管理员操作仍由 FastAPI 再次校验组织权限。
              </AlertDescription>
            </Alert>
          </>
        )}
      </div>
    </>
  );
}
