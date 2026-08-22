import { useEffect, useRef } from "react";

import { useNotifications } from "@/hooks/use-notifications";
import { useAIAssistant } from "@/lib/ai-assistant-store";
import { useAuth } from "@/lib/auth";

const HANDLED_WAKE_KEY = "bidpilot:handled-agent-wakes";
function readHandledWakeIds(): Set<string> {
  try {
    const raw = sessionStorage.getItem(HANDLED_WAKE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    return new Set(Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : []);
  } catch {
    return new Set();
  }
}

function writeHandledWakeIds(ids: Set<string>) {
  try {
    sessionStorage.setItem(HANDLED_WAKE_KEY, JSON.stringify([...ids].slice(-40)));
  } catch {
    // ignore quota / private mode
  }
}

function parseAgentWakeLink(link: string | undefined): {
  conversationId: string | null;
  wakeId: string | null;
} {
  if (!link) return { conversationId: null, wakeId: null };
  try {
    const url = new URL(link, window.location.origin);
    if (!url.pathname.startsWith("/agent")) {
      return { conversationId: null, wakeId: null };
    }
    return {
      conversationId: url.searchParams.get("conversation"),
      wakeId: url.searchParams.get("wake"),
    };
  } catch {
    return { conversationId: null, wakeId: null };
  }
}

/**
 * A background completion is a system observation, never a user message.
 * The server resumes the Agent run. This listener only refreshes an open
 * conversation so the persisted continuation becomes visible.
 *
 * Mounted inside AIAssistantProvider + authenticated platform shell.
 */
export function AgentWakeResume() {
  const { user } = useAuth();
  const { loadConversation, state } = useAIAssistant();
  const { notifications } = useNotifications({
    enabled: Boolean(user),
    // SSE is primary; poll is backup (60s when SSE healthy, 12s fallback).
    pollIntervalMs: 12_000,
    preferSse: true,
  });
  const inFlightRef = useRef<string | null>(null);
  const handledRef = useRef<Set<string>>(readHandledWakeIds());

  useEffect(() => {
    if (!user) return;
    if (inFlightRef.current) return;

    const candidate = notifications.find((item) => {
      if (item.read) return false;
      if (item.type !== "agent_task") return false;
      if (handledRef.current.has(item.id)) return false;
      const parsed = parseAgentWakeLink(item.link);
      return Boolean(parsed.conversationId && parsed.wakeId);
    });
    if (!candidate) return;

    const { conversationId, wakeId } = parseAgentWakeLink(candidate.link);
    if (!conversationId || !wakeId) return;

    const wakeKey = `${conversationId}:${wakeId}`;
    if (handledRef.current.has(wakeKey) || handledRef.current.has(candidate.id)) return;

    inFlightRef.current = candidate.id;
    handledRef.current.add(candidate.id);
    handledRef.current.add(wakeKey);
    writeHandledWakeIds(handledRef.current);

    void (async () => {
      try {
        if (state.currentConversationId === conversationId) {
          await loadConversation(conversationId);
        }
      } catch {
        // Allow a later notification poll to retry the passive refresh.
        handledRef.current.delete(candidate.id);
        handledRef.current.delete(wakeKey);
        writeHandledWakeIds(handledRef.current);
      } finally {
        inFlightRef.current = null;
      }
    })();
  }, [
    loadConversation,
    notifications,
    state.currentConversationId,
    user,
  ]);

  return null;
}
