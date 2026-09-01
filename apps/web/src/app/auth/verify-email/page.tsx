'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { buttonVariants } from '@/components/ui/button';
import { BrandLogo } from '@/components/brand';

export default function VerifyEmailPage() {
  const params = useSearchParams();
  const [state, setState] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('正在验证邮箱…');

  useEffect(() => {
    const token = params.get('token');
    if (!token) {
      setState('error');
      setMessage('验证链接无效或已过期。');
      return;
    }
    void fetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`, { method: 'POST' })
      .then(async (response) => {
        const body = (await response.json().catch(() => ({}))) as {
          message?: string;
          detail?: string;
        };
        if (!response.ok) throw new Error(body.message || body.detail || '邮箱验证失败。');
        setState('success');
        setMessage(body.message || '邮箱验证成功。');
        window.setTimeout(() => window.location.assign('/dashboard'), 1200);
      })
      .catch((cause) => {
        setState('error');
        setMessage(cause instanceof Error ? cause.message : '邮箱验证失败。');
      });
  }, [params]);

  return (
    <main className='bg-muted/20 flex min-h-svh items-center justify-center px-5 py-10'>
      <div className='w-full max-w-md'>
        <div className='mb-8 flex justify-center'>
          <Link href='/' aria-label='BidPilot 首页'>
            <BrandLogo />
          </Link>
        </div>
        <div className='bg-card rounded-xl border p-6 shadow-sm sm:p-8'>
          <Alert variant={state === 'error' ? 'destructive' : undefined}>
            <AlertTitle>
              {state === 'loading' ? '正在验证' : state === 'success' ? '验证成功' : '无法验证'}
            </AlertTitle>
            <AlertDescription>{message}</AlertDescription>
          </Alert>
          <div className='mt-6 flex justify-center'>
            {state === 'success' ? (
              <Link className={buttonVariants()} href='/dashboard'>
                进入工作台
              </Link>
            ) : (
              <Link className={buttonVariants({ variant: 'outline' })} href='/auth/sign-in'>
                返回登录
              </Link>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
