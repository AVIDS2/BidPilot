/**
 * BidPilot Runtime Bridge.
 *
 * useLocalRuntime expects a ChatModelAdapter with:
 *   run(options) -> AsyncGenerator<ChatModelRunUpdate>
 *
 * ChatModelRunUpdate = { content: ThreadAssistantMessagePart[] }
 *
 * Each yield is the FULL cumulative content (not delta).
 */

import { useLocalRuntime } from "@assistant-ui/react";
import { useMemo } from "react";
import type { ChatModelAdapter } from "@assistant-ui/react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("docpilot_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function useBidPilotRuntime({ projectId }: { projectId?: string } = {}) {
  const adapter: ChatModelAdapter = useMemo(() => ({
    async *run({ messages, abortSignal }) {
      // Extract last user message text
      const lastUser = [...messages].reverse().find((m) => m.role === "user");
      const text = lastUser?.content
        ?.map((p: { type: string; text?: string }) => (p.type === "text" ? p.text ?? "" : ""))
        .join("") ?? "";

      const response = await fetch(`${API_BASE}/assistant/stream`, {
        method: "POST",
        headers: getAuthHeaders(),
        signal: abortSignal,
        body: JSON.stringify({ message: text, project_id: projectId ?? null }),
      });

      if (!response.ok) {
        const err = await response.text().catch(() => "Request failed");
        yield { content: [{ type: "text" as const, text: `⚠️ ${response.status}: ${err}` }] };
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        yield { content: [{ type: "text" as const, text: "No response body" }] };
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";

        for (const chunk of chunks) {
          let eventType = "";
          let dataStr = "";
          for (const line of chunk.split("\n")) {
            if (line.startsWith("event: ")) eventType = line.slice(7).trim();
            if (line.startsWith("data: ")) dataStr = line.slice(6);
          }
          if (!dataStr) continue;

          let data: Record<string, unknown>;
          try { data = JSON.parse(dataStr); } catch { continue; }

          if (eventType === "assistant.message") {
            const delta = String(data.content ?? "");
            if (delta) {
              fullText += delta;
              yield { content: [{ type: "text" as const, text: fullText }] };
            }
          }
        }
      }

      // Final yield with complete text
      if (fullText) {
        yield { content: [{ type: "text" as const, text: fullText }] };
      }
    },
  }), [projectId]);

  return useLocalRuntime(adapter);
}
