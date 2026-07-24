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
 * Full-page operator surface.
 * History rail is owned by AIAssistantPanel (docked left, outside the chat column).
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
      className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col bg-background"
      aria-label="BidPilot Agent workspace"
    >
      <div className="flex shrink-0 items-end justify-between gap-3 border-b border-border/70 px-3 pb-3 pt-2 sm:px-4">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            Operate
          </p>
          <h2 className="truncate text-base font-semibold tracking-tight text-foreground sm:text-lg">
            BidPilot Agent
          </h2>
        </div>
        <div className="hidden shrink-0 rounded-md border border-border/80 bg-card px-2.5 py-1 text-[11px] text-muted-foreground sm:block">
          governed harness
        </div>
      </div>
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <AIAssistantPanel variant="workspace" />
      </div>
    </section>
  );
}
