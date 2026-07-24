import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleDashedIcon,
  DownloadIcon,
  Loader2Icon,
  Settings2Icon,
  XCircleIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { downloadAssistantArtifact } from "@/lib/api";
import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";
import { buildTranscriptTurns } from "@/lib/assistant-transcript";
import { cn } from "@/lib/utils";
import { getAssistantToolIcon, getAssistantToolLabel } from "./assistant-tool-metadata";

type ActivityTone = "running" | "succeeded" | "failed" | "pending" | "cancelled";
type Translate = (key: string, options?: Record<string, unknown>) => string;

interface FailureGuidance {
  message: string;
  canOpenProviderSettings: boolean;
}

const PROVIDER_SETTINGS_ERROR_CODES = new Set([
  "provider_not_configured",
  "provider_config_missing",
  "provider_auth_failed",
  "provider_model_unavailable",
  "provider_request_invalid",
  "provider_response_invalid",
]);

function getFailureGuidance(errorCode: string | undefined, t: Translate): FailureGuidance | null {
  if (!errorCode) return null;
  const fallback = t("activity.failure.workflow_internal_error", {
    defaultValue: "The workflow could not finish safely. Please try again later.",
  });
  return {
    message: t(`activity.failure.${errorCode}`, { defaultValue: fallback }),
    canOpenProviderSettings: PROVIDER_SETTINGS_ERROR_CODES.has(errorCode),
  };
}

function getTone(items: AssistantExecutionItem[]): ActivityTone {
  if (items.some((item) => item.status === "failed")) return "failed";
  if (items.some((item) => item.status === "running")) return "running";
  if (items.some((item) => item.status === "pending")) return "pending";
  if (items.some((item) => item.status === "cancelled")) return "cancelled";
  return "succeeded";
}

function ActivityStatusMark({
  status,
  className,
}: {
  status: ActivityTone;
  className?: string;
}) {
  const isActive = status === "running" || status === "pending";

  return (
    <span
      aria-hidden="true"
      className={cn(
        "relative z-10 flex size-5 shrink-0 items-center justify-center rounded-full border bg-background shadow-[0_1px_2px_oklch(0_0_0/0.05)]",
        isActive && "border-primary/35 bg-primary/[0.08] text-primary",
        status === "succeeded" && "border-primary/25 bg-primary/[0.06] text-primary",
        status === "failed" && "border-destructive/35 bg-destructive/[0.07] text-destructive",
        status === "cancelled" && "border-border/80 bg-muted/45 text-muted-foreground",
        className,
      )}
    >
      {isActive && (
        <span className="absolute inset-0 rounded-full border border-primary/35 animate-ping motion-reduce:hidden" />
      )}
      {isActive ? (
        <Loader2Icon className="relative size-3 animate-spin" />
      ) : status === "failed" ? (
        <XCircleIcon className="size-3.5" />
      ) : status === "succeeded" ? (
        <CheckCircle2Icon className="size-3.5" />
      ) : (
        <CircleDashedIcon className="size-3.5" />
      )}
    </span>
  );
}

function getNodeTone(status: "pending" | "running" | "completed" | "failed"): ActivityTone {
  if (status === "completed") return "succeeded";
  return status;
}

function getWorkflowNodeLabel(nodeName: string, t: Translate) {
  const labels: Record<string, string> = {
    document_analyzer: "分析资料",
    retriever: "检索资料",
    knowledge_retriever: "证据检索",
    content_plan: "内容计划",
    section_planner: "规划章节",
    section_drafter: "章节起草",
    quality_review: "质量审核",
    quality_reviewer: "质量审核",
    human_approval: "人工审核",
    persist_result: "保存结果",
    redrafter: "重新起草",
    exporter: "生成交付物",
  };
  return t(`activity.node.${nodeName}`, { defaultValue: labels[nodeName] ?? nodeName });
}

function getFieldLabel(key: string, t: Translate) {
  const labels: Record<string, string> = {
    route: "页面",
    query: "关键词",
    section_key: "章节",
    status: "状态",
    scenario: "场景",
  };
  return t(`activity.field.${key}`, { defaultValue: labels[key] ?? key });
}

function summarizeResult(item: AssistantExecutionItem, t: Translate) {
  if (item.status === "running" && item.retryAttempt && item.retryMaxAttempts) {
    return t("activity.providerRetry", {
      attempt: item.retryAttempt,
      maxAttempts: item.retryMaxAttempts,
      defaultValue: `Retrying the model service (${item.retryAttempt}/${item.retryMaxAttempts})`,
    });
  }
  if (item.status === "cancelled") {
    return t("activity.result.cancelled", { defaultValue: "Workflow cancelled" });
  }
  if (item.isCancellationRequested) {
    return t("activity.result.cancellationRequested", { defaultValue: "Cancellation requested" });
  }
  if (item.errorMessage) return item.errorMessage;
  const result = item.result ?? {};
  if (typeof result.route === "string") {
    return t("activity.result.openedRoute", { route: result.route, defaultValue: `已打开 ${result.route}` });
  }
  if (typeof result.count === "number") {
    return t("activity.result.returnedCount", { count: result.count, defaultValue: `返回 ${result.count} 条结果` });
  }
  if (Array.isArray(result.projects)) {
    return t("activity.result.foundProjects", {
      count: result.projects.length,
      defaultValue: `找到 ${result.projects.length} 个项目`,
    });
  }
  if (Array.isArray(result.runs)) {
    return t("activity.result.runningRuns", {
      count: result.runs.length,
      defaultValue: `当前 ${result.runs.length} 个运行任务`,
    });
  }
  if (typeof result.status === "string") {
    return t("activity.result.status", { status: result.status, defaultValue: `状态：${result.status}` });
  }
  if (typeof result.run_id === "string") return t("activity.result.runCreated", { defaultValue: "运行已创建" });
  return item.status === "succeeded"
    ? t("activity.result.completed", { defaultValue: "已完成" })
    : t("activity.result.processing", { defaultValue: "处理中" });
}

function sanitizeToolText(value?: string) {
  if (!value) return "";
  const looksLikeRawToolDump =
    /\btool_call_id=/.test(value) ||
    /\bname=['"]?[a-z_]+['"]?/.test(value) ||
    /\bcontent=['"]?\{/.test(value) ||
    /^\s*\{[\s\S]*\}\s*$/.test(value);
  if (looksLikeRawToolDump) return "";
  return value.replace(/\btool_call_id=['"][^'"]+['"]/g, "").trim();
}

function isLowSignalField(key: string, value: unknown) {
  if (
    [
      "projects",
      "runs",
      "content",
      "tool_call_id",
      "run_id",
      "id",
      "count",
      "project_id",
      "deliverable_id",
      "pack_id",
      "download_path",
      "xlsx_download_path",
      "docx_download_path",
    ].includes(key)
  ) {
    return true;
  }
  if (typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(value)) {
    return true;
  }
  return false;
}

interface DownloadAction {
  format: "docx" | "pdf" | "xlsx";
  path: string;
}

function getDownloadActions(result?: Record<string, unknown>): DownloadAction[] {
  if (!result) return [];
  const actions: DownloadAction[] = [];
  const add = (format: DownloadAction["format"], path: unknown) => {
    if (typeof path === "string") actions.push({ format, path });
  };

  const exportFormat = result.format;
  if ((exportFormat === "docx" || exportFormat === "pdf") && typeof result.download_path === "string") {
    add(exportFormat, result.download_path);
  }
  add("docx", result.docx_download_path);
  add("xlsx", result.xlsx_download_path);
  return actions;
}

function ResultDownloadActions({ result, t }: { result?: Record<string, unknown>; t: Translate }) {
  const actions = getDownloadActions(result);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadFailed, setDownloadFailed] = useState(false);

  if (actions.length === 0) return null;

  const handleDownload = async (action: DownloadAction) => {
    if (downloading) return;
    setDownloading(action.path);
    setDownloadFailed(false);
    try {
      await downloadAssistantArtifact(action.path, `bidpilot-${action.format}.${action.format}`);
    } catch {
      setDownloadFailed(true);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {actions.map((action) => (
        <button
          key={action.path}
          type="button"
          onClick={() => void handleDownload(action)}
          disabled={downloading !== null}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2 py-1 text-[11px] font-medium text-foreground transition hover:border-primary/45 hover:bg-muted disabled:cursor-wait disabled:opacity-60"
        >
          {downloading === action.path ? <Loader2Icon className="h-3 w-3 animate-spin" /> : <DownloadIcon className="h-3 w-3" />}
          {t(`activity.download.${action.format}`, { defaultValue: `Download ${action.format.toUpperCase()}` })}
        </button>
      ))}
      {downloadFailed && <span className="basis-full text-[11px] text-destructive">{t("activity.download.failed")}</span>}
    </div>
  );
}

function countByKind(items: AssistantExecutionItem[]) {
  const workflows = items.filter((item) => item.kind === "workflow").length;
  const tools = items.length - workflows;
  return { tools, workflows };
}

function buildLocalizedTurnSummary(
  tools: Array<{ name: string; title: string; status: string }>,
  tone: ActivityTone,
  t: Translate,
) {
  const labels = tools.map((tool) => getAssistantToolLabel(tool.name || tool.title, t));
  if (labels.length === 1) {
    const label = labels[0];
    const key =
      tone === "running" || tone === "pending"
        ? "activity.summarySingleRunning"
        : tone === "failed"
          ? "activity.summarySingleFailed"
          : tone === "cancelled"
            ? "activity.summarySingleCancelled"
            : "activity.summarySingleDone";
    return t(key, { label, defaultValue: `${label} ${tone}` });
  }
  const joined = labels.join(" · ");
  if (tone === "running" || tone === "pending") {
    return t("activity.summaryTurnRunning", {
      tools: joined,
      defaultValue: `正在处理：${joined}`,
    });
  }
  if (tone === "failed") {
    return t("activity.summaryTurnFailed", {
      tools: joined,
      defaultValue: `部分失败：${joined}`,
    });
  }
  return joined;
}

function buildActivityLabel(
  items: AssistantExecutionItem[],
  tone: ActivityTone,
  tools: number,
  workflows: number,
  t: Translate,
) {
  // Multi-tool / multi-turn harness paths use transcript aggregation for L1.
  // Single-tool paths keep the existing i18n summary contract.
  const turns = buildTranscriptTurns(items);
  if (turns.length === 1 && turns[0].tools.length > 1) {
    return buildLocalizedTurnSummary(turns[0].tools, tone, t);
  }
  if (turns.length > 1) {
    const running = turns.filter((turn) => turn.status === "running" || turn.status === "pending").length;
    const failed = turns.filter((turn) => turn.status === "failed").length;
    if (failed > 0) {
      return t("activity.summaryTurnsFailed", {
        turns: turns.length,
        failed,
        defaultValue: `${turns.length} 个回合，${failed} 个失败`,
      });
    }
    if (running > 0) {
      return t("activity.summaryTurnsRunning", {
        turns: turns.length,
        running,
        defaultValue: `正在处理 ${turns.length} 个回合`,
      });
    }
    return t("activity.summaryTurnsDone", {
      turns: turns.length,
      defaultValue: `已完成 ${turns.length} 个回合`,
    });
  }

  if (items.length === 1) {
    const item = items[0];
    const label =
      item.kind === "workflow"
        ? t("activity.workflow.default", { defaultValue: "工作流" })
        : getAssistantToolLabel(item.toolName, t);
    const key =
      tone === "running" || tone === "pending"
        ? "activity.summarySingleRunning"
        : tone === "failed"
          ? "activity.summarySingleFailed"
          : tone === "cancelled"
            ? "activity.summarySingleCancelled"
          : "activity.summarySingleDone";
    return t(key, { label, defaultValue: `${label} ${tone}` });
  }
  if (tone === "cancelled") {
    return t("activity.summaryCancelled", {
      defaultValue: "Workflow cancelled",
    });
  }
  const keyPrefix = tone === "running" || tone === "pending" ? "activity.summaryRunning" : "activity.summaryDone";
  if (workflows > 0) {
    if (tools === 0) {
      return t(`${keyPrefix}WorkflowsOnly`, {
        workflows,
        defaultValue:
          tone === "running" || tone === "pending"
            ? `正在运行 ${workflows} 个工作流`
            : `已启动 ${workflows} 个工作流`,
      });
    }
    return t(`${keyPrefix}WithWorkflows`, {
      tools,
      workflows,
      defaultValue:
        tone === "running" || tone === "pending"
          ? `正在处理 ${tools} 项操作，启动 ${workflows} 个工作流`
          : `已处理 ${tools} 项操作，启动 ${workflows} 个工作流`,
    });
  }
  return t(keyPrefix, {
    tools,
    defaultValue:
      tone === "running" || tone === "pending"
        ? `正在处理 ${tools} 项操作`
        : `已处理 ${tools} 项操作`,
  });
}

function DetailValue({ value }: { value: unknown }) {
  if (value == null) return <span className="text-muted-foreground">-</span>;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span className="break-words">{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    return <span>{value.length} items</span>;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([key, nestedValue]) => !isLowSignalField(key, nestedValue))
      .slice(0, 3);
    if (entries.length === 0) return <span className="text-muted-foreground">-</span>;
    return (
      <span className="inline-flex flex-wrap gap-1">
        {entries.map(([key, nestedValue]) => (
          <span key={key} className="rounded-md bg-muted/70 px-1.5 py-0.5">
            {key}: {Array.isArray(nestedValue) ? `${nestedValue.length} items` : String(nestedValue)}
          </span>
        ))}
      </span>
    );
  }
  return <span>{String(value)}</span>;
}

function ActivityDetail({
  item,
  onCancelWorkflow,
  onConfigureProvider,
  isCancelling,
  showHeader = true,
}: {
  item: AssistantExecutionItem;
  onCancelWorkflow?: (runtimeRunId: string) => void;
  onConfigureProvider?: () => void;
  isCancelling?: boolean;
  showHeader?: boolean;
}) {
  const { t } = useTranslation("ai-assistant");
  const Icon = getAssistantToolIcon(item);
  const label = getAssistantToolLabel(item.toolName, t);
  const safeSummary = sanitizeToolText(item.summary);
  const failureGuidance = item.status === "failed" ? getFailureGuidance(item.errorCode, t) : null;
  const detailSummary = failureGuidance?.message || safeSummary || summarizeResult(item, t);
  // Only real workflow cards own node progress. Plain tools must never show
  // "0/1 steps" just because a stale nodes array leaked onto the item.
  const workflowNodes = item.kind === "workflow" ? item.nodes ?? [] : [];
  const completedNodes = workflowNodes.filter((node) => node.status === "completed").length;
  const totalNodes = workflowNodes.length;
  const detailRows = [
    ...Object.entries(item.arguments ?? {})
      .filter(([key, value]) => !isLowSignalField(key, value))
      .slice(0, 3)
      .map(([key, value]) => ({ key, value })),
    ...Object.entries(item.result ?? {})
      .filter(([key, value]) => !isLowSignalField(key, value))
      .slice(0, 3)
      .map(([key, value]) => ({ key, value })),
  ].filter((row, index, rows) => rows.findIndex((candidate) => candidate.key === row.key) === index);
  const canCancel =
    item.kind === "workflow" &&
    Boolean(item.runtimeRunId) &&
    (item.status === "running" || item.status === "pending") &&
    !item.isCancellationRequested;

  return (
    <div className={cn("min-w-0 text-xs", showHeader && "grid grid-cols-[1rem_minmax(0,1fr)] gap-x-2.5 py-1.5")}>
      {showHeader && (
        <div className="mt-0.5 flex size-4 items-center justify-center text-muted-foreground/75">
          <Icon className="size-3.5" />
        </div>
      )}
      <div className="min-w-0">
        {showHeader && (
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-medium tracking-[-0.01em] text-foreground/95">{label}</span>
            <span className="shrink-0 text-[11px] text-muted-foreground/80">
              {t(`activity.status.${item.status}`, { defaultValue: item.status })}
            </span>
          </div>
        )}
        {detailSummary && (
          <p className="mt-1 whitespace-pre-wrap break-words leading-5 text-muted-foreground/85">
            {detailSummary}
          </p>
        )}
        {failureGuidance?.canOpenProviderSettings && onConfigureProvider && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onConfigureProvider}
            className="mt-3 h-7 rounded-md px-2 text-[11px] shadow-none"
          >
            <Settings2Icon data-icon="inline-start" />
            {t("activity.openProviderSettings", { defaultValue: "Open model settings" })}
          </Button>
        )}
        {totalNodes > 0 && (
          <div className="mt-3 border-t border-border/55 pt-3">
            <p className="text-[10px] font-medium tracking-wide text-muted-foreground/80">
              {t("activity.workflowProgress", { defaultValue: "Workflow progress" })}
              <span className="ml-2 font-normal">
                {t("execution.nodesCompleted", {
                  completed: completedNodes,
                  total: totalNodes,
                  defaultValue: `${completedNodes} of ${totalNodes} steps completed`,
                })}
              </span>
            </p>
            <ol className="mt-2 space-y-1.5">
              {workflowNodes.map((node) => (
                <li
                  key={node.name}
                  className="grid min-w-0 grid-cols-[1rem_minmax(0,1fr)_auto] items-center gap-x-2"
                >
                  <ActivityStatusMark status={getNodeTone(node.status)} className="size-4" />
                  <span className="min-w-0 truncate text-[11px] text-foreground/85">
                    {getWorkflowNodeLabel(node.name, t)}
                  </span>
                  <span className="text-[10px] text-muted-foreground/70">
                    {t(`execution.nodeStatus.${node.status}`, { defaultValue: node.status })}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        )}
        {detailRows.length > 0 && (
          <dl className="mt-3 grid grid-cols-[minmax(0,6.75rem)_minmax(0,1fr)] gap-x-3 gap-y-1.5 border-t border-border/55 pt-3 text-[11px] leading-5">
            {detailRows.map(({ key, value }) => (
              <div key={`${item.id}-${key}`} className="contents">
                <dt className="truncate text-muted-foreground/65">{getFieldLabel(key, t)}</dt>
                <dd className="min-w-0 break-words text-muted-foreground">
                  <DetailValue value={value} />
                </dd>
              </div>
            ))}
          </dl>
        )}
        <ResultDownloadActions result={item.result} t={t} />
        {canCancel && onCancelWorkflow && (
          <button
            type="button"
            onClick={() => onCancelWorkflow(item.runtimeRunId!)}
            disabled={isCancelling}
            className="mt-3 inline-flex h-7 items-center rounded-md border border-border/80 px-2.5 text-[11px] font-medium text-muted-foreground transition hover:border-foreground/25 hover:bg-muted hover:text-foreground active:translate-y-px disabled:cursor-wait disabled:opacity-60"
          >
            {isCancelling
              ? t("activity.cancelling", { defaultValue: "Cancelling..." })
              : t("activity.cancelWorkflow", { defaultValue: "Cancel workflow" })}
          </button>
        )}
        {item.isCancellationRequested && item.status !== "cancelled" && (
          <p className="mt-3 text-[11px] text-muted-foreground">
            {t("activity.cancellationRequested", { defaultValue: "Cancellation requested. Stopping at a safe boundary." })}
          </p>
        )}
      </div>
    </div>
  );
}

function TraceToolStep({
  item,
  onCancelWorkflow,
  onConfigureProvider,
  isCancelling,
}: {
  item: AssistantExecutionItem;
  onCancelWorkflow?: (runtimeRunId: string) => void;
  onConfigureProvider?: () => void;
  isCancelling?: boolean;
}) {
  const { t } = useTranslation("ai-assistant");
  const ToolIcon = getAssistantToolIcon(item);
  const label = getAssistantToolLabel(item.toolName, t);
  const failureGuidance = item.status === "failed" ? getFailureGuidance(item.errorCode, t) : null;
  const summary = failureGuidance?.canOpenProviderSettings
    ? t("activity.providerNeedsAttention", {
        defaultValue: "Model configuration needs attention",
      })
    : sanitizeToolText(item.summary) || summarizeResult(item, t);
  const isActive = item.status === "running" || item.status === "pending";
  const [expanded, setExpanded] = useState(() => isActive || item.status === "failed");
  const previousStatus = useRef(item.status);

  useEffect(() => {
    const wasActive = previousStatus.current === "running" || previousStatus.current === "pending";
    if (isActive || item.status === "failed") {
      setExpanded(true);
    } else if (wasActive) {
      setExpanded(false);
    }
    previousStatus.current = item.status;
  }, [isActive, item.status]);

  return (
    <Collapsible
      open={expanded}
      onOpenChange={(open) => setExpanded(open)}
      data-testid={`assistant-activity-step-${item.toolCallId || item.id}`}
      data-status={item.status}
      className="relative grid grid-cols-[1.25rem_minmax(0,1fr)] gap-x-3 py-2.5 before:absolute before:bottom-[-0.65rem] before:left-[9px] before:top-7 before:w-px before:bg-border/65 last:before:hidden"
    >
      <div className="pt-0.5">
        <ActivityStatusMark status={item.status} />
      </div>
      <div
        className={cn(
          "min-w-0 rounded-lg transition-colors duration-200 motion-reduce:transition-none",
          isActive && "bg-primary/[0.055] shadow-[inset_0_0_0_1px_oklch(0_0_0/0.035)]",
          item.status === "failed" && "bg-destructive/[0.045] shadow-[inset_0_0_0_1px_oklch(0_0_0/0.045)]",
        )}
      >
        <CollapsibleTrigger
          className="group/step flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left outline-none transition-colors hover:bg-muted/55 focus-visible:ring-2 focus-visible:ring-ring/45 active:translate-y-px"
          aria-label={
            expanded
              ? t("activity.hideToolDetails", {
                  label,
                  defaultValue: `Hide ${label} details`,
                })
              : t("activity.showToolDetails", {
                  label,
                  defaultValue: `Show ${label} details`,
                })
          }
          aria-busy={isActive || undefined}
        >
          <ToolIcon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/75" />
          <span className="min-w-0 flex-1">
            <span className="flex min-w-0 items-center justify-between gap-2">
              <span className="min-w-0 truncate text-[12px] font-medium tracking-[-0.01em] text-foreground/92">
                {label}
              </span>
              <span
                className={cn(
                  "hidden shrink-0 text-[10px] sm:inline",
                  isActive ? "text-primary" : "text-muted-foreground/75",
                  item.status === "failed" && "text-destructive",
                )}
              >
                {t(`activity.status.${item.status}`, { defaultValue: item.status })}
              </span>
            </span>
            {summary && (
              <span
                title={summary}
                className="mt-0.5 block line-clamp-2 break-words text-[11px] leading-4 text-muted-foreground/82"
              >
                {summary}
              </span>
            )}
          </span>
          <ChevronDownIcon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/70 transition-transform duration-200 ease-out group-data-open/step:rotate-180 motion-reduce:transition-none" />
        </CollapsibleTrigger>
        <CollapsibleContent className="overflow-hidden data-open:animate-accordion-down data-closed:animate-accordion-up motion-reduce:animate-none">
          <div className="h-(--collapsible-panel-height) min-h-0 overflow-hidden px-2.5 pb-2.5 pt-0.5">
            <ActivityDetail
              item={item}
              onCancelWorkflow={onCancelWorkflow}
              onConfigureProvider={onConfigureProvider}
              isCancelling={isCancelling}
              showHeader={false}
            />
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

export function AssistantActivityTimeline({
  items,
  onCancelWorkflow,
  onConfigureProvider,
}: {
  items: AssistantExecutionItem[];
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
}) {
  const { t } = useTranslation("ai-assistant");
  const tone = getTone(items);
  const isActive = tone === "running" || tone === "pending";
  const [expanded, setExpanded] = useState(() => isActive || tone === "failed");
  const [cancellingRunId, setCancellingRunId] = useState<string | null>(null);
  const [cancellationError, setCancellationError] = useState<string | null>(null);
  const previousTone = useRef(tone);
  const { tools, workflows } = useMemo(() => countByKind(items), [items]);

  useEffect(() => {
    const wasActive = previousTone.current === "running" || previousTone.current === "pending";
    if (isActive || tone === "failed") {
      setExpanded(true);
    } else if (wasActive) {
      setExpanded(false);
    }
    previousTone.current = tone;
  }, [isActive, tone]);

  // L1 header keeps the existing i18n activity label for product polish.
  // Turn grouping still powers stable L2 keys via toolCallId.
  const label = items.length > 0 ? buildActivityLabel(items, tone, tools, workflows, t) : "";
  const statusLabel = t(`activity.status.${tone}`, { defaultValue: tone });
  const requestCancellation = async (runtimeRunId: string) => {
    if (!onCancelWorkflow || cancellingRunId) return;
    setCancellingRunId(runtimeRunId);
    setCancellationError(null);
    try {
      await onCancelWorkflow(runtimeRunId);
    } catch {
      setCancellationError(t("activity.cancelFailed", { defaultValue: "Unable to request cancellation. Please try again." }));
    } finally {
      setCancellingRunId(null);
    }
  };

  if (items.length === 0) return null;

  return (
    <Collapsible
      open={expanded}
      onOpenChange={(open) => setExpanded(open)}
      data-testid="assistant-activity-timeline"
      data-status={tone}
      className="mb-4 border-b border-border/55 pb-2.5"
    >
      <CollapsibleTrigger
        className="group/timeline flex w-full items-center gap-2.5 rounded-md px-0.5 py-1.5 text-left outline-none transition-colors hover:bg-muted/45 focus-visible:ring-2 focus-visible:ring-ring/45 active:translate-y-px"
        aria-expanded={expanded}
        aria-label={expanded ? t("activity.collapse") : t("activity.expand")}
        aria-live={isActive ? "polite" : "off"}
      >
        <ActivityStatusMark status={tone} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12px] font-medium tracking-[-0.01em] text-foreground/90">
            {label}
          </span>
          <span className="mt-0.5 block text-[10px] text-muted-foreground/75">
            {workflows > 0
              ? t("activity.countWithWorkflows", {
                  tools,
                  workflows,
                  defaultValue: `${tools} actions · ${workflows} workflows`,
                })
              : t("activity.countTools", {
                  tools,
                  defaultValue: `${tools} actions`,
                })}
          </span>
        </span>
        <span
          className={cn(
            "flex shrink-0 items-center gap-1.5 text-[10px]",
            isActive ? "text-primary" : "text-muted-foreground/80",
            tone === "failed" && "text-destructive",
          )}
        >
          {isActive && <Loader2Icon className="size-3 animate-spin" />}
          {statusLabel}
        </span>
        <ChevronDownIcon className="size-3.5 shrink-0 text-muted-foreground/70 transition-transform duration-200 ease-out group-data-open/timeline:rotate-180 motion-reduce:transition-none" />
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden data-open:animate-accordion-down data-closed:animate-accordion-up motion-reduce:animate-none">
        <div className="h-(--collapsible-panel-height) min-h-0 overflow-hidden">
          <div className="pt-1">
            {items.map((item) => (
              <TraceToolStep
                key={item.toolCallId || item.id}
                item={item}
                onCancelWorkflow={onCancelWorkflow ? requestCancellation : undefined}
                onConfigureProvider={onConfigureProvider}
                isCancelling={cancellingRunId === item.runtimeRunId}
              />
            ))}
            {cancellationError && (
              <p className="ml-8 pt-2 text-[11px] text-destructive">{cancellationError}</p>
            )}
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
