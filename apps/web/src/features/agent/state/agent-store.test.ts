import { describe, expect, it } from "vitest";
import { mergeAssistantMessages, type ChatMessage } from "./agent-store";

const message = (overrides: Partial<ChatMessage>): ChatMessage => ({
  id: "local",
  role: "user",
  content: "你好",
  timestamp: 1,
  ...overrides,
});

describe("mergeAssistantMessages", () => {
  it("does not duplicate an optimistic user message after durable history arrives", () => {
    const current = [message({ id: "optimistic-user", durableId: "user-1" })];
    const incoming = [message({ id: "user-1", durableId: "user-1", timestamp: 2 })];

    const merged = mergeAssistantMessages(current, incoming);

    expect(merged).toHaveLength(1);
    expect(merged[0].id).toBe("user-1");
  });

  it("does not duplicate an optimistic assistant message after runtime history arrives", () => {
    const current = [message({ id: "optimistic-assistant", role: "assistant", content: "你好", runtimeRunId: "run-1" })];
    const incoming = [message({ id: "assistant-1", role: "assistant", content: "你好！", runtimeRunId: "run-1", timestamp: 2 })];

    const merged = mergeAssistantMessages(current, incoming);

    expect(merged).toHaveLength(1);
    expect(merged[0].id).toBe("assistant-1");
    expect(merged[0].content).toBe("你好！");
  });
});
