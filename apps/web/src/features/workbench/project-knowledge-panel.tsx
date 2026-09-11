'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  IconArrowUpRight,
  IconChevronDown,
  IconClock,
  IconFileText,
  IconPencil,
  IconRefresh,
  IconShieldCheck,
  IconX
} from '@tabler/icons-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  approveMemory,
  listProjectMemory,
  rejectMemory,
  supersedeMemory,
  updateMemory,
  type MemoryRead,
  type MemorySupersedePayload,
  type MemoryUpdatePayload
} from '@/lib/bidpilot-api';
import {
  ProjectKnowledgeReviewDialog,
  type ProjectKnowledgeReviewMode
} from './project-knowledge-review-dialog';

type ReviewState = {
  item: MemoryRead;
  mode: ProjectKnowledgeReviewMode;
};

export function ProjectKnowledgePanel({ projectId }: { projectId: string }) {
  const client = useQueryClient();
  const [review, setReview] = useState<ReviewState | null>(null);
  const knowledge = useQuery({
    queryKey: ['project-knowledge', projectId],
    queryFn: () => listProjectKnowledge(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const refresh = () => client.invalidateQueries({ queryKey: ['project-knowledge', projectId] });
  const approve = useMutation({
    mutationFn: approveMemory,
    onSuccess: async () => {
      await refresh();
      toast.success('项目知识已确认。');
    },
    onError: () => toast.error('这条知识暂时无法确认，请稍后重试。')
  });
  const update = useMutation({
    mutationFn: ({ memoryId, payload }: { memoryId: string; payload: MemoryUpdatePayload }) =>
      updateMemory(memoryId, payload),
    onSuccess: async () => {
      setReview(null);
      await refresh();
      toast.success('项目知识已更新。');
    },
    onError: () => toast.error('项目知识暂时无法更新，请稍后重试。')
  });
  const reject = useMutation({
    mutationFn: ({ memoryId, reason }: { memoryId: string; reason: string }) =>
      rejectMemory(memoryId, reason),
    onSuccess: async () => {
      setReview(null);
      await refresh();
      toast.success('知识建议已退回。');
    },
    onError: () => toast.error('这条知识暂时无法退回，请稍后重试。')
  });
  const supersede = useMutation({
    mutationFn: ({ memoryId, payload }: { memoryId: string; payload: MemorySupersedePayload }) =>
      supersedeMemory(memoryId, payload),
    onSuccess: async () => {
      setReview(null);
      await refresh();
      toast.success('替代版本已创建，确认后才会生效。');
    },
    onError: () => toast.error('替代版本暂时无法创建，请稍后重试。')
  });

  return (
    <>
      <Card>
        <CardHeader className='border-b'>
          <div className='flex items-start gap-3'>
            <div className='bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-lg'>
              <IconShieldCheck />
            </div>
            <div>
              <h2 className='font-medium'>项目知识</h2>
              <p className='text-muted-foreground mt-1 text-sm leading-6'>
                只展示绑定了项目依据的内容。待确认建议不会参与助手工作，历史版本会保留在这里。
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
                  projectId={projectId}
                  onApprove={() => approve.mutate(item.id)}
                  onEdit={() => setReview({ item, mode: 'edit' })}
                  onReject={() => setReview({ item, mode: 'reject' })}
                  onSupersede={() => setReview({ item, mode: 'supersede' })}
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
      <ProjectKnowledgeReviewDialog
        key={review ? `${review.mode}:${review.item.id}` : 'closed'}
        item={review?.item ?? null}
        mode={review?.mode ?? null}
        pending={update.isPending || reject.isPending || supersede.isPending}
        onOpenChange={(open) => {
          if (!open) setReview(null);
        }}
        onEdit={(payload) => {
          if (review) update.mutate({ memoryId: review.item.id, payload });
        }}
        onReject={(reason) => {
          if (review) reject.mutate({ memoryId: review.item.id, reason });
        }}
        onSupersede={(payload) => {
          if (review) supersede.mutate({ memoryId: review.item.id, payload });
        }}
      />
    </>
  );
}

function KnowledgeItem({
  item,
  projectId,
  onApprove,
  onEdit,
  onReject,
  onSupersede,
  approving
}: {
  item: MemoryRead;
  projectId: string;
  onApprove: () => void;
  onEdit: () => void;
  onReject: () => void;
  onSupersede: () => void;
  approving: boolean;
}) {
  const proposed = item.status === 'proposed';
  const active = item.status === 'active';
  const expired = isExpired(item.expires_at);

  return (
    <article className='flex flex-col gap-3 px-5 py-4'>
      <div className='flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between'>
        <div className='min-w-0'>
          <div className='flex flex-wrap items-center gap-2'>
            <h3 className='font-medium'>{item.title}</h3>
            <Badge variant={statusVariant(item.status, expired)}>
              {expired ? '已到期' : statusLabel(item.status)}
            </Badge>
            <Badge variant='outline'>{kindLabel(item.kind)}</Badge>
          </div>
          <p className='text-muted-foreground mt-2 whitespace-pre-wrap text-sm leading-6'>
            {item.body_markdown}
          </p>
        </div>
        <div className='flex shrink-0 flex-wrap gap-2 xl:justify-end'>
          {proposed ? (
            <>
              <Button onClick={onEdit} size='sm' type='button' variant='ghost'>
                <IconPencil data-icon='inline-start' />
                编辑
              </Button>
              <Button onClick={onReject} size='sm' type='button' variant='ghost'>
                <IconX data-icon='inline-start' />
                退回
              </Button>
              <Button disabled={approving} onClick={onApprove} size='sm' type='button'>
                <IconShieldCheck data-icon='inline-start' />
                {approving ? '确认中…' : '确认纳入'}
              </Button>
            </>
          ) : null}
          {active ? (
            <>
              <Button onClick={onEdit} size='sm' type='button' variant='outline'>
                <IconClock data-icon='inline-start' />
                调整有效期
              </Button>
              <Button onClick={onSupersede} size='sm' type='button' variant='outline'>
                <IconRefresh data-icon='inline-start' />
                创建替代版本
              </Button>
            </>
          ) : null}
        </div>
      </div>
      {item.expires_at ? (
        <p className='text-muted-foreground inline-flex items-center gap-1.5 text-xs'>
          <IconClock />
          有效期至 {item.expires_at.slice(0, 10)}
        </p>
      ) : null}
      {item.citations.length ? <KnowledgeSources item={item} projectId={projectId} /> : null}
    </article>
  );
}

function KnowledgeSources({ item, projectId }: { item: MemoryRead; projectId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className='text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs'>
        <IconFileText />
        查看依据（{item.citations.length}）
        <IconChevronDown
          className={open ? 'rotate-180 transition-transform' : 'transition-transform'}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className='bg-muted/40 mt-2 rounded-lg px-3 py-2'>
        <ul className='flex flex-col gap-2'>
          {item.citations.map((citation) => (
            <li key={`${citation.source_type}:${citation.source_id}`}>
              <Link
                className='text-muted-foreground hover:text-foreground inline-flex max-w-full items-start gap-1 text-xs leading-5 underline-offset-4 hover:underline'
                href={sourceHref(projectId, citation.source_type, citation.source_id)}
              >
                <span className='min-w-0'>{citation.label}</span>
                <IconArrowUpRight className='mt-0.5 shrink-0' />
              </Link>
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  );
}

async function listProjectKnowledge(projectId: string) {
  try {
    return await listProjectMemory(projectId, true, true);
  } catch {
    return listProjectMemory(projectId, false, false);
  }
}

function sourceHref(projectId: string, sourceType: string, sourceId: string) {
  const encodedId = encodeURIComponent(sourceId);
  if (sourceType === 'requirement_item') {
    return `/requirements?project_id=${projectId}&item_id=${encodedId}`;
  }
  if (sourceType === 'knowledge_chunk' || sourceType === 'evidence_item') {
    return `/projects/${projectId}?tab=materials&source_id=${encodedId}`;
  }
  return `/projects/${projectId}?tab=knowledge`;
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
      rejected: '已退回',
      deleted: '已删除',
      proposed: '待确认'
    }[status] || '项目知识'
  );
}

function statusVariant(status: MemoryRead['status'], expired: boolean) {
  if (expired || status === 'rejected') return 'destructive' as const;
  if (status === 'proposed' || status === 'superseded') return 'outline' as const;
  return 'secondary' as const;
}

function isExpired(expiresAt: string | null) {
  return Boolean(expiresAt && new Date(expiresAt).getTime() <= Date.now());
}
