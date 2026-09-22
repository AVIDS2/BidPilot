'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';
import {
  IconAlertTriangle,
  IconBook2,
  IconBrain,
  IconCheck,
  IconCircleCheck,
  IconClock,
  IconDatabase,
  IconDownload,
  IconExternalLink,
  IconFileText,
  IconListSearch,
  IconSearch,
  IconSparkles
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
import { Input } from '@/components/ui/input';
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
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { getDocumentDownloadUrl } from '@/lib/bidpilot-api';
import { sourceTypeLabels, statusLabels, type KnowledgeInspectorProps } from './knowledge-types';

export function KnowledgeInspector({
  view,
  onViewChange,
  searchText,
  onSearchTextChange,
  search,
  searching,
  searchError,
  documents,
  selectedDocument,
  onSelectDocument,
  project,
  documentCount,
  indexedCount,
  processingCount,
  activeMemoryCount,
  proposedMemoryCount,
  compiling,
  onCompile
}: KnowledgeInspectorProps) {
  return (
    <div className='flex h-full min-h-0 flex-col'>
      <div className='border-b px-4 py-4'>
        <Tabs
          value={view}
          onValueChange={(value) => onViewChange(value as KnowledgeInspectorProps['view'])}
        >
          <TabsList className='w-full'>
            <TabsTrigger className='flex-1' value='search'>
              检索
            </TabsTrigger>
            <TabsTrigger className='flex-1' value='document' disabled={!selectedDocument}>
              当前资料
            </TabsTrigger>
            <TabsTrigger className='flex-1' value='status'>
              索引状态
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      {view === 'search' ? (
        <SearchInspector
          searchText={searchText}
          onSearchTextChange={onSearchTextChange}
          results={search}
          searching={searching}
          error={searchError}
          documents={documents}
          onSelectDocument={onSelectDocument}
        />
      ) : view === 'document' ? (
        <DocumentInspector document={selectedDocument} />
      ) : (
        <StatusInspector
          project={project}
          documentCount={documentCount}
          indexedCount={indexedCount}
          processingCount={processingCount}
          activeMemoryCount={activeMemoryCount}
          proposedMemoryCount={proposedMemoryCount}
          compiling={compiling}
          onCompile={onCompile}
        />
      )}
    </div>
  );
}

function SearchInspector({
  searchText,
  onSearchTextChange,
  results,
  searching,
  error,
  documents,
  onSelectDocument
}: {
  searchText: string;
  onSearchTextChange: (value: string) => void;
  results: KnowledgeInspectorProps['search'];
  searching: boolean;
  error: boolean;
  documents: KnowledgeInspectorProps['documents'];
  onSelectDocument: (id: string) => void;
}) {
  return (
    <div className='flex min-h-0 flex-1 flex-col'>
      <div className='px-4 py-4'>
        <div className='relative'>
          <IconSearch className='text-muted-foreground pointer-events-none absolute top-1/2 left-3 -translate-y-1/2' />
          <Input
            aria-label='检索项目知识'
            className='h-9 pl-9'
            onChange={(event) => onSearchTextChange(event.target.value)}
            placeholder='问一个关于项目资料的问题'
            value={searchText}
          />
        </div>
        <p className='text-muted-foreground mt-2 text-xs'>结果来自当前项目已完成索引的资料。</p>
      </div>
      <Separator />
      <ScrollArea className='min-h-0 flex-1'>
        {searchText.trim().length < 2 ? (
          <Empty className='m-4 min-h-56 border-0'>
            <EmptyHeader>
              <EmptyMedia variant='icon'>
                <IconListSearch />
              </EmptyMedia>
              <EmptyTitle>从问题开始</EmptyTitle>
              <EmptyDescription>
                例如“项目有哪些同类交付案例？”结果会带上可回溯的资料来源。
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : searching ? (
          <div className='p-4'>
            <QuerySkeleton rows={4} />
          </div>
        ) : error ? (
          <div className='p-4'>
            <QueryError message='检索暂时不可用，请确认资料已经建立索引。' />
          </div>
        ) : results.length ? (
          <ItemGroup className='gap-0 p-3'>
            {results.map((result) => {
              const document = documents.find((item) => item.id === result.source_document_id);
              return (
                <Item
                  key={result.chunk_id}
                  size='sm'
                  variant='default'
                  className='cursor-pointer rounded-md border-0 border-b hover:bg-muted/50'
                  onClick={() => document && onSelectDocument(document.id)}
                >
                  <ItemMedia variant='icon'>
                    <IconBook2 className='text-primary' />
                  </ItemMedia>
                  <ItemContent>
                    <ItemTitle>{document?.original_filename ?? '项目资料'}</ItemTitle>
                    <ItemDescription className='line-clamp-4'>{result.content}</ItemDescription>
                    <p className='text-muted-foreground text-xs'>
                      匹配度 {Math.round(result.score * 100)}%
                    </p>
                  </ItemContent>
                  <ItemActions>
                    <IconExternalLink className='text-muted-foreground' />
                  </ItemActions>
                </Item>
              );
            })}
          </ItemGroup>
        ) : (
          <Empty className='m-4 min-h-56 border-0'>
            <EmptyHeader>
              <EmptyMedia variant='icon'>
                <IconSearch />
              </EmptyMedia>
              <EmptyTitle>没有找到相关内容</EmptyTitle>
              <EmptyDescription>换一种问法，或先检查资料是否已经完成处理。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </ScrollArea>
    </div>
  );
}

function DocumentInspector({
  document
}: {
  document: KnowledgeInspectorProps['selectedDocument'];
}) {
  if (!document)
    return (
      <Empty className='m-4 min-h-64 border-0'>
        <EmptyTitle>选择一份资料</EmptyTitle>
      </Empty>
    );
  return (
    <ScrollArea className='min-h-0 flex-1'>
      <div className='flex flex-col gap-5 p-5'>
        <div>
          <div className='flex items-start gap-3'>
            <IconFileText className='text-primary mt-1 shrink-0' />
            <div className='min-w-0'>
              <h2 className='break-words font-semibold'>{document.original_filename}</h2>
              <p className='text-muted-foreground mt-1 text-xs'>{document.bundle.label}</p>
            </div>
          </div>
          <div className='mt-4 flex flex-wrap gap-2'>
            <Badge
              variant={
                document.parse_status === 'failed'
                  ? 'destructive'
                  : document.parse_status === 'parsed'
                    ? 'secondary'
                    : 'outline'
              }
            >
              {statusLabels[document.parse_status] ?? document.parse_status}
            </Badge>
            <Badge variant={document.index_status === 'indexed' ? 'secondary' : 'outline'}>
              {document.index_status === 'indexed'
                ? '可检索'
                : (statusLabels[document.index_status] ?? document.index_status)}
            </Badge>
          </div>
        </div>
        <Separator />
        <dl className='flex flex-col gap-3 text-sm'>
          <DetailRow
            label='资料类型'
            value={sourceTypeLabels[document.bundle.source_type] ?? document.bundle.source_type}
          />
          <DetailRow label='版本' value={`第 ${document.version_number} 版`} />
          <DetailRow label='格式' value={document.mime_type} />
          <DetailRow label='解析器' value={document.parser_name ?? '自动选择'} />
          <DetailRow label='所在项目' value={document.project.name} />
        </dl>
        {document.parse_error_code ? (
          <div className='border-destructive/30 bg-destructive/5 text-destructive flex gap-2 rounded-md border p-3 text-sm'>
            <IconAlertTriangle className='mt-0.5 shrink-0' />
            <span>这份资料处理失败，可以回到项目资料页重新处理。</span>
          </div>
        ) : null}
        <div className='flex flex-wrap gap-2'>
          <a className={buttonVariants({ size: 'sm' })} href={getDocumentDownloadUrl(document.id)}>
            <IconDownload data-icon='inline-start' />
            下载原文件
          </a>
          <Link
            className={buttonVariants({ size: 'sm', variant: 'outline' })}
            href={`/projects/${document.project.id}?tab=materials`}
          >
            <IconExternalLink data-icon='inline-start' />
            打开项目资料
          </Link>
        </div>
      </div>
    </ScrollArea>
  );
}

function StatusInspector({
  project,
  documentCount,
  indexedCount,
  processingCount,
  activeMemoryCount,
  proposedMemoryCount,
  compiling,
  onCompile
}: Omit<
  KnowledgeInspectorProps,
  | 'view'
  | 'onViewChange'
  | 'searchText'
  | 'onSearchTextChange'
  | 'search'
  | 'searching'
  | 'searchError'
  | 'documents'
  | 'selectedDocument'
  | 'onSelectDocument'
>) {
  return (
    <ScrollArea className='min-h-0 flex-1'>
      <div className='flex flex-col gap-5 p-5'>
        <div>
          <p className='text-sm font-semibold'>当前索引状态</p>
          <p className='text-muted-foreground mt-1 text-xs'>{project?.name}</p>
        </div>
        <div className='grid grid-cols-2 gap-x-4 gap-y-5'>
          <StatusMetric label='资料总数' value={documentCount} icon={<IconFileText />} />
          <StatusMetric label='可检索' value={indexedCount} icon={<IconCircleCheck />} />
          <StatusMetric label='处理中' value={processingCount} icon={<IconClock />} />
          <StatusMetric label='已确认知识' value={activeMemoryCount} icon={<IconBrain />} />
        </div>
        <Separator />
        <div className='flex flex-col gap-3'>
          <div className='flex items-start gap-3'>
            <IconDatabase className='text-primary mt-0.5 shrink-0' />
            <div>
              <p className='text-sm font-medium'>把资料整理成项目知识</p>
              <p className='text-muted-foreground mt-1 text-xs leading-5'>
                系统会从已处理资料中提取可复用事实，确认后才会进入项目上下文。
              </p>
            </div>
          </div>
          <div className='flex items-center justify-between gap-3'>
            <Badge variant={proposedMemoryCount ? 'default' : 'outline'}>
              {proposedMemoryCount ? `${proposedMemoryCount} 条待确认` : '没有待确认内容'}
            </Badge>
            <Button
              disabled={compiling || !indexedCount}
              onClick={onCompile}
              size='sm'
              variant='outline'
            >
              <IconSparkles data-icon='inline-start' />
              {compiling ? '整理中…' : '整理知识建议'}
            </Button>
          </div>
        </div>
        <div className='text-muted-foreground flex items-start gap-2 text-xs leading-5'>
          <IconCheck className='mt-0.5 shrink-0' />
          <span>只有带来源、经过确认的项目知识会被 Copilot 使用。</span>
        </div>
      </div>
    </ScrollArea>
  );
}

function StatusMetric({ label, value, icon }: { label: string; value: number; icon: ReactNode }) {
  return (
    <div>
      <div className='text-muted-foreground flex items-center gap-1.5 text-xs'>
        {icon}
        {label}
      </div>
      <p className='mt-1 text-xl font-semibold tabular-nums'>{value}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className='flex items-start justify-between gap-4'>
      <dt className='text-muted-foreground shrink-0'>{label}</dt>
      <dd className='max-w-[65%] break-words text-right font-medium'>{value}</dd>
    </div>
  );
}
