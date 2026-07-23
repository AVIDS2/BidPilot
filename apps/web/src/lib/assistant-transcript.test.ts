import { describe, expect, it } from "vitest";
import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";
import {
  appendNarrativePart,
  buildTranscriptTurns,
  ensureTurnPart,
  narrativeTextFromParts,
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
});
