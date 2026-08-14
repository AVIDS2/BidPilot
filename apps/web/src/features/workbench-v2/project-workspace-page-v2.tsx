import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  AlertCircleIcon,
  ArrowRightIcon,
  BotIcon,
  CheckCircle2Icon,
  ChevronRightIcon,
  FileCheck2Icon,
  FileClockIcon,
  FileOutputIcon,
  FileSearchIcon,
  FileTextIcon,
  FileWarningIcon,
  FolderOpenIcon,
  HistoryIcon,
  LoaderCircleIcon,
  PlusIcon,
  RefreshCwIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  UploadIcon,
} from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { WorkflowCanvas } from "@/components/workflow-canvas";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  createBundle,
  createDeliverable,
  createDeliverableSection,
  draftSection,
  exportDeliverableDocx,
  exportDeliverablePdf,
  getApiErrorDetail,
  getProject,
  getCollaborationBoard,
  getRequirement,
  getReadinessSummary,
  listBundles,
  listDocuments,
  listDeliverableSections,
  listDeliverables,
  listEvidence,
  listExecutionRuns,
  listParsedAssets,
  listProviderConfigs,
  listSectionVersions,
  getResponsePlan,
  listRequirements,
  listResponsePlans,
  listRuntimeEvents,
  reindexBundle,
  reingestBundle,
  redraftSection,
  submitReviewDecision,
  updateRequirement,
  uploadDocument,
  verifyRequirementClaim,
  verifyRequirementEvidenceLink,
  type BidReadinessSummary,
  type CollaborationBoardRead,
  type BundleRead,
  type DeliverableRead,
  type DeliverableSectionRead,
  type ExecutionRunRead,
  type RequirementItemRead,
  type RequirementDetailRead,
  type ParsedAssetRead,
  type ResponsePlanDetailRead,
  type RuntimeEventRead,
  type SectionVersionRead,
  type SourceDocumentRead,
  type ProviderConfig,
} from "@/lib/api";
import type { AgentNode } from "@/components/agent-status-stream";
import { cn } from "@/lib/utils";

import { displayDeliverableType, displayRunType } from "./workbench-v2-labels";

type ProjectSurface = "overview" | "materials" | "requirements" | "plan" | "workflow" | "sections" | "review" | "deliverables";
type RequirementFilter = "all" | "mandatory-gaps" | "evidence-gaps" | "verification";
type WorkflowReasoningEffort = "low" | "medium" | "high" | "extra" | "max";

type WorkflowRunOptions = {
  providerConfigId: string;
  reasoningEffort: WorkflowReasoningEffort;
  maxIterations: number;
};

const PROJECT_SURFACES: Array<{ value: ProjectSurface; label: string }> = [
  { value: "overview", label: "概览" },
  { value: "materials", label: "资料" },
  { value: "requirements", label: "要求与合规" },
  { value: "plan", label: "响应计划" },
  { value: "workflow", label: "响应工作流" },
  { value: "sections", label: "章节" },
  { value: "review", label: "审阅" },
  { value: "deliverables", label: "交付" },
];

function documentQueueErrorMessage(error: unknown) {
  const detail = getApiErrorDetail(error);
  const message = typeof detail === "string" ? detail : "";
  if (/indexing|index|quota|limit/i.test(message)) {
    return "当前工作区的解析额度已用尽。文件已保留，可下载原件，或在额度恢复后重新解析。";
  }
  return "文件已上传，但未能进入解析队列。可在资料页查看处理状态后重新解析。";
}

const PROJECT_READINESS_CHART_CONFIG = {
  score: {
    label: "完成度",
    color: "#2f8f6b",
  },
} satisfies ChartConfig;

const RESPONSE_WORKFLOW_STAGES = [
  { key: "supervisor", label: "调度规划", detail: "根据项目当前事实选择下一业务节点", icon: BotIcon },
  { key: "rfp_parser", label: "资料解析", detail: "从招标文件提取可追溯要求", icon: FileSearchIcon },
  { key: "memory_context", label: "加载项目记忆", detail: "读取已获授权的项目知识和历史决策", icon: HistoryIcon },
  { key: "knowledge_retriever", label: "证据检索", detail: "为要求匹配项目资料中的证据", icon: FileCheck2Icon },
  { key: "content_plan", label: "响应计划", detail: "把要求和证据编排到响应结构", icon: ArrowRightIcon },
  { key: "section_drafter", label: "章节起草", detail: "生成带引用依据的章节草稿", icon: FileTextIcon },
  { key: "quality_reviewer", label: "质量审阅", detail: "检查覆盖、引用和主张完整性", icon: ShieldCheckIcon },
  { key: "human_approval", label: "人工确认", detail: "由负责人批准或退回修改", icon: ShieldAlertIcon },
  { key: "persist_result", label: "成果保存", detail: "将版本、证据和审阅结果写回项目", icon: CheckCircle2Icon },
  { key: "memory_proposals", label: "知识提案", detail: "把可复用结论保留为待审核提案", icon: FileCheck2Icon },
] as const;

const RESPONSE_WORKFLOW_AGENT_STAGES = [
  { key: "supervisor", label: "调度规划" },
  { key: "rfp_parser", label: "资料解析" },
  { key: "memory_context", label: "加载项目记忆" },
  { key: "knowledge_retriever", label: "证据检索" },
  { key: "content_plan", label: "响应计划" },
  { key: "section_drafter", label: "章节起草" },
  { key: "quality_reviewer", label: "质量审阅" },
  { key: "human_approval", label: "人工确认" },
  { key: "persist_result", label: "成果保存" },
  { key: "memory_proposals", label: "知识提案" },
] as const;

type WorkflowStageState = "pending" | "active" | "complete" | "attention" | "review";

function workflowEventNode(event: RuntimeEventRead) {
  const node = event.payload.node ?? event.payload.capability;
  return typeof node === "string" ? node : null;
}

function workflowStageState(stageKey: string, events: RuntimeEventRead[]): WorkflowStageState {
  const matching = events
    .filter((event) => workflowEventNode(event) === stageKey)
    .sort((left, right) => left.sequence - right.sequence);
  const latest = matching[matching.length - 1];
  if (!latest) return "pending";
  if (latest.type === "capability.failed") return "attention";
  if (latest.payload.review_status === "degraded") return "review";
  if (latest.type === "approval.requested") return "review";
  if (latest.type === "capability.started" || latest.type === "capability.progressed") return "active";
  if (latest.type === "capability.succeeded" || latest.type === "approval.resolved") return "complete";
  return "pending";
}

function workflowStatusValue(state: WorkflowStageState) {
  if (state === "complete") return "succeeded";
  if (state === "active") return "running";
  if (state === "review") return "awaiting_approval";
  if (state === "attention") return "failed";
  return "queued";
}

function workflowEventStageLabel(event: RuntimeEventRead) {
  const node = workflowEventNode(event);
  return RESPONSE_WORKFLOW_AGENT_STAGES.find((stage) => stage.key === node)?.label ?? "工作流";
}

function workflowAgentNodes(events: RuntimeEventRead[]): AgentNode[] {
  return RESPONSE_WORKFLOW_AGENT_STAGES.map((stage) => {
    const matching = events
      .filter((event) => workflowEventNode(event) === stage.key)
      .sort((left, right) => left.sequence - right.sequence);
    const latest = matching[matching.length - 1];
    if (!latest) return { name: stage.key, status: "pending" };
    if (latest.type === "capability.failed") return { name: stage.key, status: "failed", error: latest.public_summary };
    if (latest.payload.review_status === "degraded") return { name: stage.key, status: "completed", summary: "自动审核不可用，等待人工复核" };
    if (latest.type === "approval.requested") return { name: stage.key, status: "running", summary: latest.public_summary };
    if (latest.type === "capability.started" || latest.type === "capability.progressed") return { name: stage.key, status: "running", summary: latest.public_summary };
    if (latest.type === "capability.succeeded" || latest.type === "approval.resolved") return { name: stage.key, status: "completed", summary: latest.public_summary };
    return { name: stage.key, status: "pending" };
  });
}

function WorkflowRunControls({
  options,
  onChange,
  providers,
}: {
  options: WorkflowRunOptions;
  onChange: (next: WorkflowRunOptions) => void;
  providers: ProviderConfig[];
}) {
  return (
    <section className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4" aria-label="下一次工作流配置">
      <div className="min-w-40 flex-1"><p className="text-sm font-medium">下一次起草配置</p><p className="mt-1 text-xs text-muted-foreground">这些参数会写入本次运行，并在失败重试时继承。</p></div>
      <label className="grid gap-1 text-xs text-muted-foreground"><span>模型来源</span><Select onValueChange={(providerConfigId) => providerConfigId && onChange({ ...options, providerConfigId })} value={options.providerConfigId}><SelectTrigger className="h-9 min-w-36"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="official">平台默认</SelectItem>{providers.map((provider) => <SelectItem key={provider.id} value={provider.id}>{provider.label || provider.model}</SelectItem>)}</SelectContent></Select></label>
      <label className="grid gap-1 text-xs text-muted-foreground"><span>推理强度</span><Select onValueChange={(reasoningEffort) => reasoningEffort && onChange({ ...options, reasoningEffort: reasoningEffort as WorkflowReasoningEffort })} value={options.reasoningEffort}><SelectTrigger className="h-9 min-w-28"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="low">低</SelectItem><SelectItem value="medium">标准</SelectItem><SelectItem value="high">高</SelectItem><SelectItem value="extra">更高</SelectItem><SelectItem value="max">最大</SelectItem></SelectContent></Select></label>
      <label className="grid gap-1 text-xs text-muted-foreground"><span>最多返工</span><Select onValueChange={(value) => value && onChange({ ...options, maxIterations: Number(value) })} value={String(options.maxIterations)}><SelectTrigger className="h-9 min-w-28"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="1">1 轮</SelectItem><SelectItem value="2">2 轮</SelectItem><SelectItem value="3">3 轮</SelectItem><SelectItem value="4">4 轮</SelectItem><SelectItem value="5">5 轮</SelectItem></SelectContent></Select></label>
    </section>
  );
}

function formatWorkflowTime(timestamp: string) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "刚刚";
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}

function workflowRunContext(run: ExecutionRunRead) {
  const sectionKey = run.input_json?.section_key;
  if (typeof sectionKey === "string" && sectionKey.trim()) return `章节 ${sectionKey}`;
  const deliverableId = run.input_json?.deliverable_id;
  if (typeof deliverableId === "string" && deliverableId.trim()) return "响应交付物";
  return "项目级运行";
}

function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return 0;
  return Math.round(Math.max(0, Math.min(100, value <= 1 ? value * 100 : value)));
}

function formatLocator(locator: Record<string, unknown> | null | undefined) {
  if (!locator) return "未提供原文定位";
  const labels: Record<string, string> = {
    page: "第",
    section: "章节",
    table: "表格",
    text_anchor: "原文锚点",
  };
  const parts = Object.entries(labels)
    .map(([key, label]) => {
      const value = locator[key];
      if (value === null || value === undefined || value === "") return "";
      return key === "page" ? `${label}${String(value)}页` : `${label} ${String(value)}`;
    })
    .filter(Boolean);
  return parts.length ? parts.join(" · ") : "未提供原文定位";
}

function labelForStatus(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "mandatory") return "强制项";
  if (normalized === "normal") return "普通项";
  if (normalized === "ready" || normalized === "available") return "可使用";
  if (normalized === "not_applicable") return "无需解析";
  if (normalized === "parsed") return "已解析";
  if (normalized === "parsing" || normalized === "indexing") return "处理中";
  if (normalized === "indexed") return "已建立索引";
  if (normalized === "queued") return "排队中";
  if (normalized === "unverified") return "待核验";
  if (normalized === "missing") return "缺失";
  if (normalized === "uncovered") return "未覆盖";
  if (normalized === "partial") return "部分覆盖";
  if (normalized === "verified") return "已核验";
  if (normalized === "pending") return "待处理";
  if (normalized.includes("approval") || normalized.includes("review")) return "待审核";
  if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("blocked")) return "需处理";
  if (normalized.includes("complete") || normalized.includes("success") || normalized.includes("ready")) return "已完成";
  if (normalized.includes("running") || normalized.includes("active") || normalized.includes("draft")) return "进行中";
  if (normalized.includes("archive")) return "已归档";
  return status || "未知";
}

function formatAssetPreview(asset: ParsedAssetRead | undefined) {
  if (!asset?.content_json) return "";
  const content = asset.content_json;
  for (const key of ["text", "normalized_text", "markdown", "content"]) {
    const value = content[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function toSectionKey(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "section";
}

function toneForStatus(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("blocked") || normalized.includes("gap")) return "attention";
  if (normalized.includes("approval") || normalized.includes("review") || normalized.includes("pending") || normalized.includes("partial")) return "review";
  if (normalized.includes("complete") || normalized.includes("success") || normalized.includes("ready") || normalized.includes("verified") || normalized.includes("covered")) return "complete";
  if (normalized.includes("running") || normalized.includes("active") || normalized.includes("draft")) return "active";
  return "muted";
}

function SurfaceHeader({ action, title }: { action?: ReactNode; title: string }) {
  const { t } = useTranslation();
  const key = `workbench.surfaces.${title.toLowerCase()}`;
  return (
    <header className="wb-project-surface-heading">
      <h1>{t(key, { defaultValue: title })}</h1>
      {action}
    </header>
  );
}

function StatusMark({ status }: { status: string }) {
  const tone = toneForStatus(status);
  return (
    <span className={cn("wb-inline-status", `wb-inline-status--${tone}`)}>
      <i aria-hidden="true" />
      {labelForStatus(status)}
    </span>
  );
}

function DataUnavailable({ label }: { label: string }) {
  return <p className="wb-project-data-unavailable">暂时无法读取{label}。</p>;
}

function ProjectBrief({
  bundleCount,
  deliverableCount,
  documents,
  documentsLoading,
  evidenceCount,
  onOpenMaterials,
  onOpenRequirements,
  onUpload,
  projectName,
  projectStatus,
  requirementCount,
  readiness,
  runs,
  collaboration,
}: {
  bundleCount: number;
  deliverableCount: number;
  documents: SourceDocumentRead[];
  documentsLoading: boolean;
  evidenceCount: number;
  onOpenMaterials: () => void;
  onOpenRequirements: (filter: RequirementFilter) => void;
  onUpload: () => void;
  projectName: string;
  projectStatus: string;
  requirementCount: number;
  readiness: BidReadinessSummary | undefined;
  runs: ExecutionRunRead[];
  collaboration: CollaborationBoardRead | undefined;
}) {
  const activeRuns = runs.filter((run) => toneForStatus(run.status) === "active").length;
  const reviewRuns = runs.filter((run) => toneForStatus(run.status) === "review").length;
  const requirementTotal = readiness?.counts.total ?? requirementCount;
  const verifiedEvidence = readiness?.counts.verified ?? evidenceCount;
  const uncoveredEvidence = readiness?.counts.uncovered ?? 0;
  const parsedDocumentCount = documents.filter((document) => document.parse_status === "parsed").length;
  const processingDocumentCount = documents.filter((document) => (
    document.parse_status !== "parsed" && document.parse_status !== "failed" && document.parse_status !== "not_applicable"
  ) || document.index_status === "indexing").length;
  const failedDocumentCount = documents.filter((document) => (
    document.parse_status === "failed" || ["failed", "degraded"].includes(document.index_status)
  )).length;
  const readinessScores = readiness
    ? [
        { label: "强制项闭环", score: formatScore(readiness.scores.mandatory_closure), detail: "必须满足的要求已覆盖" },
        { label: "评分项覆盖", score: formatScore(readiness.scores.scored_coverage), detail: "可得分要求已建立响应" },
        { label: "证据核验", score: formatScore(readiness.scores.verification), detail: "要求与引用已人工确认" },
        { label: "责任分配", score: formatScore(readiness.scores.assignment), detail: "要求已明确负责人" },
      ]
    : [];
  const mandatoryGapCount = readiness?.mandatory_gaps.length ?? 0;
  const evidenceGapCount = readiness?.evidence_gaps.length ?? 0;
  const reviewCount = (readiness?.contradictions.length ?? 0) + (readiness?.overdue.length ?? 0) + reviewRuns;
  const actionItems = [
    !documents.length
      ? { id: "upload", title: "先上传招标文件", detail: "资料解析后才能识别要求、提取证据并计算就绪度。", count: "开始", icon: UploadIcon, onClick: onUpload }
      : null,
    processingDocumentCount > 0
      ? { id: "processing", title: "关注资料解析状态", detail: `${processingDocumentCount} 份资料仍在解析或建立索引。`, count: `${processingDocumentCount} 份`, icon: LoaderCircleIcon, onClick: onOpenMaterials }
      : null,
    failedDocumentCount > 0
      ? { id: "failed", title: "处理不可用的资料", detail: "解析或检索索引异常的资料不会参与后续证据检索。", count: `${failedDocumentCount} 份`, icon: FileWarningIcon, onClick: onOpenMaterials }
      : null,
    mandatoryGapCount > 0
      ? { id: "mandatory", title: "补齐强制项缺口", detail: "这些要求会直接影响投标资格或提交完整性。", count: `${mandatoryGapCount} 项`, icon: AlertCircleIcon, onClick: () => onOpenRequirements("mandatory-gaps") }
      : null,
    evidenceGapCount > 0
      ? { id: "evidence", title: "为要求补充可引用证据", detail: "缺少证据的响应无法形成可审计的承诺。", count: `${evidenceGapCount} 项`, icon: FileCheck2Icon, onClick: () => onOpenRequirements("evidence-gaps") }
      : null,
    reviewCount > 0
      ? { id: "review", title: "处理待核验与团队决定", detail: "冲突、逾期或等待审批的事项需要人工确认。", count: `${reviewCount} 项`, icon: ShieldAlertIcon, onClick: () => onOpenRequirements("verification") }
      : null,
  ].filter((item): item is NonNullable<typeof item> => item !== null).slice(0, 4);

  return (
    <div className="wb-project-overview">
      <div className="wb-project-overview__hero">
        <section className="wb-project-overview__intro" aria-labelledby="project-overview-title">
          <p className="wb-project-overview__kicker">项目工作台</p>
          <h1 id="project-overview-title">{projectName}</h1>
          <p className="wb-project-overview__description">把招标资料、要求、证据和交付集中在一处。下一步只围绕明确的业务缺口展开。</p>

          <div className="wb-project-overview__status">
            <StatusMark status={projectStatus} />
            <span>{activeRuns > 0 ? `${activeRuns} 个自动化运行中` : reviewRuns > 0 ? `${reviewRuns} 个事项等待团队确认` : "当前没有正在执行的自动化任务"}</span>
          </div>

          <dl className="wb-project-overview__facts" aria-label="项目关键数据">
            <div><dt>资料</dt><dd>{documentsLoading ? "…" : documents.length}</dd><small>{bundleCount ? `${bundleCount} 个资料包 · ${parsedDocumentCount} 已解析` : "尚未上传"}</small></div>
            <div><dt>要求</dt><dd>{requirementTotal}</dd><small>{readiness ? `${readiness.counts.mandatory} 项强制要求` : "等待资料解析"}</small></div>
            <div><dt>交付</dt><dd>{deliverableCount}</dd><small>{verifiedEvidence ? `${verifiedEvidence} 项已核验` : "尚无已核验证据"}</small></div>
          </dl>

          <div className="wb-project-overview__actions">
            <Button onClick={onUpload} size="sm" type="button"><UploadIcon aria-hidden="true" data-icon="inline-start" />上传资料</Button>
            <Button onClick={() => onOpenRequirements("all")} size="sm" type="button" variant="outline">查看要求矩阵<ArrowRightIcon aria-hidden="true" data-icon="inline-end" /></Button>
          </div>
        </section>

        <section className="wb-project-readiness-panel" aria-labelledby="readiness-breakdown-title">
          <header className="wb-project-readiness-panel__head">
            <div><h2 id="readiness-breakdown-title">投标就绪度</h2><p>强制项、评分项、证据核验与责任分配</p></div>
            <strong>{readiness ? `${Math.round(readiness.readiness_score)}%` : "--"}</strong>
          </header>
          {readinessScores.length ? (
            <>
              <ChartContainer className="wb-project-readiness-chart" config={PROJECT_READINESS_CHART_CONFIG}>
                <BarChart accessibilityLayer data={readinessScores} layout="vertical" margin={{ top: 2, right: 8, left: 4, bottom: 2 }}>
                  <CartesianGrid horizontal={false} />
                  <XAxis axisLine={false} dataKey="score" domain={[0, 100]} tickFormatter={(value) => `${value}%`} tickLine={false} type="number" />
                  <YAxis axisLine={false} dataKey="label" tickLine={false} type="category" width={76} />
                  <ChartTooltip cursor={{ fill: "#f4f5f5" }} content={<ChartTooltipContent formatter={(value, _name, item) => [`${value}% · ${item.payload.detail}`, "完成度"]} />} />
                  <Bar dataKey="score" fill="var(--color-score)" isAnimationActive={false} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ChartContainer>
              <div className="wb-project-readiness-list">
                {readinessScores.map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.score}%</strong><Progress aria-label={`${item.label} ${item.score}%`} value={item.score} /></div>)}
              </div>
            </>
          ) : (
            <div className="wb-project-readiness-empty"><FileTextIcon aria-hidden="true" /><strong>尚未建立要求基线</strong><span>上传招标文件并完成解析后，平台会在这里展示真实就绪度和缺口。</span><Button onClick={onUpload} size="sm" type="button" variant="outline">上传第一份资料</Button></div>
          )}
          <footer>{readiness ? `${readiness.counts.covered} / ${readiness.counts.total} 项要求已覆盖 · ${uncoveredEvidence} 项尚未覆盖` : "基于已识别要求和证据实时计算"}</footer>
        </section>
      </div>

      <section className="wb-project-next-actions" aria-labelledby="next-actions-title">
        <header className="wb-project-overview-section-head">
          <div><h2 id="next-actions-title">下一步处理</h2><p>只显示会影响投标推进的资料、要求与核验事项。</p></div>
          <Button onClick={() => onOpenRequirements("all")} size="xs" type="button" variant="ghost">全部要求<ArrowRightIcon aria-hidden="true" data-icon="inline-end" /></Button>
        </header>
        {actionItems.length ? <div className="wb-project-action-list">{actionItems.map((item) => {
          const Icon = item.icon;
          return <button className="wb-project-action-row" key={item.id} onClick={item.onClick} type="button"><span className={cn("wb-project-action-row__icon", item.id === "mandatory" || item.id === "failed" ? "is-attention" : "")}><Icon aria-hidden="true" className={item.id === "processing" ? "animate-spin" : undefined} /></span><span><strong>{item.title}</strong><small>{item.detail}</small></span><b>{item.count}</b><ChevronRightIcon aria-hidden="true" /></button>;
        })}</div> : <div className="wb-project-action-empty"><CheckCircle2Icon aria-hidden="true" /><span><strong>当前没有明确缺口</strong><small>继续在要求矩阵中跟进新增要求和证据变更。</small></span><Button onClick={() => onOpenRequirements("all")} size="sm" type="button" variant="outline">打开要求矩阵</Button></div>}
      </section>

      {documents.length ? <section className="wb-project-material-pulse" aria-labelledby="material-pulse-title">
        <header className="wb-project-overview-section-head"><div><h2 id="material-pulse-title">资料处理状态</h2><p>资料是后续要求识别、证据检索和交付起草的来源。</p></div><Button onClick={onOpenMaterials} size="xs" type="button" variant="ghost">管理资料<ArrowRightIcon aria-hidden="true" data-icon="inline-end" /></Button></header>
        <div className="wb-project-material-pulse__body"><div><span>已解析</span><strong>{parsedDocumentCount}</strong></div><div><span>处理中</span><strong>{processingDocumentCount}</strong></div><div className={failedDocumentCount ? "is-attention" : ""}><span>需处理</span><strong>{failedDocumentCount}</strong></div><p>{documents.slice(0, 2).map((document) => document.original_filename).join(" · ")}{documents.length > 2 ? ` · 另 ${documents.length - 2} 份` : ""}</p></div>
      </section> : null}

      {collaboration ? <section className="wb-project-material-pulse" aria-labelledby="collaboration-pulse-title">
        <header className="wb-project-overview-section-head">
          <div><h2 id="collaboration-pulse-title">团队协作状态</h2><p>责任分配、逾期事项和人工确认都从要求台账实时汇总。</p></div>
          <Button onClick={() => onOpenRequirements("verification")} size="xs" type="button" variant="ghost">处理待确认<ArrowRightIcon aria-hidden="true" data-icon="inline-end" /></Button>
        </header>
        <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-5">
          <div><span className="text-xs text-muted-foreground">协作成员</span><strong className="mt-1 block text-xl">{collaboration.members.length}</strong></div>
          <div><span className="text-xs text-muted-foreground">待分配要求</span><strong className={cn("mt-1 block text-xl", collaboration.unassigned_requirement_count > 0 && "text-amber-600")}>{collaboration.unassigned_requirement_count}</strong></div>
          <div><span className="text-xs text-muted-foreground">逾期要求</span><strong className={cn("mt-1 block text-xl", collaboration.overdue_requirement_count > 0 && "text-red-600")}>{collaboration.overdue_requirement_count}</strong></div>
          <div><span className="text-xs text-muted-foreground">待人工确认</span><strong className="mt-1 block text-xl">{collaboration.review_required_count}</strong></div>
          <div><span className="text-xs text-muted-foreground">活跃工作流</span><strong className="mt-1 block text-xl">{collaboration.active_workflow_count}</strong></div>
        </div>
      </section> : null}
    </div>
  );
}

function RequirementsSurface({
  filter,
  isError,
  onOpenRequirement,
  onFilterChange,
  readiness,
  requirements,
  selectedRequirementId,
  requirementDetail,
  requirementDetailLoading,
  requirementDetailError,
  onCloseRequirement,
  onVerifyExtraction,
  onVerifyEvidence,
  onVerifyClaim,
  requirementMutationPending,
}: {
  filter: RequirementFilter;
  isError: boolean;
  onOpenRequirement: (id: string) => void;
  onFilterChange: (filter: RequirementFilter) => void;
  readiness: BidReadinessSummary | undefined;
  requirements: RequirementItemRead[];
  selectedRequirementId: string | null;
  requirementDetail: RequirementDetailRead | undefined;
  requirementDetailLoading: boolean;
  requirementDetailError: boolean;
  onCloseRequirement: () => void;
  onVerifyExtraction: (requirement: RequirementDetailRead) => void;
  onVerifyEvidence: (requirementId: string, linkId: string) => void;
  onVerifyClaim: (requirementId: string, claimId: string) => void;
  requirementMutationPending: boolean;
}) {
  const mandatoryGapIds = useMemo(() => new Set(readiness?.mandatory_gaps.map((item) => item.id) ?? []), [readiness]);
  const evidenceGapIds = useMemo(() => new Set(readiness?.evidence_gaps.map((item) => item.id) ?? []), [readiness]);
  const visibleRequirements = useMemo(() => requirements.filter((requirement) => {
    if (filter === "all") return true;
    if (filter === "mandatory-gaps") return mandatoryGapIds.has(requirement.id);
    if (filter === "evidence-gaps") return evidenceGapIds.has(requirement.id);
    return requirement.verification_status !== "verified";
  }), [evidenceGapIds, filter, mandatoryGapIds, requirements]);

  return (
    <>
      <SurfaceHeader title="要求与合规" />
      <p className="wb-project-summary">每项要求都应有负责人、响应状态和可回溯证据。先处理缺口，再进入章节起草。</p>
      <Tabs className="wb-project-requirement-filters" onValueChange={(value) => onFilterChange(value as RequirementFilter)} value={filter}>
        <TabsList aria-label="要求矩阵筛选">
          <TabsTrigger value="all">全部 <small>{requirements.length}</small></TabsTrigger>
          <TabsTrigger value="mandatory-gaps">强制项缺口 <small>{mandatoryGapIds.size}</small></TabsTrigger>
          <TabsTrigger value="evidence-gaps">证据缺口 <small>{evidenceGapIds.size}</small></TabsTrigger>
          <TabsTrigger value="verification">待核验 <small>{readiness ? Math.max(0, readiness.counts.total - readiness.counts.verified) : "-"}</small></TabsTrigger>
        </TabsList>
      </Tabs>
      {isError ? <DataUnavailable label="要求清单" /> : null}
      {!isError && requirements.length === 0 ? <p className="wb-project-quiet-copy">尚未识别出要求。上传并解析 RFP 后会出现在这里。</p> : null}
      {!isError && requirements.length > 0 && visibleRequirements.length === 0 ? <p className="wb-project-quiet-copy">该筛选下暂时没有要求。</p> : null}
      {visibleRequirements.length > 0 ? (
        <div className="wb-project-lines" role="table" aria-label="项目要求">
          <div className="wb-project-lines__head" role="row">
            <span>要求</span><span>状态</span><span>证据来源</span><span>验证</span>
          </div>
          {visibleRequirements.map((requirement) => (
            <div
              className="wb-project-line wb-project-line--interactive"
              key={requirement.id}
              onClick={() => onOpenRequirement(requirement.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onOpenRequirement(requirement.id);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <div className="wb-project-line__primary">
                <FileCheck2Icon aria-hidden="true" />
                <span><strong>{requirement.requirement_text}</strong><small>{requirement.section_key}{requirement.owner_user_id ? " · 已分配负责人" : " · 待分配负责人"}</small></span>
              </div>
              <StatusMark status={requirement.status} />
              <span className="wb-project-line__muted">{requirement.source_document_name || "尚未关联"}</span>
              <StatusMark status={requirement.verification_status} />
            </div>
          ))}
        </div>
      ) : null}
      <RequirementInspectorSheet
        detail={requirementDetail}
        error={requirementDetailError}
        loading={requirementDetailLoading}
        onClose={onCloseRequirement}
        onVerifyClaim={onVerifyClaim}
        onVerifyEvidence={onVerifyEvidence}
        onVerifyExtraction={onVerifyExtraction}
        open={Boolean(selectedRequirementId)}
        mutationPending={requirementMutationPending}
      />
    </>
  );
}

function RequirementInspectorSheet({
  detail,
  error,
  loading,
  mutationPending,
  onClose,
  onVerifyClaim,
  onVerifyEvidence,
  onVerifyExtraction,
  open,
}: {
  detail: RequirementDetailRead | undefined;
  error: boolean;
  loading: boolean;
  mutationPending: boolean;
  onClose: () => void;
  onVerifyClaim: (requirementId: string, claimId: string) => void;
  onVerifyEvidence: (requirementId: string, linkId: string) => void;
  onVerifyExtraction: (requirement: RequirementDetailRead) => void;
  open: boolean;
}) {
  const profile = detail?.bid_profile;
  const verifiedEvidenceIds = new Set(
    detail?.evidence_links
      .filter((link) => link.relation_type === "supports" && link.verification_status === "verified")
      .map((link) => link.evidence_id) ?? [],
  );

  return (
    <Sheet onOpenChange={(nextOpen) => !nextOpen && onClose()} open={open}>
      <SheetContent className="wb-requirement-inspector" side="right">
        <SheetHeader className="wb-requirement-inspector__header">
          <SheetTitle>要求详情</SheetTitle>
          <SheetDescription>在当前项目上下文中核对原文、证据和响应责任。</SheetDescription>
        </SheetHeader>
        <div className="wb-requirement-inspector__body">
          {loading ? <div className="wb-requirement-inspector__loading"><span /><span /><span /></div> : null}
          {error ? <div className="wb-requirement-inspector__error">暂时无法读取这条要求的详情，请稍后重试。</div> : null}
          {detail ? (
            <div className="wb-requirement-inspector__content">
              <section className="wb-requirement-inspector__lead">
                <div className="wb-requirement-inspector__badges">
                  <StatusMark status={profile?.is_mandatory ? "mandatory" : "normal"} />
                  <StatusMark status={profile?.coverage_status ?? detail.status} />
                  <StatusMark status={detail.verification_status} />
                </div>
                <h2>{detail.requirement_text}</h2>
                <p>{detail.section_key} · 提取置信度 {detail.extraction_confidence === null ? "未评分" : `${formatScore(detail.extraction_confidence)}%`}</p>
                {detail.verification_status !== "verified" ? <Button disabled={mutationPending} onClick={() => onVerifyExtraction(detail)} size="sm" type="button" variant="outline"><ShieldCheckIcon aria-hidden="true" data-icon="inline-start" />确认要求已核验</Button> : null}
              </section>

              <section className="wb-requirement-inspector__section">
                <header><FileSearchIcon aria-hidden="true" /><h3>原文与定位</h3></header>
                <blockquote>{detail.original_text ?? detail.requirement_text}</blockquote>
                <dl>
                  <div><dt>来源文件</dt><dd>{detail.source_document_name ?? "尚未关联"}</dd></div>
                  <div><dt>原文位置</dt><dd>{formatLocator(detail.source_locator_json)}</dd></div>
                </dl>
              </section>

              <section className="wb-requirement-inspector__section">
                <header><CheckCircle2Icon aria-hidden="true" /><h3>责任与时限</h3></header>
                <dl>
                  <div><dt>负责人</dt><dd>{detail.owner_user_id ?? "待分配"}</dd></div>
                  <div><dt>审核人</dt><dd>{detail.reviewer_user_id ?? "待分配"}</dd></div>
                  <div><dt>截止时间</dt><dd>{detail.due_at ? new Date(detail.due_at).toLocaleString("zh-CN") : "未设置"}</dd></div>
                  <div><dt>风险级别</dt><dd>{profile?.risk_level ?? "未设置"}</dd></div>
                </dl>
              </section>

              <section className="wb-requirement-inspector__section">
                <header><FileCheck2Icon aria-hidden="true" /><h3>证据引用 <small>{detail.evidence_links.length}</small></h3></header>
                {detail.evidence_links.length ? <div className="wb-requirement-trace-list">{detail.evidence_links.map((link) => (
                  <article key={link.id}>
                    <div><StatusMark status={link.verification_status} /><small>{link.source_document_name ?? "未知来源"}</small></div>
                    <p>{link.quote_text}</p>
                    <span>{formatLocator(link.locator_json)}</span>
                    {link.verification_status !== "verified" ? <Button disabled={mutationPending} onClick={() => onVerifyEvidence(detail.id, link.id)} size="xs" type="button" variant="outline"><ShieldCheckIcon aria-hidden="true" data-icon="inline-start" />核验证据</Button> : null}
                  </article>
                ))}</div> : <p className="wb-requirement-inspector__empty">还没有可回溯的证据。先在资料中补充来源，才能形成可审计响应。</p>}
              </section>

              <section className="wb-requirement-inspector__section">
                <header><ShieldCheckIcon aria-hidden="true" /><h3>响应主张 <small>{detail.claims.length}</small></h3></header>
                {detail.claims.length ? <div className="wb-requirement-trace-list">{detail.claims.map((claim) => {
                  const evidenceReady = claim.claim_type !== "factual" || (claim.evidence_ids.length > 0 && claim.evidence_ids.every((evidenceId) => verifiedEvidenceIds.has(evidenceId)));
                  return <article key={claim.id}><div><StatusMark status={claim.status} /><small>{claim.created_by_actor === "ai" ? "AI 建议" : "团队主张"}</small></div><p>{claim.claim_text}</p>{claim.status !== "verified" ? <Button disabled={mutationPending || !evidenceReady} onClick={() => onVerifyClaim(detail.id, claim.id)} size="xs" type="button" variant="outline"><ShieldCheckIcon aria-hidden="true" data-icon="inline-start" />核验主张</Button> : null}{!evidenceReady ? <span>先核验证据后再确认事实主张。</span> : null}</article>;
                })}</div> : <p className="wb-requirement-inspector__empty">当前没有生成的响应主张。</p>}
              </section>
            </div>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function EvidenceSurface({
  bundles,
  bundleActionPending,
  documents,
  documentsLoading,
  evidence,
  isError,
  onOpenDocument,
  onReindex,
  onReingest,
  onUpload,
  parsedAssets,
  parsedAssetsError,
  parsedAssetsLoading,
  selectedDocument,
  onCloseDocument,
}: {
  bundles: BundleRead[];
  bundleActionPending: (bundleId: string) => boolean;
  documents: SourceDocumentRead[];
  documentsLoading: boolean;
  evidence: Awaited<ReturnType<typeof listEvidence>>;
  isError: boolean;
  onOpenDocument: (id: string) => void;
  onReindex: (bundleId: string) => void;
  onReingest: (bundleId: string) => void;
  onUpload: () => void;
  parsedAssets: ParsedAssetRead[] | undefined;
  parsedAssetsError: boolean;
  parsedAssetsLoading: boolean;
  selectedDocument: SourceDocumentRead | undefined;
  onCloseDocument: () => void;
}) {
  const parsedCount = documents.filter((document) => document.parse_status === "parsed").length;
  const storedArtifactCount = documents.filter((document) => document.parse_status === "not_applicable").length;
  const processingCount = documents.filter((document) => (
    document.parse_status !== "parsed" && document.parse_status !== "failed" && document.parse_status !== "not_applicable"
  ) || document.index_status === "indexing").length;
  const failedCount = documents.filter((document) => (
    document.parse_status === "failed" || ["failed", "degraded"].includes(document.index_status)
  )).length;

  return (
    <>
      <div className="wb-project-surface-heading wb-material-heading">
        <div><h1>资料</h1><p>确认资料已经可用，再进入要求、证据和章节工作。</p></div>
        <Button onClick={onUpload} size="sm" type="button"><UploadIcon aria-hidden="true" data-icon="inline-start" />上传资料</Button>
      </div>
      {isError ? <DataUnavailable label="资料与证据" /> : null}
      {!isError && bundles.length === 0 ? <div className="wb-material-empty"><FolderOpenIcon aria-hidden="true" /><strong>还没有资料包</strong><p>上传 RFP、资质文件和历史响应后，平台会自动解析并建立可回溯的来源。</p><Button onClick={onUpload} size="sm" type="button" variant="outline">上传第一份资料</Button></div> : null}
      {bundles.length > 0 ? (
        <>
          <section className="wb-material-health" aria-labelledby="material-health-title">
            <header className="wb-project-overview-section-head"><div><h2 id="material-health-title">处理健康</h2><p>这些数字回答“资料现在能不能继续用于投标工作”。</p></div><span className="wb-material-health__updated">实时状态</span></header>
            <div className="wb-material-health__metrics"><div><span>已解析</span><strong>{parsedCount}</strong><small>可用于要求识别</small></div><div><span>已归档</span><strong>{storedArtifactCount}</strong><small>可下载，不参与解析</small></div><div><span>处理中</span><strong>{processingCount}</strong><small>等待后台完成</small></div><div className={failedCount ? "is-attention" : ""}><span>需重试</span><strong>{failedCount}</strong><small>{failedCount ? "不会参与检索" : "没有失败资料"}</small></div></div>
          </section>
          <section className="wb-project-summary-section wb-material-bundles" aria-labelledby="material-bundles-title">
            <header className="wb-project-overview-section-head"><div><h2 id="material-bundles-title">资料包</h2><p>按来源分组管理解析和索引任务。</p></div></header>
            <div className="wb-material-bundle-list">
              {bundles.map((bundle) => {
                const bundleDocuments = documents.filter((document) => document.bundle_id === bundle.id);
                const hasFailedDocument = bundleDocuments.some((document) => document.parse_status === "failed");
                const hasIndexFailure = bundleDocuments.some((document) => (
                  document.parse_status === "parsed" && ["failed", "degraded"].includes(document.index_status)
                ));
                const hasIndexGap = bundleDocuments.some((document) => document.parse_status === "parsed" && document.index_status !== "indexed");
                const canReingest = bundle.ingest_status === "failed" || hasFailedDocument;
                const canReindex = !canReingest
                  && !["queued", "running", "indexing"].includes(bundle.ingest_status)
                  && hasIndexGap;
                return (
                  <article className="wb-material-bundle" key={bundle.id}>
                    <div className="wb-material-bundle__head">
                      <div className="wb-project-line__primary"><FolderOpenIcon aria-hidden="true" /><span><strong>{bundle.label}</strong><small>{bundle.source_type} · {bundleDocuments.length} 份源文档</small></span></div>
                      <StatusMark status={bundle.ingest_status} />
                      <div className="wb-material-bundle__actions">
                        {canReingest ? <Button disabled={bundleActionPending(bundle.id)} onClick={() => onReingest(bundle.id)} size="xs" type="button" variant="outline"><RefreshCwIcon aria-hidden="true" data-icon="inline-start" />重新解析</Button> : null}
                        {canReindex ? <Button disabled={bundleActionPending(bundle.id)} onClick={() => onReindex(bundle.id)} size="xs" type="button" variant="ghost"><RefreshCwIcon aria-hidden="true" data-icon="inline-start" />重建索引</Button> : null}
                      </div>
                    </div>
                    {hasFailedDocument ? <p className="wb-material-bundle__error"><FileWarningIcon aria-hidden="true" />{bundleDocuments.find((document) => document.parse_status === "failed")?.parse_error_detail ?? "部分资料解析失败，请重新解析后再继续。"}</p> : null}
                    {!hasFailedDocument && hasIndexFailure ? <p className="wb-material-bundle__error"><FileWarningIcon aria-hidden="true" />检索索引未完成。可重建索引；资料文本与已识别的要求不会丢失。</p> : null}
                  </article>
                );
              })}
            </div>
          </section>
          <section className="wb-project-summary-section wb-material-documents" aria-labelledby="material-documents-title">
            <header className="wb-project-overview-section-head"><div><h2 id="material-documents-title">源文档</h2><p>点击一份资料查看解析器、预览和版本血缘。</p></div></header>
            {documentsLoading ? <p className="wb-project-quiet-copy">正在读取源文档…</p> : null}
            {!documentsLoading && documents.length === 0 ? <p className="wb-project-quiet-copy">当前资料包还没有源文档。</p> : null}
            {documents.length > 0 ? <div className="wb-project-lines wb-project-lines--documents" role="table" aria-label="源文档"><div className="wb-project-lines__head" role="row"><span>文件</span><span>解析</span><span>索引</span><span>版本</span></div>{documents.map((document) => <div className="wb-project-line wb-project-line--interactive" key={document.id} onClick={() => onOpenDocument(document.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onOpenDocument(document.id); } }} role="button" tabIndex={0}><div className="wb-project-line__primary"><FileTextIcon aria-hidden="true" /><span><strong>{document.original_filename}</strong><small>{document.mime_type} · {document.parse_attempt_count} 次尝试</small></span></div><StatusMark status={document.parse_status} /><StatusMark status={document.index_status} /><span className="wb-project-line__muted">v{document.version_number}</span></div>)}</div> : null}
          </section>
        </>
      ) : null}
      <section className="wb-project-summary-section" aria-labelledby="evidence-results-title">
        <header className="wb-project-overview-section-head"><div><h2 id="evidence-results-title">已检索证据</h2><p>要求详情会显示每条证据的来源和核验状态。</p></div></header>
        {evidence.length === 0 ? <p className="wb-project-quiet-copy">当前没有可引用证据片段。</p> : null}
        {evidence.length > 0 ? <div className="wb-evidence-list">{evidence.slice(0, 20).map((item) => <div className="wb-evidence-line" key={item.id}><FileTextIcon aria-hidden="true" /><p>{item.quote_text}</p><small>{item.confidence === null ? "未评分" : `${Math.round(item.confidence * 100)}%`}</small></div>)}</div> : null}
      </section>
      <DocumentInspectorSheet assets={parsedAssets} error={parsedAssetsError} loading={parsedAssetsLoading} onClose={onCloseDocument} open={Boolean(selectedDocument)} document={selectedDocument} />
    </>
  );
}

function DocumentInspectorSheet({ assets, document, error, loading, onClose, open }: { assets: ParsedAssetRead[] | undefined; document: SourceDocumentRead | undefined; error: boolean; loading: boolean; onClose: () => void; open: boolean }) {
  const preview = formatAssetPreview(assets?.[0]);
  return (
    <Sheet onOpenChange={(nextOpen) => !nextOpen && onClose()} open={open}>
      <SheetContent className="wb-document-inspector" side="right">
        <SheetHeader className="wb-document-inspector__header"><SheetTitle>文档详情</SheetTitle><SheetDescription>查看解析状态、预览内容和版本来源。</SheetDescription></SheetHeader>
        <div className="wb-document-inspector__body">
          {document ? <div className="wb-document-inspector__content">
            <section className="wb-document-inspector__lead"><div className="wb-document-inspector__file"><FileTextIcon aria-hidden="true" /><div><h2>{document.original_filename}</h2><p>{document.mime_type}</p></div></div><div className="wb-document-inspector__badges"><StatusMark status={document.parse_status} /><StatusMark status={document.index_status} /></div></section>
            <section className="wb-document-inspector__section"><header><FileClockIcon aria-hidden="true" /><h3>处理信息</h3></header><dl><div><dt>解析器</dt><dd>{document.parse_status === "not_applicable" ? "该附件无需文本解析" : (document.parser_name ?? "尚未运行")}{document.parser_version ? ` · ${document.parser_version}` : ""}</dd></div><div><dt>解析尝试</dt><dd>{document.parse_attempt_count} 次</dd></div><div><dt>当前版本</dt><dd>v{document.version_number}</dd></div><div><dt>被替代版本</dt><dd>{document.supersedes_document_id ?? "无"}</dd></div></dl>{document.parse_error_detail ? <p className="wb-document-inspector__error"><FileWarningIcon aria-hidden="true" />{document.parse_error_detail}</p> : null}</section>
            <section className="wb-document-inspector__section"><header><FileSearchIcon aria-hidden="true" /><h3>解析预览</h3></header>{document.parse_status === "not_applicable" ? <p className="wb-document-inspector__empty">此文件已作为项目附件归档，可下载使用；当前格式不参与文本解析、要求识别或证据检索。</p> : <>{loading ? <div className="wb-document-inspector__loading"><span /><span /><span /></div> : null}{error ? <p className="wb-document-inspector__error">暂时无法读取解析结果。</p> : null}{!loading && !error && preview ? <pre className="wb-document-inspector__preview">{preview.slice(0, 8000)}</pre> : null}{!loading && !error && !preview ? <p className="wb-document-inspector__empty">这份资料还没有可预览的解析文本，完成解析后会自动出现。</p> : null}</>}</section>
          </div> : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function ResponseSurface({
  addSectionPending,
  createDeliverablePending,
  deliverables,
  draftPending,
  onAddSection,
  onCloseSection,
  onCreateDeliverable,
  onDraftSection,
  onOpenRequirement,
  onOpenReview,
  selectedDeliverableId,
  onSelectDeliverable,
  onSelectSection,
  workflowOptions,
  onWorkflowOptionsChange,
  providers,
  responsePlan,
  sections,
  sectionVersions,
  sectionVersionsError,
  sectionVersionsLoading,
  selectedSectionId,
}: {
  addSectionPending: boolean;
  createDeliverablePending: boolean;
  deliverables: DeliverableRead[];
  draftPending: boolean;
  onAddSection: (deliverableId: string, title: string, sectionKey: string) => void;
  onCloseSection: () => void;
  onCreateDeliverable: () => void;
  onDraftSection: (section: DeliverableSectionRead, hasVersions: boolean) => void;
  onOpenRequirement: (requirementId: string) => void;
  onOpenReview: (sectionId: string) => void;
  selectedDeliverableId: string | null;
  onSelectDeliverable: (id: string) => void;
  onSelectSection: (id: string) => void;
  workflowOptions: WorkflowRunOptions;
  onWorkflowOptionsChange: (next: WorkflowRunOptions) => void;
  providers: ProviderConfig[];
  responsePlan: ResponsePlanDetailRead | undefined;
  sections: Awaited<ReturnType<typeof listDeliverableSections>>;
  sectionVersions: SectionVersionRead[] | undefined;
  sectionVersionsError: boolean;
  sectionVersionsLoading: boolean;
  selectedSectionId: string | null;
}) {
  const [sectionTitle, setSectionTitle] = useState("");
  const [sectionKey, setSectionKey] = useState("");
  const planSections = useMemo(
    () => new Map((responsePlan?.sections ?? []).map((section) => [section.deliverable_section_id, section])),
    [responsePlan?.sections],
  );

  return (
    <>
      <SurfaceHeader
        action={<Button disabled={createDeliverablePending} onClick={onCreateDeliverable} size="sm" type="button"><PlusIcon aria-hidden="true" data-icon="inline-start" />新建交付物</Button>}
        title="章节"
      />
      <WorkflowRunControls onChange={onWorkflowOptionsChange} options={workflowOptions} providers={providers} />
      {deliverables.length === 0 ? (
        <section className="wb-project-empty-state">
          <FileOutputIcon aria-hidden="true" />
          <strong>先建立响应文件</strong>
          <p>交付物决定章节、审核和最终导出的边界；创建后不会自动开始起草。</p>
        </section>
      ) : null}
      {deliverables.length > 0 ? (
        <div className="wb-response-layout">
          <div className="wb-response-list">
            {deliverables.map((deliverable) => (
              <button
                className={cn("wb-response-list-row", selectedDeliverableId === deliverable.id && "is-selected")}
                key={deliverable.id}
                onClick={() => onSelectDeliverable(deliverable.id)}
                type="button"
              >
                <FileOutputIcon aria-hidden="true" />
                <span><strong>{deliverable.title}</strong><small>{displayDeliverableType(deliverable.type)}</small></span>
                <StatusMark status={deliverable.status} />
              </button>
            ))}
          </div>
          <div className="wb-response-sections">
            <div className="wb-response-sections__head"><div><p className="wb-section-heading">章节</p><small>先确认要求和证据是否已经落到响应结构中。</small></div><span>{sections.length} 个</span></div>
            {selectedDeliverableId ? (
              <form
                className="flex flex-wrap items-end gap-2 border-b pb-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  const title = sectionTitle.trim();
                  const key = sectionKey.trim();
                  if (!title || !key) return;
                  onAddSection(selectedDeliverableId, title, key);
                  setSectionTitle("");
                  setSectionKey("");
                }}
              >
                <Input
                  aria-label="章节标题"
                  className="min-w-48 flex-1"
                  onChange={(event) => {
                    const value = event.target.value;
                    setSectionTitle(value);
                    if (!sectionKey) setSectionKey(toSectionKey(value));
                  }}
                  placeholder="例如：技术方案"
                  value={sectionTitle}
                />
                <Input
                  aria-label="章节标识"
                  className="min-w-40 flex-1"
                  onChange={(event) => setSectionKey(toSectionKey(event.target.value))}
                  placeholder="technical-approach"
                  value={sectionKey}
                />
                <Button disabled={!sectionTitle.trim() || !sectionKey.trim() || addSectionPending} size="sm" type="submit">
                  <PlusIcon aria-hidden="true" data-icon="inline-start" />添加章节
                </Button>
              </form>
            ) : null}
            {sections.length === 0 ? <p className="wb-project-quiet-copy">此交付物暂无章节。</p> : null}
            {sections.map((section) => {
              const planSection = planSections.get(section.id);
              return <button className={cn("wb-response-section-row", selectedSectionId === section.id && "is-selected")} key={section.id} onClick={() => onSelectSection(section.id)} type="button">
                <span className="wb-section-order">{section.sort_order ?? "-"}</span>
                <span className="wb-response-section-row__copy"><strong>{section.title}</strong><small>{planSection ? `${planSection.requirements.length} 项要求 · ${planSection.evidence_bindings.length} 组证据` : "尚未进入响应计划"}</small></span>
                <StatusMark status={section.status} />
                <ArrowRightIcon aria-hidden="true" />
              </button>;
            })}
          </div>
        </div>
      ) : null}
      <SectionInspectorSheet
        draftPending={draftPending}
        onClose={onCloseSection}
        onDraftSection={onDraftSection}
        onOpenRequirement={onOpenRequirement}
        onOpenReview={onOpenReview}
        open={Boolean(selectedSectionId)}
        responsePlan={responsePlan}
        section={sections.find((item) => item.id === selectedSectionId)}
        sectionVersions={sectionVersions}
        sectionVersionsError={sectionVersionsError}
        sectionVersionsLoading={sectionVersionsLoading}
        workflowOptions={workflowOptions}
        onWorkflowOptionsChange={onWorkflowOptionsChange}
        providers={providers}
      />
    </>
  );
}

function SectionInspectorSheet({
  draftPending,
  onClose,
  onDraftSection,
  onOpenRequirement,
  onOpenReview,
  open,
  responsePlan,
  section,
  sectionVersions,
  sectionVersionsError,
  sectionVersionsLoading,
  workflowOptions,
  onWorkflowOptionsChange,
  providers,
}: {
  draftPending: boolean;
  onClose: () => void;
  onDraftSection: (section: DeliverableSectionRead, hasVersions: boolean) => void;
  onOpenRequirement: (requirementId: string) => void;
  onOpenReview: (sectionId: string) => void;
  open: boolean;
  responsePlan: ResponsePlanDetailRead | undefined;
  section: DeliverableSectionRead | undefined;
  sectionVersions: SectionVersionRead[] | undefined;
  sectionVersionsError: boolean;
  sectionVersionsLoading: boolean;
  workflowOptions: WorkflowRunOptions;
  onWorkflowOptionsChange: (next: WorkflowRunOptions) => void;
  providers: ProviderConfig[];
}) {
  const planSection = responsePlan?.sections.find((item) => item.deliverable_section_id === section?.id);
  const versions = [...(sectionVersions ?? [])].sort((left, right) => right.version_number - left.version_number);
  const latestVersion = versions[0];
  const mappedRequirements = planSection?.requirements ?? [];
  const evidenceBindings = planSection?.evidence_bindings ?? [];

  return (
    <Sheet onOpenChange={(nextOpen) => !nextOpen && onClose()} open={open}>
      <SheetContent className="wb-section-inspector" side="right">
        <SheetHeader className="wb-section-inspector__header"><SheetTitle>章节详情</SheetTitle><SheetDescription>从要求、证据到版本，确认这一节是否可以进入审阅。</SheetDescription></SheetHeader>
        <div className="wb-section-inspector__body">
          {section ? <div className="wb-section-inspector__content">
            <section className="wb-section-inspector__lead"><div><span className="wb-section-inspector__eyebrow">{section.section_key}</span><h2>{section.title}</h2></div><StatusMark status={section.status} /></section>
            <WorkflowRunControls onChange={onWorkflowOptionsChange} options={workflowOptions} providers={providers} />
            <div className="wb-section-inspector__actions"><Button disabled={draftPending} onClick={() => onDraftSection(section, versions.length > 0)} size="sm" type="button"><FileCheck2Icon aria-hidden="true" data-icon="inline-start" />{versions.length ? "重新生成草稿" : "生成初稿"}</Button><Button onClick={() => onOpenReview(section.id)} size="sm" type="button" variant="outline"><ShieldCheckIcon aria-hidden="true" data-icon="inline-start" />进入审阅</Button></div>
            <section className="wb-section-inspector__section"><header><FileSearchIcon aria-hidden="true" /><h3>要求覆盖 <small>{mappedRequirements.length}</small></h3></header>{mappedRequirements.length ? <div className="wb-section-inspector__requirement-list">{mappedRequirements.map((requirement) => <button key={requirement.id} onClick={() => onOpenRequirement(requirement.requirement_id)} type="button"><span>{requirement.requirement_text}</span><StatusMark status={requirement.verification_status} /><ArrowRightIcon aria-hidden="true" /></button>)}</div> : <p className="wb-section-inspector__empty">响应计划还没有把要求映射到这一节。</p>}</section>
            <section className="wb-section-inspector__section"><header><FileCheck2Icon aria-hidden="true" /><h3>证据绑定 <small>{evidenceBindings.length}</small></h3></header>{evidenceBindings.length ? <div className="wb-section-inspector__binding-list">{evidenceBindings.map((binding) => <article key={binding.id}><div><strong>证据集合</strong><StatusMark status={binding.evidence_set_status} /></div><small>第 {binding.generation_iteration} 轮 · {binding.unmet_requirement_ids.length ? `还有 ${binding.unmet_requirement_ids.length} 项要求缺证据` : "没有未满足要求"}</small>{binding.degraded_reasons.length ? <p>{binding.degraded_reasons.join("；")}</p> : null}</article>)}</div> : <p className="wb-section-inspector__empty">还没有证据绑定；没有证据的章节不应直接进入最终导出。</p>}</section>
            <section className="wb-section-inspector__section"><header><HistoryIcon aria-hidden="true" /><h3>正文版本 <small>{versions.length}</small></h3></header>{sectionVersionsLoading ? <p className="wb-project-quiet-copy">正在读取版本…</p> : null}{sectionVersionsError ? <p className="wb-section-inspector__error">暂时无法读取正文版本。</p> : null}{!sectionVersionsLoading && !sectionVersionsError && !versions.length ? <p className="wb-section-inspector__empty">尚未生成正文。可以先生成初稿，再进入审阅。</p> : null}{latestVersion ? <div className="wb-section-inspector__version-preview"><div><strong>v{latestVersion.version_number}</strong><span>{latestVersion.created_by_actor === "ai" ? "AI 草稿" : latestVersion.created_by_actor}</span><small>{section.approved_version_id === latestVersion.id ? "已批准" : "待审阅"}</small></div><pre>{latestVersion.content_markdown?.trim() || "此版本没有可展示的正文。"}</pre>{versions.length > 1 ? <p>还有 {versions.length - 1} 个历史版本，可在版本对比工作面继续查看。</p> : null}</div> : null}</section>
          </div> : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function WorkflowSurface({
  events,
  eventsError,
  eventsLoading,
  onOpenAgent,
  onSelectRun,
  runs,
  selectedRunId,
  workflowOptions,
  onWorkflowOptionsChange,
  providers,
}: {
  events: RuntimeEventRead[];
  eventsError: boolean;
  eventsLoading: boolean;
  onOpenAgent: () => void;
  onSelectRun: (runtimeRunId: string) => void;
  runs: ExecutionRunRead[];
  selectedRunId: string | null;
  workflowOptions: WorkflowRunOptions;
  onWorkflowOptionsChange: (next: WorkflowRunOptions) => void;
  providers: ProviderConfig[];
}) {
  const selectedRun = runs.find((run) => run.runtime_run_id === selectedRunId) ?? runs[0];
  const orderedEvents = [...events].sort((left, right) => right.sequence - left.sequence);
  const completedStages = RESPONSE_WORKFLOW_STAGES.filter((stage) => workflowStageState(stage.key, events) === "complete").length;
  const currentStage = RESPONSE_WORKFLOW_STAGES.find((stage) => {
    const state = workflowStageState(stage.key, events);
    return state === "active" || state === "review" || state === "attention";
  });
  const agentNodes = workflowAgentNodes(events);
  const currentAgentNode = agentNodes.find((node) => node.status === "running")?.name ?? null;
  const isWaitingApproval = agentNodes.some((node) => node.name === "human_approval" && node.status === "running");

  return (
    <>
      <SurfaceHeader title="响应工作流" />
      <p className="wb-project-summary">这里展示招标响应从资料到交付的真实执行进度。LangGraph 负责编排，项目运行记录负责留下可追溯结果；你只需要在需要确认的节点接管。</p>
      <WorkflowRunControls onChange={onWorkflowOptionsChange} options={workflowOptions} providers={providers} />
      {runs.length === 0 ? (
        <section className="wb-workflow-empty">
          <BotIcon aria-hidden="true" />
          <strong>还没有响应工作流运行</strong>
          <p>上传并解析招标资料后，可以让 Agent 生成响应计划或起草章节。每次执行都会在这里留下阶段进度和结果。</p>
          <Button onClick={onOpenAgent} size="sm" type="button"><BotIcon aria-hidden="true" data-icon="inline-start" />打开 Agent</Button>
        </section>
      ) : (
        <section className="wb-workflow-shell" aria-label="响应工作流运行">
          <div className="wb-workflow-runs">
            <header className="wb-workflow-runs__head">
              <div><h2>运行记录</h2><p>选择一次执行查看它经过的业务阶段。</p></div>
              <span>{runs.length} 次</span>
            </header>
            <div className="wb-workflow-run-list">
              {runs.map((run) => {
                const runtimeRunId = run.runtime_run_id;
                const isSelected = runtimeRunId
                  ? runtimeRunId === selectedRun?.runtime_run_id
                  : !selectedRun?.runtime_run_id && run.id === selectedRun?.id;
                return (
                  <button
                    aria-pressed={isSelected}
                    className={cn("wb-workflow-run-row", isSelected && "is-selected", !runtimeRunId && "is-unavailable")}
                    disabled={!runtimeRunId}
                    key={run.id}
                    onClick={() => runtimeRunId && onSelectRun(runtimeRunId)}
                    type="button"
                  >
                    <span className="wb-workflow-run-row__marker" aria-hidden="true"><i /></span>
                    <span className="wb-workflow-run-row__copy"><strong>{displayRunType(run.run_type)}</strong><small>{workflowRunContext(run)} · 第 {run.attempt_number} 次尝试{runtimeRunId ? "" : " · 暂无事件流"}</small></span>
                    <StatusMark status={run.status} />
                  </button>
                );
              })}
            </div>
          </div>

          <div className="wb-workflow-detail">
            {selectedRun ? (
              <>
                <header className="wb-workflow-detail__head">
                  <div><p className="wb-section-heading">{displayRunType(selectedRun.run_type)}</p><h2>{workflowRunContext(selectedRun)}</h2><p>运行编号 {selectedRun.id.slice(0, 8)} · {selectedRun.attempt_number} 次尝试</p></div>
                  <StatusMark status={selectedRun.status} />
                </header>
                <div className="wb-workflow-progress">
                  <div><span>阶段完成度</span><strong>{completedStages}/{RESPONSE_WORKFLOW_STAGES.length}</strong></div>
                  <Progress aria-label="工作流阶段完成度" value={(completedStages / RESPONSE_WORKFLOW_STAGES.length) * 100} />
                  <small>{currentStage ? `当前：${currentStage.label}` : selectedRun.status === "succeeded" ? "本次运行已结束" : selectedRun.runtime_run_id ? "等待后台事件" : "这条历史记录没有可关联的事件流"}</small>
                </div>
                <section className="mt-5" aria-label="LangGraph 节点拓扑">
                  <div className="mb-3 flex items-baseline justify-between gap-3"><div><h3 className="text-sm font-medium">节点执行拓扑</h3><p className="mt-1 text-xs text-muted-foreground">拖动仅调整当前浏览视图；运行路径、审批边界与状态均来自持久化事件。</p></div><span className="text-xs text-muted-foreground">Trace {selectedRun.runtime_run_id?.slice(0, 8)}</span></div>
                  <WorkflowCanvas currentNode={currentAgentNode} isWaitingApproval={isWaitingApproval} nodes={agentNodes} />
                </section>
                <div className="wb-workflow-stage-list" aria-label="响应阶段">
                  {RESPONSE_WORKFLOW_STAGES.map((stage, index) => {
                    const state = workflowStageState(stage.key, events);
                    const StageIcon = stage.icon;
                    const stageEvent = events.filter((event) => workflowEventNode(event) === stage.key).sort((left, right) => right.sequence - left.sequence)[0];
                    return (
                      <div className={cn("wb-workflow-stage", `is-${state}`)} key={stage.key}>
                        <div className="wb-workflow-stage__rail" aria-hidden="true"><span><StageIcon /></span>{index < RESPONSE_WORKFLOW_STAGES.length - 1 ? <i /> : null}</div>
                        <div className="wb-workflow-stage__copy"><div><strong>{stage.label}</strong><StatusMark status={workflowStatusValue(state)} /></div><p>{stageEvent?.public_summary || stage.detail}</p></div>
                      </div>
                    );
                  })}
                </div>
                <section className="wb-workflow-events" aria-labelledby="workflow-events-title">
                  <header><div><h3 id="workflow-events-title">执行记录</h3><p>只显示对项目有意义的公开进度，不展示模型内部思考。</p></div>{eventsLoading ? <LoaderCircleIcon aria-label="正在读取" className="wb-spin-icon" /> : null}</header>
                  {eventsError ? <p className="wb-project-data-unavailable">暂时无法读取这次运行的事件记录。</p> : null}
                  {!eventsLoading && !eventsError && orderedEvents.length === 0 ? <p className="wb-project-quiet-copy">{selectedRun.runtime_run_id ? "这次运行还没有可展示的事件。" : "这条历史运行没有关联事件流；新运行会在此记录 LangGraph 阶段。"}</p> : null}
                  {!eventsLoading && !eventsError && orderedEvents.length > 0 ? <div className="wb-workflow-event-list">{orderedEvents.slice(0, 12).map((event) => <div className="wb-workflow-event-row" key={event.event_id}><span>{workflowEventStageLabel(event)}</span><p>{event.public_summary}</p><small>{formatWorkflowTime(event.timestamp)}</small></div>)}</div> : null}
                </section>
              </>
            ) : <p className="wb-project-quiet-copy">选择一条运行记录。</p>}
          </div>
        </section>
      )}
    </>
  );
}

function ReviewSurface({
  readiness,
  runs,
  sections,
  sectionVersions,
  selectedSectionId,
  onSelectSection,
  onSubmitDecision,
  submitDecisionPending,
}: {
  readiness: Awaited<ReturnType<typeof getReadinessSummary>> | undefined;
  runs: ExecutionRunRead[];
  sections: DeliverableSectionRead[];
  sectionVersions: SectionVersionRead[] | undefined;
  selectedSectionId: string | null;
  onSelectSection: (sectionId: string) => void;
  onSubmitDecision: (sectionId: string, sectionVersionId: string, decision: "approved" | "rejected", comment: string | null) => void;
  submitDecisionPending: boolean;
}) {
  const [comment, setComment] = useState("");
  const needsReview = runs.filter((run) => toneForStatus(run.status) === "review");
  const selectedSection = sections.find((section) => section.id === selectedSectionId) ?? null;
  const latestVersion = [...(sectionVersions ?? [])].sort((left, right) => right.version_number - left.version_number)[0] ?? null;
  const unresolved = readiness
    ? [...readiness.contradictions, ...readiness.mandatory_gaps, ...readiness.evidence_gaps].slice(0, 20)
    : [];

  return (
    <>
      <SurfaceHeader title="审阅" />
      <section className="wb-project-summary-section">
        <header className="wb-project-overview-section-head"><div><h2>章节审核</h2><p>审核决定始终绑定当前展示的不可变草稿版本，避免误批后续重生成的内容。</p></div></header>
        {sections.length === 0 ? <p className="wb-project-quiet-copy">当前交付物还没有章节。先创建章节并生成草稿。</p> : null}
        {sections.length > 0 ? (
          <div className="flex flex-col gap-3">
            <Select onValueChange={(value) => value && onSelectSection(value)} value={selectedSectionId ?? undefined}>
              <SelectTrigger aria-label="选择审核章节"><SelectValue placeholder="选择要审核的章节" /></SelectTrigger>
              <SelectContent><SelectGroup>{sections.map((section) => <SelectItem key={section.id} value={section.id}>{section.title}</SelectItem>)}</SelectGroup></SelectContent>
            </Select>
            {!selectedSection ? <p className="wb-project-quiet-copy">选择一节草稿后，即可查看正文并提交审核决定。</p> : null}
            {selectedSection && !latestVersion ? <p className="wb-project-quiet-copy">“{selectedSection.title}”尚未生成草稿，不能提交审核决定。</p> : null}
            {selectedSection && latestVersion ? (
              <div className="wb-section-inspector__version-preview">
                <div><strong>v{latestVersion.version_number}</strong><span>{latestVersion.created_by_actor === "ai" ? "AI 草稿" : latestVersion.created_by_actor}</span><small>{selectedSection.approved_version_id === latestVersion.id ? "已批准" : "待审阅"}</small></div>
                <pre>{latestVersion.content_markdown?.trim() || "此版本没有可展示的正文。"}</pre>
                <div className="flex flex-wrap items-center gap-2">
                  <Input aria-label="审核意见" onChange={(event) => setComment(event.target.value)} placeholder="可选：说明通过依据或退回原因" value={comment} />
                  <Button
                    disabled={submitDecisionPending || selectedSection.approved_version_id === latestVersion.id}
                    onClick={() => onSubmitDecision(selectedSection.id, latestVersion.id, "approved", comment.trim() || null)}
                    size="sm"
                    type="button"
                  >
                    <CheckCircle2Icon aria-hidden="true" data-icon="inline-start" />批准版本
                  </Button>
                  <Button
                    disabled={submitDecisionPending}
                    onClick={() => onSubmitDecision(selectedSection.id, latestVersion.id, "rejected", comment.trim() || null)}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    <RefreshCwIcon aria-hidden="true" data-icon="inline-start" />退回重写
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
      <section className="wb-project-summary-section">
        <h2>等待人工处理的运行</h2>
        {needsReview.length === 0 ? <p className="wb-project-quiet-copy">没有等待审批的运行。</p> : null}
        {needsReview.map((run) => (
          <div className="wb-project-attention-list" key={run.id}>
            <div><ShieldAlertIcon aria-hidden="true" /><span>{displayRunType(run.run_type)}</span><StatusMark status={run.status} /></div>
          </div>
        ))}
      </section>
      <section className="wb-project-summary-section">
        <h2>要求与证据问题</h2>
        {unresolved.length === 0 ? <p className="wb-project-quiet-copy">当前没有由就绪度计算发现的冲突或强制项缺口。</p> : null}
        {unresolved.map((item) => (
          <div className="wb-project-attention-list" key={item.id}>
            <div><AlertCircleIcon aria-hidden="true" /><span>{item.requirement_text}</span><StatusMark status={item.evidence_status || item.coverage_status} /></div>
          </div>
        ))}
      </section>
    </>
  );
}

function DeliverablesSurface({
  deliverables,
  exporting,
  onExport,
}: {
  deliverables: DeliverableRead[];
  exporting: boolean;
  onExport: (deliverableId: string, format: "docx" | "pdf") => void;
}) {
  return (
    <>
      <SurfaceHeader title="交付" />
      {deliverables.length === 0 ? <p className="wb-project-quiet-copy">尚未创建交付物。</p> : null}
      {deliverables.length > 0 ? (
        <div className="wb-project-lines" role="table" aria-label="项目交付物">
          <div className="wb-project-lines__head" role="row"><span>交付物</span><span>类型</span><span>内容状态</span><span>导出状态</span><span>操作</span></div>
          {deliverables.map((deliverable) => (
            <div className="wb-project-line" key={deliverable.id} role="row">
              <div className="wb-project-line__primary"><FileOutputIcon aria-hidden="true" /><span>{deliverable.title}</span></div>
              <span className="wb-project-line__muted">{displayDeliverableType(deliverable.type)}</span>
              <StatusMark status={deliverable.status} />
              <StatusMark status={deliverable.export_status} />
              <div className="flex flex-wrap gap-2">
                <Button aria-label={`导出 ${deliverable.title} 为 DOCX`} disabled={deliverable.status !== "approved" || exporting} onClick={() => onExport(deliverable.id, "docx")} size="xs" type="button">导出 DOCX</Button>
                <Button aria-label={`导出 ${deliverable.title} 为 PDF`} disabled={deliverable.status !== "approved" || exporting} onClick={() => onExport(deliverable.id, "pdf")} size="xs" type="button" variant="outline">导出 PDF</Button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </>
  );
}

function ResponsePlanSurface({
  plan,
  isLoading,
  onOpenMaterials,
}: {
  plan: ResponsePlanDetailRead | undefined;
  isLoading: boolean;
  onOpenMaterials: () => void;
}) {
  return (
    <>
      <SurfaceHeader title="响应计划" />
      <p className="wb-project-summary">把资料、要求和章节顺序收敛为一份可确认的响应计划。执行过程只在需要接管或排障时显示。</p>
      {isLoading ? <p className="wb-project-quiet-copy">正在读取响应计划…</p> : null}
      {!isLoading && !plan ? (
        <section className="wb-project-empty-state">
          <FileCheck2Icon aria-hidden="true" />
          <strong>还没有响应计划</strong>
          <p>先上传招标文件并确认要求，团队即可在此核对章节结构、责任与证据覆盖。</p>
          <Button className="wb-flat-button" onClick={onOpenMaterials} size="sm" type="button" variant="outline">查看资料</Button>
        </section>
      ) : null}
      {plan ? (
        <section className="wb-response-plan">
          <header className="wb-response-plan__head">
            <div><h2>响应书结构</h2><p>版本 {plan.version_number} · {plan.sections.length} 个章节</p></div>
            <StatusMark status={plan.status} />
          </header>
          <div className="wb-project-lines" role="table" aria-label="响应计划章节">
            <div className="wb-project-lines__head" role="row"><span>章节</span><span>要求</span><span>证据</span><span>状态</span></div>
            {plan.sections.map((section) => (
              <div className="wb-project-line" key={section.id} role="row">
                <div className="wb-project-line__primary"><span className="wb-section-order">{section.sort_order}</span><span>{section.title}</span></div>
                <span className="wb-project-line__muted">{section.requirements.length} 项</span>
                <span className="wb-project-line__muted">{section.evidence_bindings.length} 组</span>
                <StatusMark status={section.status} />
              </div>
            ))}
          </div>
          {plan.unmapped_requirement_ids.length > 0 ? <p className="wb-project-plan-note">仍有 {plan.unmapped_requirement_ids.length} 项要求尚未分配到章节。</p> : null}
        </section>
      ) : null}
    </>
  );
}

export function ProjectWorkspacePageV2() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [surface, setSurface] = useState<ProjectSurface>("overview");
  const [requirementFilter, setRequirementFilter] = useState<RequirementFilter>("all");
  const [selectedRequirementId, setSelectedRequirementId] = useState<string | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [selectedDeliverableId, setSelectedDeliverableId] = useState<string | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [selectedWorkflowRunId, setSelectedWorkflowRunId] = useState<string | null>(null);
  const [createDeliverableOpen, setCreateDeliverableOpen] = useState(false);
  const [deliverableTitle, setDeliverableTitle] = useState("");
  const [deliverableType, setDeliverableType] = useState("technical_response");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [workflowOptions, setWorkflowOptions] = useState<WorkflowRunOptions>({
    providerConfigId: "official",
    reasoningEffort: "medium",
    maxIterations: 3,
  });

  const projectQuery = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id!), enabled: Boolean(id), staleTime: 60_000 });
  const bundlesQuery = useQuery({ queryKey: ["bundles", id], queryFn: () => listBundles(id!), enabled: Boolean(id), staleTime: 30_000, refetchInterval: 5_000 });
  const requirementsQuery = useQuery({ queryKey: ["requirements", id], queryFn: () => listRequirements(id!), enabled: Boolean(id), staleTime: 30_000 });
  const requirementDetailQuery = useQuery({
    queryKey: ["requirement-detail", selectedRequirementId],
    queryFn: () => getRequirement(selectedRequirementId!),
    enabled: Boolean(selectedRequirementId),
    staleTime: 15_000,
  });
  const parsedAssetsQuery = useQuery({
    queryKey: ["parsed-assets", selectedDocumentId],
    queryFn: () => listParsedAssets(selectedDocumentId!),
    enabled: Boolean(selectedDocumentId),
    staleTime: 30_000,
  });
  const readinessQuery = useQuery({ queryKey: ["readiness", id], queryFn: () => getReadinessSummary(id!), enabled: Boolean(id), staleTime: 15_000 });
  const collaborationQuery = useQuery({ queryKey: ["collaboration-board", id], queryFn: () => getCollaborationBoard(id!), enabled: Boolean(id), staleTime: 15_000, refetchInterval: 15_000 });
  const evidenceQuery = useQuery({ queryKey: ["evidence", id], queryFn: () => listEvidence(id!), enabled: Boolean(id), staleTime: 30_000 });
  const deliverablesQuery = useQuery({ queryKey: ["deliverables", id], queryFn: () => listDeliverables(id!), enabled: Boolean(id), staleTime: 30_000 });
  const runsQuery = useQuery({ queryKey: ["execution-runs", id], queryFn: () => listExecutionRuns(id!), enabled: Boolean(id), staleTime: 10_000 });
  const responsePlansQuery = useQuery({ queryKey: ["response-plans", id], queryFn: () => listResponsePlans(id!), enabled: Boolean(id), staleTime: 30_000 });
  const providerConfigsQuery = useQuery({ queryKey: ["provider-configs"], queryFn: listProviderConfigs, staleTime: 30_000 });

  const bundles = useMemo(() => bundlesQuery.data ?? [], [bundlesQuery.data]);
  const documentQueries = useQueries({
    queries: bundles.map((bundle) => ({
      queryKey: ["bundle-documents", bundle.id],
      queryFn: () => listDocuments(bundle.id),
      staleTime: 15_000,
      refetchInterval: 5_000,
    })),
  });
  const documents = useMemo(() => documentQueries.flatMap((query) => query.data?.items ?? []), [documentQueries]);
  const selectedDocument = useMemo(() => documents.find((document) => document.id === selectedDocumentId), [documents, selectedDocumentId]);
  const documentsLoading = documentQueries.some((query) => query.isLoading);
  const requirements = useMemo(() => requirementsQuery.data ?? [], [requirementsQuery.data]);
  const evidence = useMemo(() => evidenceQuery.data ?? [], [evidenceQuery.data]);
  const deliverables = useMemo(() => deliverablesQuery.data ?? [], [deliverablesQuery.data]);
  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data]);
  const workflowRuns = runs;
  const selectedWorkflowRun =
    workflowRuns.find((run) => run.runtime_run_id === selectedWorkflowRunId) ??
    workflowRuns.find((run) => Boolean(run.runtime_run_id)) ??
    workflowRuns[0];
  const effectiveWorkflowRunId = selectedWorkflowRun?.runtime_run_id ?? null;
  const workflowEventsQuery = useQuery({
    queryKey: ["runtime-events", effectiveWorkflowRunId],
    queryFn: () => listRuntimeEvents(effectiveWorkflowRunId!),
    enabled: Boolean(effectiveWorkflowRunId),
    staleTime: 3_000,
    refetchInterval:
      selectedWorkflowRun && ["active", "review"].includes(toneForStatus(selectedWorkflowRun.status))
        ? 5_000
        : false,
  });
  const responsePlans = useMemo(() => responsePlansQuery.data ?? [], [responsePlansQuery.data]);
  const activeProviders = useMemo(() => (providerConfigsQuery.data?.data ?? []).filter((provider) => provider.is_active), [providerConfigsQuery.data]);
  const latestResponsePlanId = responsePlans[0]?.id;
  const responsePlanQuery = useQuery({
    queryKey: ["response-plan", id, latestResponsePlanId],
    queryFn: () => getResponsePlan(id!, latestResponsePlanId!),
    enabled: Boolean(id && latestResponsePlanId),
    staleTime: 30_000,
  });
  const effectiveDeliverableId = selectedDeliverableId ?? deliverables[0]?.id ?? null;

  const invalidateRequirementLedger = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["requirements", id] }),
      queryClient.invalidateQueries({ queryKey: ["readiness", id] }),
      queryClient.invalidateQueries({ queryKey: ["requirement-detail", selectedRequirementId] }),
    ]);
  };

  const updateRequirementMutation = useMutation({
    mutationFn: ({ requirementId, data }: { requirementId: string; data: Parameters<typeof updateRequirement>[1] }) => updateRequirement(requirementId, data),
    onSuccess: async () => {
      await invalidateRequirementLedger();
      toast.success("要求已更新");
    },
    onError: () => toast.error("要求更新失败，请刷新后重试。"),
  });
  const verifyEvidenceMutation = useMutation({
    mutationFn: ({ requirementId, linkId }: { requirementId: string; linkId: string }) => verifyRequirementEvidenceLink(requirementId, linkId),
    onSuccess: async () => {
      await invalidateRequirementLedger();
      toast.success("证据已核验");
    },
    onError: () => toast.error("证据核验失败，请稍后重试。"),
  });
  const verifyClaimMutation = useMutation({
    mutationFn: ({ requirementId, claimId }: { requirementId: string; claimId: string }) => verifyRequirementClaim(requirementId, claimId),
    onSuccess: async () => {
      await invalidateRequirementLedger();
      toast.success("响应主张已核验");
    },
    onError: () => toast.error("主张核验失败，请先确认关联证据有效。"),
  });
  const reingestMutation = useMutation({
    mutationFn: (bundleId: string) => reingestBundle(bundleId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bundles", id] }),
        queryClient.invalidateQueries({ queryKey: ["bundle-documents"] }),
        queryClient.invalidateQueries({ queryKey: ["requirements", id] }),
        queryClient.invalidateQueries({ queryKey: ["readiness", id] }),
      ]);
      toast.success("资料包已重新进入解析队列");
    },
    onError: () => toast.error("资料包重解析失败，请稍后重试。"),
  });
  const reindexMutation = useMutation({
    mutationFn: (bundleId: string) => reindexBundle(bundleId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bundles", id] }),
        queryClient.invalidateQueries({ queryKey: ["bundle-documents"] }),
      ]);
      toast.success("资料包已重新进入索引队列");
    },
    onError: () => toast.error("资料包重建索引失败，请稍后重试。"),
  });

  const sectionsQuery = useQuery({
    queryKey: ["deliverable-sections", effectiveDeliverableId],
    queryFn: () => listDeliverableSections(effectiveDeliverableId!),
    enabled: Boolean(effectiveDeliverableId),
    staleTime: 30_000,
    // A draft is generated by a worker after the submission response returns.
    // Keep the focused work surfaces synchronized with its durable result.
    refetchInterval: surface === "sections" || surface === "review" ? 5_000 : false,
  });
  const sections = useMemo(() => sectionsQuery.data ?? [], [sectionsQuery.data]);
  const sectionVersionsQuery = useQuery({
    queryKey: ["section-versions", selectedSectionId],
    queryFn: () => listSectionVersions(selectedSectionId!),
    enabled: Boolean(selectedSectionId),
    staleTime: 15_000,
    refetchInterval: surface === "sections" || surface === "review" ? 5_000 : false,
  });
  const draftSectionMutation = useMutation({
    mutationFn: ({ section, hasVersions }: { section: DeliverableSectionRead; hasVersions: boolean }) => {
      if (!id) throw new Error("Missing project id");
      const requestOptions = {
        provider_config_id: workflowOptions.providerConfigId === "official" ? undefined : workflowOptions.providerConfigId,
        reasoning_effort: workflowOptions.reasoningEffort,
        max_iterations: workflowOptions.maxIterations,
      };
      return hasVersions
        ? redraftSection({ project_id: id, section_key: section.section_key, section_id: section.id, ...requestOptions })
        : draftSection({ project_id: id, section_key: section.section_key, section_id: section.id, ...requestOptions });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["execution-runs", id] }),
        queryClient.invalidateQueries({ queryKey: ["section-versions", selectedSectionId] }),
        queryClient.invalidateQueries({ queryKey: ["deliverable-sections", effectiveDeliverableId] }),
        queryClient.invalidateQueries({ queryKey: ["response-plan", id, latestResponsePlanId] }),
      ]);
      toast.success("章节已进入生成队列");
    },
    onError: () => toast.error("章节生成未能启动，请先确认资料和证据状态。"),
  });
  const createDeliverableMutation = useMutation({
    mutationFn: (payload: { project_id: string; title: string; type: string }) => createDeliverable(payload),
    onSuccess: async (deliverable) => {
      await queryClient.invalidateQueries({ queryKey: ["deliverables", id] });
      setSelectedDeliverableId(deliverable.id);
      setCreateDeliverableOpen(false);
      setDeliverableTitle("");
      setSurface("sections");
      toast.success("交付物已创建。下一步添加章节，再开始起草。");
    },
    onError: () => toast.error("交付物未能创建，请检查项目权限后重试。"),
  });
  const createSectionMutation = useMutation({
    mutationFn: (payload: { deliverable_id: string; section_key: string; title: string }) => createDeliverableSection(payload),
    onSuccess: async (section) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["deliverable-sections", section.deliverable_id] }),
        queryClient.invalidateQueries({ queryKey: ["deliverables", id] }),
      ]);
      setSelectedSectionId(section.id);
      toast.success("章节已加入响应结构。");
    },
    onError: () => toast.error("章节未能创建。章节标识不能与同一交付物重复。"),
  });
  const reviewDecisionMutation = useMutation({
    mutationFn: ({
      sectionId,
      sectionVersionId,
      decision,
      comment,
    }: {
      sectionId: string;
      sectionVersionId: string;
      decision: "approved" | "rejected";
      comment: string | null;
    }) => submitReviewDecision({
      section_id: sectionId,
      section_version_id: sectionVersionId,
      decision,
      comment,
    }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["deliverable-sections", effectiveDeliverableId] }),
        queryClient.invalidateQueries({ queryKey: ["section-versions", selectedSectionId] }),
        queryClient.invalidateQueries({ queryKey: ["execution-runs", id] }),
        queryClient.invalidateQueries({ queryKey: ["runtime-events"] }),
        queryClient.invalidateQueries({ queryKey: ["deliverables", id] }),
      ]);
      toast.success("审核决定已保存；需要恢复的起草运行已进入队列。");
    },
    onError: () => toast.error("审核决定未能保存。请刷新后确认草稿版本仍是当前候选版本。"),
  });
  const exportDeliverableMutation = useMutation({
    mutationFn: ({ deliverableId, format }: { deliverableId: string; format: "docx" | "pdf" }) => (
      format === "docx" ? exportDeliverableDocx(deliverableId) : exportDeliverablePdf(deliverableId)
    ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["deliverables", id] });
      toast.success("交付物已开始下载。");
    },
    onError: () => toast.error("导出失败。请确认每个章节都已批准。"),
  });
  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      if (!id) throw new Error("Missing project id");
      const bundle = bundles[0] ?? await createBundle({ project_id: id, label: "招标资料", source_type: "rfp" });
      let completed = 0;
      const uploaded = [];
      for (const file of files) {
        uploaded.push(await uploadDocument(bundle.id, file, (progress) => {
          setUploadProgress(Math.round(((completed + progress / 100) / files.length) * 100));
        }, undefined, true));
        completed += 1;
      }
      const queuedForParsing = uploaded.some((document) => document.parse_status !== "not_applicable");
      let queueError: unknown;
      if (queuedForParsing) {
        try {
          await reingestBundle(bundle.id);
        } catch (error) {
          queueError = error;
        }
      }
      return { count: files.length, queuedForParsing, queueError };
    },
    onSuccess: ({ count, queuedForParsing, queueError }) => {
      void queryClient.invalidateQueries({ queryKey: ["bundles", id] });
      void queryClient.invalidateQueries({ queryKey: ["bundle-documents"] });
      void queryClient.invalidateQueries({ queryKey: ["readiness", id] });
      void queryClient.invalidateQueries({ queryKey: ["requirements", id] });
      setUploadFiles([]);
      setUploadProgress(0);
      setUploadOpen(false);
      if (queueError) {
        toast.warning(documentQueueErrorMessage(queueError));
      } else {
        toast.success(queuedForParsing ? `${count} 份资料已上传，正在自动解析。` : `${count} 份附件已归档，可在资料页下载使用。`);
      }
    },
    onError: () => {
      setUploadProgress(0);
      toast.error("资料未能上传。请确认文件类型、大小和项目权限。");
    },
  });

  const openRequirements = (filter: RequirementFilter) => {
    setRequirementFilter(filter);
    setSurface("requirements");
  };

  if (projectQuery.isPending) {
    return <div className="wb-project-loading">正在读取项目…</div>;
  }

  if (projectQuery.isError || !projectQuery.data) {
    return (
      <section className="wb-project-not-found">
        <FolderOpenIcon aria-hidden="true" />
        <strong>未找到该项目</strong>
        <span>该项目可能已删除，或你没有访问权限。</span>
        <Button className="wb-primary-button" onClick={() => navigate("/projects")} size="sm" type="button">返回项目列表</Button>
      </section>
    );
  }

  const project = projectQuery.data;
  const surfaceProps = {
    bundles,
    deliverables,
    evidence,
    readiness: readinessQuery.data,
    requirements,
    runs,
  };

  const renderSurface = () => {
    if (surface === "requirements") return <RequirementsSurface
      filter={requirementFilter}
      isError={requirementsQuery.isError}
      onCloseRequirement={() => setSelectedRequirementId(null)}
      onFilterChange={setRequirementFilter}
      onOpenRequirement={setSelectedRequirementId}
      onVerifyClaim={(requirementId, claimId) => { verifyClaimMutation.mutate({ requirementId, claimId }); }}
      onVerifyEvidence={(requirementId, linkId) => { verifyEvidenceMutation.mutate({ requirementId, linkId }); }}
      onVerifyExtraction={(requirement) => { updateRequirementMutation.mutate({ requirementId: requirement.id, data: { lock_version: requirement.lock_version, verification_status: "verified" } }); }}
      readiness={readinessQuery.data}
      requirementDetail={requirementDetailQuery.data}
      requirementDetailError={requirementDetailQuery.isError}
      requirementDetailLoading={requirementDetailQuery.isLoading}
      requirementMutationPending={updateRequirementMutation.isPending || verifyEvidenceMutation.isPending || verifyClaimMutation.isPending}
      requirements={requirements}
      selectedRequirementId={selectedRequirementId}
    />;
    if (surface === "materials") return <EvidenceSurface
      bundleActionPending={(bundleId) => (
        (reingestMutation.isPending && reingestMutation.variables === bundleId)
        || (reindexMutation.isPending && reindexMutation.variables === bundleId)
      )}
      bundles={bundles}
      documents={documents}
      documentsLoading={documentsLoading}
      evidence={evidence}
      isError={bundlesQuery.isError || evidenceQuery.isError}
      onCloseDocument={() => setSelectedDocumentId(null)}
      onOpenDocument={setSelectedDocumentId}
      onReindex={(bundleId) => reindexMutation.mutate(bundleId)}
      onReingest={(bundleId) => reingestMutation.mutate(bundleId)}
      onUpload={() => setUploadOpen(true)}
      parsedAssets={parsedAssetsQuery.data}
      parsedAssetsError={parsedAssetsQuery.isError}
      parsedAssetsLoading={parsedAssetsQuery.isLoading}
      selectedDocument={selectedDocument}
    />;
    if (surface === "plan") return <ResponsePlanSurface isLoading={responsePlansQuery.isLoading || responsePlanQuery.isLoading} onOpenMaterials={() => setSurface("materials")} plan={responsePlanQuery.data} />;
    if (surface === "workflow") return <WorkflowSurface
      events={workflowEventsQuery.data?.items ?? []}
      eventsError={workflowEventsQuery.isError}
      eventsLoading={workflowEventsQuery.isLoading}
      onOpenAgent={() => navigate(`/agent?project_id=${project.id}`)}
      onSelectRun={setSelectedWorkflowRunId}
      runs={workflowRuns}
      selectedRunId={effectiveWorkflowRunId}
      workflowOptions={workflowOptions}
      onWorkflowOptionsChange={setWorkflowOptions}
      providers={activeProviders}
    />;
    if (surface === "sections") return <ResponseSurface
      addSectionPending={createSectionMutation.isPending}
      createDeliverablePending={createDeliverableMutation.isPending}
      deliverables={deliverables}
      draftPending={draftSectionMutation.isPending}
      onAddSection={(deliverableId, title, sectionKey) => createSectionMutation.mutate({ deliverable_id: deliverableId, title, section_key: sectionKey })}
      onCloseSection={() => setSelectedSectionId(null)}
      onCreateDeliverable={() => setCreateDeliverableOpen(true)}
      onDraftSection={(section, hasVersions) => { draftSectionMutation.mutate({ section, hasVersions }); }}
      onOpenRequirement={(requirementId) => { setSelectedSectionId(null); setSelectedRequirementId(requirementId); setRequirementFilter("all"); setSurface("requirements"); }}
      onOpenReview={(sectionId) => { setSelectedSectionId(sectionId); setSurface("review"); }}
      onSelectDeliverable={setSelectedDeliverableId}
      onSelectSection={setSelectedSectionId}
      responsePlan={responsePlanQuery.data}
      sections={sections}
      sectionVersions={sectionVersionsQuery.data}
      sectionVersionsError={sectionVersionsQuery.isError}
      sectionVersionsLoading={sectionVersionsQuery.isLoading}
      selectedDeliverableId={effectiveDeliverableId}
      selectedSectionId={selectedSectionId}
      workflowOptions={workflowOptions}
      onWorkflowOptionsChange={setWorkflowOptions}
      providers={activeProviders}
    />;
    if (surface === "review") return <ReviewSurface
      onSelectSection={setSelectedSectionId}
      onSubmitDecision={(sectionId, sectionVersionId, decision, comment) => reviewDecisionMutation.mutate({ sectionId, sectionVersionId, decision, comment })}
      readiness={surfaceProps.readiness}
      runs={runs}
      sectionVersions={sectionVersionsQuery.data}
      sections={sections}
      selectedSectionId={selectedSectionId}
      submitDecisionPending={reviewDecisionMutation.isPending}
    />;
    if (surface === "deliverables") return <DeliverablesSurface deliverables={deliverables} exporting={exportDeliverableMutation.isPending} onExport={(deliverableId, format) => exportDeliverableMutation.mutate({ deliverableId, format })} />;
    return (
      <ProjectBrief
        bundleCount={bundles.length}
        deliverableCount={deliverables.length}
        documents={documents}
        documentsLoading={documentsLoading}
        evidenceCount={evidence.length}
        onOpenMaterials={() => setSurface("materials")}
        onOpenRequirements={openRequirements}
        onUpload={() => setUploadOpen(true)}
        projectName={project.name}
        projectStatus={project.status}
        readiness={surfaceProps.readiness}
        requirementCount={requirements.length}
        runs={runs}
        collaboration={collaborationQuery.data}
      />
    );
  };

  return (
    <section className="wb-project-workspace" aria-label={`${project.name} 项目工作区`}>
      <header className="wb-project-workspace-head">
        <div className="wb-project-breadcrumb">
          <button onClick={() => navigate("/projects")} type="button">投标机会</button>
          <ChevronRightIcon aria-hidden="true" />
          <strong>{project.name}</strong>
        </div>
        <Button className="wb-primary-button" onClick={() => navigate(`/agent?project_id=${project.id}`)} size="sm" type="button">
          <BotIcon aria-hidden="true" />
          询问 Agent
          <ArrowRightIcon aria-hidden="true" />
        </Button>
      </header>

      <div className="wb-project-workspace-body">
        <nav className="wb-project-subnav" aria-label="项目工作区导航">
          {PROJECT_SURFACES.map((item) => (
            <button
              className={cn(surface === item.value && "is-active")}
              key={item.value}
              onClick={() => setSurface(item.value)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
        <article className="wb-project-surface">{renderSurface()}</article>
      </div>

      <Dialog onOpenChange={setCreateDeliverableOpen} open={createDeliverableOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建交付物</DialogTitle>
            <DialogDescription>创建响应文件容器；后续在章节页维护结构、起草、审核和导出。</DialogDescription>
          </DialogHeader>
          <form
            id="project-create-deliverable-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (!deliverableTitle.trim()) return;
              createDeliverableMutation.mutate({
                project_id: project.id,
                title: deliverableTitle.trim(),
                type: deliverableType,
              });
            }}
          >
            <div className="grid gap-4">
              <div className="grid gap-2">
                <label className="text-sm font-medium" htmlFor="project-deliverable-title">交付物名称</label>
                <Input id="project-deliverable-title" onChange={(event) => setDeliverableTitle(event.target.value)} placeholder="例如：技术响应文件" value={deliverableTitle} />
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium" htmlFor="project-deliverable-type">文件类型</label>
                <Select onValueChange={(value) => value && setDeliverableType(value)} value={deliverableType}>
                  <SelectTrigger id="project-deliverable-type"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectGroup><SelectItem value="technical_response">技术响应</SelectItem><SelectItem value="commercial_response">商务响应</SelectItem><SelectItem value="bid_response">完整投标响应</SelectItem><SelectItem value="proposal">投标方案</SelectItem></SelectGroup></SelectContent>
                </Select>
              </div>
            </div>
          </form>
          <DialogFooter>
            <Button disabled={createDeliverableMutation.isPending} onClick={() => setCreateDeliverableOpen(false)} type="button" variant="outline">取消</Button>
            <Button disabled={!deliverableTitle.trim() || createDeliverableMutation.isPending} form="project-create-deliverable-form" type="submit">
              {createDeliverableMutation.isPending ? <LoaderCircleIcon aria-hidden="true" className="animate-spin" data-icon="inline-start" /> : <PlusIcon aria-hidden="true" data-icon="inline-start" />}创建交付物
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog onOpenChange={(open) => {
        setUploadOpen(open);
        if (!open && !uploadMutation.isPending) {
          setUploadFiles([]);
          setUploadProgress(0);
        }
      }} open={uploadOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>上传项目资料</DialogTitle>
            <DialogDescription>资料会自动进入解析和索引流程，用于提取要求、检索证据和计算投标就绪度。</DialogDescription>
          </DialogHeader>
          <form id="project-upload-form" onSubmit={(event) => {
            event.preventDefault();
            if (!uploadFiles.length) {
              toast.error("请选择至少一份资料。");
              return;
            }
            uploadMutation.mutate(uploadFiles);
          }}>
            <Input accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.md" aria-describedby="project-upload-hint" multiple onChange={(event) => setUploadFiles(Array.from(event.target.files ?? []))} type="file" />
            <p className="mt-3 text-sm text-muted-foreground" id="project-upload-hint">支持 PDF、DOCX、XLSX、CSV、TXT 和 Markdown。{uploadFiles.length ? `已选择 ${uploadFiles.length} 份资料。` : ""}</p>
            {uploadMutation.isPending ? <div className="mt-4 grid gap-2"><div className="flex items-center justify-between text-sm text-muted-foreground"><span>正在上传</span><span>{uploadProgress}%</span></div><Progress value={uploadProgress} /></div> : null}
          </form>
          <DialogFooter>
            <Button disabled={uploadMutation.isPending} onClick={() => setUploadOpen(false)} type="button" variant="outline">取消</Button>
            <Button disabled={!uploadFiles.length || uploadMutation.isPending} form="project-upload-form" type="submit">{uploadMutation.isPending ? <LoaderCircleIcon aria-hidden="true" className="animate-spin" data-icon="inline-start" /> : <UploadIcon aria-hidden="true" data-icon="inline-start" />}上传并解析</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
