import { useEffect, useMemo, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
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
import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion";
import ShinyText from "@/components/ShinyText";
import { Button } from "@/components/ui/button";
import { REACTBITS_AURORA } from "@/components/reactbits-theme";
import { downloadAssistantArtifact } from "@/lib/api";
import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";
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

function getWorkflowNodeLabel(nodeName: string, t: Translate) {
  const labels: Record<string, string> = {
    document_analyzer: "分析资料",
    retriever: "检索资料",
    section_planner: "规划章节",
    section_drafter: "章节起草",
    quality_review: "质量审核",
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

function buildActivityLabel(
  items: AssistantExecutionItem[],
  tone: ActivityTone,
  tools: number,
  workflows: number,
  t: Translate,
) {
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
}: {
  item: AssistantExecutionItem;
  onCancelWorkflow?: (runtimeRunId: string) => void;
  onConfigureProvider?: () => void;
  isCancelling?: boolean;
}) {
  const { t } = useTranslation("ai-assistant");
  const Icon = getAssistantToolIcon(item);
  const label = getAssistantToolLabel(item.toolName, t);
  const safeSummary = sanitizeToolText(item.summary);
  const failureGuidance = item.status === "failed" ? getFailureGuidance(item.errorCode, t) : null;
  const completedNodes = item.nodes?.filter((node) => node.status === "completed").length ?? 0;
  const totalNodes = item.nodes?.length ?? 0;
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
    <div className="group flex gap-2.5 py-1.5 text-xs">
      <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center text-muted-foreground/75">
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-medium tracking-[-0.01em] text-foreground/95">{label}</span>
          <span className="shrink-0 text-[11px] text-muted-foreground/80">
            {t(`activity.status.${item.status}`, { defaultValue: item.status })}
          </span>
        </div>
        <div className="mt-0.5 leading-5 text-muted-foreground/85">
          {failureGuidance?.message || safeSummary || summarizeResult(item, t)}
        </div>
        {failureGuidance?.canOpenProviderSettings && onConfigureProvider && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onConfigureProvider}
            className="mt-2 h-7 px-2 text-[11px]"
          >
            <Settings2Icon data-icon="inline-start" />
            {t("activity.openProviderSettings", { defaultValue: "Open model settings" })}
          </Button>
        )}
        {totalNodes > 0 && (
          <div className="mt-1 text-[11px] text-muted-foreground">
            {t("execution.nodesCompleted", {
              completed: completedNodes,
              total: totalNodes,
              defaultValue: `${completedNodes} of ${totalNodes} steps completed`,
            })}
          </div>
        )}
        {detailRows.length > 0 && (
          <div className="mt-1.5 flex flex-col gap-1 text-[11px] leading-5 text-muted-foreground">
            {detailRows.map(({ key, value }) => (
              <div key={`${item.id}-${key}`} className="flex gap-1.5">
                <span className="shrink-0 text-muted-foreground/65">{getFieldLabel(key, t)}</span>
                <DetailValue value={value} />
              </div>
            ))}
          </div>
        )}
        <ResultDownloadActions result={item.result} t={t} />
        {item.nodes && item.nodes.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {item.nodes.map((node) => (
              <span key={node.name} className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                {getWorkflowNodeLabel(node.name, t)} · {t(`execution.nodeStatus.${node.status}`, { defaultValue: node.status })}
              </span>
            ))}
          </div>
        )}
        {canCancel && onCancelWorkflow && (
          <button
            type="button"
            onClick={() => onCancelWorkflow(item.runtimeRunId!)}
            disabled={isCancelling}
            className="mt-2 rounded-md border border-border px-2 py-1 text-[11px] font-medium text-muted-foreground transition hover:border-foreground/25 hover:bg-muted hover:text-foreground disabled:cursor-wait disabled:opacity-60"
          >
            {isCancelling
              ? t("activity.cancelling", { defaultValue: "Cancelling..." })
              : t("activity.cancelWorkflow", { defaultValue: "Cancel workflow" })}
          </button>
        )}
        {item.isCancellationRequested && item.status !== "cancelled" && (
          <p className="mt-2 text-[11px] text-muted-foreground">
            {t("activity.cancellationRequested", { defaultValue: "Cancellation requested. Stopping at a safe boundary." })}
          </p>
        )}
      </div>
    </div>
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
  const defaultExpanded = tone === "running" || tone === "failed";
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [cancellingRunId, setCancellingRunId] = useState<string | null>(null);
  const [cancellationError, setCancellationError] = useState<string | null>(null);
  const prefersReducedMotion = usePrefersReducedMotion();
  const activityRef = useRef<HTMLDivElement | null>(null);
  const { tools, workflows } = useMemo(() => countByKind(items), [items]);

  useEffect(() => {
    setExpanded(defaultExpanded);
  }, [defaultExpanded, items.length, tone]);

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

  useGSAP(
    () => {
      if (prefersReducedMotion || !activityRef.current) return;

      gsap.fromTo(
        ".assistant-activity-summary",
        { opacity: 0, y: 5 },
        { opacity: 1, y: 0, duration: 0.28, ease: "power3.out" },
      );

      if (expanded) {
        gsap.fromTo(
          ".assistant-activity-detail",
          { opacity: 0, y: 8 },
          { opacity: 1, y: 0, duration: 0.26, stagger: 0.045, ease: "power3.out" },
        );
      }
    },
    { dependencies: [expanded, items.length, tone, prefersReducedMotion], scope: activityRef },
  );

  if (items.length === 0) return null;

  return (
    <div
      ref={activityRef}
      className={cn("mb-4", expanded && "border-b pb-3")}
      style={{ borderColor: "color-mix(in oklch, var(--border) 54%, transparent)" }}
    >
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="assistant-activity-summary group flex w-full items-center gap-2 rounded-md py-0.5 text-left text-[12px] text-muted-foreground transition hover:text-foreground"
        aria-expanded={expanded}
        aria-label={expanded ? t("activity.collapse") : t("activity.expand")}
      >
        <span
          className={cn(
            "flex h-4 w-4 shrink-0 items-center justify-center",
            tone === "running" && "animate-pulse",
          )}
          style={{ color: tone === "failed" ? "var(--destructive)" : "var(--primary)" }}
        >
          {tone === "running" ? (
            <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
          ) : tone === "failed" ? (
            <XCircleIcon className="h-3.5 w-3.5" />
          ) : tone === "succeeded" ? (
            <CheckCircle2Icon className="h-3.5 w-3.5" />
          ) : (
            <CircleDashedIcon className="h-3.5 w-3.5" />
          )}
        </span>
        <span className="min-w-0 flex-1 truncate tracking-[-0.01em]">
          {tone === "running" && !prefersReducedMotion ? (
            <ShinyText
              text={label}
              speed={2.6}
              color="var(--muted-foreground)"
              shineColor={REACTBITS_AURORA.accentAlt}
              spread={105}
              className="max-w-full truncate align-bottom"
            />
          ) : (
            label
          )}
        </span>
        <span className="shrink-0 text-[11px] text-muted-foreground/80">{statusLabel}</span>
        <ChevronDownIcon className={cn("h-3.5 w-3.5 shrink-0 transition-transform opacity-70 group-hover:opacity-100", expanded && "rotate-180")} />
      </button>
      {expanded && (
        <div
          className="ml-[7px] mt-2 flex flex-col gap-1 border-l pl-5"
          style={{ borderColor: "color-mix(in oklch, var(--border) 62%, transparent)" }}
        >
          {items.map((item) => (
            <div key={item.id} className="assistant-activity-detail">
              <ActivityDetail
                item={item}
                onCancelWorkflow={onCancelWorkflow ? requestCancellation : undefined}
                onConfigureProvider={onConfigureProvider}
                isCancelling={cancellingRunId === item.runtimeRunId}
              />
            </div>
          ))}
          {cancellationError && <p className="pt-1 text-[11px] text-destructive">{cancellationError}</p>}
        </div>
      )}
    </div>
  );
}
