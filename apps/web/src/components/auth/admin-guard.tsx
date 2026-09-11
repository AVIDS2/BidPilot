'use client';

import Link from 'next/link';
import { ShieldX } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { buttonVariants } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const { status, user } = useAuth();

  if (status === 'loading') {
    return (
      <div className='flex flex-1 items-start justify-center p-6 lg:p-8'>
        <Skeleton className='h-32 w-full max-w-2xl rounded-xl' />
      </div>
    );
  }

  if (user?.role !== 'admin') {
    return (
      <div className='flex flex-1 items-start justify-center p-6 lg:p-8'>
        <Alert className='max-w-2xl'>
          <ShieldX />
          <AlertTitle>这是管理员区域</AlertTitle>
          <AlertDescription className='flex flex-wrap items-center gap-3'>
            当前账户只能访问自己的工作区数据和操作。管理员诊断、用户、团队和业务通知
            控制不会展示给普通成员。
            <Link className={buttonVariants({ variant: 'outline', size: 'sm' })} href='/dashboard'>
              返回工作台
            </Link>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return <>{children}</>;
}
