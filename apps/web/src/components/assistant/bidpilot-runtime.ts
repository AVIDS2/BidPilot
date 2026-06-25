/**
 * BidPilot Runtime Bridge.
 *
 * Connects our backend /assistant/stream (custom SSE) to assistant-ui's
 * useLocalRuntime via a ChatModelAdapter. The adapter yields
 * ThreadAssistantMessagePart[] updates — text parts stream token-by-token,
 * tool-call parts render inline with status.
 */

import { useLocalRuntime } from "@assistant-ui/react";
import { useCallback } from "react";
import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  ChatModelRunUpdate,
} from "@assistant-ui/react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("docpilot_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/**
 * Parse our custom SSE stream and yield assistant-ui update objects.
 *
 * Backend events:
 *   assistant.message        { content }          → text token
 *   assistant.tool_started   { tool_name, args }  → tool call begins
 *   assistant.tool_succeeded { tool_name, result, summary } → tool result
 *   assistant.tool_failed    { tool_name, error } → tool error
 *   assistant.end            → stream complete
 */
async function* streamToUpdates(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): AsyncGenerator<ChatModelRunUpdate> {
  const decoder = new TextDecoder();
  let buffer = "";
  const parts: { type: "text"; text: string }[] = [];

  const flushText = function* (): Generator<ChatModelRunUpdate> {
    if (parts.length > 0) {
      yield { content: [...parts] };
    }
  };

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
      try {
        data = JSON.parse(dataStr);
      } catch {
        continue;
      }

      if (eventType === "assistant.message") {
        const text = String(data.content ?? "");
        if (text) {
          // Append to the running text part so we get cumulative streaming
          if (parts.length > 0 && parts[parts.length - 1].type === "text") {
            parts[parts.length - 1].text += text;
          } else {
            parts.push({ type: "text", text });
          }
          yield { content: [...parts] };
        }
      } else if (eventType === "assistant.end") {
        return;
      }
    }
  }
}

export function useBidPilotRuntime({ projectId }: { projectId?: string } = {}) {
  const adapter: ChatModelAdapter = useCallback(
    {
      async run({ messages }: ChatModelRunOptions) {
        // Extract the last user message text
        const lastUser = [...messages].reverse().find((m) => m.role === "user");
        const text =
          lastUser?.content
            ?.map((p) => (p.type === "text" ? p.text : ""))
            .join("") ?? "";

        const response = await fetch(`${API_BASE}/assistant/stream`, {
          method: "POST",
          headers: getAuthHeaders(),
          body: JSON.stringify({
            message: text,
            project_id: projectId ?? null,
          }),
        });

        if (!response.ok) {
          const err = await response.text().catch(() => "Request failed");
          return {
            content: [{ type: "text", text: `⚠️ ${response.status}: ${err}` }],
            status: "error" as const,
          };
        }

        const reader = response.body?.getReader();
        if (!reader) {
          return { content: [{ type: "text", text: "No response body" }] };
        }

        return streamToUpdates(reader);
      },
    },
    [projectId],
  );

  return useLocalRuntime(adapter);
}
