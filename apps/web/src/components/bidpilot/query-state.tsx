import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';

export function QuerySkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className='grid gap-3' aria-label='正在加载' role='status'>
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton className='h-16 w-full rounded-lg' key={index} />
      ))}
    </div>
  );
}

export function QueryError({ message = '数据暂时无法加载，请稍后重试。' }: { message?: string }) {
  const safeMessage = getSafeQueryMessage(message);
  return (
    <Alert variant='destructive'>
      <AlertTitle>加载失败</AlertTitle>
      <AlertDescription>{safeMessage}</AlertDescription>
    </Alert>
  );
}

function getSafeQueryMessage(message: string) {
  const normalized = message.replace(/^API\s+\d{3}:\s*/i, '').trim();
  if (/\b403\b|admin role|permission|forbidden|无权|权限/i.test(message)) {
    return '当前账户没有访问这项工作区能力的权限。';
  }
  if (/\b5\d{2}\b|failed to fetch|network|backend unavailable|服务暂时不可用/i.test(message)) {
    return '服务暂时无法读取，请稍后重试。';
  }
  return normalized || '数据暂时无法加载，请稍后重试。';
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className='bg-muted/20 flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed px-6 text-center'>
      <h2 className='text-base font-medium'>{title}</h2>
      <p className='text-muted-foreground mt-2 max-w-md text-sm leading-6'>{description}</p>
    </div>
  );
}
