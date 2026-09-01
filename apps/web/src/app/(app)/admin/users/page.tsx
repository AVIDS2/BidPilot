'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Shield, UserCheck, UserRound } from 'lucide-react';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { listUsers, setUserStatus, updateUserRole } from '@/lib/bidpilot-api';

export default function AdminUsersPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['admin-users'], queryFn: () => listUsers(1, 100) });
  const status = useMutation({
    mutationFn: ({ id, disabled }: { id: string; disabled: boolean }) =>
      setUserStatus(id, disabled),
    onSuccess: () => client.invalidateQueries({ queryKey: ['admin-users'] })
  });
  const role = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => updateUserRole(id, value),
    onSuccess: () => client.invalidateQueries({ queryKey: ['admin-users'] })
  });
  const users = query.data?.items ?? [];
  return (
    <>
      <PageHeader
        eyebrow='管理'
        title='用户管理'
        description='仅管理员可查看和调整账户状态；最终权限仍由 FastAPI 校验。'
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {query.isPending ? (
          <QuerySkeleton rows={6} />
        ) : query.error ? (
          <QueryError message={query.error instanceof Error ? query.error.message : undefined} />
        ) : !users.length ? (
          <EmptyState title='没有用户' description='当前接口没有返回可管理的用户。' />
        ) : (
          <Card>
            <CardContent className='p-0'>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>用户</TableHead>
                    <TableHead>角色</TableHead>
                    <TableHead>邮箱验证</TableHead>
                    <TableHead>账户状态</TableHead>
                    <TableHead className='text-right'>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className='flex items-center gap-3'>
                          <span className='bg-muted flex size-8 items-center justify-center rounded-full'>
                            <UserRound className='size-4' />
                          </span>
                          <span className='min-w-0'>
                            <span className='block truncate font-medium'>{user.display_name}</span>
                            <span className='text-muted-foreground mt-1 block truncate text-xs'>
                              {user.email}
                            </span>
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant='outline'>
                          <Shield className='size-3' />
                          {user.role}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {user.email_verified ? (
                          <Badge variant='secondary'>
                            <UserCheck className='size-3' />
                            已验证
                          </Badge>
                        ) : (
                          <Badge variant='outline'>待验证</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {user.disabled ? (
                          <Badge variant='destructive'>已停用</Badge>
                        ) : (
                          <Badge variant='secondary'>正常</Badge>
                        )}
                      </TableCell>
                      <TableCell className='space-x-1 text-right'>
                        <Button
                          size='sm'
                          variant='ghost'
                          disabled={status.isPending}
                          onClick={() => status.mutate({ id: user.id, disabled: !user.disabled })}
                        >
                          {user.disabled ? '启用' : '停用'}
                        </Button>
                        {user.role !== 'admin' && (
                          <Button
                            size='sm'
                            variant='ghost'
                            disabled={role.isPending}
                            onClick={() => role.mutate({ id: user.id, value: 'admin' })}
                          >
                            设为管理员
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  );
}
