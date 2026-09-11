'use client';

import Link from 'next/link';
import { ArrowUpRight, BookOpen, BrainCircuit, Search, Sparkles } from 'lucide-react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { LiveSyncStatus } from '@/components/bidpilot/live-sync-status';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ProjectPicker } from '@/components/bidpilot/project-picker';
import { useProjectSelection } from '@/hooks/use-project-selection';
import {
  listKnowledgePortfolio,
  listProjects,
  searchKnowledge,
  startMemoryCompilation
} from '@/lib/bidpilot-api';
import { toast } from 'sonner';

export default function KnowledgePage() {
  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const portfolio = useQuery({
    queryKey: ['knowledge-portfolio'],
    queryFn: () => listKnowledgePortfolio(50),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const {
    projectId,
    onChange: setProjectId,
    hasExplicitSelection
  } = useProjectSelection(projects.data);
  const [searchText, setSearchText] = useState('');
  const searchQuery = useQuery({
    queryKey: ['knowledge-search', projectId, searchText.trim()],
    queryFn: () => searchKnowledge({ project_id: projectId, query: searchText.trim(), top_k: 8 }),
    enabled: Boolean(projectId && searchText.trim().length >= 2),
    staleTime: 10_000,
    retry: false
  });
  const compileMutation = useMutation({
    mutationFn: () => startMemoryCompilation({ project_id: projectId }),
    onSuccess: () => {
      void portfolio.refetch();
      toast.success('知识库正在更新，完成后会显示在这里。');
    },
    onError: () => toast.error('项目记忆暂时无法编译，请先确认资料已经处理完成。')
  });
  const visiblePortfolio = hasExplicitSelection
    ? portfolio.data?.filter((item) => item.project_id === projectId)
    : portfolio.data;
  return (
    <>
      <PageHeader
        eyebrow='投标工作流'
        title='知识库'
        description='按项目检索已处理的资料、共享记忆和可追溯来源。'
        action={
          <div className='flex flex-wrap items-center justify-end gap-2'>
            <LiveSyncStatus
              active={Boolean(portfolio.data)}
              dataUpdatedAt={portfolio.dataUpdatedAt}
              intervalLabel='每 30 秒'
              isFetching={portfolio.isFetching || projects.isFetching}
              onRefresh={() => void Promise.all([portfolio.refetch(), projects.refetch()])}
            />
            {projects.data?.length ? (
              <ProjectPicker projects={projects.data} value={projectId} onChange={setProjectId} />
            ) : null}
          </div>
        }
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {projects.isPending || portfolio.isPending ? (
          <QuerySkeleton rows={5} />
        ) : projects.error || portfolio.error ? (
          <QueryError
            message={
              (projects.error || portfolio.error) instanceof Error
                ? (projects.error || portfolio.error)?.message
                : undefined
            }
          />
        ) : projects.data?.length ? (
          <>
            {projectId ? (
              <Card>
                <CardHeader className='gap-3 border-b sm:flex-row sm:items-start sm:justify-between'>
                  <div>
                    <CardTitle>检索项目知识</CardTitle>
                    <CardDescription>
                      从已解析的资料和已生效记忆中查找依据，不需要先打开 Agent。
                    </CardDescription>
                  </div>
                  <Button
                    disabled={compileMutation.isPending}
                    onClick={() => compileMutation.mutate()}
                    size='sm'
                    variant='outline'
                  >
                    <Sparkles data-icon='inline-start' />
                    生成知识建议
                  </Button>
                </CardHeader>
                <CardContent className='flex flex-col gap-4 p-5'>
                  <div className='relative max-w-2xl'>
                    <Search className='text-muted-foreground pointer-events-none absolute top-1/2 left-3 -translate-y-1/2' />
                    <Input
                      aria-label='检索项目知识'
                      className='pl-9'
                      onChange={(event) => setSearchText(event.target.value)}
                      placeholder='例如：项目团队有哪些医疗设备维保案例？'
                      value={searchText}
                    />
                  </div>
                  {searchText.trim().length < 2 ? (
                    <p className='text-muted-foreground text-sm'>
                      输入至少两个字，查看带来源的检索结果。
                    </p>
                  ) : searchQuery.isPending ? (
                    <QuerySkeleton rows={3} />
                  ) : searchQuery.error ? (
                    <QueryError message='知识检索暂时不可用，请确认项目资料已经建立索引。' />
                  ) : searchQuery.data?.length ? (
                    <div className='flex flex-col gap-3'>
                      {searchQuery.data.map((result) => (
                        <div className='bg-muted/30 rounded-lg p-4' key={result.chunk_id}>
                          <div className='flex items-start gap-3'>
                            <BookOpen className='text-primary mt-0.5 shrink-0' />
                            <div className='min-w-0'>
                              <p className='text-sm leading-6'>{result.content}</p>
                              <p className='text-muted-foreground mt-2 text-xs'>
                                来源文档 {result.source_document_id.slice(0, 8)}… · 匹配度{' '}
                                {Math.round(result.score * 100)}%
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <EmptyState
                      title='没有找到相关依据'
                      description='换一个问题，或先回到项目资料页确认文件已经完成解析和索引。'
                    />
                  )}
                </CardContent>
              </Card>
            ) : null}
            {visiblePortfolio?.length ? (
              <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-3'>
                {visiblePortfolio.map((item) => (
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
                        href={`/projects/${item.project_id}?tab=knowledge`}
                      >
                        打开项目 <ArrowUpRight data-icon='inline-end' />
                      </Link>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <EmptyState
                title='当前项目还没有共享知识'
                description='资料完成解析后，生成知识建议并审核，即可形成可检索的项目知识。'
              />
            )}
          </>
        ) : (
          <EmptyState
            title='还没有项目知识'
            description='项目资料被解析并形成共享知识后，会按项目显示在这里。'
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
