import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleDashedIcon,
  Loader2Icon,
  XCircleIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";
import { cn } from "@/lib/utils";
import { getAssistantToolIcon, getAssistantToolLabel } from "./assistant-tool-metadata";

type ActivityTone = "running" | "succeeded" | "failed" | "pending";
type Translate = (key: string, options?: Record<string, unknown>) => string;

function getTone(items: AssistantExecutionItem[]): ActivityTone {
  if (items.some((item) => item.status === "failed")) return "failed";
  if (items.some((item) => item.status === "running")) return "running";
  if (items.some((item) => item.status === "pending")) return "pending";
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
  if (["projects", "runs", "content", "tool_call_id", "run_id", "id", "count", "project_id"].includes(key)) {
    return true;
  }
  if (typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(value)) {
    return true;
  }
  return false;
}

function countByKind(items: AssistantExecutionItem[]) {
  const workflows = items.filter((item) => item.kind === "workflow").length;
  const tools = items.length - workflows;
  return { tools, workflows };
}

function buildActivityLabel(
  tone: ActivityTone,
  tools: number,
  workflows: number,
  t: Translate,
) {
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

function ActivityDetail({ item }: { item: AssistantExecutionItem }) {
  const { t } = useTranslation("ai-assistant");
  const Icon = getAssistantToolIcon(item);
  const label = getAssistantToolLabel(item.toolName, t);
  const safeSummary = sanitizeToolText(item.summary);
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
        <div className="mt-0.5 leading-5 text-muted-foreground/85">{safeSummary || summarizeResult(item, t)}</div>
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
        {item.nodes && item.nodes.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {item.nodes.map((node) => (
              <span key={node.name} className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                {getWorkflowNodeLabel(node.name, t)} · {t(`execution.nodeStatus.${node.status}`, { defaultValue: node.status })}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AssistantActivityTimeline({ items }: { items: AssistantExecutionItem[] }) {
  const { t } = useTranslation("ai-assistant");
  const tone = getTone(items);
  const defaultExpanded = tone === "running" || tone === "failed";
  const [expanded, setExpanded] = useState(defaultExpanded);
  const { tools, workflows } = useMemo(() => countByKind(items), [items]);

  useEffect(() => {
    setExpanded(defaultExpanded);
  }, [defaultExpanded, items.length, tone]);

  if (items.length === 0) return null;

  const label = buildActivityLabel(tone, tools, workflows, t);
  const statusLabel = t(`activity.status.${tone}`, { defaultValue: tone });

  return (
    <div className={cn("mb-4", expanded && "border-b pb-3")} style={{ borderColor: "color-mix(in oklch, var(--border) 54%, transparent)" }}>
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="group flex w-full items-center gap-2 rounded-md py-0.5 text-left text-[12px] text-muted-foreground transition hover:text-foreground"
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
        <span className="min-w-0 flex-1 truncate tracking-[-0.01em]">{label}</span>
        <span className="shrink-0 text-[11px] text-muted-foreground/80">{statusLabel}</span>
        <ChevronDownIcon className={cn("h-3.5 w-3.5 shrink-0 transition-transform opacity-70 group-hover:opacity-100", expanded && "rotate-180")} />
      </button>
      {expanded && (
        <div
          className="ml-[7px] mt-2 flex flex-col gap-1 border-l pl-5"
          style={{ borderColor: "color-mix(in oklch, var(--border) 62%, transparent)" }}
        >
          {items.map((item) => (
            <ActivityDetail key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
