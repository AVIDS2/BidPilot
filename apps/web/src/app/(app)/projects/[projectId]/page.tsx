'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, FileCheck2, Files, ListChecks, MessageSquare, PlayCircle } from 'lucide-react';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { getProject, getReadinessSummary, listBundles, listDeliverables } from '@/lib/bidpilot-api';

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const project = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: Boolean(projectId)
  });
  const bundles = useQuery({
    queryKey: ['bundles', projectId],
    queryFn: () => listBundles(projectId),
    enabled: Boolean(projectId)
  });
  const deliverables = useQuery({
    queryKey: ['deliverables', projectId],
    queryFn: () => listDeliverables(projectId),
    enabled: Boolean(projectId)
  });
  const readiness = useQuery({
    queryKey: ['readiness', projectId],
    queryFn: () => getReadinessSummary(projectId),
    enabled: Boolean(projectId)
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
  return (
    <>
      <PageHeader
        eyebrow='项目工作区'
        title={item.name}
        description={`${item.scenario_package} · ${item.slug}`}
        action={
          <div className='flex flex-wrap gap-2'>
            <Link
              className={buttonVariants({ variant: 'outline' })}
              href={`/agent?project_id=${item.id}`}
            >
              <MessageSquare data-icon='inline-start' />
              打开助手
            </Link>
            <Link className={buttonVariants()} href={`/agent?project_id=${item.id}`}>
              开始任务 <ArrowRight data-icon='inline-end' />
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
          <SummaryCard icon={<PlayCircle />} title='项目状态' value={item.status} />
        </div>
        <Tabs defaultValue='overview'>
          <TabsList>
            <TabsTrigger value='overview'>项目概览</TabsTrigger>
            <TabsTrigger value='materials'>资料与知识</TabsTrigger>
            <TabsTrigger value='delivery'>响应与交付</TabsTrigger>
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
                    href={`/agent?project_id=${item.id}`}
                    icon={<MessageSquare />}
                    title='让 Agent 检查资料完整度'
                    copy='使用真实 Pi 运行读取项目范围内的资料和需求。'
                  />
                  <ActionLink
                    href={`/agent?project_id=${item.id}`}
                    icon={<ListChecks />}
                    title='拆解投标要求'
                    copy='把资格、商务和技术要求整理为可追踪条目。'
                  />
                  <ActionLink
                    href={`/agent?project_id=${item.id}`}
                    icon={<FileCheck2 />}
                    title='开始起草响应'
                    copy='在证据准备完成后生成可审阅的章节草稿。'
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
                  <InfoRow label='场景包' value={item.scenario_package} />
                  <InfoRow label='状态' value={item.status} />
                </CardContent>
              </Card>
            </div>
          </TabsContent>
          <TabsContent value='materials' className='mt-5'>
            <Materials bundles={bundles.data} loading={bundles.isPending} error={bundles.error} />
          </TabsContent>
          <TabsContent value='delivery' className='mt-5'>
            <Delivery
              deliverables={deliverables.data}
              loading={deliverables.isPending}
              error={deliverables.error}
            />
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
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
function Materials({
  bundles,
  loading,
  error
}: {
  bundles?: Awaited<ReturnType<typeof listBundles>>;
  loading: boolean;
  error: Error | null;
}) {
  if (loading) return <QuerySkeleton rows={3} />;
  if (error) return <QueryError message={error.message} />;
  if (!bundles?.length)
    return (
      <EmptyState
        title='还没有资料包'
        description='先上传招标文件或企业材料，再让 Agent 进行解析。'
      />
    );
  return (
    <div className='grid gap-4 md:grid-cols-2'>
      {bundles.map((bundle) => (
        <Card key={bundle.id}>
          <CardHeader>
            <h2 className='font-medium'>{bundle.label}</h2>
            <p className='text-muted-foreground text-sm'>{bundle.source_type}</p>
          </CardHeader>
          <CardContent>
            <Link
              className={buttonVariants({ size: 'sm', variant: 'outline' })}
              href={`/knowledge?project_id=${bundle.project_id}`}
            >
              查看资料 <ArrowRight data-icon='inline-end' />
            </Link>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
function Delivery({
  deliverables,
  loading,
  error
}: {
  deliverables?: Awaited<ReturnType<typeof listDeliverables>>;
  loading: boolean;
  error: Error | null;
}) {
  if (loading) return <QuerySkeleton rows={3} />;
  if (error) return <QueryError message={error.message} />;
  if (!deliverables?.length)
    return (
      <EmptyState
        title='还没有交付物'
        description='Agent 完成起草和审核后，交付版本会显示在这里。'
      />
    );
  return (
    <div className='grid gap-4 md:grid-cols-2'>
      {deliverables.map((deliverable) => (
        <Card key={deliverable.id}>
          <CardHeader className='flex flex-row items-start justify-between gap-3'>
            <div>
              <h2 className='font-medium'>{deliverable.title}</h2>
              <p className='text-muted-foreground mt-1 text-sm'>{deliverable.type}</p>
            </div>
            <Badge variant='outline'>{deliverable.status}</Badge>
          </CardHeader>
          <CardContent>
            <Link
              className={buttonVariants({ size: 'sm', variant: 'outline' })}
              href={`/deliverables?deliverable=${deliverable.id}`}
            >
              打开交付物 <ArrowRight data-icon='inline-end' />
            </Link>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
