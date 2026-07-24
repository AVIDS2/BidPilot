import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { AIAssistantPanel } from "@/components/ai-assistant/AIAssistantPanel";
import { isAssistantBusy, useAIAssistant } from "@/lib/ai-assistant-store";

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
 * The full-page operator reuses the same conversation and Runtime event state
 * as the contextual side panel. It is a workspace surface, not a second chat.
 *
 * Query params:
 * - project: bind assistant project context
 * - conversation: restore a specific conversation
 * - wake: if present, auto-send a resume prompt after load so the agent
 *   continues after a background workflow notification.
 *
 * Global AgentWakeResume also consumes durable agent_task notifications; both
 * paths share the same sessionStorage wake key to avoid double-resume.
 */
export function AgentWorkspacePage() {
  const [params] = useSearchParams();
  const { loadConversation, sendMessage, state } = useAIAssistant();
  const handledWakeRef = useRef<string | null>(null);

  useEffect(() => {
    const conversationId = params.get("conversation");
    const wake = params.get("wake");
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
        {
          displayContent: "继续后台任务",
        },
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
    params,
    sendMessage,
    state.currentConversationId,
    state.messages.length,
    state.status,
  ]);

  return (
    <section
      className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col"
      aria-label="BidPilot Agent workspace"
    >
      <h2 className="sr-only">BidPilot AI</h2>
      <div className="mx-auto flex h-full min-h-0 w-full min-w-0 max-w-[1120px] flex-1 flex-col">
        <AIAssistantPanel variant="workspace" />
      </div>
    </section>
  );
}
