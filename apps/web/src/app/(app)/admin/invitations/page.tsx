'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Mail, Plus, X } from 'lucide-react';
import { useState } from 'react';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { createInvitation, listInvitations, revokeInvitation } from '@/lib/bidpilot-api';

export default function InvitationsPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['invitations'], queryFn: listInvitations });
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const create = useMutation({
    mutationFn: createInvitation,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['invitations'] });
      setOpen(false);
      setEmail('');
    }
  });
  const revoke = useMutation({
    mutationFn: revokeInvitation,
    onSuccess: () => client.invalidateQueries({ queryKey: ['invitations'] })
  });
  return (
    <>
      <PageHeader
        eyebrow='管理'
        title='邀请'
        description='邀请成员加入当前工作区，状态会在这里持续更新。'
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus data-icon='inline-start' />
            发出邀请
          </Button>
        }
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {query.isPending ? (
          <QuerySkeleton rows={4} />
        ) : query.error ? (
          <QueryError message={query.error instanceof Error ? query.error.message : undefined} />
        ) : !query.data?.length ? (
          <EmptyState title='没有待处理邀请' description='发出邀请后，邀请状态会显示在这里。' />
        ) : (
          <Card>
            <CardHeader className='border-b'>
              <h2 className='font-medium'>邀请记录</h2>
            </CardHeader>
            <CardContent className='divide-y p-0'>
              {query.data.map((invitation) => (
                <div className='flex items-center gap-4 px-5 py-4' key={invitation.id}>
                  <span className='bg-muted flex size-8 items-center justify-center rounded-lg'>
                    <Mail className='size-4' />
                  </span>
                  <span className='min-w-0 flex-1'>
                    <span className='block truncate text-sm font-medium'>{invitation.email}</span>
                    <span className='text-muted-foreground mt-1 block text-xs'>
                      {invitation.created_at ? formatDate(invitation.created_at) : '—'}
                    </span>
                  </span>
                  <Badge variant='outline'>{invitation.status}</Badge>
                  <Button
                    size='icon-sm'
                    variant='ghost'
                    aria-label={`撤销 ${invitation.email}`}
                    title='撤销邀请'
                    onClick={() => revoke.mutate(invitation.id)}
                    disabled={revoke.isPending}
                  >
                    <X className='size-4' />
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>邀请成员</DialogTitle>
            <DialogDescription>邀请邮件由后端发送和记录。</DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (email.trim()) create.mutate({ email: email.trim() });
            }}
          >
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor='invitation-email'>邮箱</FieldLabel>
                <Input
                  id='invitation-email'
                  type='email'
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </Field>
            </FieldGroup>
            <DialogFooter>
              <Button type='button' variant='outline' onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button type='submit' disabled={create.isPending || !email.trim()}>
                发送邀请
              </Button>
            </DialogFooter>
            {create.error && (
              <p className='text-destructive text-sm' role='alert'>
                {create.error instanceof Error ? create.error.message : '发送失败'}
              </p>
            )}
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium' }).format(new Date(value));
}
