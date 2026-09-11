'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, FileText, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { approveMemory, listProjectMemory, type MemoryRead } from '@/lib/bidpilot-api';

export function ProjectKnowledgePanel({ projectId }: { projectId: string }) {
  const client = useQueryClient();
  const knowledge = useQuery({
    queryKey: ['project-knowledge', projectId],
    queryFn: () => listProjectKnowledge(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const approve = useMutation({
    mutationFn: approveMemory,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['project-knowledge', projectId] });
      toast.success('项目知识已确认。');
    },
    onError: () => toast.error('这条知识暂时无法确认，请稍后重试。')
  });

  return (
    <Card>
      <CardHeader className='border-b'>
        <div className='flex items-start gap-3'>
          <div className='bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-lg'>
            <ShieldCheck />
          </div>
          <div>
            <h2 className='font-medium'>项目知识</h2>
            <p className='text-muted-foreground mt-1 text-sm leading-6'>
              只展示已经绑定来源的项目事实。待确认内容不会参与助手工作。
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className='p-0'>
        {knowledge.isPending ? (
          <div className='p-5'>
            <QuerySkeleton rows={4} />
          </div>
        ) : knowledge.error ? (
          <div className='p-5'>
            <QueryError message='项目知识暂时无法加载，请稍后重试。' />
          </div>
        ) : knowledge.data?.length ? (
          <div className='divide-y'>
            {knowledge.data.map((item) => (
              <KnowledgeItem
                item={item}
                key={item.id}
                onApprove={() => approve.mutate(item.id)}
                approving={approve.isPending && approve.variables === item.id}
              />
            ))}
          </div>
        ) : (
          <div className='p-5'>
            <EmptyState
              title='还没有项目知识'
              description='资料完成解析后，生成知识建议并确认，项目事实会出现在这里。'
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function KnowledgeItem({
  item,
  onApprove,
  approving
}: {
  item: MemoryRead;
  onApprove: () => void;
  approving: boolean;
}) {
  const proposed = item.status === 'proposed';
  return (
    <article className='flex flex-col gap-3 px-5 py-4'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div className='min-w-0'>
          <div className='flex flex-wrap items-center gap-2'>
            <h3 className='font-medium'>{item.title}</h3>
            <Badge variant={proposed ? 'outline' : 'secondary'}>
              {proposed ? '待确认' : statusLabel(item.status)}
            </Badge>
            <Badge variant='outline'>{kindLabel(item.kind)}</Badge>
          </div>
          <p className='text-muted-foreground mt-2 whitespace-pre-wrap text-sm leading-6'>
            {item.body_markdown}
          </p>
        </div>
        {proposed ? (
          <Button disabled={approving} onClick={onApprove} size='sm' type='button'>
            <Check data-icon='inline-start' />
            {approving ? '确认中…' : '确认纳入'}
          </Button>
        ) : null}
      </div>
      {item.citations.length ? (
        <div className='text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs'>
          <span className='inline-flex items-center gap-1.5'>
            <FileText />
            依据
          </span>
          {item.citations.slice(0, 3).map((citation) => (
            <span key={`${citation.source_type}:${citation.source_id}`}>{citation.label}</span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

async function listProjectKnowledge(projectId: string) {
  try {
    return await listProjectMemory(projectId, true);
  } catch {
    return listProjectMemory(projectId, false);
  }
}

function kindLabel(kind: MemoryRead['kind']) {
  return (
    {
      fact: '事实',
      decision: '决定',
      risk: '风险',
      procedure: '方法',
      summary: '摘要',
      entity_note: '对象',
      preference: '偏好'
    }[kind] || '知识'
  );
}

function statusLabel(status: MemoryRead['status']) {
  return (
    {
      active: '已生效',
      superseded: '已替代',
      rejected: '已拒绝',
      deleted: '已删除',
      proposed: '待确认'
    }[status] || '已生效'
  );
}
