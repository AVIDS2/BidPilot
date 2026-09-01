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
    if (status !== 'unauthenticated') return;
    // Let AuthProvider's current-path check settle before redirecting. During
    // a client transition the provider can briefly expose the previous
    // pathname's unauthenticated state even though the new cookie is valid.
    const timer = window.setTimeout(() => {
      router.replace(`/auth/sign-in?next=${encodeURIComponent(pathname)}`);
    }, 0);
    return () => window.clearTimeout(timer);
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
