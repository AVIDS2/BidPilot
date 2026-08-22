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

export type AssistantTranscriptPart =
  | { id: string; kind: "narrative"; text: string; timestamp: number }
  | {
      id: string;
      kind: "reasoning";
      text: string;
      source: "provider" | "harness";
      turnId?: string;
      title?: string;
      completed: boolean;
      timestamp: number;
    }
  | {
      id: string;
      kind: "turn";
      turnId: string;
      /**
       * Frontend-only projection identity for one continuous tool burst.
       * A single Pi model turn may contain several tool bursts separated by
       * public narration, so turnId alone is not a visual grouping key.
       */
      executionGroupId?: string;
      timestamp: number;
    };

export interface TranscriptExecutionProjection {
  itemsByPartId: Map<string, AssistantExecutionItem[]>;
  orphanItems: AssistantExecutionItem[];
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
      item.executionGroupId ||
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

/** Append streamed assistant text into the open narrative part (or open a new one). */
export function appendNarrativePart(
  parts: AssistantTranscriptPart[] | undefined,
  text: string,
  now = Date.now(),
): AssistantTranscriptPart[] {
  if (!text) return parts ? [...parts] : [];
  const next = parts ? [...parts] : [];
  const last = next[next.length - 1];
  if (last?.kind === "narrative") {
    next[next.length - 1] = { ...last, text: last.text + text };
    return next;
  }
  next.push({
    id: `narrative-${now}-${next.length}`,
    kind: "narrative",
    text,
    timestamp: now,
  });
  return next;
}

/**
 * Keep provider-visible reasoning as its own chronological transcript block.
 * It is never merged into the final answer or a tool payload.
 */
export function appendReasoningPart(
  parts: AssistantTranscriptPart[] | undefined,
  text: string,
  options: {
    source?: "provider" | "harness";
    turnId?: string;
    title?: string;
    now?: number;
  } = {},
): AssistantTranscriptPart[] {
  if (!text) return parts ? [...parts] : [];
  const next = parts ? [...parts] : [];
  const source = options.source ?? "provider";
  const normalizedText = normalizeTranscriptText(text);
  const normalizedTitle = normalizeTranscriptText(options.title ?? "");
  // Runtime event replay can overlap with the live SSE stream after a
  // reconnect. Public narration is emitted as a complete, titled event, so
  // an identical event must be a no-op rather than a second visual step.
  if (
    options.title &&
    next.some(
      (part) =>
        part.kind === "reasoning" &&
        part.source === source &&
        part.turnId === options.turnId &&
        normalizeTranscriptText(part.title ?? "") === normalizedTitle &&
        normalizeTranscriptText(part.text) === normalizedText,
    )
  ) {
    return next;
  }
  const last = next[next.length - 1];
  if (
    last?.kind === "reasoning" &&
    last.source === source &&
    last.turnId === options.turnId &&
    !last.completed
  ) {
    next[next.length - 1] = {
      ...last,
      text: last.text + text,
      title: last.title ?? options.title,
    };
    return next;
  }
  const now = options.now ?? Date.now();
  next.push({
    id: `reasoning-${now}-${next.length}`,
    kind: "reasoning",
    text,
    source,
    turnId: options.turnId,
    title: options.title,
    completed: false,
    timestamp: now,
  });
  return next;
}

function normalizeTranscriptText(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

/** Mark the latest visible reasoning block for this model turn as complete. */
export function completeReasoningPart(
  parts: AssistantTranscriptPart[] | undefined,
  turnId?: string,
): AssistantTranscriptPart[] {
  if (!parts?.length) return [];
  const next = [...parts];
  for (let index = next.length - 1; index >= 0; index -= 1) {
    const part = next[index];
    if (part.kind !== "reasoning") continue;
    if (turnId && part.turnId && part.turnId !== turnId) continue;
    next[index] = { ...part, completed: true };
    break;
  }
  return next;
}

/**
 * Ensure a visual execution group exists at the current chronological
 * position. Consecutive tools reuse the open group; any narrative/reasoning
 * part closes that visual position, so the next tool opens a new group even
 * when Pi keeps the same model turnId.
 */
export function ensureTurnPart(
  parts: AssistantTranscriptPart[] | undefined,
  turnId: string,
  now = Date.now(),
  identitySeed?: string | number,
): AssistantTranscriptPart[] {
  const next = parts ? [...parts] : [];
  const last = next[next.length - 1];
  if (last?.kind === "turn" && last.turnId === turnId) return next;
  const seed = identitySeed === undefined ? `${now}-${next.length}` : String(identitySeed);
  const executionGroupId = `execution-group-${turnId}-${seed}`;
  next.push({
    id: executionGroupId,
    kind: "turn",
    turnId,
    executionGroupId,
    timestamp: now,
  });
  return next;
}

/**
 * Project execution items onto chronological transcript positions without
 * inspecting user or model text. New events use executionGroupId; persisted
 * legacy messages fall back to turnId exactly once.
 */
export function projectExecutionItemsOntoTranscript(
  parts: AssistantTranscriptPart[] | undefined,
  items: AssistantExecutionItem[],
): TranscriptExecutionProjection {
  // A feature runtime is one visual unit even when Pi narrates between its
  // tool calls. The server-issued presentation session, not chat text or tool
  // names, identifies which later events belong under its first timeline row.
  const presentationGroups = new Map<string, string>();
  for (const item of items) {
    if (
      item.presentationSessionId &&
      item.presentationKind &&
      item.executionGroupId &&
      !presentationGroups.has(item.presentationSessionId)
    ) {
      presentationGroups.set(item.presentationSessionId, item.executionGroupId);
    }
  }
  const projectedItems = items.map((item) => {
    const presentationGroup = item.presentationSessionId
      ? presentationGroups.get(item.presentationSessionId)
      : undefined;
    return presentationGroup && item.executionGroupId !== presentationGroup
      ? { ...item, executionGroupId: presentationGroup }
      : item;
  });
  const itemsByPartId = new Map<string, AssistantExecutionItem[]>();
  const itemsByGroup = new Map<string, AssistantExecutionItem[]>();
  const legacyItemsByTurn = new Map<string, AssistantExecutionItem[]>();

  for (const item of projectedItems) {
    if (item.executionGroupId) {
      const grouped = itemsByGroup.get(item.executionGroupId) ?? [];
      grouped.push(item);
      itemsByGroup.set(item.executionGroupId, grouped);
      continue;
    }
    if (item.turnId) {
      const grouped = legacyItemsByTurn.get(item.turnId) ?? [];
      grouped.push(item);
      legacyItemsByTurn.set(item.turnId, grouped);
    }
  }

  const consumedGroups = new Set<string>();
  const consumedLegacyTurns = new Set<string>();
  for (const part of parts ?? []) {
    if (part.kind !== "turn") continue;
    if (part.executionGroupId) {
      const grouped = itemsByGroup.get(part.executionGroupId) ?? [];
      if (grouped.length > 0) {
        itemsByPartId.set(part.id, grouped);
        consumedGroups.add(part.executionGroupId);
      }
      continue;
    }
    if (consumedLegacyTurns.has(part.turnId)) continue;
    const grouped = legacyItemsByTurn.get(part.turnId) ?? [];
    if (grouped.length > 0) {
      itemsByPartId.set(part.id, grouped);
      consumedLegacyTurns.add(part.turnId);
    }
  }

  return {
    itemsByPartId,
    orphanItems: projectedItems.filter((item) => {
      if (item.executionGroupId) return !consumedGroups.has(item.executionGroupId);
      if (item.turnId) return !consumedLegacyTurns.has(item.turnId);
      return true;
    }),
  };
}

export function narrativeTextFromParts(parts: AssistantTranscriptPart[] | undefined): string {
  if (!parts?.length) return "";
  return parts
    .filter((part): part is Extract<AssistantTranscriptPart, { kind: "narrative" }> => part.kind === "narrative")
    .map((part) => part.text)
    .join("");
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
    if (tool.status === "failed") return tool.errorMessage || `${tool.title}失败`;
    if (tool.status === "cancelled") return `${tool.title}已取消`;
    return tool.summary || `已完成${tool.title}`;
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
  const completedSummaries = tools
    .filter((tool) => tool.status === "succeeded" && tool.summary)
    .map((tool) => tool.summary!);
  return completedSummaries[completedSummaries.length - 1] || parts.join(" · ");
}
