'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowUpRight,
  Check,
  CheckCircle2,
  FileDown,
  FileText,
  MessageSquare,
  RotateCcw,
  WandSparkles,
  X
} from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from '@/components/ui/accordion';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle
} from '@/components/ui/empty';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { LoadingButton } from '@/components/ui/loading-button';
import { Markdown } from '@/components/ui/markdown';
import { QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import {
  draftSection,
  exportDeliverableDocx,
  exportDeliverablePdf,
  listDeliverableSections,
  listExecutionRuns,
  listSectionVersions,
  redraftSection,
  submitReviewDecision,
  type DeliverableRead,
  type DeliverableSectionRead,
  type SectionVersionRead
} from '@/lib/bidpilot-api';
import { toast } from 'sonner';

function deliverableStatusLabel(status: string) {
  return (
    ({ draft: '准备中', in_review: '审核中', approved: '已批准' } as Record<string, string>)[
      status
    ] || status
  );
}

function sectionStatusLabel(status: string, approved: boolean) {
  if (approved) return '已通过';
  return (
    (
      { draft: '待起草', in_review: '待审核', rejected: '待修改', approved: '已通过' } as Record<
        string,
        string
      >
    )[status] || status
  );
}

function runStatusLabel(status: string) {
  return (
    (
      {
        pending: '等待处理',
        queued: '准备起草',
        running: '执行中',
        awaiting_human: '等待审核',
        succeeded: '已完成',
        failed: '失败',
        cancelled: '已取消'
      } as Record<string, string>
    )[status] || status
  );
}

export function ProjectResponsePanel({
  projectId,
  deliverables,
  loading,
  error,
  requestedDeliverableId,
  requestedRunId
}: {
  projectId: string;
  deliverables?: DeliverableRead[];
  loading: boolean;
  error: Error | null;
  requestedDeliverableId?: string | null;
  requestedRunId?: string | null;
}) {
  const client = useQueryClient();
  const [selectedDeliverableId, setSelectedDeliverableId] = useState(requestedDeliverableId || '');
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const selectedDeliverable =
    deliverables?.find((item) => item.id === selectedDeliverableId) || deliverables?.[0];
  const sectionsQuery = useQuery({
    queryKey: ['deliverable-sections', selectedDeliverable?.id],
    queryFn: () => listDeliverableSections(selectedDeliverable?.id || ''),
    enabled: Boolean(selectedDeliverable?.id),
    refetchInterval: 15_000,
    refetchOnWindowFocus: true
  });
  const versionsQueries = useQueries({
    queries: (sectionsQuery.data ?? []).map((section) => ({
      queryKey: ['section-versions', section.id],
      queryFn: () => listSectionVersions(section.id),
      enabled: Boolean(section.id),
      refetchInterval: section.status === 'in_review' ? 10_000 : 30_000,
      refetchOnWindowFocus: true
    }))
  });
  const runs = useQuery({
    queryKey: ['execution-runs', projectId],
    queryFn: () => listExecutionRuns(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 10_000,
    refetchOnWindowFocus: true
  });
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['deliverables', projectId] }),
      client.invalidateQueries({ queryKey: ['deliverable-sections'] }),
      client.invalidateQueries({ queryKey: ['section-versions'] }),
      client.invalidateQueries({ queryKey: ['execution-runs', projectId] }),
      client.invalidateQueries({ queryKey: ['collaboration-board', projectId] }),
      client.invalidateQueries({ queryKey: ['readiness', projectId] })
    ]);
  };
  const draftMutation = useMutation({
    mutationFn: ({
      section,
      redraft,
      feedback
    }: {
      section: DeliverableSectionRead;
      redraft?: boolean;
      feedback?: string;
    }) => {
      const payload = {
        project_id: projectId,
        section_key: section.section_key,
        section_id: section.id,
        client_request_id: `web-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      };
      return redraft
        ? redraftSection({ ...payload, review_feedback: feedback?.trim() || undefined })
        : draftSection(payload);
    },
    onSuccess: async () => {
      await refresh();
      toast.success('章节起草已开始，完成后会显示在这里。');
    },
    onError: () => toast.error('章节暂时无法起草，请先确认资料已经处理完成。')
  });
  const reviewMutation = useMutation({
    mutationFn: ({
      sectionId,
      versionId,
      decision,
      comment
    }: {
      sectionId: string;
      versionId: string;
      decision: 'approved' | 'rejected';
      comment?: string;
    }) =>
      submitReviewDecision({
        section_id: sectionId,
        section_version_id: versionId,
        decision,
        comment: comment?.trim() || null
      }),
    onSuccess: async ({ decision }) => {
      await refresh();
      toast.success(decision === 'approved' ? '章节版本已通过。' : '章节版本已退回修改。');
    },
    onError: () => toast.error('审核动作未完成，请刷新后重试。')
  });
  const exportMutation = useMutation({
    mutationFn: ({ deliverableId, format }: { deliverableId: string; format: 'docx' | 'pdf' }) =>
      format === 'docx'
        ? exportDeliverableDocx(deliverableId)
        : exportDeliverablePdf(deliverableId),
    onSuccess: (_, variables) =>
      toast.success(`${variables.format.toUpperCase()} 文件已开始下载。`),
    onError: () => toast.error('导出失败，请确认至少有一个已批准的章节。')
  });

  const sections = sectionsQuery.data ?? [];
  const approvedCount = sections.filter((section) => Boolean(section.approved_version_id)).length;
  const latestRun = runs.data?.find((run) => run.id === requestedRunId) ?? runs.data?.[0];
  const exportLabel =
    approvedCount === sections.length && sections.length ? '导出最终文件' : '导出已批准内容';

  if (loading) return <QuerySkeleton rows={3} />;
  if (error) return <QueryError message='响应交付数据暂时无法读取。' />;
  if (!deliverables?.length) {
    return (
      <Empty className='min-h-64 border-0'>
        <EmptyHeader>
          <EmptyMedia variant='icon'>
            <FileText />
          </EmptyMedia>
          <EmptyTitle>响应结构尚未准备好</EmptyTitle>
          <EmptyDescription>
            项目创建时会生成默认章节；如果这里为空，请刷新项目或检查场景包配置。
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <div className='flex flex-col gap-4'>
      <Card>
        <CardHeader className='gap-3 border-b sm:flex-row sm:items-start sm:justify-between'>
          <div className='min-w-0'>
            <CardTitle>响应与交付</CardTitle>
            <CardDescription>
              起草只产生不可变候选版本；通过审核后，才能导出可交付文件。
            </CardDescription>
          </div>
          <div className='flex flex-wrap items-center gap-2'>
            <Link
              className={buttonVariants({ size: 'sm', variant: 'outline' })}
              href={`/reviews?project_id=${projectId}`}
            >
              <MessageSquare data-icon='inline-start' />
              进入评审
            </Link>
            <LoadingButton
              disabled={!selectedDeliverable || approvedCount === 0}
              loading={exportMutation.isPending && exportMutation.variables?.format === 'docx'}
              loadingLabel='正在生成 DOCX'
              onClick={() =>
                selectedDeliverable &&
                exportMutation.mutate({ deliverableId: selectedDeliverable.id, format: 'docx' })
              }
              size='sm'
            >
              <FileDown data-icon='inline-start' />
              {exportLabel} DOCX
            </LoadingButton>
            <LoadingButton
              disabled={!selectedDeliverable || approvedCount === 0}
              loading={exportMutation.isPending && exportMutation.variables?.format === 'pdf'}
              loadingLabel='正在生成 PDF'
              onClick={() =>
                selectedDeliverable &&
                exportMutation.mutate({ deliverableId: selectedDeliverable.id, format: 'pdf' })
              }
              size='sm'
              variant='outline'
            >
              <FileDown data-icon='inline-start' />
              PDF
            </LoadingButton>
          </div>
        </CardHeader>
        <CardContent className='flex flex-col gap-4 p-5'>
          {deliverables.length > 1 ? (
            <Field>
              <FieldLabel>选择响应版本</FieldLabel>
              <Select
                value={selectedDeliverable?.id}
                onValueChange={(value) => value && setSelectedDeliverableId(value)}
              >
                <SelectTrigger aria-label='选择响应版本'>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {deliverables.map((deliverable) => (
                      <SelectItem key={deliverable.id} value={deliverable.id}>
                        {deliverable.title}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          ) : null}
          <div className='flex flex-wrap items-center gap-2'>
            <Badge variant={selectedDeliverable?.status === 'approved' ? 'secondary' : 'outline'}>
              {deliverableStatusLabel(selectedDeliverable?.status || 'draft')}
            </Badge>
            <span className='text-muted-foreground text-sm'>
              {approvedCount}/{sections.length} 个章节已批准
            </span>
            {latestRun ? (
              <span className='text-muted-foreground text-sm'>
                最近运行：{runStatusLabel(latestRun.status)}
              </span>
            ) : null}
          </div>
          {approvedCount === 0 ? (
            <Alert>
              <WandSparkles />
              <AlertTitle>从一个章节开始</AlertTitle>
              <AlertDescription>
                先在章节下点击“开始起草”，等待工作流生成候选版本，再提交人工审核。
              </AlertDescription>
            </Alert>
          ) : null}
          {sectionsQuery.isPending ? (
            <QuerySkeleton rows={4} />
          ) : sectionsQuery.error ? (
            <QueryError message='章节列表暂时无法读取。' />
          ) : sections.length ? (
            <Accordion multiple>
              {sections.map((section, index) => {
                const versionsQuery = versionsQueries[index];
                const latest = latestVersion(versionsQuery.data);
                const title = sectionTitleLabel(section);
                const approved = Boolean(latest && section.approved_version_id === latest.id);
                const draftPending =
                  draftMutation.isPending && draftMutation.variables?.section.id === section.id;
                const reviewPending =
                  reviewMutation.isPending && reviewMutation.variables?.sectionId === section.id;
                return (
                  <AccordionItem key={section.id} value={section.id}>
                    <AccordionTrigger className='gap-3 py-4 hover:no-underline'>
                      <span className='flex min-w-0 items-start gap-3 text-left'>
                        <span className='bg-primary/10 text-primary mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md'>
                          <FileText />
                        </span>
                        <span className='grid min-w-0 gap-1'>
                          <span className='truncate font-medium'>{title}</span>
                          <span className='text-muted-foreground truncate text-xs'>
                            {section.section_key} · {versionsQuery.data?.length ?? 0} 个版本
                          </span>
                        </span>
                      </span>
                      <Badge
                        className='mr-2 shrink-0'
                        variant={
                          approved
                            ? 'secondary'
                            : section.status === 'rejected'
                              ? 'destructive'
                              : 'outline'
                        }
                      >
                        {sectionStatusLabel(section.status, approved)}
                      </Badge>
                    </AccordionTrigger>
                    <AccordionContent className='pb-5'>
                      {versionsQuery.isPending ? (
                        <QuerySkeleton rows={2} />
                      ) : versionsQuery.error ? (
                        <QueryError message='版本暂时无法读取。' />
                      ) : latest ? (
                        <div className='flex flex-col gap-4'>
                          <div className='bg-muted/20 rounded-lg border p-4'>
                            <div className='text-muted-foreground mb-3 flex flex-wrap items-center gap-2 text-xs'>
                              <Badge variant='outline'>版本 {latest.version_number}</Badge>
                              <span>{latest.created_by_actor}</span>
                              {latest.evidence_set_id ? (
                                <span>已关联证据集</span>
                              ) : (
                                <span>等待证据核对</span>
                              )}
                            </div>
                            <Markdown className='text-sm leading-7' variant='typora'>
                              {latest.content_markdown || '该版本没有可展示正文。'}
                            </Markdown>
                          </div>
                          {!approved ? (
                            <FieldGroup>
                              <Field>
                                <FieldLabel htmlFor={`review-note-${section.id}`}>
                                  审核意见
                                </FieldLabel>
                                <Textarea
                                  id={`review-note-${section.id}`}
                                  value={reviewNotes[section.id] || ''}
                                  onChange={(event) =>
                                    setReviewNotes((current) => ({
                                      ...current,
                                      [section.id]: event.target.value
                                    }))
                                  }
                                  placeholder='通过可留空；退回时写清需要补充或修改的地方。'
                                  rows={3}
                                />
                                <FieldDescription>
                                  审核结果会写入版本记录，并在需要时触发下一轮起草。
                                </FieldDescription>
                              </Field>
                            </FieldGroup>
                          ) : null}
                          <div className='flex flex-wrap items-center gap-2'>
                            {!approved ? (
                              <>
                                <LoadingButton
                                  loading={
                                    reviewPending &&
                                    reviewMutation.variables?.decision === 'approved'
                                  }
                                  loadingLabel='正在通过'
                                  onClick={() =>
                                    reviewMutation.mutate({
                                      sectionId: section.id,
                                      versionId: latest.id,
                                      decision: 'approved',
                                      comment: reviewNotes[section.id]
                                    })
                                  }
                                  size='sm'
                                >
                                  <Check data-icon='inline-start' />
                                  通过版本
                                </LoadingButton>
                                <LoadingButton
                                  loading={
                                    reviewPending &&
                                    reviewMutation.variables?.decision === 'rejected'
                                  }
                                  loadingLabel='正在退回'
                                  onClick={() =>
                                    reviewMutation.mutate({
                                      sectionId: section.id,
                                      versionId: latest.id,
                                      decision: 'rejected',
                                      comment: reviewNotes[section.id]
                                    })
                                  }
                                  size='sm'
                                  variant='outline'
                                >
                                  <X data-icon='inline-start' />
                                  退回修改
                                </LoadingButton>
                              </>
                            ) : (
                              <Badge variant='secondary'>
                                <CheckCircle2 data-icon='inline-start' />
                                当前版本已批准
                              </Badge>
                            )}
                            <LoadingButton
                              loading={draftPending}
                              loadingLabel='正在重新起草'
                              onClick={() =>
                                draftMutation.mutate({
                                  section,
                                  redraft: true,
                                  feedback: reviewNotes[section.id]
                                })
                              }
                              size='sm'
                              variant='ghost'
                            >
                              <RotateCcw data-icon='inline-start' />
                              重新起草
                            </LoadingButton>
                          </div>
                        </div>
                      ) : (
                        <Empty className='min-h-36 border-0 px-2 py-4 text-left'>
                          <EmptyHeader className='items-start gap-1'>
                            <EmptyTitle>还没有章节版本</EmptyTitle>
                            <EmptyDescription>
                              上传并处理资料后，起草按钮会把本章节交给响应工作流。
                            </EmptyDescription>
                          </EmptyHeader>
                          <LoadingButton
                            loading={draftPending}
                            loadingLabel='正在准备起草'
                            onClick={() => draftMutation.mutate({ section })}
                            size='sm'
                          >
                            <WandSparkles data-icon='inline-start' />
                            开始起草
                          </LoadingButton>
                        </Empty>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          ) : (
            <Empty className='min-h-36 border-0'>
              <EmptyHeader>
                <EmptyTitle>响应没有章节</EmptyTitle>
                <EmptyDescription>请检查当前场景包的默认章节配置。</EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className='border-b'>
          <CardTitle>下一步入口</CardTitle>
          <CardDescription>
            每个入口都回到对应的业务页面，不需要通过 Copilot 才能查看事实。
          </CardDescription>
        </CardHeader>
        <CardContent className='grid gap-3 p-5 sm:grid-cols-3'>
          <Link
            className='hover:bg-muted/40 flex items-start gap-3 rounded-lg border p-3 transition-colors'
            href={`/requirements?project_id=${projectId}`}
          >
            <FileText className='text-primary mt-0.5' />
            <span>
              <span className='block text-sm font-medium'>核对需求</span>
              <span className='text-muted-foreground mt-1 block text-xs'>
                确认要求是否覆盖、是否有证据。
              </span>
            </span>
            <ArrowUpRight className='text-muted-foreground ml-auto' />
          </Link>
          <Link
            className='hover:bg-muted/40 flex items-start gap-3 rounded-lg border p-3 transition-colors'
            href={`/knowledge?project_id=${projectId}`}
          >
            <MessageSquare className='text-primary mt-0.5' />
            <span>
              <span className='block text-sm font-medium'>检索知识</span>
              <span className='text-muted-foreground mt-1 block text-xs'>查看来源和检索结果。</span>
            </span>
            <ArrowUpRight className='text-muted-foreground ml-auto' />
          </Link>
          <Link
            className='hover:bg-muted/40 flex items-start gap-3 rounded-lg border p-3 transition-colors'
            href={`/deliverables?project_id=${projectId}`}
          >
            <FileDown className='text-primary mt-0.5' />
            <span>
              <span className='block text-sm font-medium'>查看交付物</span>
              <span className='text-muted-foreground mt-1 block text-xs'>
                下载已批准的最终文件。
              </span>
            </span>
            <ArrowUpRight className='text-muted-foreground ml-auto' />
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

function latestVersion(versions?: SectionVersionRead[]) {
  return versions?.reduce<SectionVersionRead | null>(
    (current, version) =>
      !current || version.version_number > current.version_number ? version : current,
    null
  );
}

function sectionTitleLabel(section: DeliverableSectionRead) {
  const labels: Record<string, string> = {
    'exec-summary': '项目概述',
    'past-performance': '类似业绩',
    'pricing-summary': '报价说明',
    'staffing-plan': '项目团队',
    'technical-approach': '技术方案'
  };
  return labels[section.section_key] || section.title;
}
