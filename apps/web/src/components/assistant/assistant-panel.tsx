/**
 * BidPilot AI Assistant — minimal assistant-ui integration.
 *
 * Uses the SIMPLEST possible assistant-ui API to avoid rendering bugs.
 * No asChild, no custom components, no BranchPicker — just works.
 */

import {
  ThreadPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  AssistantRuntimeProvider,
} from "@assistant-ui/react";
import {
  SparklesIcon,
  PanelRightCloseIcon,
  HistoryIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
  MessageSquareIcon,
  SendIcon,
  ChevronDownIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useState, useCallback, useMemo } from "react";
import { cn } from "@/lib/utils";
import { useBidPilotRuntime } from "./bidpilot-runtime";
import { useAIAssistant } from "@/lib/ai-assistant-store";
import { deleteChatConversation, type ChatConversationRead } from "@/lib/api";

/* ─── Date grouping ─── */
function getDateGroup(dateStr: string | null): string {
  if (!dateStr) return "earlier";
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);
  if (date >= today) return "today";
  if (date >= yesterday) return "yesterday";
  if (date >= weekAgo) return "thisWeek";
  return "earlier";
}

/* ─── History sidebar ─── */
function HistorySidebar({ conversations, currentId, onClose, onDelete, onNew, onLoad, t }: {
  conversations: ChatConversationRead[];
  currentId: string | null;
  onClose: () => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  onLoad: (id: string) => void;
  t: (k: string) => string;
}) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter((c) => (c.title || "").toLowerCase().includes(q));
  }, [conversations, searchQuery]);

  const groups = useMemo(() => {
    const g: Record<string, ChatConversationRead[]> = { today: [], yesterday: [], thisWeek: [], earlier: [] };
    for (const c of filtered) g[getDateGroup(c.created_at)].push(c);
    return g;
  }, [filtered]);

  const labels: Record<string, string> = {
    today: t("history.today"), yesterday: t("history.yesterday"),
    thisWeek: t("history.thisWeek"), earlier: t("history.earlier"),
  };

  return (
    <div className="w-64 h-full shrink-0 flex flex-col border-r border-border bg-card shadow-2xl">
      <div className="p-3 flex items-center justify-between border-b border-border shrink-0">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{t("panel.history")}</span>
        <div className="flex items-center gap-1">
          <button className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" onClick={onNew}>
            <PlusIcon className="size-3" />
          </button>
          <button className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" onClick={onClose}>
            <PanelRightCloseIcon className="size-3" />
          </button>
        </div>
      </div>
      <div className="px-3 pt-2 pb-1 shrink-0">
        <div className="relative">
          <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder={t("history.searchPlaceholder")}
            className="w-full h-7 pl-8 pr-2 rounded-lg border border-border bg-background text-xs outline-none focus:border-primary" />
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-3">
        {filtered.length === 0 ? (
          <div className="text-center py-8">
            <MessageSquareIcon className="size-8 mx-auto mb-2 text-muted-foreground/40" />
            <p className="text-xs text-muted-foreground">{searchQuery ? t("history.noResults") : t("panel.noHistory")}</p>
          </div>
        ) : Object.entries(groups).map(([key, items]) => items.length > 0 && (
          <div key={key}>
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60 px-2 mb-1">{labels[key]}</p>
            <div className="space-y-0.5">
              {items.map((conv) => {
                const active = conv.id === currentId;
                return (
                  <div key={conv.id}
                    className={cn("relative rounded-lg px-2.5 py-2 cursor-pointer transition-colors text-left", active ? "bg-muted" : "hover:bg-muted/50")}
                    onMouseEnter={() => setHoveredId(conv.id)} onMouseLeave={() => setHoveredId(null)}
                    onClick={() => { onLoad(conv.id); onClose(); }}>
                    <div className="text-xs font-medium truncate pr-6 text-foreground">{conv.title || t("panel.untitledConversation")}</div>
                    <div className="text-[10px] mt-0.5 text-muted-foreground/60">{conv.created_at ? new Date(conv.created_at).toLocaleDateString() : ""}</div>
                    {hoveredId === conv.id && !active && (
                      <button className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors"
                        onClick={(e) => { e.stopPropagation(); onDelete(conv.id); }}>
                        <Trash2Icon className="size-3" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Main Panel — uses assistant-ui primitives with minimal customization ─── */
export function AssistantPanel() {
  const { state, close, startNewConversation, loadConversation, refreshConversations } = useAIAssistant();
  const { t } = useTranslation("ai-assistant");
  const [historyOpen, setHistoryOpen] = useState(false);
  const runtime = useBidPilotRuntime({ projectId: state.currentContext.projectId ?? undefined });

  const handleDelete = useCallback(async (id: string) => {
    try {
      await deleteChatConversation(id);
      if (state.currentConversationId === id) startNewConversation();
      await refreshConversations();
    } catch (e) { console.error("Delete failed:", e); }
  }, [state.currentConversationId, startNewConversation, refreshConversations]);

  if (!state.isOpen || state.mode !== "panel") return null;

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="fixed top-0 right-0 z-40 h-full w-full sm:w-[400px] md:w-[480px] flex flex-col bg-background border-l border-border shadow-lg animate-slide-in">

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-3 h-12 shrink-0 border-b border-border">
          <div className="flex items-center gap-2 min-w-0">
            <button
              className={cn("p-1.5 rounded-lg transition-colors", historyOpen ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-muted")}
              onClick={() => setHistoryOpen(v => !v)}
            >
              <HistoryIcon className="size-4" />
            </button>
            <div className="flex items-center gap-2">
              <div className="flex size-6 items-center justify-center rounded-md bg-primary">
                <SparklesIcon className="size-3.5 text-primary-foreground" />
              </div>
              <span className="text-sm font-semibold text-foreground">{t("title")}</span>
            </div>
            <ThreadPrimitive.If running>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary animate-pulse">
                {t("status.thinking")}
              </span>
            </ThreadPrimitive.If>
          </div>
          <button className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" onClick={close}>
            <PanelRightCloseIcon className="size-4" />
          </button>
        </div>

        {/* ── Content ── */}
        <div className="relative flex-1 min-h-0 overflow-hidden">
          {/* History overlay */}
          {historyOpen && (
            <>
              <div className="absolute inset-0 z-10 bg-black/30 backdrop-blur-[2px]" onClick={() => setHistoryOpen(false)} />
              <div className="absolute inset-y-0 left-0 z-20">
                <HistorySidebar
                  conversations={Array.isArray(state.conversations) ? state.conversations : []}
                  currentId={state.currentConversationId}
                  onClose={() => setHistoryOpen(false)}
                  onDelete={handleDelete}
                  onNew={startNewConversation}
                  onLoad={loadConversation}
                  t={t}
                />
              </div>
            </>
          )}

          {/* ── Thread (assistant-ui handles everything) ── */}
          <ThreadPrimitive.Root className="h-full flex flex-col">
            <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto p-4">
              {/* Empty state */}
              <ThreadPrimitive.Empty>
                <div className="flex flex-col items-center justify-center h-full py-16 text-center">
                  <div className="w-14 h-14 rounded-2xl mb-4 flex items-center justify-center bg-primary">
                    <SparklesIcon className="w-7 h-7 text-primary-foreground" />
                  </div>
                  <h3 className="text-base font-semibold mb-1 text-foreground">{t("welcome.title")}</h3>
                  <p className="text-sm mb-6 text-muted-foreground max-w-xs">{t("welcome.description")}</p>
                  <div className="flex flex-wrap gap-2 px-1 justify-center">
                    <ThreadPrimitive.Suggestion prompt={t("actions.createProjectPrompt")} autoSend className="text-xs px-3 py-1.5 rounded-full bg-muted text-muted-foreground border border-border hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer">
                      {t("actions.createProject")}
                    </ThreadPrimitive.Suggestion>
                    <ThreadPrimitive.Suggestion prompt={t("actions.uploadDocPrompt")} autoSend className="text-xs px-3 py-1.5 rounded-full bg-muted text-muted-foreground border border-border hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer">
                      {t("actions.uploadDoc")}
                    </ThreadPrimitive.Suggestion>
                    <ThreadPrimitive.Suggestion prompt={t("actions.generateSectionPrompt")} autoSend className="text-xs px-3 py-1.5 rounded-full bg-muted text-muted-foreground border border-border hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer">
                      {t("actions.generateSection")}
                    </ThreadPrimitive.Suggestion>
                    <ThreadPrimitive.Suggestion prompt={t("actions.howToUsePrompt")} autoSend className="text-xs px-3 py-1.5 rounded-full bg-muted text-muted-foreground border border-border hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer">
                      {t("actions.howToUse")}
                    </ThreadPrimitive.Suggestion>
                  </div>
                </div>
              </ThreadPrimitive.Empty>

              {/* Messages — must provide components prop */}
              <ThreadPrimitive.Messages
                components={{
                  UserMessage: () => (
                    <MessagePrimitive.Root className="flex justify-end mb-3">
                      <div className="max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed bg-primary text-primary-foreground">
                        <MessagePrimitive.Content />
                      </div>
                    </MessagePrimitive.Root>
                  ),
                  AssistantMessage: () => (
                    <MessagePrimitive.Root className="flex justify-start mb-3">
                      <div className="max-w-[85%] rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed bg-muted text-foreground whitespace-pre-wrap">
                        <MessagePrimitive.Content />
                      </div>
                    </MessagePrimitive.Root>
                  ),
                }}
              />

              {/* Scroll to bottom */}
              <ThreadPrimitive.ScrollToBottom className="sticky bottom-2 mx-auto size-8 rounded-full bg-muted border border-border shadow flex items-center justify-center cursor-pointer data-[hidden]:hidden">
                <ChevronDownIcon className="size-4 text-muted-foreground" />
              </ThreadPrimitive.ScrollToBottom>
            </ThreadPrimitive.Viewport>

            {/* ── Composer (input) ── */}
            <div className="shrink-0 px-3 pt-2 pb-2 border-t border-border">
              <div className="flex items-center gap-2 rounded-xl px-3 py-1.5 bg-muted border border-border">
                <ComposerPrimitive.Input
                  autoFocus
                  rows={1}
                  className="flex-1 bg-transparent text-sm outline-none resize-none min-h-5 max-h-24 placeholder:text-muted-foreground text-foreground"
                  placeholder={t("inputPlaceholder")}
                />
                <ComposerPrimitive.Send className="shrink-0 w-8 h-8 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center">
                  <SendIcon className="size-4" />
                </ComposerPrimitive.Send>
              </div>
              <div className="flex items-center justify-between mt-1 px-1">
                <span className="text-[10px] text-muted-foreground">Enter 发送 · Shift+Enter 换行</span>
                <span className="text-[10px] text-muted-foreground/60">DeepSeek V4 Flash</span>
              </div>
            </div>
          </ThreadPrimitive.Root>
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
}
