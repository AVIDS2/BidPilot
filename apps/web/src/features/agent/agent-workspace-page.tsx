import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { isAssistantBusy, useAIAssistant } from "@/lib/ai-assistant-store";
import { LinearAgentWorkspace } from "./linear-agent-workspace";

const HANDLED_WAKE_KEY = "bidpilot:handled-agent-wakes";

function rememberWakeKey(wakeKey: string) {
  try {
    const raw = sessionStorage.getItem(HANDLED_WAKE_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    const ids = new Set(Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : []);
    ids.add(wakeKey);
    sessionStorage.setItem(HANDLED_WAKE_KEY, JSON.stringify([...ids].slice(-40)));
  } catch {
    // ignore
  }
}

function wasWakeHandled(wakeKey: string) {
  try {
    const raw = sessionStorage.getItem(HANDLED_WAKE_KEY);
    if (!raw) return false;
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) && parsed.includes(wakeKey);
  } catch {
    return false;
  }
}

/**
 * Full-page chat surface: app nav (shell) | history | conversation.
 * No decorative page title chrome — height goes to the chat.
 */
export function AgentWorkspacePage() {
  const [params] = useSearchParams();
  const { dispatch, loadConversation, sendMessage, state } = useAIAssistant();
  const handledWakeRef = useRef<string | null>(null);
  const projectId = params.get("project_id") || undefined;
  const conversationId = params.get("conversation");
  const wake = params.get("wake");

  useEffect(() => {
    dispatch({ type: "SET_CONTEXT", context: { page: "agent", projectId } });
  }, [dispatch, projectId]);

  useEffect(() => {
    if (!conversationId) return;

    const wakeKey = wake ? `${conversationId}:${wake}` : null;
    const alreadyLoaded =
      state.currentConversationId === conversationId && state.messages.length > 0;

    const resumeIfNeeded = () => {
      if (!wakeKey || handledWakeRef.current === wakeKey) return;
      if (wasWakeHandled(wakeKey)) {
        handledWakeRef.current = wakeKey;
        return;
      }
      if (isAssistantBusy(state.status)) return;
      handledWakeRef.current = wakeKey;
      rememberWakeKey(wakeKey);
      void sendMessage(
        "后台长任务已更新。请根据最新结果继续推进未完成步骤；不要重复发起同一个已完成任务。",
        { displayContent: "继续后台任务" },
      );
    };

    if (alreadyLoaded) {
      resumeIfNeeded();
      return;
    }

    void loadConversation(conversationId).then(() => {
      resumeIfNeeded();
    });
  }, [
    loadConversation,
    sendMessage,
    conversationId,
    state.currentConversationId,
    state.messages.length,
    state.status,
    wake,
  ]);

  return (
    <LinearAgentWorkspace />
  );
}
