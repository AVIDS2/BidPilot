'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldSet
} from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { BrandLogo } from '@/components/brand';

export function AuthForm({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, register } = useAuth();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(false);

  const isSignIn = mode === 'sign-in';
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setIsPending(true);
    try {
      if (isSignIn) {
        await login(email.trim(), password);
        router.replace(searchParams.get('next') || '/dashboard');
      } else {
        await register({ email: email.trim(), display_name: displayName.trim(), password });
        setSuccess('账户已创建。请检查邮箱完成验证，然后登录。');
        setPassword('');
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '操作失败，请稍后重试。');
    } finally {
      setIsPending(false);
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
          <div className='mb-7'>
            <h1 className='text-2xl font-semibold tracking-tight'>
              {isSignIn ? '登录 BidPilot' : '创建 BidPilot 工作区'}
            </h1>
            <p className='text-muted-foreground mt-2 text-sm'>
              {isSignIn
                ? '进入你的项目、知识库和 Agent 运行记录。'
                : '用一个真实工作区开始管理招标资料与响应任务。'}
            </p>
          </div>
          {error && (
            <Alert variant='destructive' className='mb-5'>
              <AlertTitle>无法继续</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {success && (
            <Alert className='mb-5'>
              <AlertTitle>注册成功</AlertTitle>
              <AlertDescription>{success}</AlertDescription>
            </Alert>
          )}
          <form onSubmit={submit}>
            <FieldSet>
              <FieldGroup>
                {!isSignIn && (
                  <Field>
                    <FieldLabel htmlFor='display-name'>姓名或团队称呼</FieldLabel>
                    <Input
                      id='display-name'
                      autoComplete='name'
                      value={displayName}
                      onChange={(event) => setDisplayName(event.target.value)}
                      required
                      minLength={2}
                    />
                    <FieldDescription>用于团队协作和审核记录。</FieldDescription>
                  </Field>
                )}
                <Field>
                  <FieldLabel htmlFor='email'>邮箱</FieldLabel>
                  <Input
                    id='email'
                    type='email'
                    autoComplete='email'
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                </Field>
                <Field>
                  <div className='flex items-center justify-between gap-3'>
                    <FieldLabel htmlFor='password'>密码</FieldLabel>
                    {isSignIn && (
                      <Link
                        className='text-primary text-xs underline-offset-4 hover:underline'
                        href='/auth/forgot-password'
                      >
                        忘记密码？
                      </Link>
                    )}
                  </div>
                  <Input
                    id='password'
                    type='password'
                    autoComplete={isSignIn ? 'current-password' : 'new-password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    minLength={8}
                  />
                  {!isSignIn && (
                    <FieldDescription>至少 8 位，建议同时包含字母和数字。</FieldDescription>
                  )}
                </Field>
                {error && <FieldError>{error}</FieldError>}
              </FieldGroup>
            </FieldSet>
            <Button className='mt-6 w-full' size='lg' type='submit' disabled={isPending}>
              {isPending && <Spinner data-icon='inline-start' />}
              {isSignIn ? '登录' : '创建账户'}
            </Button>
          </form>
          <p className='text-muted-foreground mt-6 text-center text-sm'>
            {isSignIn ? '还没有工作区？' : '已经有账户？'}{' '}
            <Link
              className='text-primary font-medium underline-offset-4 hover:underline'
              href={isSignIn ? '/auth/sign-up' : '/auth/sign-in'}
            >
              {isSignIn ? '立即创建' : '返回登录'}
            </Link>
          </p>
        </div>
        <p className='text-muted-foreground mt-6 text-center text-xs'>
          继续操作即表示你同意使用条款和隐私政策。
        </p>
      </div>
    </main>
  );
}
