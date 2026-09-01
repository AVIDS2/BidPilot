'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useMutation, useQuery, type UseQueryResult } from '@tanstack/react-query';
import { Check, CreditCard, LockKeyhole, UserRound } from 'lucide-react';
import { useAuth, type CurrentUser } from '@/lib/auth';
import { PageHeader } from '@/components/bidpilot/page-header';
import { QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { buttonVariants, Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { getBillingSummary, updateCurrentUser } from '@/lib/bidpilot-api';

type BillingData = Awaited<ReturnType<typeof getBillingSummary>>;

export default function AccountPage() {
  const { user, refresh } = useAuth();
  const billing = useQuery({
    queryKey: ['billing-summary'],
    queryFn: getBillingSummary,
    enabled: Boolean(user)
  });
  if (!user) {
    return (
      <>
        <PageHeader title='账户' />
        <div className='p-5 lg:p-8'>
          <QuerySkeleton rows={3} />
        </div>
      </>
    );
  }
  return (
    <>
      <PageHeader
        eyebrow='管理'
        title='账户'
        description='管理个人资料、登录安全和当前工作区权益。'
      />
      <div className='grid flex-1 gap-6 px-5 py-6 lg:grid-cols-[1.1fr_0.9fr] lg:px-8'>
        <AccountProfile key={user.id} user={user} refresh={refresh} />
        <div className='grid content-start gap-6'>
          <BillingCard query={billing} />
          <Card>
            <CardHeader className='border-b'>
              <div className='flex items-center gap-2'>
                <LockKeyhole className='text-primary size-4' />
                <h2 className='font-medium'>登录安全</h2>
              </div>
            </CardHeader>
            <CardContent className='p-5'>
              <p className='text-muted-foreground text-sm leading-6'>
                访问令牌只保存在 HttpOnly cookie 中，浏览器端不会读取或持久化 bearer token。
              </p>
              <Link
                className={buttonVariants({ variant: 'outline', className: 'mt-4' })}
                href='/auth/forgot-password'
              >
                重置密码
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

function AccountProfile({
  user,
  refresh
}: {
  user: CurrentUser;
  refresh: () => Promise<CurrentUser | null>;
}) {
  const [displayName, setDisplayName] = useState(user.display_name);
  const [message, setMessage] = useState<string | null>(null);
  const update = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: async () => {
      await refresh();
      setMessage('账户资料已更新。');
    }
  });
  return (
    <Card>
      <CardHeader className='border-b'>
        <div className='flex items-center gap-2'>
          <UserRound className='text-primary size-4' />
          <h2 className='font-medium'>个人资料</h2>
        </div>
        <p className='text-muted-foreground mt-1 text-sm'>这些信息会出现在团队协作和审核记录中。</p>
      </CardHeader>
      <CardContent className='p-5'>
        {message && (
          <Alert className='mb-5'>
            <Check className='size-4' />
            <AlertTitle>已保存</AlertTitle>
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        )}
        <form
          className='space-y-5'
          onSubmit={(event) => {
            event.preventDefault();
            setMessage(null);
            update.mutate({ display_name: displayName.trim() });
          }}
        >
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor='account-name'>姓名或团队称呼</FieldLabel>
              <Input
                id='account-name'
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                required
                minLength={2}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor='account-email'>邮箱</FieldLabel>
              <Input id='account-email' value={user.email} readOnly />
              <FieldDescription>邮箱由认证系统管理。</FieldDescription>
            </Field>
          </FieldGroup>
          <Button type='submit' disabled={update.isPending || displayName.trim().length < 2}>
            {update.isPending ? '保存中…' : '保存资料'}
          </Button>
          {update.error && (
            <p className='text-destructive text-sm' role='alert'>
              {update.error instanceof Error ? update.error.message : '保存失败'}
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  );
}

function BillingCard({ query }: { query: UseQueryResult<BillingData> }) {
  return (
    <Card>
      <CardHeader className='border-b'>
        <div className='flex items-center gap-2'>
          <CreditCard className='text-primary size-4' />
          <h2 className='font-medium'>当前计划</h2>
        </div>
      </CardHeader>
      <CardContent className='p-5'>
        {query.isPending ? (
          <QuerySkeleton rows={2} />
        ) : query.error ? (
          <QueryError message={query.error instanceof Error ? query.error.message : undefined} />
        ) : query.data?.data ? (
          <div className='space-y-4'>
            <div className='flex items-center justify-between'>
              <span className='text-muted-foreground text-sm'>计划</span>
              <Badge variant='secondary'>{query.data.data.plan}</Badge>
            </div>
            <div className='flex items-center justify-between'>
              <span className='text-muted-foreground text-sm'>状态</span>
              <span className='text-sm'>{query.data.data.status}</span>
            </div>
            <div className='grid grid-cols-2 gap-3'>
              <Quota
                label='助手次数'
                value={query.data.data.monthly_assistant_used}
                limit={query.data.data.monthly_assistant_limit}
              />
              <Quota
                label='工作流次数'
                value={query.data.data.monthly_workflow_used}
                limit={query.data.data.monthly_workflow_limit}
              />
            </div>
          </div>
        ) : (
          <p className='text-muted-foreground text-sm'>暂无计划信息。</p>
        )}
      </CardContent>
    </Card>
  );
}

function Quota({ label, value, limit }: { label: string; value: number; limit: number }) {
  return (
    <div className='bg-muted/40 rounded-lg p-3'>
      <p className='text-muted-foreground text-xs'>{label}</p>
      <p className='mt-1 text-base font-semibold'>
        {value} <span className='text-muted-foreground text-xs font-normal'>/ {limit}</span>
      </p>
    </div>
  );
}
