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
  return (
    <Alert variant='destructive'>
      <AlertTitle>加载失败</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className='bg-muted/20 flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed px-6 text-center'>
      <h2 className='text-base font-medium'>{title}</h2>
      <p className='text-muted-foreground mt-2 max-w-md text-sm leading-6'>{description}</p>
    </div>
  );
}
