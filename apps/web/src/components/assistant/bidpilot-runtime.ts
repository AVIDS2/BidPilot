/**
 * BidPilot Runtime Bridge — connects our backend /assistant/stream API
 * to assistant-ui components via useLocalRuntime.
 *
 * We do NOT use useLangGraphRuntime because our backend emits custom
 * SSE events, not LangGraph SDK format. useLocalRuntime gives us full
 * control to push messages as we receive them from the SSE stream.
 */

import { useLocalRuntime } from "@assistant-ui/react";
import { useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("docpilot_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/**
 * Parse our custom SSE stream from the backend.
 * Backend events:
 *   assistant.message    → text chunk
 *   assistant.tool_started → tool call start
 *   assistant.tool_succeeded → tool result
 *   assistant.end         → stream complete
 */
async function* parseStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): AsyncGenerator<{ content?: string; done?: boolean }> {
  const decoder = new TextDecoder();
  let buffer = "";
  let fullContent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      let eventType = "";
      let dataStr = "";
      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        if (line.startsWith("data: ")) dataStr = line.slice(6);
      }
      if (!dataStr) continue;

      let data: Record<string, unknown>;
      try {
        data = JSON.parse(dataStr);
      } catch {
        continue;
      }

      switch (eventType) {
        case "assistant.message": {
          const text = String(data.content ?? "");
          fullContent += text;
          yield { content: text };
          break;
        }
        case "assistant.end":
          yield { content: fullContent, done: true };
          return;
      }
    }
  }

  yield { content: fullContent, done: true };
}

export function useBidPilotRuntime({ projectId }: { projectId?: string } = {}) {
  const onSend = useCallback(
    async (message: string) => {
      const response = await fetch(`${API_BASE}/assistant/stream`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          message,
          project_id: projectId ?? null,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      return parseStream(reader);
    },
    [projectId],
  );

  return useLocalRuntime({ onSend });
}
