'use client';

import { useState } from 'react';
import { useMutation, useQueries, useQueryClient } from '@tanstack/react-query';
import {
  FileDown,
  FileText,
  FileUp,
  PackageOpen,
  RefreshCw,
  RotateCcw,
  UploadCloud
} from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from '@/components/ui/accordion';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle
} from '@/components/ui/empty';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { LoadingButton } from '@/components/ui/loading-button';
import { Progress, ProgressLabel, ProgressValue } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Spinner } from '@/components/ui/spinner';
import {
  createBundle,
  getDocumentDownloadUrl,
  listDocuments,
  reindexBundle,
  reingestBundle,
  uploadDocument,
  type BundleRead,
  type DocumentsPaginatedResponse,
  type SourceDocumentRead
} from '@/lib/bidpilot-api';
import { toast } from 'sonner';

const SOURCE_TYPES = [
  { value: 'buyer_rfp', label: '招标文件', description: '采购方发布的要求、评分和合同条件' },
  { value: 'supplier_evidence', label: '企业资料', description: '资质、案例、产品和交付能力证明' },
  { value: 'supporting_material', label: '补充资料', description: '需要纳入项目判断的其它文件' }
] as const;

const PARSEABLE_EXTENSIONS = /\.(pdf|docx|xlsx|csv|txt|md|markdown)$/i;
const ACTIVE_BUNDLE_STATUSES = new Set(['queued', 'running', 'indexing']);

function bundleStatusLabel(status: string) {
  return (
    (
      {
        awaiting_upload: '等待上传',
        ready_to_ingest: '等待处理',
        queued: '准备处理',
        running: '解析中',
        indexing: '建立索引',
        ingested: '已完成',
        failed: '需要重试'
      } as Record<string, string>
    )[status] || status
  );
}

function documentStatusLabel(status: string) {
  return (
    (
      {
        pending: '等待处理',
        parsing: '解析中',
        parsed: '已解析',
        failed: '解析失败',
        not_applicable: '无需解析',
        queued: '准备处理',
        indexed: '已入库'
      } as Record<string, string>
    )[status] || status
  );
}

function bundleTone(status: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (status === 'failed') return 'destructive';
  if (status === 'ingested') return 'secondary';
  if (ACTIVE_BUNDLE_STATUSES.has(status)) return 'default';
  return 'outline';
}

function documentTone(status: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (status === 'failed') return 'destructive';
  if (status === 'parsed' || status === 'indexed') return 'secondary';
  return 'outline';
}

export function ProjectMaterialsPanel({
  projectId,
  bundles,
  loading,
  error
}: {
  projectId: string;
  bundles?: BundleRead[];
  loading: boolean;
  error: Error | null;
}) {
  const client = useQueryClient();
  const [uploadOpen, setUploadOpen] = useState(false);
  const documentQueries = useQueries({
    queries: (bundles ?? []).map((bundle) => ({
      queryKey: ['project-bundle-documents', bundle.id],
      queryFn: () => listDocuments(bundle.id),
      refetchInterval: ACTIVE_BUNDLE_STATUSES.has(bundle.ingest_status) ? 5_000 : 30_000,
      refetchOnWindowFocus: true
    }))
  });
  const processMutation = useMutation({
    mutationFn: ({
      bundle,
      documents
    }: {
      bundle: BundleRead;
      documents: SourceDocumentRead[];
    }) => {
      const hasParsedDocument = documents.some((document) => document.parse_status === 'parsed');
      if (hasParsedDocument && bundle.ingest_status === 'ingested') return reindexBundle(bundle.id);
      return reingestBundle(bundle.id);
    },
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['bundles', projectId] }),
        client.invalidateQueries({ queryKey: ['project-bundle-documents'] }),
        client.invalidateQueries({ queryKey: ['readiness', projectId] }),
        client.invalidateQueries({ queryKey: ['requirements', projectId] }),
        client.invalidateQueries({ queryKey: ['knowledge-portfolio'] })
      ]);
      toast.success('资料已重新开始处理。');
    },
    onError: () => toast.error('资料暂时无法重新处理，请稍后重试。')
  });

  if (loading)
    return (
      <div className='p-1'>
        <Spinner />
      </div>
    );
  if (error)
    return (
      <Alert variant='destructive'>
        <AlertTitle>资料加载失败</AlertTitle>
        <AlertDescription>当前项目资料暂时无法读取，请稍后重试。</AlertDescription>
      </Alert>
    );

  return (
    <div className='flex flex-col gap-4'>
      <Card>
        <CardHeader className='gap-3 border-b sm:flex-row sm:items-start sm:justify-between'>
          <div>
            <CardTitle>资料包</CardTitle>
            <CardDescription>
              把采购方要求和企业依据分开管理，处理完成后才进入需求与知识检索。
            </CardDescription>
          </div>
          <Button onClick={() => setUploadOpen(true)} size='sm'>
            <FileUp data-icon='inline-start' />
            上传资料
          </Button>
        </CardHeader>
        <CardContent className='p-0'>
          {bundles?.length ? (
            <Accordion multiple>
              {bundles.map((bundle, index) => {
                const query = documentQueries[index];
                const documents = query.data?.items ?? [];
                return (
                  <AccordionItem key={bundle.id} value={bundle.id} className='px-5 last:border-b-0'>
                    <AccordionTrigger className='gap-3 py-4 hover:no-underline'>
                      <span className='flex min-w-0 items-start gap-3 text-left'>
                        <span className='bg-primary/10 text-primary mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md'>
                          <PackageOpen />
                        </span>
                        <span className='grid min-w-0 gap-1'>
                          <span className='truncate font-medium'>{bundle.label}</span>
                          <span className='text-muted-foreground truncate text-xs'>
                            {sourceTypeLabel(bundle.source_type)} · {documents.length} 份文件
                          </span>
                        </span>
                      </span>
                      <Badge className='mr-2 shrink-0' variant={bundleTone(bundle.ingest_status)}>
                        {bundleStatusLabel(bundle.ingest_status)}
                      </Badge>
                    </AccordionTrigger>
                    <AccordionContent className='pb-4 pl-11'>
                      <BundleDocuments
                        bundle={bundle}
                        query={query}
                        documents={documents}
                        processing={
                          processMutation.isPending &&
                          processMutation.variables?.bundle.id === bundle.id
                        }
                        onProcess={() => processMutation.mutate({ bundle, documents })}
                      />
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          ) : (
            <Empty className='min-h-64 rounded-none border-0'>
              <EmptyHeader>
                <EmptyMedia variant='icon'>
                  <UploadCloud />
                </EmptyMedia>
                <EmptyTitle>从第一份资料开始</EmptyTitle>
                <EmptyDescription>
                  上传招标文件或企业资料，系统会解析要求、建立知识索引并计算响应准备度。
                </EmptyDescription>
              </EmptyHeader>
              <Button onClick={() => setUploadOpen(true)} size='sm'>
                <FileUp data-icon='inline-start' />
                上传项目资料
              </Button>
            </Empty>
          )}
        </CardContent>
      </Card>
      <Alert>
        <FileText />
        <AlertTitle>处理完成后会发生什么</AlertTitle>
        <AlertDescription>
          解析内容会进入需求清单和知识库；你可以先核对缺口，再起草响应。原始文件始终保留在当前项目范围内。
        </AlertDescription>
      </Alert>
      <UploadMaterialsDialog
        open={uploadOpen}
        projectId={projectId}
        onOpenChange={setUploadOpen}
        onCompleted={() => {
          void Promise.all([
            client.invalidateQueries({ queryKey: ['bundles', projectId] }),
            client.invalidateQueries({ queryKey: ['readiness', projectId] }),
            client.invalidateQueries({ queryKey: ['requirements', projectId] }),
            client.invalidateQueries({ queryKey: ['knowledge-portfolio'] })
          ]);
        }}
      />
    </div>
  );
}

function BundleDocuments({
  bundle,
  query,
  documents,
  processing,
  onProcess
}: {
  bundle: BundleRead;
  query: { isPending: boolean; isError: boolean; data?: DocumentsPaginatedResponse };
  documents: SourceDocumentRead[];
  processing: boolean;
  onProcess: () => void;
}) {
  const canProcess = Boolean(documents.length) && !ACTIVE_BUNDLE_STATUSES.has(bundle.ingest_status);
  const processedCount = documents.filter(
    (document) => document.parse_status === 'parsed' && document.index_status === 'indexed'
  ).length;
  return (
    <div className='flex flex-col gap-3'>
      <div className='flex flex-wrap items-center justify-between gap-2'>
        <div className='text-muted-foreground flex items-center gap-2 text-xs'>
          <span>
            {processedCount}/{documents.length} 份文件已进入知识索引
          </span>
          {query.isPending ? <Spinner className='size-3.5' /> : null}
        </div>
        {canProcess ? (
          <LoadingButton
            loading={processing}
            loadingLabel='正在准备处理'
            onClick={onProcess}
            size='xs'
            variant='outline'
          >
            {bundle.ingest_status === 'ingested' ? (
              <RefreshCw data-icon='inline-start' />
            ) : (
              <RotateCcw data-icon='inline-start' />
            )}
            {bundle.ingest_status === 'ingested' ? '刷新索引' : '开始处理'}
          </LoadingButton>
        ) : null}
      </div>
      <Separator />
      {query.isError ? (
        <p className='text-muted-foreground text-sm'>文件列表暂时无法读取。</p>
      ) : documents.length ? (
        <div className='flex flex-col gap-2'>
          {documents.map((document) => (
            <DocumentRow document={document} key={document.id} />
          ))}
        </div>
      ) : (
        <p className='text-muted-foreground text-sm'>资料包还没有文件。</p>
      )}
    </div>
  );
}

function DocumentRow({ document }: { document: SourceDocumentRead }) {
  return (
    <div className='bg-muted/30 flex items-center gap-3 rounded-lg px-3 py-2.5'>
      <FileText className='text-muted-foreground size-4 shrink-0' />
      <div className='min-w-0 flex-1'>
        <p className='truncate text-sm font-medium'>{document.original_filename}</p>
        <div className='text-muted-foreground mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs'>
          <Badge variant={documentTone(document.parse_status)}>
            {documentStatusLabel(document.parse_status)}
          </Badge>
          <span>
            {document.index_status === 'indexed'
              ? '已建立索引'
              : documentStatusLabel(document.index_status)}
          </span>
          {document.version_number > 1 ? <span>第 {document.version_number} 版</span> : null}
        </div>
        {document.parse_error_code ? (
          <p className='text-destructive mt-1 text-xs'>解析失败，可重新处理。</p>
        ) : null}
      </div>
      <a
        aria-label={`下载 ${document.original_filename}`}
        className='text-muted-foreground hover:text-foreground rounded-md p-1.5 transition-colors'
        href={getDocumentDownloadUrl(document.id)}
        title='下载原始文件'
      >
        <FileDown />
      </a>
    </div>
  );
}

function UploadMaterialsDialog({
  open,
  projectId,
  onOpenChange,
  onCompleted
}: {
  open: boolean;
  projectId: string;
  onOpenChange: (open: boolean) => void;
  onCompleted: () => void;
}) {
  const [label, setLabel] = useState('招标文件');
  const [sourceType, setSourceType] = useState<string>('buyer_rfp');
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState(0);
  const upload = useMutation({
    mutationFn: async () => {
      if (!label.trim()) throw new Error('请填写资料包名称');
      if (!files.length) throw new Error('请选择至少一个文件');
      const bundle = await createBundle({
        project_id: projectId,
        label: label.trim(),
        source_type: sourceType
      });
      for (const [index, file] of files.entries()) {
        await uploadDocument(
          bundle.id,
          file,
          (fileProgress) =>
            setProgress(Math.round(((index + fileProgress / 100) / files.length) * 100)),
          undefined,
          true
        );
      }
      if (files.some((file) => PARSEABLE_EXTENSIONS.test(file.name))) {
        await reingestBundle(bundle.id);
      }
      return { bundle, parseable: files.some((file) => PARSEABLE_EXTENSIONS.test(file.name)) };
    },
    onSuccess: ({ parseable }) => {
      toast.success(parseable ? '资料已上传，解析和索引已开始。' : '资料已上传。');
      onCompleted();
      reset();
      onOpenChange(false);
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : '资料上传失败，请重试。')
  });

  const reset = () => {
    setLabel('招标文件');
    setSourceType('buyer_rfp');
    setFiles([]);
    setProgress(0);
    upload.reset();
  };
  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && !upload.isPending) reset();
    onOpenChange(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className='max-h-[min(44rem,calc(100vh-2rem))] overflow-y-auto'>
        <DialogHeader>
          <DialogTitle>上传项目资料</DialogTitle>
          <DialogDescription>
            先选择资料用途，再一次上传同一资料包中的文件；全部上传完成后统一解析和建立索引。
          </DialogDescription>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor='project-bundle-label'>资料包名称</FieldLabel>
            <Input
              id='project-bundle-label'
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder='例如：智慧社区招标文件'
            />
          </Field>
          <Field>
            <FieldLabel>资料用途</FieldLabel>
            <Select
              value={sourceType || null}
              onValueChange={(value) => setSourceType(value ?? 'buyer_rfp')}
            >
              <SelectTrigger aria-label='选择资料用途'>
                <SelectValue>
                  {SOURCE_TYPES.find((item) => item.value === sourceType)?.label || '选择资料用途'}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {SOURCE_TYPES.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <FieldDescription>
              {SOURCE_TYPES.find((item) => item.value === sourceType)?.description}
            </FieldDescription>
          </Field>
          <Field>
            <FieldLabel htmlFor='project-material-files'>文件</FieldLabel>
            <Input
              id='project-material-files'
              type='file'
              multiple
              accept='.pdf,.docx,.xlsx,.csv,.txt,.md,.markdown'
              onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            />
            <FieldDescription>
              支持 PDF、DOCX、XLSX、CSV、TXT 和 Markdown；原始文件会保存在当前项目。
            </FieldDescription>
          </Field>
          {files.length ? (
            <div className='bg-muted/30 flex flex-col gap-2 rounded-lg p-3'>
              <div className='flex items-center justify-between gap-3 text-sm'>
                <span>{files.length} 个文件待上传</span>
                <span className='text-muted-foreground'>{formatFilesSize(files)}</span>
              </div>
              {upload.isPending ? (
                <Progress value={progress}>
                  <ProgressLabel>上传进度</ProgressLabel>
                  <ProgressValue />
                </Progress>
              ) : null}
              <ul className='text-muted-foreground flex flex-col gap-1 text-xs'>
                {files.map((file) => (
                  <li className='truncate' key={`${file.name}-${file.lastModified}`}>
                    {file.name}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {upload.error ? (
            <Alert variant='destructive'>
              <AlertTitle>上传未完成</AlertTitle>
              <AlertDescription>
                已创建的资料包仍会保留，可以关闭后检查并重新上传缺失文件。
              </AlertDescription>
            </Alert>
          ) : null}
        </FieldGroup>
        <DialogFooter>
          <Button
            disabled={upload.isPending}
            onClick={() => handleOpenChange(false)}
            type='button'
            variant='outline'
          >
            取消
          </Button>
          <LoadingButton
            loading={upload.isPending}
            loadingLabel='正在上传并处理'
            onClick={() => upload.mutate()}
            type='button'
          >
            <UploadCloud data-icon='inline-start' />
            上传并开始处理
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function sourceTypeLabel(value: string) {
  return SOURCE_TYPES.find((item) => item.value === value)?.label || value;
}

function formatFilesSize(files: File[]) {
  const bytes = files.reduce((total, file) => total + file.size, 0);
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
