import { describe, expect, it } from "vitest";
import { getAssistantToolLabel } from "./assistant-tool-metadata";

const EN_TOOL_LABELS: Record<string, string> = {
  "activity.tool.list_claim_review_queue": "Check claims awaiting review",
  "activity.tool.search_bid_wiki": "Search Bid Wiki",
  "activity.tool.list_knowledge_portfolio": "View knowledge portfolio",
  "activity.tool.propose_memory": "Save personal preference",
  "activity.tool.forget_memory": "Forget memory",
};

function translate(key: string, options?: Record<string, unknown>) {
  return EN_TOOL_LABELS[key] ?? String(options?.defaultValue ?? key);
}

describe("assistant tool metadata", () => {
  it("renders current knowledge and memory capabilities with user-facing labels", () => {
    for (const [toolName, expectedLabel] of Object.entries({
      list_claim_review_queue: "Check claims awaiting review",
      search_bid_wiki: "Search Bid Wiki",
      list_knowledge_portfolio: "View knowledge portfolio",
      propose_memory: "Save personal preference",
      forget_memory: "Forget memory",
    })) {
      expect(getAssistantToolLabel(toolName, translate)).toBe(expectedLabel);
    }
  });
});
