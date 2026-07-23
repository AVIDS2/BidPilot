import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";

export type TranscriptToolStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";

export interface TranscriptTool {
  toolCallId: string;
  name: string;
  title: string;
  status: TranscriptToolStatus;
  summary?: string;
  detail?: Record<string, unknown>;
  errorMessage?: string;
}

export interface TranscriptTurn {
  kind: "turn";
  turnId: string;
  summary: string;
  status: TranscriptToolStatus;
  tools: TranscriptTool[];
}

/**
 * Aggregate flat execution items into L1 turns.
 *
 * Grouping rules:
 * 1. Prefer explicit turnId from the streaming harness
 * 2. Else group by runtimeRunId
 * 3. Else each item is its own turn
 */
export function buildTranscriptTurns(items: AssistantExecutionItem[]): TranscriptTurn[] {
  if (items.length === 0) return [];

  const groups = new Map<string, AssistantExecutionItem[]>();
  const order: string[] = [];

  for (const item of items) {
    const key =
      item.turnId ||
      (item.runtimeRunId ? `run:${item.runtimeRunId}` : undefined) ||
      item.toolCallId ||
      item.id;
    if (!groups.has(key)) {
      groups.set(key, []);
      order.push(key);
    }
    groups.get(key)!.push(item);
  }

  return order.map((key) => {
    const tools = (groups.get(key) ?? []).map(toTranscriptTool);
    return {
      kind: "turn" as const,
      turnId: key,
      summary: buildTurnSummary(tools),
      status: aggregateStatus(tools.map((tool) => tool.status)),
      tools,
    };
  });
}

function toTranscriptTool(item: AssistantExecutionItem): TranscriptTool {
  return {
    toolCallId: item.toolCallId || item.id,
    name: item.toolName || item.title,
    title: item.title || item.toolName || "操作",
    status: item.status,
    summary: item.summary || item.errorMessage,
    detail: item.result ?? item.arguments,
    errorMessage: item.errorMessage,
  };
}

function aggregateStatus(statuses: TranscriptToolStatus[]): TranscriptToolStatus {
  if (statuses.some((status) => status === "failed")) return "failed";
  if (statuses.some((status) => status === "running")) return "running";
  if (statuses.some((status) => status === "pending")) return "pending";
  if (statuses.some((status) => status === "cancelled")) return "cancelled";
  return "succeeded";
}

function buildTurnSummary(tools: TranscriptTool[]): string {
  if (tools.length === 0) return "本轮无工具调用";
  if (tools.length === 1) {
    const tool = tools[0];
    if (tool.status === "running" || tool.status === "pending") return `正在${tool.title}`;
    if (tool.status === "failed") return `${tool.title}失败`;
    if (tool.status === "cancelled") return `${tool.title}已取消`;
    return `已完成${tool.title}`;
  }

  const counts = new Map<string, number>();
  for (const tool of tools) {
    counts.set(tool.title, (counts.get(tool.title) ?? 0) + 1);
  }
  const parts = Array.from(counts.entries()).map(([title, count]) =>
    count > 1 ? `${title} ×${count}` : title,
  );
  const status = aggregateStatus(tools.map((tool) => tool.status));
  if (status === "running" || status === "pending") return `正在处理：${parts.join(" · ")}`;
  if (status === "failed") return `部分失败：${parts.join(" · ")}`;
  return parts.join(" · ");
}
