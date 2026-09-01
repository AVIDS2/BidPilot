'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, UsersRound } from 'lucide-react';
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
import { createTeam, listTeams } from '@/lib/bidpilot-api';

export default function AdminTeamsPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['teams'], queryFn: listTeams });
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const create = useMutation({
    mutationFn: createTeam,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['teams'] });
      setOpen(false);
      setName('');
    }
  });
  const teams = query.data?.items ?? [];
  return (
    <>
      <PageHeader
        eyebrow='管理'
        title='团队'
        description='按团队组织成员和审核协作范围。'
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus data-icon='inline-start' />
            新建团队
          </Button>
        }
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {query.isPending ? (
          <QuerySkeleton rows={4} />
        ) : query.error ? (
          <QueryError message={query.error instanceof Error ? query.error.message : undefined} />
        ) : !teams.length ? (
          <EmptyState title='还没有团队' description='创建团队后，可以继续在项目中分配成员。' />
        ) : (
          <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-3'>
            {teams.map((team) => (
              <Card key={team.id}>
                <CardHeader className='flex flex-row items-start gap-3'>
                  <span className='bg-primary/10 text-primary flex size-9 items-center justify-center rounded-lg'>
                    <UsersRound className='size-4' />
                  </span>
                  <div className='min-w-0'>
                    <h2 className='truncate font-medium'>{team.name}</h2>
                    <p className='text-muted-foreground mt-1 truncate text-xs'>{team.slug}</p>
                  </div>
                </CardHeader>
                <CardContent>
                  <Badge variant='outline'>{team.members?.length ?? 0} 位成员</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建团队</DialogTitle>
            <DialogDescription>团队名称和 slug 会发送给 FastAPI 创建接口。</DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const value = name.trim();
              if (value)
                create.mutate({
                  name: value,
                  slug: value
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, '-')
                    .replace(/^-|-$/g, '')
                });
            }}
          >
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor='team-name'>团队名称</FieldLabel>
                <Input
                  id='team-name'
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                />
              </Field>
            </FieldGroup>
            <DialogFooter>
              <Button type='button' variant='outline' onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button type='submit' disabled={create.isPending || !name.trim()}>
                创建团队
              </Button>
            </DialogFooter>
            {create.error && (
              <p className='text-destructive text-sm' role='alert'>
                {create.error instanceof Error ? create.error.message : '创建失败'}
              </p>
            )}
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
