'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  BotIcon,
  CheckCircle2Icon,
  CircleXIcon,
  Clock3Icon,
  Loader2Icon,
  XIcon
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle
} from '@/components/ui/empty';
import { Item, ItemContent, ItemGroup, ItemMedia, ItemTitle } from '@/components/ui/item';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { listRuntimeChildRuns, type RuntimeChildRunRead } from '@/lib/api';

const ACTIVE_STATUSES = new Set(['queued', 'running', 'cancel_requested']);

function profileLabel(profile: string | null) {
  if (profile === 'researcher') return '资料研究员';
  if (profile === 'reviewer') return '审核员';
  if (profile === 'analyst') return '分析员';
  return '协作助理';
}

function statusLabel(status: string) {
  if (status === 'queued') return '准备中';
  if (status === 'running') return '处理中';
  if (status === 'cancel_requested') return '正在停止';
  if (status === 'succeeded' || status === 'completed') return '已完成';
  if (status === 'cancelled') return '已取消';
  if (status === 'failed' || status === 'expired') return '未完成';
  return '等待更新';
}

function statusVariant(status: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (status === 'failed' || status === 'expired') return 'destructive';
  if (status === 'running') return 'default';
  if (status === 'queued' || status === 'cancel_requested') return 'secondary';
  return 'outline';
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'succeeded' || status === 'completed') {
    return <CheckCircle2Icon className='size-4 text-primary' aria-hidden='true' />;
  }
  if (status === 'failed' || status === 'expired' || status === 'cancelled') {
    return <CircleXIcon className='size-4 text-destructive' aria-hidden='true' />;
  }
  if (status === 'running' || status === 'cancel_requested') {
    return <Loader2Icon className='size-4 animate-spin text-primary' aria-hidden='true' />;
  }
  return <Clock3Icon className='size-4 text-muted-foreground' aria-hidden='true' />;
}

function activeCount(children: RuntimeChildRunRead[]) {
  return children.filter((child) => ACTIVE_STATUSES.has(child.status)).length;
}

export function AgentSubagentsPanel({
  parentRunId,
  onClose,
  showHeader = true
}: {
  parentRunId: string;
  onClose: () => void;
  showHeader?: boolean;
}) {
  const [children, setChildren] = useState<RuntimeChildRunRead[]>([]);
  const childrenRef = useRef<RuntimeChildRunRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const rows = await listRuntimeChildRuns(parentRunId, 20);
        if (cancelled) return;
        childrenRef.current = rows;
        setChildren(rows);
        setHasError(false);
      } catch {
        if (!cancelled) setHasError(true);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    void refresh();
    const timer = window.setInterval(() => {
      if (activeCount(childrenRef.current) > 0 || childrenRef.current.length === 0) void refresh();
    }, 2_500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [parentRunId]);

  const running = useMemo(() => activeCount(children), [children]);
  const summary = isLoading
    ? '正在读取协作进度'
    : hasError
      ? '协作进度暂时无法更新'
      : running > 0
        ? `${running} 个协作助理正在处理`
        : `${children.length} 个协作助理已完成本轮工作`;

  return (
    <Card
      className='agent-preview-canvas agent-subagents-canvas h-full min-h-0 rounded-none border-0'
      size='sm'
    >
      {showHeader ? (
        <CardHeader className='agent-preview-header shrink-0 border-b px-4'>
          <div className='agent-preview-heading'>
            <CardTitle className='flex items-center gap-2 text-sm'>
              <BotIcon className='size-4 text-primary' aria-hidden='true' />
              协作任务
            </CardTitle>
            <CardDescription className='text-[11px]'>{summary}</CardDescription>
          </div>
          <Button
            type='button'
            variant='ghost'
            size='icon-sm'
            className='agent-preview-close'
            aria-label='关闭协作任务'
            title='关闭协作任务'
            onClick={onClose}
          >
            <XIcon aria-hidden='true' />
          </Button>
        </CardHeader>
      ) : null}
      <ScrollArea className='min-h-0 flex-1'>
        <CardContent className='p-4'>
          {isLoading && children.length === 0 ? (
            <div className='flex flex-col gap-3' aria-busy='true' role='status'>
              <Skeleton className='h-12 w-full' />
              <Skeleton className='h-12 w-full' />
            </div>
          ) : children.length > 0 ? (
            <ItemGroup className='gap-2'>
              {children.map((child) => (
                <Item key={child.id} size='sm' variant='muted' className='items-start'>
                  <ItemMedia variant='icon'>
                    <StatusIcon status={child.status} />
                  </ItemMedia>
                  <ItemContent className='min-w-0'>
                    <ItemTitle>{profileLabel(child.profile)}</ItemTitle>
                    <p className='line-clamp-2 text-left text-xs leading-5 text-muted-foreground'>
                      {child.latest_event_summary || '正在处理当前对话分配的任务。'}
                    </p>
                  </ItemContent>
                  <Badge className='shrink-0' variant={statusVariant(child.status)}>
                    {statusLabel(child.status)}
                  </Badge>
                </Item>
              ))}
            </ItemGroup>
          ) : (
            <Empty className='min-h-56 border-0 px-2 py-8'>
              <EmptyHeader>
                <EmptyMedia variant='icon'>
                  <BotIcon aria-hidden='true' />
                </EmptyMedia>
                <EmptyTitle>当前没有协作任务</EmptyTitle>
                <EmptyDescription>
                  当 Copilot 需要并行核对资料时，协作进度会显示在这里。
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
          {hasError ? (
            <p className='mt-3 text-xs text-destructive' role='alert'>
              协作进度暂时无法更新，请稍后再看。
            </p>
          ) : null}
        </CardContent>
      </ScrollArea>
    </Card>
  );
}
