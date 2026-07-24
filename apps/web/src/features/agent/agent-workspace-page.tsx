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
      className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col bg-[radial-gradient(1200px_480px_at_50%_-80px,color-mix(in_oklch,var(--primary)_10%,transparent),transparent)]"
      aria-label="BidPilot Agent workspace"
    >
      <div className="mx-auto flex w-full max-w-[1120px] shrink-0 items-end justify-between gap-3 px-4 pb-2 pt-4 sm:px-6">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
            Operate
          </p>
          <h2 className="truncate text-lg font-semibold tracking-tight text-foreground sm:text-xl">
            BidPilot Agent
          </h2>
          <p className="mt-0.5 max-w-[52ch] text-xs leading-5 text-muted-foreground">
            大纲优先、受治工具与后台续跑。长任务完成后会自动唤醒继续。
          </p>
        </div>
        <div className="hidden shrink-0 rounded-full border bg-background/80 px-3 py-1 text-[11px] text-muted-foreground shadow-sm backdrop-blur sm:block">
          governed harness
        </div>
      </div>
      <div className="mx-auto flex h-full min-h-0 w-full min-w-0 max-w-[1120px] flex-1 flex-col overflow-hidden rounded-t-2xl border border-b-0 bg-background/90 shadow-[0_-8px_40px_oklch(0_0_0/0.06)] backdrop-blur">
        <AIAssistantPanel variant="workspace" />
      </div>
    </section>
  );
}
