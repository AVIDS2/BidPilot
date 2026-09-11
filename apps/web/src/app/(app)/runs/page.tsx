'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { AlertCircle, CheckCircle2, Clock3, Eye, Square } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { LiveSyncStatus } from '@/components/bidpilot/live-sync-status';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { AdminGuard } from '@/components/auth/admin-guard';
import { Badge } from '@/components/ui/badge';
import { buttonVariants, Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { cancelRuntimeWorkflow, listRuntimeEvents, listRuntimeRuns } from '@/lib/bidpilot-api';

export default function RunsPage() {
  return (
    <AdminGuard>
      <RunsContent />
    </AdminGuard>
  );
}

function RunsContent() {
  const params = useSearchParams();
  const selectedRunId = params.get('run');
  const client = useQueryClient();
  const runs = useQuery({
    queryKey: ['runtime-runs', 'all'],
    queryFn: () => listRuntimeRuns(100),
    refetchInterval: 15_000,
    refetchOnWindowFocus: true
  });
  const events = useQuery({
    queryKey: ['runtime-events', selectedRunId],
    queryFn: () => listRuntimeEvents(selectedRunId || ''),
    enabled: Boolean(selectedRunId)
  });
  const cancel = useMutation({
    mutationFn: cancelRuntimeWorkflow,
    onSuccess: () => client.invalidateQueries({ queryKey: ['runtime-runs'] })
  });
  return (
    <>
      <PageHeader
        eyebrow='投标工作流'
        title='任务详情'
        description='查看项目任务的进展、结果和需要你确认的事项。'
        action={
          <LiveSyncStatus
            active={Boolean(runs.data)}
            dataUpdatedAt={runs.dataUpdatedAt}
            intervalLabel='每 15 秒'
            isFetching={runs.isFetching}
            onRefresh={() => void runs.refetch()}
          />
        }
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {runs.isPending ? (
          <QuerySkeleton rows={6} />
        ) : runs.error ? (
          <QueryError message={runs.error instanceof Error ? runs.error.message : undefined} />
        ) : !runs.data?.length ? (
          <EmptyState
            title='还没有任务'
            description='从 Copilot 发起项目工作后，进展和结果会保存在这里。'
          />
        ) : (
          <div className='grid gap-6 xl:grid-cols-[1.1fr_0.9fr]'>
            <Card>
              <CardContent className='p-0'>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>任务</TableHead>
                      <TableHead>项目</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead className='text-right'>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runs.data.map((run) => (
                      <TableRow
                        key={run.id}
                        data-state={run.id === selectedRunId ? 'selected' : undefined}
                      >
                        <TableCell>
                          <Link
                            className='flex min-w-0 items-center gap-3'
                            href={`/runs?run=${run.id}`}
                          >
                            <RunIcon status={run.status} />
                            <span className='min-w-0'>
                              <span className='block max-w-[26rem] truncate text-sm font-medium'>
                                {run.latest_event_summary || runKindLabel(run.kind)}
                              </span>
                              <span className='text-muted-foreground mt-1 block truncate text-xs'>
                                {formatDate(run.created_at)}
                              </span>
                            </span>
                          </Link>
                        </TableCell>
                        <TableCell className='text-muted-foreground'>
                          {run.project_name || '未关联项目'}
                        </TableCell>
                        <TableCell>
                          <StatusBadge value={run.status} />
                        </TableCell>
                        <TableCell className='text-right'>
                          {['running', 'queued', 'pending'].includes(run.status) ? (
                            <Button
                              size='sm'
                              variant='destructive'
                              disabled={cancel.isPending}
                              onClick={() => cancel.mutate(run.id)}
                            >
                              <Square data-icon='inline-start' />
                              停止
                            </Button>
                          ) : (
                            <Link
                              className={buttonVariants({ size: 'sm', variant: 'ghost' })}
                              href={`/runs?run=${run.id}`}
                            >
                              查看 <Eye data-icon='inline-start' />
                            </Link>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className='border-b'>
                <h2 className='font-medium'>进展记录</h2>
                <p className='text-muted-foreground mt-1 text-sm'>
                  {selectedRunId ? `运行 ${selectedRunId.slice(0, 8)}…` : '选择一项任务查看进展。'}
                </p>
              </CardHeader>
              <CardContent className='p-0'>
                {!selectedRunId ? (
                  <div className='p-5'>
                    <EmptyState title='选择一项任务' description='选择后查看任务的进展和结果。' />
                  </div>
                ) : events.isPending ? (
                  <div className='p-5'>
                    <QuerySkeleton rows={4} />
                  </div>
                ) : events.error ? (
                  <div className='p-5'>
                    <QueryError
                      message={events.error instanceof Error ? events.error.message : undefined}
                    />
                  </div>
                ) : events.data?.items.length ? (
                  <div className='divide-y'>
                    {events.data.items.map((event) => (
                      <div className='px-5 py-4' key={event.event_id}>
                        <div className='flex items-center gap-2'>
                          <Badge variant='outline'>{eventLabel(event.type)}</Badge>
                          <span className='text-muted-foreground ml-auto text-xs'>
                            {formatDate(event.timestamp)}
                          </span>
                        </div>
                        <p className='mt-2 text-sm leading-6'>{event.public_summary}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className='p-5'>
                    <EmptyState title='暂无进展' description='该任务还没有可展示的更新。' />
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </>
  );
}

function RunIcon({ status }: { status: string }) {
  if (['failed', 'error'].includes(status))
    return <AlertCircle className='text-destructive size-4 shrink-0' />;
  if (['completed', 'succeeded'].includes(status))
    return <CheckCircle2 className='text-emerald-600 size-4 shrink-0' />;
  return <Clock3 className='text-primary size-4 shrink-0' />;
}
function StatusBadge({ value }: { value: string }) {
  const variant = ['failed', 'error', 'cancelled'].includes(value)
    ? 'destructive'
    : value === 'completed' || value === 'succeeded'
      ? 'secondary'
      : 'outline';
  return (
    <Badge variant={variant}>
      {(
        {
          running: '运行中',
          queued: '准备中',
          pending: '等待中',
          awaiting_approval: '等待审批',
          awaiting_input: '需要补充信息',
          cancel_requested: '停止中',
          completed: '已完成',
          succeeded: '已完成',
          failed: '失败',
          error: '失败',
          cancelled: '已取消',
          expired: '已过期'
        } as Record<string, string>
      )[value] || value}
    </Badge>
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

function eventLabel(value: string) {
  return (
    (
      {
        'assistant.start': '任务开始',
        'assistant.message': '助手更新',
        'assistant.tool_started': '开始处理',
        'assistant.tool_succeeded': '处理完成',
        'assistant.tool_failed': '处理失败',
        'assistant.end': '任务结束'
      } as Record<string, string>
    )[value] || '任务更新'
  );
}

function runKindLabel(value: string) {
  return (
    (
      {
        assistant_turn: '助手任务',
        workflow_bridge: '响应工作流',
        subagent: '协作任务',
        deep_research: '深度调研',
        remote_import: '资料导入'
      } as Record<string, string>
    )[value] || '工作流任务'
  );
}
