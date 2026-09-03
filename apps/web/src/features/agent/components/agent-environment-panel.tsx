import { useMemo } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import {
  ActivityIcon,
  BotIcon,
  ChevronRightIcon,
  CircleDotIcon,
  FileTextIcon,
  FolderKanbanIcon,
  Globe2Icon,
  Layers3Icon,
  SparklesIcon,
  WorkflowIcon
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  listProjects,
  listRuntimeRuns,
  type ProjectRead,
  type RuntimeRunListItem
} from '@/lib/api';
import { cn } from '@/lib/utils';

const ACTIVE_STATUSES = new Set([
  'queued',
  'running',
  'awaiting_approval',
  'awaiting_input',
  'cancel_requested'
]);
const BACKGROUND_RUN_KINDS = new Set([
  'subagent',
  'deep_research',
  'workflow_bridge',
  'remote_import',
  'system_recovery'
]);
const BACKGROUND_RUN_KIND_LIST = [
  'subagent',
  'deep_research',
  'workflow_bridge',
  'remote_import',
  'system_recovery'
];
const EMPTY_RUNS: RuntimeRunListItem[] = [];
const EMPTY_PROJECTS: ProjectRead[] = [];

interface AgentEnvironmentPanelProps {
  currentProjectId?: string | null;
  onOpenProject?: (projectId: string) => void;
  onOpenRun: (run: RuntimeRunListItem) => void;
}

function runLabel(run: RuntimeRunListItem) {
  if (run.kind === 'subagent') return '子 Agent';
  if (run.kind === 'deep_research') return '深度调研';
  if (run.kind === 'workflow_bridge') return '响应工作流';
  if (run.kind === 'remote_import') return '资料导入';
  if (run.kind === 'system_recovery') return '任务恢复';
  if (run.kind === 'assistant_turn') return '助手会话';
  return '后台任务';
}

function RunIcon({ kind }: { kind: string }) {
  const props = { className: 'size-3.5' };
  if (kind === 'subagent') return <BotIcon {...props} />;
  if (kind === 'deep_research') return <Globe2Icon {...props} />;
  if (kind === 'workflow_bridge') return <WorkflowIcon {...props} />;
  if (kind === 'remote_import') return <Layers3Icon {...props} />;
  return <ActivityIcon {...props} />;
}

function statusLabel(status: string) {
  if (status === 'queued') return '准备开始';
  if (status === 'awaiting_approval') return '需要确认';
  if (status === 'awaiting_input') return '需要补充信息';
  if (status === 'cancel_requested') return '正在停止';
  if (status === 'running') return '处理中';
  if (status === 'succeeded' || status === 'completed') return '已结束';
  if (status === 'failed') return '失败';
  return status;
}

function statusVariant(status: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (status === 'failed') return 'destructive';
  if (status === 'running') return 'default';
  if (status === 'awaiting_approval' || status === 'awaiting_input') return 'secondary';
  return 'outline';
}

function ActiveRunRow({
  run,
  onOpen
}: {
  run: RuntimeRunListItem;
  onOpen: (run: RuntimeRunListItem) => void;
}) {
  const isLive = ACTIVE_STATUSES.has(run.status);
  return (
    <Button
      aria-label={`${runLabel(run)}${run.latest_event_summary ? `：${run.latest_event_summary}` : ''}`}
      className='h-auto w-full justify-start gap-2.5 px-2.5 py-2 text-left'
      onClick={() => onOpen(run)}
      size='sm'
      variant='ghost'
    >
      <span
        className={cn(
          'grid size-7 shrink-0 place-items-center rounded-md bg-muted',
          isLive && 'text-primary'
        )}
      >
        <RunIcon kind={run.kind} />
      </span>
      <span className='flex min-w-0 flex-1 flex-col gap-0.5'>
        <span className='flex min-w-0 items-center gap-1.5'>
          <span className='truncate text-xs font-medium'>{runLabel(run)}</span>
          <Badge className='shrink-0' variant={statusVariant(run.status)}>
            {statusLabel(run.status)}
          </Badge>
        </span>
        <span className='truncate text-[11px] text-muted-foreground'>
          {run.latest_event_summary || run.project_name || '后台工作'}
        </span>
      </span>
      {isLive ? <ChevronRightIcon className='size-3.5 shrink-0 text-muted-foreground' /> : null}
    </Button>
  );
}

function ProjectRow({
  project,
  current,
  onOpen
}: {
  project: ProjectRead;
  current: boolean;
  onOpen?: () => void;
}) {
  return (
    <Button
      className='h-auto w-full justify-start gap-2.5 px-2.5 py-2 text-left'
      onClick={onOpen}
      size='sm'
      variant={current ? 'secondary' : 'ghost'}
    >
      <span className='grid size-7 shrink-0 place-items-center rounded-md bg-muted'>
        <FolderKanbanIcon className='size-3.5 text-muted-foreground' />
      </span>
      <span className='flex min-w-0 flex-1 flex-col gap-0.5'>
        <span className='truncate text-xs font-medium'>{project.name}</span>
        <span className='truncate text-[11px] text-muted-foreground'>
          {project.scenario_package || '投标工作区'}
        </span>
      </span>
      <ChevronRightIcon className='size-3.5 shrink-0 text-muted-foreground' />
    </Button>
  );
}

export function AgentEnvironmentPanel({
  currentProjectId,
  onOpenProject,
  onOpenRun
}: AgentEnvironmentPanelProps) {
  const runsQuery = useQuery<RuntimeRunListItem[]>({
    queryKey: ['agent-environment-runs', 'live'],
    queryFn: () => listRuntimeRuns(30, null, BACKGROUND_RUN_KIND_LIST, true),
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
    staleTime: 5_000
  });
  const projectsQuery = useQuery<ProjectRead[]>({
    queryKey: ['projects'],
    queryFn: listProjects,
    staleTime: 30_000
  });
  const runs = Array.isArray(runsQuery.data) ? runsQuery.data : EMPTY_RUNS;
  const projects = Array.isArray(projectsQuery.data) ? projectsQuery.data : EMPTY_PROJECTS;
  const loadError = runsQuery.isError || projectsQuery.isError;
  const activeRuns = useMemo(
    () =>
      runs.filter((run) => BACKGROUND_RUN_KINDS.has(run.kind) && ACTIVE_STATUSES.has(run.status)),
    [runs]
  );
  const completedRuns = useMemo(
    () =>
      runs.filter(
        (run) =>
          BACKGROUND_RUN_KINDS.has(run.kind) &&
          (run.status === 'succeeded' || run.status === 'completed')
      ),
    [runs]
  );
  const currentProject = projects.find((project) => project.id === currentProjectId) ?? null;
  const activeSubagentCount = activeRuns.filter((run) => run.kind === 'subagent').length;
  const overviewSummary = activeSubagentCount
    ? `${activeSubagentCount} 个子 Agent 正在工作`
    : activeRuns.length
      ? `${activeRuns.length} 项任务需要关注`
      : '当前没有进行中的任务';

  return (
    <Card className='agent-environment-panel h-full min-h-0 rounded-xl' size='sm'>
      <CardHeader className='border-b px-3.5 pb-3'>
        <CardTitle className='flex items-center gap-2 text-sm'>
          <CircleDotIcon className='size-3.5 text-primary' />
          工作概览
        </CardTitle>
        <CardDescription className='text-[11px]'>{overviewSummary}</CardDescription>
      </CardHeader>
      <ScrollArea className='min-h-0 flex-1'>
        <CardContent className='flex flex-col gap-4 px-3.5 py-3.5'>
          {currentProject ? (
            <section aria-label='当前项目' className='flex flex-col gap-2'>
              <div className='flex items-center justify-between'>
                <div className='flex items-center gap-2 text-xs font-medium'>
                  <FolderKanbanIcon className='size-3.5 text-muted-foreground' />
                  当前项目
                </div>
                <Badge variant='secondary'>工作中</Badge>
              </div>
              <ProjectRow
                current
                onOpen={onOpenProject ? () => onOpenProject(currentProject.id) : undefined}
                project={currentProject}
              />
            </section>
          ) : null}

          <section aria-label='进行中的任务' className='flex flex-col gap-2'>
            <div className='flex items-center justify-between'>
              <div className='flex items-center gap-2 text-xs font-medium'>
                <ActivityIcon className='size-3.5 text-muted-foreground' />
                进行中的任务
              </div>
              {activeRuns.length ? <Badge variant='default'>{activeRuns.length}</Badge> : null}
            </div>
            {runsQuery.isLoading ? (
              <div
                aria-busy='true'
                className='flex flex-col gap-2 rounded-md bg-muted/40 px-2.5 py-2'
                role='status'
                aria-label='正在加载后台工作'
              >
                <Skeleton className='h-3 w-2/3' />
                <Skeleton className='h-3 w-1/2' />
              </div>
            ) : runsQuery.isError && !runsQuery.data ? (
              <div
                className='rounded-md bg-destructive/10 px-2.5 py-2 text-xs text-destructive'
                role='alert'
              >
                后台工作暂时无法读取。
              </div>
            ) : activeRuns.length ? (
              <div className='flex flex-col gap-1'>
                {activeRuns.slice(0, 8).map((run) => (
                  <ActiveRunRow key={run.id} onOpen={onOpenRun} run={run} />
                ))}
              </div>
            ) : (
              <div className='flex items-center gap-2 rounded-md bg-muted/40 px-2.5 py-2 text-xs text-muted-foreground'>
                <SparklesIcon className='size-3.5' />
                目前没有后台工作
              </div>
            )}
            {activeRuns.length > 8 ? (
              <p className='text-[11px] text-muted-foreground'>
                还有 {activeRuns.length - 8} 项工作，可打开后台工作查看。
              </p>
            ) : null}
          </section>

          {completedRuns.length ? (
            <>
              <Separator />
              <section aria-label='最近完成' className='flex flex-col gap-2'>
                <div className='flex items-center gap-2 text-xs font-medium'>
                  <FileTextIcon className='size-3.5 text-muted-foreground' />
                  最近完成
                </div>
                <div className='flex flex-col gap-1'>
                  {completedRuns.slice(0, 3).map((run) => (
                    <ActiveRunRow key={run.id} onOpen={onOpenRun} run={run} />
                  ))}
                </div>
              </section>
            </>
          ) : null}

          <Separator />

          <section aria-label='项目工作区' className='flex flex-col gap-2'>
            <div className='flex items-center justify-between'>
              <div className='flex items-center gap-2 text-xs font-medium'>
                <FolderKanbanIcon className='size-3.5 text-muted-foreground' />
                项目工作区
              </div>
              <Link
                className='text-[11px] text-muted-foreground underline-offset-4 hover:underline'
                href='/projects'
              >
                查看全部
              </Link>
            </div>
            {projectsQuery.isLoading ? (
              <div
                aria-busy='true'
                className='flex flex-col gap-2 rounded-md bg-muted/40 px-2.5 py-2'
                role='status'
                aria-label='正在加载项目工作区'
              >
                <Skeleton className='h-3 w-3/4' />
                <Skeleton className='h-3 w-1/2' />
              </div>
            ) : projectsQuery.isError && !projectsQuery.data ? (
              <div
                className='rounded-md bg-destructive/10 px-2.5 py-2 text-xs text-destructive'
                role='alert'
              >
                项目工作区暂时无法读取。
              </div>
            ) : projects.length ? (
              <div className='flex flex-col gap-1'>
                {projects.slice(0, 5).map((project) => (
                  <ProjectRow
                    current={project.id === currentProjectId}
                    key={project.id}
                    onOpen={onOpenProject ? () => onOpenProject(project.id) : undefined}
                    project={project}
                  />
                ))}
              </div>
            ) : (
              <div className='flex items-center gap-2 rounded-md bg-muted/40 px-2.5 py-2 text-xs text-muted-foreground'>
                <Layers3Icon className='size-3.5' />
                还没有投标项目
              </div>
            )}
          </section>

          {loadError ? (
            <p className='text-[11px] text-destructive'>工作概览暂时无法刷新，正在保留上次状态。</p>
          ) : null}
        </CardContent>
      </ScrollArea>
    </Card>
  );
}
