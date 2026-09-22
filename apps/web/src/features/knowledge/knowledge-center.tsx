'use client';

import Link from 'next/link';
import {
  IconCheck,
  IconCircleCheck,
  IconClock,
  IconCloudUpload,
  IconFileText,
  IconBrain
} from '@tabler/icons-react';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle
} from '@/components/ui/empty';
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle
} from '@/components/ui/item';
import { QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { MemoryRead } from '@/lib/bidpilot-api';
import {
  documentTone,
  memoryKindLabel,
  memoryStatusLabel,
  statusLabel,
  type DocumentRecord,
  type KnowledgeCenterProps
} from './knowledge-types';

export function KnowledgeCenter({
  view,
  onViewChange,
  documents,
  memories,
  loadingDocuments,
  memoryLoading,
  memoryError,
  selectedDocumentId,
  onSelectDocument,
  onApproveMemory,
  approvingMemoryId,
  projectId
}: KnowledgeCenterProps) {
  return (
    <div className='flex h-full min-h-0 flex-col'>
      <div className='flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4'>
        <div>
          <p className='text-sm font-semibold'>知识资产</p>
          <p className='text-muted-foreground mt-1 text-xs'>
            项目资料、检索内容和已确认事实在这里汇合。
          </p>
        </div>
        <Tabs
          value={view}
          onValueChange={(value) => onViewChange(value as KnowledgeCenterProps['view'])}
        >
          <TabsList>
            <TabsTrigger value='documents'>资料</TabsTrigger>
            <TabsTrigger value='knowledge'>项目知识</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      <div className='flex min-h-0 flex-1 flex-col'>
        {view === 'documents' ? (
          <DocumentList
            documents={documents}
            loading={loadingDocuments}
            selectedDocumentId={selectedDocumentId}
            onSelectDocument={onSelectDocument}
            projectId={projectId}
          />
        ) : (
          <MemoryList
            memories={memories}
            loading={memoryLoading}
            error={memoryError}
            onApproveMemory={onApproveMemory}
            approvingMemoryId={approvingMemoryId}
          />
        )}
      </div>
    </div>
  );
}

function DocumentList({
  documents,
  loading,
  selectedDocumentId,
  onSelectDocument,
  projectId
}: {
  documents: DocumentRecord[];
  loading: boolean;
  selectedDocumentId: string | null;
  onSelectDocument: (id: string) => void;
  projectId: string;
}) {
  if (loading)
    return (
      <div className='p-5'>
        <QuerySkeleton rows={7} />
      </div>
    );
  if (!documents.length) {
    return (
      <Empty className='m-5 min-h-80 border'>
        <EmptyHeader>
          <EmptyMedia variant='icon'>
            <IconCloudUpload />
          </EmptyMedia>
          <EmptyTitle>从第一份资料开始</EmptyTitle>
          <EmptyDescription>
            把招标文件或企业依据导入当前项目，处理完成后即可检索和引用。
          </EmptyDescription>
        </EmptyHeader>
        <Link
          className={buttonVariants({ size: 'sm' })}
          href={`/projects/${projectId}?tab=materials`}
        >
          导入项目资料
        </Link>
      </Empty>
    );
  }
  return (
    <ScrollArea className='min-h-0 flex-1'>
      <div className='flex items-center justify-between px-5 py-3'>
        <p className='text-muted-foreground text-xs'>{documents.length} 份资料</p>
        <p className='text-muted-foreground text-xs'>点击资料查看详情</p>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>资料</TableHead>
            <TableHead className='hidden xl:table-cell'>资料包</TableHead>
            <TableHead>状态</TableHead>
            <TableHead className='w-20 text-right'>版本</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((document) => {
            const selected = document.id === selectedDocumentId;
            return (
              <TableRow
                aria-label={`打开资料 ${document.original_filename}`}
                className={`cursor-pointer ${selected ? 'bg-muted/70' : ''}`}
                data-state={selected ? 'selected' : undefined}
                key={document.id}
                onClick={() => onSelectDocument(document.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') onSelectDocument(document.id);
                }}
                tabIndex={0}
              >
                <TableCell className='max-w-0'>
                  <div className='flex min-w-0 items-center gap-2.5'>
                    <IconFileText className='text-muted-foreground shrink-0' />
                    <div className='min-w-0'>
                      <p className='truncate font-medium'>{document.original_filename}</p>
                      <p className='text-muted-foreground mt-1 truncate text-xs'>
                        {document.mime_type}
                      </p>
                    </div>
                  </div>
                </TableCell>
                <TableCell className='text-muted-foreground hidden max-w-40 truncate xl:table-cell'>
                  {document.bundle.label}
                </TableCell>
                <TableCell>
                  <div className='flex flex-wrap gap-1.5'>
                    <Badge variant={documentTone(document.parse_status)}>
                      {statusLabel(document.parse_status)}
                    </Badge>
                    <span className='text-muted-foreground hidden text-xs 2xl:inline'>
                      {document.index_status === 'indexed'
                        ? '可检索'
                        : statusLabel(document.index_status)}
                    </span>
                  </div>
                </TableCell>
                <TableCell className='text-muted-foreground text-right text-xs'>
                  v{document.version_number}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </ScrollArea>
  );
}

function MemoryList({
  memories,
  loading,
  error,
  onApproveMemory,
  approvingMemoryId
}: {
  memories: MemoryRead[];
  loading: boolean;
  error: boolean;
  onApproveMemory: (id: string) => void;
  approvingMemoryId: string | null;
}) {
  if (loading)
    return (
      <div className='p-5'>
        <QuerySkeleton rows={5} />
      </div>
    );
  if (error)
    return (
      <div className='p-5'>
        <QueryError message='项目知识暂时无法加载，请稍后重试。' />
      </div>
    );
  if (!memories.length) {
    return (
      <Empty className='m-5 min-h-80 border'>
        <EmptyHeader>
          <EmptyMedia variant='icon'>
            <IconBrain />
          </EmptyMedia>
          <EmptyTitle>还没有已确认的项目知识</EmptyTitle>
          <EmptyDescription>
            处理资料后，在右侧索引状态中整理知识建议，再逐条确认。
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <ScrollArea className='min-h-0 flex-1'>
      <ItemGroup className='gap-0 p-3'>
        {memories.map((memory) => (
          <Item
            key={memory.id}
            size='sm'
            variant='default'
            className='rounded-none border-x-0 border-t-0 border-b'
          >
            <ItemMedia variant='icon'>
              {memory.status === 'active' ? (
                <IconCircleCheck className='text-primary' />
              ) : (
                <IconClock className='text-muted-foreground' />
              )}
            </ItemMedia>
            <ItemContent>
              <ItemTitle>
                <span className='truncate'>{memory.title}</span>
                <Badge variant={memory.status === 'active' ? 'secondary' : 'outline'}>
                  {memoryStatusLabel(memory.status)}
                </Badge>
              </ItemTitle>
              <ItemDescription className='line-clamp-2'>{memory.body_markdown}</ItemDescription>
              <p className='text-muted-foreground text-xs'>
                {memory.citations.length} 个来源 · {memoryKindLabel(memory.kind)}
              </p>
            </ItemContent>
            {memory.status === 'proposed' ? (
              <ItemActions>
                <Button
                  disabled={approvingMemoryId === memory.id}
                  onClick={() => onApproveMemory(memory.id)}
                  size='xs'
                >
                  <IconCheck data-icon='inline-start' />
                  确认
                </Button>
              </ItemActions>
            ) : null}
          </Item>
        ))}
      </ItemGroup>
    </ScrollArea>
  );
}
