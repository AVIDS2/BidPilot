import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useNotifications } from "@/hooks/use-notifications";
import { isAssistantBusy, useAIAssistant } from "@/lib/ai-assistant-store";
import { useAuth } from "@/lib/auth";

const HANDLED_WAKE_KEY = "bidpilot:handled-agent-wakes";
const RESUME_PROMPT =
  "后台长任务已更新。请根据最新结果继续推进未完成步骤；不要重复发起同一个已完成任务。";

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
 * Global wake consumer: when a durable agent_task notification arrives,
 * resume the bound conversation without requiring the user to open /agent.
 *
 * Mounted inside AIAssistantProvider + authenticated platform shell.
 */
export function AgentWakeResume() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { loadConversation, sendMessage, state } = useAIAssistant();
  const { notifications, markAsRead } = useNotifications({
    enabled: Boolean(user),
    pollIntervalMs: 8_000,
  });
  const inFlightRef = useRef<string | null>(null);
  const handledRef = useRef<Set<string>>(readHandledWakeIds());

  useEffect(() => {
    if (!user || isAssistantBusy(state.status)) return;
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
        if (state.currentConversationId !== conversationId) {
          await loadConversation(conversationId);
        }
        await sendMessage(RESUME_PROMPT, {
          displayContent: "继续后台任务",
        });
        await markAsRead(candidate.id);

        // Keep the operator surface in sync when user is already browsing the app,
        // without forcing a hard navigation away from project detail unless helpful.
        const onAgentPage = location.pathname.startsWith("/agent");
        if (onAgentPage) {
          const next = `/agent?conversation=${encodeURIComponent(conversationId)}&wake=${encodeURIComponent(wakeId)}`;
          if (`${location.pathname}${location.search}` !== next) {
            navigate(next, { replace: true });
          }
        }
      } catch {
        // Allow retry on a later poll if resume failed.
        handledRef.current.delete(candidate.id);
        handledRef.current.delete(wakeKey);
        writeHandledWakeIds(handledRef.current);
      } finally {
        inFlightRef.current = null;
      }
    })();
  }, [
    loadConversation,
    location.pathname,
    location.search,
    markAsRead,
    navigate,
    notifications,
    sendMessage,
    state.currentConversationId,
    state.status,
    user,
  ]);

  return null;
}
