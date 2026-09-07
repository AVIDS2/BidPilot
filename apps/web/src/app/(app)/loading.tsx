import { Skeleton } from '@/components/ui/skeleton';

export default function AuthenticatedLoading() {
  return (
    <div
      className='flex min-h-0 flex-1 flex-col gap-6 px-5 py-6 lg:px-8'
      role='status'
      aria-label='正在加载页面'
    >
      <div className='flex flex-col gap-3'>
        <Skeleton className='h-4 w-24' />
        <Skeleton className='h-9 w-48' />
        <Skeleton className='h-4 w-full max-w-xl' />
      </div>
      <div className='grid min-h-0 flex-1 gap-5 lg:grid-cols-2'>
        <Skeleton className='min-h-56 w-full rounded-xl' />
        <Skeleton className='min-h-56 w-full rounded-xl' />
      </div>
    </div>
  );
}
