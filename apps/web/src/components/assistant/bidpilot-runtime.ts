/**
 * Runtime bridge: connects BidPilot's backend /assistant/stream API
 * to assistant-ui's useLangGraphRuntime.
 *
 * Our backend uses custom SSE events, not the LangGraph SDK format.
 * This bridge translates between the two so we can use assistant-ui
 * components directly without changing the backend API.
 */

import { useLangGraphRuntime } from "@assistant-ui/react-langgraph";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("docpilot_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

type StreamEvent =
  | { type: "text"; content: string }
  | { type: "tool_call"; toolName: string; args: unknown }
  | { type: "tool_result"; toolName: string; result: unknown; summary: string }
  | { type: "done" };

/**
 * Parse our custom SSE format into typed events.
 * Our backend sends: event: <type>\ndata: <json>\n\n
 */
async function* parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): AsyncGenerator<StreamEvent> {
  const decoder = new TextDecoder();
  let buffer = "";

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
        if (line.startsWith("event: ")) eventType = line.slice(7);
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
        case "assistant.message":
          if (data.content) {
            yield { type: "text", content: String(data.content) };
          }
          break;
        case "assistant.tool_started":
          yield {
            type: "tool_call",
            toolName: String(data.tool_name ?? ""),
            args: data.arguments ?? {},
          };
          break;
        case "assistant.tool_succeeded":
          yield {
            type: "tool_result",
            toolName: String(data.tool_name ?? ""),
            result: data.result,
            summary: String(data.summary ?? ""),
          };
          break;
        case "assistant.tool_failed":
          yield {
            type: "text",
            content: `\n\n工具执行失败: ${data.error_message ?? "未知错误"}`,
          };
          break;
        case "assistant.end":
          yield { type: "done" };
          return;
      }
    }
  }
  yield { type: "done" };
}

/**
 * Send a message to the assistant and yield assistant-ui compatible events.
 */
async function* streamMessage(
  message: string,
  conversationId: string | null,
  projectId?: string,
) {
  const response = await fetch(`${API_BASE}/assistant/stream`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      project_id: projectId,
    }),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => "Unknown error");
    yield {
      type: "text" as const,
      content: `请求失败 (${response.status}): ${errText}`,
    };
    yield { type: "done" as const };
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    yield { type: "done" as const };
    return;
  }

  yield* parseSSEStream(reader);
}

// ── Conversation management (maps to our chat API) ──

async function createConversation(projectId?: string) {
  // The assistant auto-creates conversations, so we just return a placeholder
  // The actual conversation_id comes back in the SSE stream
  return { thread_id: `new-${Date.now()}` };
}

async function loadConversation(conversationId: string) {
  try {
    const response = await fetch(
      `${API_BASE}/chat/conversations/${conversationId}/messages`,
      { headers: getAuthHeaders() },
    );
    if (!response.ok) return { messages: [] };
    const data = await response.json();
    return {
      messages: (data.items ?? []).map(
        (m: { role: string; content: string }) => ({
          role: m.role,
          content: m.content,
        }),
      ),
    };
  } catch {
    return { messages: [] };
  }
}

// ── Hook ──

interface UseBidPilotRuntimeOptions {
  projectId?: string;
}

export function useBidPilotRuntime({ projectId }: UseBidPilotRuntimeOptions = {}) {
  return useLangGraphRuntime({
    stream: async function* (messages) {
      // Extract the last user message
      const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
      const text =
        lastUserMsg?.content
          ?.map((part) => (part.type === "text" ? part.text : ""))
          .join("") ?? "";

      // Stream from our backend
      yield* streamMessage(text, null, projectId);
    },
    create: async () => {
      return await createConversation(projectId);
    },
    load: async (externalId) => {
      return await loadConversation(externalId);
    },
  });
}
