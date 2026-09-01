'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Skeleton } from '@/components/ui/skeleton';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { status } = useAuth();

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.replace(`/auth/sign-in?next=${encodeURIComponent(pathname)}`);
    }
  }, [pathname, router, status]);

  if (status === 'loading' || status === 'unauthenticated') {
    return (
      <div className='flex min-h-svh items-center justify-center p-6'>
        <Skeleton className='h-8 w-40' />
      </div>
    );
  }

  return <>{children}</>;
}
