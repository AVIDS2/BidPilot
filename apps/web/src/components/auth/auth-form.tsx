'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
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
import { AuthSplitLayout } from './auth-split-layout';

export function AuthForm({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const searchParams = useSearchParams();
  const { login, register } = useAuth();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [invitationToken, setInvitationToken] = useState('');
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
        const nextPath = searchParams.get('next') || '/dashboard';
        window.location.assign(nextPath);
        return;
      }

      await register({
        email: email.trim(),
        display_name: displayName.trim(),
        password,
        invitation_token: invitationToken.trim() || null
      });
      setSuccess('账户已创建。请检查邮箱完成验证，然后登录。');
      setPassword('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '操作失败，请稍后重试。');
    } finally {
      setIsPending(false);
    }
  };

  return (
    <AuthSplitLayout mode={mode}>
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
      <form className='w-full' onSubmit={submit}>
        <FieldSet>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor='email'>邮箱地址</FieldLabel>
              <Input
                id='email'
                type='email'
                autoComplete='email'
                placeholder='name@example.com'
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={isPending}
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
                placeholder='至少 8 位'
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={isPending}
                minLength={8}
                required
              />
              {!isSignIn && <FieldDescription>建议同时包含字母和数字。</FieldDescription>}
            </Field>
            {!isSignIn && (
              <>
                <Field>
                  <FieldLabel htmlFor='display-name'>你的称呼</FieldLabel>
                  <Input
                    id='display-name'
                    autoComplete='name'
                    placeholder='例如：投标负责人'
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    disabled={isPending}
                    minLength={2}
                    required
                  />
                  <FieldDescription>用于团队协作和审核记录。</FieldDescription>
                </Field>
                <Field>
                  <FieldLabel htmlFor='invitation-token'>邀请码（可选）</FieldLabel>
                  <Input
                    id='invitation-token'
                    autoComplete='off'
                    placeholder='已有工作区邀请时填写'
                    value={invitationToken}
                    onChange={(event) => setInvitationToken(event.target.value)}
                    disabled={isPending}
                  />
                </Field>
              </>
            )}
            {error && <FieldError>{error}</FieldError>}
          </FieldGroup>
        </FieldSet>
        <Button className='mt-6 w-full' size='lg' type='submit' disabled={isPending}>
          {isPending && <Spinner data-icon='inline-start' />}
          {isSignIn ? '进入工作台' : '创建账户'}
        </Button>
      </form>
      <p className='text-muted-foreground mt-8 text-center text-xs leading-5'>
        继续操作即表示你同意使用条款和隐私政策。
      </p>
    </AuthSplitLayout>
  );
}
