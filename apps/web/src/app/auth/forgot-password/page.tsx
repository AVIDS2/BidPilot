'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { BrandLogo } from '@/components/brand';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPending(true);
    setMessage(null);
    try {
      const response = await fetch('/api/bidpilot/auth/password-reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), turnstile_token: null })
      });
      if (!response.ok) throw new Error('无法提交，请稍后重试。');
      setMessage('如果该邮箱已注册，重置链接会发送到你的邮箱。');
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : '无法提交，请稍后重试。');
    } finally {
      setPending(false);
    }
  };
  return (
    <main className='bg-muted/20 flex min-h-svh items-center justify-center px-5 py-10'>
      <div className='w-full max-w-md'>
        <div className='mb-8 flex justify-center'>
          <Link href='/'>
            <BrandLogo />
          </Link>
        </div>
        <div className='bg-card rounded-xl border p-6 shadow-sm sm:p-8'>
          <h1 className='text-2xl font-semibold tracking-tight'>重置密码</h1>
          <p className='text-muted-foreground mt-2 text-sm'>输入账户邮箱，我们会发送下一步说明。</p>
          {message && (
            <Alert className='mt-5'>
              <AlertTitle>已提交</AlertTitle>
              <AlertDescription>{message}</AlertDescription>
            </Alert>
          )}
          <form className='mt-6 space-y-5' onSubmit={submit}>
            <Field>
              <FieldLabel htmlFor='reset-email'>邮箱</FieldLabel>
              <Input
                id='reset-email'
                type='email'
                autoComplete='email'
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
              <FieldDescription>不会显示账户是否存在。</FieldDescription>
            </Field>
            <Button className='w-full' size='lg' type='submit' disabled={pending}>
              {pending && <Spinner data-icon='inline-start' />}发送重置说明
            </Button>
          </form>
          <p className='text-muted-foreground mt-6 text-center text-sm'>
            <Link className='text-primary underline-offset-4 hover:underline' href='/auth/sign-in'>
              返回登录
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
