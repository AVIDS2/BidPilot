'use client';

import { useQuery } from '@tanstack/react-query';
import { Mail, Shield, Users } from 'lucide-react';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { listOrganizationMembers } from '@/lib/bidpilot-api';

export default function MembersPage() {
  const query = useQuery({ queryKey: ['organization-members'], queryFn: listOrganizationMembers });
  return (
    <>
      <PageHeader
        eyebrow='工作区'
        title='团队成员'
        description='查看当前工作区中的成员、角色和审核责任。'
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {query.isPending ? (
          <QuerySkeleton rows={5} />
        ) : query.error ? (
          <QueryError message={query.error instanceof Error ? query.error.message : undefined} />
        ) : !query.data?.length ? (
          <EmptyState title='还没有团队成员' description='当前工作区暂时没有可显示的成员。' />
        ) : (
          <Card>
            <CardHeader className='border-b'>
              <div className='flex items-center gap-2'>
                <Users className='text-primary size-4' />
                <h2 className='font-medium'>工作区成员</h2>
              </div>
              <p className='text-muted-foreground mt-1 text-sm'>{query.data.length} 位成员</p>
            </CardHeader>
            <CardContent className='p-0'>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>成员</TableHead>
                    <TableHead>角色</TableHead>
                    <TableHead>账单权限</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.map((member) => (
                    <TableRow key={member.id}>
                      <TableCell>
                        <div className='flex min-w-0 items-center gap-3'>
                          <span className='bg-muted flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-medium'>
                            {member.display_name.slice(0, 1).toUpperCase()}
                          </span>
                          <span className='min-w-0'>
                            <span className='block truncate font-medium'>
                              {member.display_name}
                            </span>
                            <span className='text-muted-foreground mt-1 flex items-center gap-1 text-xs'>
                              <Mail className='size-3' />
                              {member.email}
                            </span>
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant='outline'>
                          <Shield className='size-3' />
                          {member.role}
                        </Badge>
                      </TableCell>
                      <TableCell className='text-muted-foreground'>
                        {member.is_billing_owner ? '账单负责人' : '—'}
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
