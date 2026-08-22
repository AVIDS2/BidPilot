import { describe, expect, it } from "vitest";
import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";
import {
  appendNarrativePart,
  appendReasoningPart,
  buildTranscriptTurns,
  ensureTurnPart,
  narrativeTextFromParts,
  projectExecutionItemsOntoTranscript,
} from "@/lib/assistant-transcript";

function item(partial: Partial<AssistantExecutionItem> & Pick<AssistantExecutionItem, "id" | "title">): AssistantExecutionItem {
  return {
    kind: "tool",
    status: "succeeded",
    timestamp: Date.now(),
    ...partial,
  };
}

describe("buildTranscriptTurns", () => {
  it("groups tools with the same turnId into one L1 summary", () => {
    const turns = buildTranscriptTurns([
      item({
        id: "1",
        toolCallId: "c1",
        turnId: "turn-1",
        toolName: "search_projects",
        title: "搜索项目",
        status: "succeeded",
      }),
      item({
        id: "2",
        toolCallId: "c2",
        turnId: "turn-1",
        toolName: "list_requirements",
        title: "查看需求",
        status: "running",
      }),
    ]);

    expect(turns).toHaveLength(1);
    expect(turns[0].turnId).toBe("turn-1");
    expect(turns[0].tools).toHaveLength(2);
    expect(turns[0].status).toBe("running");
    expect(turns[0].summary).toContain("搜索项目");
    expect(turns[0].summary).toContain("查看需求");
  });

  it("keeps separate turns when turn ids differ", () => {
    const turns = buildTranscriptTurns([
      item({ id: "1", toolCallId: "c1", turnId: "turn-1", title: "搜索项目", toolName: "search_projects" }),
      item({ id: "2", toolCallId: "c2", turnId: "turn-2", title: "查看需求", toolName: "list_requirements" }),
    ]);
    expect(turns).toHaveLength(2);
  });

  it("does not clobber distinct tool call ids without turn ids", () => {
    const turns = buildTranscriptTurns([
      item({ id: "1", toolCallId: "c1", title: "搜索项目", toolName: "search_projects" }),
      item({ id: "2", toolCallId: "c2", title: "查看需求", toolName: "list_requirements" }),
    ]);
    expect(turns).toHaveLength(2);
    expect(turns[0].tools[0].toolCallId).toBe("c1");
    expect(turns[1].tools[0].toolCallId).toBe("c2");
  });
});

describe("interleaved transcript parts", () => {
  it("appends text into the open narrative and opens a new one after a turn", () => {
    let parts = appendNarrativePart(undefined, "先看一下项目。");
    parts = ensureTurnPart(parts, "turn-1");
    parts = appendNarrativePart(parts, "找到 3 个项目。");
    expect(parts.map((part) => part.kind)).toEqual(["narrative", "turn", "narrative"]);
    expect(narrativeTextFromParts(parts)).toBe("先看一下项目。找到 3 个项目。");
  });

  it("is idempotent for the same turn id", () => {
    let parts = ensureTurnPart(undefined, "turn-1");
    parts = ensureTurnPart(parts, "turn-1");
    expect(parts).toHaveLength(1);
  });

  it("opens a new execution group after public narration even when Pi keeps the same turn id", () => {
    let parts = ensureTurnPart(undefined, "turn-1", 1, 1);
    parts = appendNarrativePart(parts, "第一批工具完成，我继续核对。", 2);
    parts = ensureTurnPart(parts, "turn-1", 3, 3);

    expect(parts.map((part) => part.kind)).toEqual(["turn", "narrative", "turn"]);
    const turns = parts.filter((part) => part.kind === "turn");
    expect(turns[0].executionGroupId).not.toBe(turns[1].executionGroupId);
  });

  it("projects tools onto chronological groups without inspecting message text", () => {
    const parts = [
      { id: "group-1", kind: "turn" as const, turnId: "same-turn", executionGroupId: "group-1", timestamp: 1 },
      { id: "narrative", kind: "narrative" as const, text: "继续下一阶段。", timestamp: 2 },
      { id: "group-2", kind: "turn" as const, turnId: "same-turn", executionGroupId: "group-2", timestamp: 3 },
    ];
    const projection = projectExecutionItemsOntoTranscript(parts, [
      item({ id: "first", title: "第一次执行", executionGroupId: "group-1", turnId: "same-turn" }),
      item({ id: "second", title: "第二次执行", executionGroupId: "group-2", turnId: "same-turn" }),
      item({ id: "orphan", title: "未归属执行" }),
    ]);

    expect(projection.itemsByPartId.get("group-1")?.map((entry) => entry.id)).toEqual(["first"]);
    expect(projection.itemsByPartId.get("group-2")?.map((entry) => entry.id)).toEqual(["second"]);
    expect(projection.orphanItems.map((entry) => entry.id)).toEqual(["orphan"]);
  });

  it("keeps one structured research runtime across public progress narration", () => {
    const parts = [
      { id: "group-1", kind: "turn" as const, turnId: "turn-1", executionGroupId: "group-1", timestamp: 1 },
      { id: "narrative", kind: "narrative" as const, text: "已经找到第一批来源。", timestamp: 2 },
      { id: "group-2", kind: "turn" as const, turnId: "turn-1", executionGroupId: "group-2", timestamp: 3 },
    ];
    const projection = projectExecutionItemsOntoTranscript(parts, [
      item({
        id: "research-runtime",
        title: "招标机会深度调研",
        executionGroupId: "group-1",
        presentationKind: "deep_research",
        presentationSessionId: "research-1",
      }),
      item({
        id: "search-1",
        title: "联网搜索",
        executionGroupId: "group-1",
        presentationKind: "deep_research",
        presentationSessionId: "research-1",
      }),
      item({
        id: "search-2",
        title: "联网搜索",
        executionGroupId: "group-2",
        presentationKind: "deep_research",
        presentationSessionId: "research-1",
      }),
    ]);

    expect(projection.itemsByPartId.get("group-1")?.map((entry) => entry.id)).toEqual([
      "research-runtime",
      "search-1",
      "search-2",
    ]);
    expect(projection.itemsByPartId.get("group-2")).toBeUndefined();
  });

  it("uses the server-provided completion summary for a completed tool", () => {
    const [turn] = buildTranscriptTurns([
      item({
        id: "export",
        title: "导出交付物",
        toolName: "export_deliverable",
        summary: "交付物「技术响应文件」导出已就绪，可直接下载。",
      }),
    ]);
    expect(turn.summary).toBe("交付物「技术响应文件」导出已就绪，可直接下载。");
  });

  it("does not duplicate a replayed titled public narration", () => {
    const options = {
      source: "harness" as const,
      turnId: "turn-1",
      title: "先确认项目范围，再读取大纲。",
    };
    let parts = appendReasoningPart(undefined, options.title, options);
    parts = appendReasoningPart(parts, options.title, options);
    expect(parts).toHaveLength(1);
  });
});
