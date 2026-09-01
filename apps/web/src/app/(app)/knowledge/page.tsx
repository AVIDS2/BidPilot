'use client';

import Link from 'next/link';
import { ArrowUpRight, BookOpen, BrainCircuit } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { listKnowledgePortfolio } from '@/lib/bidpilot-api';

export default function KnowledgePage() {
  const query = useQuery({
    queryKey: ['knowledge-portfolio'],
    queryFn: () => listKnowledgePortfolio(50)
  });
  return (
    <>
      <PageHeader
        eyebrow='投标工作流'
        title='知识库'
        description='查看项目共享记忆、编译状态和可追溯的知识来源。'
        action={
          <Link className={buttonVariants({ variant: 'outline' })} href='/agent'>
            让助手检索 <ArrowUpRight data-icon='inline-end' />
          </Link>
        }
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {query.isPending ? (
          <QuerySkeleton rows={5} />
        ) : query.error ? (
          <QueryError message={query.error instanceof Error ? query.error.message : undefined} />
        ) : query.data?.length ? (
          <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-3'>
            {query.data.map((item) => (
              <Card key={item.project_id}>
                <CardHeader className='flex flex-row items-start gap-3'>
                  <div className='bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-lg'>
                    <BrainCircuit className='size-4' />
                  </div>
                  <div className='min-w-0'>
                    <h2 className='truncate font-medium'>{item.project_name}</h2>
                    <p className='text-muted-foreground mt-1 text-xs'>项目共享知识</p>
                  </div>
                </CardHeader>
                <CardContent className='space-y-4'>
                  <div className='grid grid-cols-2 gap-3'>
                    <Stat label='已生效' value={item.active_shared_count} />
                    <Stat label='待审核' value={item.proposed_shared_count ?? '—'} />
                  </div>
                  <div className='text-muted-foreground flex items-center gap-2 text-xs'>
                    <BookOpen className='size-3.5' />
                    {item.latest_compilation_status || '尚未编译'}
                    <span className='ml-auto'>{formatDate(item.latest_compilation_at)}</span>
                  </div>
                  <Link
                    className={buttonVariants({
                      className: 'w-full',
                      size: 'sm',
                      variant: 'outline'
                    })}
                    href={`/projects/${item.project_id}?tab=materials`}
                  >
                    打开项目 <ArrowUpRight data-icon='inline-end' />
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState
            title='还没有项目知识'
            description='项目资料被解析并形成共享记忆后，会按项目显示在这里。'
          />
        )}
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className='bg-muted/40 rounded-lg p-3'>
      <p className='text-muted-foreground text-xs'>{label}</p>
      <p className='mt-1 text-lg font-semibold tabular-nums'>{value}</p>
    </div>
  );
}
function formatDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric' }).format(new Date(value))
    : '—';
}
