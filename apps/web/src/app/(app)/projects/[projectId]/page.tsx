'use client';

import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  ClipboardCheck,
  FileCheck2,
  Files,
  ListChecks,
  MessageSquare,
  PlayCircle
} from 'lucide-react';
import { LiveSyncStatus } from '@/components/bidpilot/live-sync-status';
import { PageHeader } from '@/components/bidpilot/page-header';
import { QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Progress, ProgressLabel, ProgressValue } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProjectMaterialsPanel } from '@/features/workbench/project-materials-panel';
import { ProjectKnowledgePanel } from '@/features/workbench/project-knowledge-panel';
import { ProjectResponsePanel } from '@/features/workbench/project-response-panel';
import { getProject, getReadinessSummary, listBundles, listDeliverables } from '@/lib/bidpilot-api';

type ProjectTab =
  | 'overview'
  | 'materials'
  | 'requirements'
  | 'response'
  | 'review'
  | 'deliverables'
  | 'knowledge';

function projectTab(value: string | null): ProjectTab {
  if (
    value === 'materials' ||
    value === 'requirements' ||
    value === 'response' ||
    value === 'review' ||
    value === 'deliverables' ||
    value === 'knowledge'
  ) {
    return value;
  }
  return 'overview';
}

export default function ProjectDetailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const activeTab = projectTab(searchParams.get('tab'));
  const requestedDeliverableId = searchParams.get('deliverable');
  const requestedRunId = searchParams.get('run');
  const project = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const bundles = useQuery({
    queryKey: ['bundles', projectId],
    queryFn: () => listBundles(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const deliverables = useQuery({
    queryKey: ['deliverables', projectId],
    queryFn: () => listDeliverables(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const readiness = useQuery({
    queryKey: ['readiness', projectId],
    queryFn: () => getReadinessSummary(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 15_000,
    refetchOnWindowFocus: true
  });

  if (project.isPending)
    return (
      <>
        <PageHeader title='项目' />
        <div className='p-5 lg:p-8'>
          <QuerySkeleton rows={4} />
        </div>
      </>
    );
  if (project.error || !project.data)
    return (
      <>
        <PageHeader title='项目' />
        <div className='p-5 lg:p-8'>
          <QueryError
            message={project.error instanceof Error ? project.error.message : '项目不存在。'}
          />
        </div>
      </>
    );
  const item = project.data;
  const isRefreshing =
    project.isFetching || bundles.isFetching || deliverables.isFetching || readiness.isFetching;
  const dataUpdatedAt = Math.max(
    project.dataUpdatedAt,
    bundles.dataUpdatedAt,
    deliverables.dataUpdatedAt,
    readiness.dataUpdatedAt
  );
  const refreshAll = () => {
    void Promise.all([
      project.refetch(),
      bundles.refetch(),
      deliverables.refetch(),
      readiness.refetch()
    ]);
  };
  const setActiveTab = (tab: ProjectTab) => {
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.set('tab', tab);
    router.replace(`/projects/${projectId}?${nextParams.toString()}`, { scroll: false });
  };
  const readinessScore = readiness.data
    ? Math.min(100, Math.max(0, Math.round(readiness.data.readiness_score)))
    : 0;
  return (
    <>
      <PageHeader
        eyebrow='项目工作区'
        title={item.name}
        description={`${scenarioLabel(item.scenario_package)} · ${item.slug}`}
        action={
          <div className='flex flex-wrap items-center justify-end gap-2'>
            <LiveSyncStatus
              active
              dataUpdatedAt={dataUpdatedAt}
              intervalLabel='每 15 秒'
              isFetching={isRefreshing}
              onRefresh={refreshAll}
            />
            <Link
              className={buttonVariants({ variant: 'outline' })}
              href={`/projects/${item.id}?tab=materials`}
            >
              <Files data-icon='inline-start' />
              查看资料
            </Link>
            <Link className={buttonVariants()} href={`/projects/${item.id}?tab=response`}>
              进入响应工作区 <ArrowRight data-icon='inline-end' />
            </Link>
            <Link
              className={buttonVariants({ variant: 'outline' })}
              href={`/agent?project_id=${item.id}&entry=project`}
            >
              <MessageSquare data-icon='inline-start' />问 Copilot
            </Link>
          </div>
        }
      />
      <div className='flex flex-1 flex-col gap-6 px-5 py-6 lg:px-8'>
        <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
          <SummaryCard
            icon={<Files />}
            title='资料包'
            value={bundles.data?.length}
            loading={bundles.isPending}
          />
          <SummaryCard
            icon={<ListChecks />}
            title='就绪评分'
            value={readiness.data ? `${Math.round(readiness.data.readiness_score)}%` : undefined}
            loading={readiness.isPending}
          />
          <SummaryCard
            icon={<FileCheck2 />}
            title='交付物'
            value={deliverables.data?.length}
            loading={deliverables.isPending}
          />
          <SummaryCard
            icon={<PlayCircle />}
            title='项目状态'
            value={projectStatusLabel(item.status)}
          />
        </div>
        {readiness.data ? (
          <Card>
            <CardHeader className='border-b'>
              <div className='flex flex-wrap items-center justify-between gap-3'>
                <div>
                  <h2 className='font-medium'>响应准备度</h2>
                  <p className='text-muted-foreground mt-1 text-sm'>
                    由当前要求、证据和核验状态实时计算。
                  </p>
                </div>
                <Badge variant='outline'>{readinessLabel(readiness.data.score_label)}</Badge>
              </div>
            </CardHeader>
            <CardContent className='grid gap-5 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center'>
              <Progress value={readinessScore}>
                <ProgressLabel>整体就绪度</ProgressLabel>
                <ProgressValue />
              </Progress>
              <div className='grid grid-cols-2 gap-3 sm:min-w-56'>
                <ReadinessMetric label='已覆盖要求' value={readiness.data.counts.covered} />
                <ReadinessMetric label='待补证据' value={readiness.data.evidence_gaps.length} />
              </div>
            </CardContent>
          </Card>
        ) : null}
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(projectTab(value))}>
          <TabsList className='max-w-full overflow-x-auto'>
            <TabsTrigger value='overview'>项目概览</TabsTrigger>
            <TabsTrigger value='materials'>资料</TabsTrigger>
            <TabsTrigger value='requirements'>要求</TabsTrigger>
            <TabsTrigger value='response'>响应</TabsTrigger>
            <TabsTrigger value='review'>评审</TabsTrigger>
            <TabsTrigger value='deliverables'>交付</TabsTrigger>
            <TabsTrigger value='knowledge'>项目知识</TabsTrigger>
          </TabsList>
          <TabsContent value='overview' className='mt-5'>
            <div className='grid gap-6 lg:grid-cols-2'>
              <Card>
                <CardHeader className='border-b'>
                  <h2 className='font-medium'>下一步</h2>
                  <p className='text-muted-foreground mt-1 text-sm'>围绕项目事实推进响应任务。</p>
                </CardHeader>
                <CardContent className='grid gap-3 p-5'>
                  <ActionLink
                    href={`/projects/${item.id}?tab=materials`}
                    icon={<Files />}
                    title='整理项目资料'
                    copy='上传招标文件和企业依据，查看解析与索引状态。'
                  />
                  <ActionLink
                    href={`/requirements?project_id=${item.id}`}
                    icon={<ListChecks />}
                    title='拆解投标要求'
                    copy='在需求清单中确认要求、优先级和证据覆盖。'
                  />
                  <ActionLink
                    href={`/projects/${item.id}?tab=response`}
                    icon={<FileCheck2 />}
                    title='开始起草响应'
                    copy='选择章节发起起草，审核通过后导出交付文件。'
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader className='border-b'>
                  <h2 className='font-medium'>项目边界</h2>
                </CardHeader>
                <CardContent className='space-y-4 p-5 text-sm'>
                  <InfoRow label='项目 ID' value={item.id} />
                  <InfoRow label='工作区' value={item.org_slug || item.org_id || '当前账户'} />
                  <InfoRow label='场景包' value={scenarioLabel(item.scenario_package)} />
                  <InfoRow label='状态' value={projectStatusLabel(item.status)} />
                </CardContent>
              </Card>
            </div>
          </TabsContent>
          <TabsContent value='materials' className='mt-5'>
            <ProjectMaterialsPanel
              projectId={item.id}
              bundles={bundles.data}
              loading={bundles.isPending}
              error={bundles.error}
            />
          </TabsContent>
          <TabsContent value='requirements' className='mt-5'>
            <ProjectLinkedSection
              icon={<ListChecks />}
              title='项目要求'
              description='按当前项目查看要求、优先级、验证状态和证据覆盖。'
              href={`/requirements?project_id=${item.id}`}
              action='打开要求清单'
            />
          </TabsContent>
          <TabsContent value='response' className='mt-5'>
            <ProjectResponsePanel
              key={`${item.id}:${requestedDeliverableId ?? ''}:${requestedRunId ?? ''}`}
              projectId={item.id}
              requestedDeliverableId={requestedDeliverableId}
              requestedRunId={requestedRunId}
              deliverables={deliverables.data}
              loading={deliverables.isPending}
              error={deliverables.error}
            />
          </TabsContent>
          <TabsContent value='review' className='mt-5'>
            <ProjectLinkedSection
              icon={<ClipboardCheck />}
              title='项目评审'
              description='集中处理当前项目的分配、审核和待回复讨论。'
              href={`/reviews?project_id=${item.id}`}
              action='打开评审看板'
            />
          </TabsContent>
          <TabsContent value='deliverables' className='mt-5'>
            <ProjectLinkedSection
              icon={<FileCheck2 />}
              title='项目交付'
              description='查看响应文档、版本状态，并导出最终文件。'
              href={`/deliverables?project_id=${item.id}`}
              action='打开交付物'
            />
          </TabsContent>
          <TabsContent value='knowledge' className='mt-5'>
            <ProjectKnowledgePanel projectId={item.id} />
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}

function ProjectLinkedSection({
  icon,
  title,
  description,
  href,
  action
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  href: string;
  action: string;
}) {
  return (
    <Card>
      <CardHeader className='border-b'>
        <div className='flex items-center gap-3'>
          <span className='bg-primary/10 text-primary flex size-9 items-center justify-center rounded-lg'>
            {icon}
          </span>
          <div>
            <h2 className='font-medium'>{title}</h2>
            <p className='text-muted-foreground mt-1 text-sm'>{description}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className='flex items-center justify-between gap-4 p-5'>
        <p className='text-muted-foreground text-sm'>已保留当前项目上下文。</p>
        <Link className={buttonVariants({ size: 'sm' })} href={href}>
          {action} <ArrowRight data-icon='inline-end' />
        </Link>
      </CardContent>
    </Card>
  );
}

function ReadinessMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className='bg-muted/40 rounded-lg p-3'>
      <p className='text-muted-foreground text-xs'>{label}</p>
      <p className='mt-1 text-lg font-semibold tabular-nums'>{value}</p>
    </div>
  );
}

function projectStatusLabel(value: string) {
  return (
    {
      active: '进行中',
      draft: '草稿',
      completed: '已完成',
      archived: '已归档',
      failed: '需要处理'
    }[value] || '进行中'
  );
}

function scenarioLabel(value: string) {
  return value === 'bidpilot' ? 'BidPilot 招标响应场景' : value;
}

function readinessLabel(value: string) {
  return value === 'response_readiness' ? '响应准备度' : value || '响应准备度';
}

function SummaryCard({
  icon,
  title,
  value,
  loading = false
}: {
  icon: React.ReactNode;
  title: string;
  value?: number | string;
  loading?: boolean;
}) {
  return (
    <Card>
      <CardContent className='flex items-center gap-3 p-5'>
        <div className='bg-primary/10 text-primary flex size-9 items-center justify-center rounded-lg [&_svg]:size-4'>
          {icon}
        </div>
        <div className='min-w-0'>
          <p className='text-muted-foreground text-sm'>{title}</p>
          {loading ? (
            <div className='bg-muted mt-2 h-6 w-16 animate-pulse rounded' />
          ) : (
            <p className='mt-1 truncate text-lg font-semibold'>{value ?? '—'}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
function ActionLink({
  href,
  icon,
  title,
  copy
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  copy: string;
}) {
  return (
    <Link
      className='hover:bg-muted/50 flex items-start gap-3 rounded-lg border p-4 transition-colors'
      href={href}
    >
      <span className='text-primary mt-0.5 [&_svg]:size-4'>{icon}</span>
      <span className='min-w-0'>
        <span className='block text-sm font-medium'>{title}</span>
        <span className='text-muted-foreground mt-1 block text-xs leading-5'>{copy}</span>
      </span>
      <ArrowRight className='text-muted-foreground ml-auto mt-0.5 size-4 shrink-0' />
    </Link>
  );
}
function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className='flex items-start justify-between gap-4 border-b pb-3 last:border-0 last:pb-0'>
      <span className='text-muted-foreground'>{label}</span>
      <span className='max-w-[65%] break-all text-right font-medium'>{value}</span>
    </div>
  );
}
