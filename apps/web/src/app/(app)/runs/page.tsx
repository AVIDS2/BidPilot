'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { AlertCircle, CheckCircle2, Clock3, Eye, Square } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
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
  const params = useSearchParams();
  const selectedRunId = params.get('run');
  const client = useQueryClient();
  const runs = useQuery({ queryKey: ['runtime-runs', 'all'], queryFn: () => listRuntimeRuns(100) });
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
        title='运行记录'
        description='查看真实 Pi Agent 和工作流的执行状态、事件摘要与终态。'
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {runs.isPending ? (
          <QuerySkeleton rows={6} />
        ) : runs.error ? (
          <QueryError message={runs.error instanceof Error ? runs.error.message : undefined} />
        ) : !runs.data?.length ? (
          <EmptyState
            title='还没有运行记录'
            description='从助手发起一次项目任务后，真实运行事件会保存在这里。'
          />
        ) : (
          <div className='grid gap-6 xl:grid-cols-[1.1fr_0.9fr]'>
            <Card>
              <CardContent className='p-0'>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>运行</TableHead>
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
                                {run.latest_event_summary || run.kind}
                              </span>
                              <span className='text-muted-foreground mt-1 block truncate text-xs'>
                                {run.engine} · {formatDate(run.created_at)}
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
                <h2 className='font-medium'>事件时间线</h2>
                <p className='text-muted-foreground mt-1 text-sm'>
                  {selectedRunId
                    ? `运行 ${selectedRunId.slice(0, 8)}…`
                    : '选择一条运行记录查看事件。'}
                </p>
              </CardHeader>
              <CardContent className='p-0'>
                {!selectedRunId ? (
                  <div className='p-5'>
                    <EmptyState
                      title='选择运行记录'
                      description='事件详情只在选择具体运行后加载。'
                    />
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
                          <Badge variant='outline'>{event.type}</Badge>
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
                    <EmptyState title='没有事件' description='该运行尚未产生可展示的公开事件。' />
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
          queued: '排队中',
          pending: '等待中',
          completed: '已完成',
          succeeded: '已完成',
          failed: '失败',
          cancelled: '已取消'
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
