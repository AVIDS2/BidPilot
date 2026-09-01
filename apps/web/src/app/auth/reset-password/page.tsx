'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { buttonVariants, Button } from '@/components/ui/button';
import { BrandLogo } from '@/components/brand';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';

export default function ResetPasswordPage() {
  const params = useSearchParams();
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    setError(null);
    if (!token) return setError('重置链接无效或已过期。');
    if (password !== confirmation) return setError('两次输入的密码不一致。');
    setPending(true);
    try {
      const response = await fetch('/api/bidpilot/auth/password-reset/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password })
      });
      const body = (await response.json().catch(() => ({}))) as {
        message?: string;
        detail?: string;
      };
      if (!response.ok) throw new Error(body.message || body.detail || '密码重置失败。');
      setMessage(body.message || '密码已重置，请重新登录。');
      setPassword('');
      setConfirmation('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '密码重置失败。');
    } finally {
      setPending(false);
    }
  };
  return (
    <main className='bg-muted/20 flex min-h-svh items-center justify-center px-5 py-10'>
      <div className='w-full max-w-md'>
        <div className='mb-8 flex justify-center'>
          <Link href='/' aria-label='BidPilot 首页'>
            <BrandLogo />
          </Link>
        </div>
        <div className='bg-card rounded-xl border p-6 shadow-sm sm:p-8'>
          <h1 className='text-2xl font-semibold tracking-tight'>设置新密码</h1>
          <p className='text-muted-foreground mt-2 text-sm'>设置完成后使用新密码登录。</p>
          {(error || message) && (
            <Alert className='mt-5' variant={error ? 'destructive' : undefined}>
              <AlertTitle>{error ? '无法保存' : '已完成'}</AlertTitle>
              <AlertDescription>{error || message}</AlertDescription>
            </Alert>
          )}
          <form className='mt-6 space-y-5' onSubmit={submit}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor='new-password'>新密码</FieldLabel>
                <Input
                  id='new-password'
                  type='password'
                  autoComplete='new-password'
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={8}
                  required
                />
                <FieldDescription>至少 8 位。</FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor='confirm-password'>确认新密码</FieldLabel>
                <Input
                  id='confirm-password'
                  type='password'
                  autoComplete='new-password'
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  minLength={8}
                  required
                />
              </Field>
            </FieldGroup>
            <Button className='w-full' type='submit' disabled={pending || !token}>
              {pending ? '保存中…' : '保存新密码'}
            </Button>
          </form>
          <div className='mt-6 flex justify-center'>
            <Link className={buttonVariants({ variant: 'link' })} href='/auth/sign-in'>
              返回登录
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
