import { Skeleton } from '@/components/ui/skeleton';

export default function Loading() {
  return (
    <div
      className='flex min-h-svh items-center justify-center p-6'
      role='status'
      aria-label='正在加载页面'
    >
      <div className='flex w-full max-w-md flex-col gap-3'>
        <Skeleton className='h-8 w-40' />
        <Skeleton className='h-4 w-64' />
        <Skeleton className='h-24 w-full rounded-xl' />
      </div>
    </div>
  );
}
