import { IconRadar, IconRefresh } from '@tabler/icons-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

function formatSyncTime(value: number) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(new Date(value));
}

export function LiveSyncStatus({
  active = true,
  dataUpdatedAt = 0,
  isFetching,
  intervalLabel = '自动检查',
  onRefresh
}: {
  active?: boolean;
  dataUpdatedAt?: number;
  isFetching: boolean;
  intervalLabel?: string;
  onRefresh?: () => void;
}) {
  const label = isFetching ? '正在同步' : active ? '自动更新' : '等待数据';
  const detail = dataUpdatedAt
    ? `最近更新 ${formatSyncTime(dataUpdatedAt)} · ${intervalLabel}`
    : `等待首次同步 · ${intervalLabel}`;

  return (
    <div
      aria-live='polite'
      className='flex min-w-0 items-center gap-2'
      data-testid='live-sync-status'
    >
      <Badge className='gap-1.5' variant='outline'>
        <span
          aria-hidden='true'
          className={cn(
            'relative flex size-1.5 shrink-0',
            active && !isFetching && 'motion-safe:animate-pulse'
          )}
        >
          <span
            className={cn(
              'absolute inset-0 rounded-full',
              active ? 'bg-primary' : 'bg-muted-foreground'
            )}
          />
        </span>
        {label}
      </Badge>
      <span className='text-muted-foreground hidden text-xs sm:inline'>{detail}</span>
      {onRefresh ? (
        <Button
          aria-label='立即刷新数据'
          disabled={isFetching}
          onClick={onRefresh}
          size='icon-sm'
          title='立即刷新数据'
          type='button'
          variant='ghost'
        >
          <IconRefresh className={cn(isFetching && 'motion-safe:animate-spin')} />
        </Button>
      ) : (
        <IconRadar
          aria-hidden='true'
          className={cn(
            'text-muted-foreground size-3.5 shrink-0 sm:hidden',
            isFetching && 'motion-safe:animate-spin'
          )}
        />
      )}
    </div>
  );
}
