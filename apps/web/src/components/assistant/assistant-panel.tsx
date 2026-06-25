/**
 * BidPilot AI Assistant — powered by assistant-ui primitives.
 *
 * Uses @assistant-ui/react for Thread, Composer, Message, ThreadList,
 * BranchPicker, and Markdown rendering. Connects to our LangGraph
 * backend via useBidPilotRuntime → POST /assistant/stream.
 */

import {
  ThreadPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  ActionBarPrimitive,
  BranchPickerPrimitive,
  AssistantRuntimeProvider,
} from "@assistant-ui/react";
import { Markdown } from "@/components/ui/markdown";
import {
  SparklesIcon,
  PanelRightCloseIcon,
  SendIcon,
  CopyIcon,
  RefreshCwIcon,
  SquareIcon,
  HistoryIcon,
  PlusIcon,
  MessageSquareIcon,
  Trash2Icon,
  SearchIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useState, useCallback, useMemo, type FC } from "react";
import { cn } from "@/lib/utils";
import { useBidPilotRuntime } from "./bidpilot-runtime";
import { useAIAssistant } from "@/lib/ai-assistant-store";
import { deleteChatConversation, type ChatConversationRead } from "@/lib/api";

import "./assistant.css";

/* ─── Date grouping for history ─── */

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

/* ─── Suggestion prompts ─── */

function Suggestions() {
  const { t } = useTranslation("ai-assistant");
  const suggestions = [
    { key: "createProject", text: t("actions.createProjectPrompt") },
    { key: "uploadDoc", text: t("actions.uploadDocPrompt") },
    { key: "generateSection", text: t("actions.generateSectionPrompt") },
    { key: "howToUse", text: t("actions.howToUsePrompt") },
  ];
  return (
    <div className="flex flex-wrap gap-2 px-1">
      {suggestions.map((s) => (
        <ThreadPrimitive.Suggestion
          key={s.key}
          prompt={s.text}
          className="text-xs px-3 py-1.5 rounded-full bg-muted text-muted-foreground border border-border hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer"
        />
      ))}
    </div>
  );
}

/* ─── Message components ─── */

const AssistantMessage: FC = () => {
  return (
    <MessagePrimitive.Root className="group mb-3">
      <div className="max-w-[85%] rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words bg-muted text-foreground">
        <MessagePrimitive.Content />
      </div>
      <MessagePrimitive.If assistant>
        <ActionBarPrimitive.Root className="flex items-center gap-1 mt-1 ml-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <ActionBarPrimitive.Copy asChild>
            <button className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
              <CopyIcon className="size-3" />
            </button>
          </ActionBarPrimitive.Copy>
          <ActionBarPrimitive.Reload asChild>
            <button className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
              <RefreshCwIcon className="size-3" />
            </button>
          </ActionBarPrimitive.Reload>
          <BranchPickerPrimitive.Root asChild>
            <button className="flex items-center gap-0.5 p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors text-[11px]">
              <BranchPickerPrimitive.Previous asChild>
                <button className="p-0"><RefreshCwIcon className="size-2.5 rotate-180" /></button>
              </BranchPickerPrimitive.Previous>
              <BranchPickerPrimitive.Number className="tabular-nums" />
              <BranchPickerPrimitive.Next asChild>
                <button className="p-0"><RefreshCwIcon className="size-2.5" /></button>
              </BranchPickerPrimitive.Next>
            </button>
          </BranchPickerPrimitive.Root>
        </ActionBarPrimitive.Root>
      </MessagePrimitive.If>
    </MessagePrimitive.Root>
  );
};

const UserMessage: FC = () => {
  return (
    <MessagePrimitive.Root className="flex justify-end mb-3">
      <div className="max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed bg-gradient-to-br from-primary to-[oklch(from_var(--primary)_calc(l+0.08)_c_h)] text-primary-foreground">
        <MessagePrimitive.Content />
      </div>
    </MessagePrimitive.Root>
  );
};

/* ─── Composer ─── */

function Composer() {
  const { t } = useTranslation("ai-assistant");

  return (
    <ComposerPrimitive.Root className="shrink-0 px-3 pt-2.5 pb-2 border-t border-border">
      <div className="flex items-center gap-2 rounded-xl px-3 py-1.5 min-h-11 bg-muted border border-border">
        <ComposerPrimitive.AddAttachment asChild>
          <button
            className="shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-background transition-colors"
            aria-label={t("actions.uploadDoc")}
          >
            <PlusIcon className="size-4" />
          </button>
        </ComposerPrimitive.AddAttachment>
        <ComposerPrimitive.Input
          autoFocus
          rows={1}
          className="flex-1 bg-transparent text-sm leading-5 outline-none resize-none min-h-5 max-h-24 placeholder:text-muted-foreground overflow-y-auto text-foreground"
          placeholder={t("inputPlaceholder")}
        />
        <ComposerPrimitive.If condition={(c) => !c.value.trim()}>
          <div className="shrink-0 w-8 h-8 flex items-center justify-center text-muted-foreground/30">
            <SendIcon className="w-4 h-4" />
          </div>
        </ComposerPrimitive.If>
        <ComposerPrimitive.If condition={(c) => c.value.trim().length > 0}>
          <ComposerPrimitive.Send asChild>
            <button
              className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all bg-gradient-to-br from-primary to-[oklch(from_var(--primary)_calc(l+0.08)_c_h)] text-primary-foreground hover:opacity-90"
              aria-label={t("actions.send")}
            >
              <SendIcon className="w-4 h-4" />
            </button>
          </ComposerPrimitive.Send>
        </ComposerPrimitive.If>
        <ComposerPrimitive.Cancel asChild>
          <button
            className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-destructive hover:bg-destructive/10 transition-colors"
            aria-label={t("actions.stop")}
          >
            <SquareIcon className="w-4 h-4" />
          </button>
        </ComposerPrimitive.Cancel>
      </div>
      <div className="flex items-center justify-between mt-1 px-1">
        <span className="text-[10px] text-muted-foreground">
          Enter 发送 · Shift+Enter 换行
        </span>
      </div>
    </ComposerPrimitive.Root>
  );
}

/* ─── History sidebar using ThreadListPrimitive ─── */

function HistorySidebar({
  conversations,
  currentId,
  onClose,
  onDelete,
  onNew,
  onLoadConversation,
  t,
}: {
  conversations: ChatConversationRead[];
  currentId: string | null;
  onClose: () => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  onLoadConversation: (id: string) => void;
  t: (key: string) => string;
}) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter((c) => (c.title || "").toLowerCase().includes(q));
  }, [conversations, searchQuery]);

  const groups = useMemo(() => {
    const grouped: Record<string, ChatConversationRead[]> = {
      today: [], yesterday: [], thisWeek: [], earlier: [],
    };
    for (const c of filtered) {
      const group = getDateGroup(c.created_at);
      grouped[group].push(c);
    }
    return grouped;
  }, [filtered]);

  const groupLabels: Record<string, string> = {
    today: t("history.today"),
    yesterday: t("history.yesterday"),
    thisWeek: t("history.thisWeek"),
    earlier: t("history.earlier"),
  };

  return (
    <div className="w-64 h-full shrink-0 flex flex-col border-r bg-card shadow-xl" style={{ borderColor: "var(--border)" }}>
      <div className="p-3 flex items-center justify-between border-b shrink-0" style={{ borderColor: "var(--border)" }}>
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{t("panel.history")}</span>
        <div className="flex items-center gap-1">
          <button className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" onClick={onNew} title={t("panel.newConversation")}>
            <PlusIcon className="size-3" />
          </button>
          <button className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" onClick={onClose} title={t("panel.closeHistory")}>
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
        ) : (
          Object.entries(groups).map(([key, items]) => {
            if (items.length === 0) return null;
            return (
              <div key={key}>
                <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60 px-2 mb-1">{groupLabels[key]}</p>
                <div className="space-y-0.5">
                  {items.map((conv) => {
                    const active = conv.id === currentId;
                    const isHovered = hoveredId === conv.id;
                    return (
                      <div key={conv.id}
                        className={cn("relative rounded-lg px-2.5 py-2 cursor-pointer transition-colors text-left", active ? "bg-muted" : "hover:bg-muted/50")}
                        onMouseEnter={() => setHoveredId(conv.id)} onMouseLeave={() => setHoveredId(null)}
                        onClick={() => { onLoadConversation(conv.id); onClose(); }}>
                        <div className="text-xs font-medium truncate pr-6 text-foreground">{conv.title || t("panel.untitledConversation")}</div>
                        <div className="text-[10px] mt-0.5 text-muted-foreground/60">{conv.created_at ? new Date(conv.created_at).toLocaleDateString() : ""}</div>
                        {isHovered && !active && (
                          <button className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors"
                            onClick={(e) => { e.stopPropagation(); onDelete(conv.id); }} title={t("history.delete")}>
                            <Trash2Icon className="size-3" />
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

/* ─── Main Panel ─── */

export function AssistantPanel() {
  const { state, close, startNewConversation, loadConversation, refreshConversations } = useAIAssistant();
  const { t } = useTranslation("ai-assistant");
  const [historyOpen, setHistoryOpen] = useState(false);
  const runtime = useBidPilotRuntime({
    projectId: state.currentContext.projectId ?? undefined,
  });

  const handleDeleteConversation = useCallback(async (id: string) => {
    try {
      await deleteChatConversation(id);
      if (state.currentConversationId === id) {
        startNewConversation();
      }
      await refreshConversations();
    } catch (error) {
      console.error("Failed to delete conversation:", error);
    }
  }, [state.currentConversationId, startNewConversation, refreshConversations]);

  if (!state.isOpen || state.mode !== "panel") return null;

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="fixed top-0 right-0 z-40 h-full w-full sm:w-[400px] md:w-[480px] lg:w-[520px] flex flex-col animate-slide-in bg-background border-l border-border shadow-[-8px_0_30px_oklch(0_0_0/0.08)]">
        {/* Header */}
        <div className="flex items-center justify-between px-3 h-12 shrink-0 border-b border-border">
          <div className="flex items-center gap-2 min-w-0">
            <button
              className={cn(
                "p-1.5 rounded-lg transition-colors",
                historyOpen ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-muted",
              )}
              onClick={() => setHistoryOpen((v) => !v)}
              title={t("panel.history")}
            >
              <HistoryIcon className="size-4" />
            </button>
            <div className="flex items-center gap-2 min-w-0">
              <SparklesIcon className="size-4 text-primary shrink-0" />
              <span className="text-sm font-semibold truncate text-foreground">
                {t("title")}
              </span>
            </div>
            <ThreadPrimitive.If running>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary animate-pulse">
                {t("status.thinking")}
              </span>
            </ThreadPrimitive.If>
          </div>
          <button
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            onClick={close}
            title={t("panel.close")}
          >
            <PanelRightCloseIcon className="size-4" />
          </button>
        </div>

        {/* Content: History + Thread */}
        <div className="relative flex-1 min-h-0 overflow-hidden">
          {historyOpen && (
            <>
              <div
                className="absolute inset-0 z-10 bg-black/20 backdrop-blur-[1px]"
                onClick={() => setHistoryOpen(false)}
              />
              <div className="absolute inset-y-0 left-0 z-20">
                <HistorySidebar
                  conversations={Array.isArray(state.conversations) ? state.conversations : []}
                  currentId={state.currentConversationId}
                  onClose={() => setHistoryOpen(false)}
                  onDelete={handleDeleteConversation}
                  onNew={startNewConversation}
                  onLoadConversation={loadConversation}
                  t={t}
                />
              </div>
            </>
          )}

          <ThreadPrimitive.Root className="h-full flex flex-col">
            <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto p-4">
              <ThreadPrimitive.Empty>
                <div className="flex flex-col items-center justify-center h-full py-16">
                  <div className="w-14 h-14 rounded-2xl mb-4 flex items-center justify-center bg-gradient-to-br from-primary to-[oklch(from_var(--primary)_calc(l+0.08)_c_h)]">
                    <SparklesIcon className="w-7 h-7 text-primary-foreground" />
                  </div>
                  <h3 className="text-base font-semibold mb-1 text-foreground">
                    {t("welcome.title")}
                  </h3>
                  <p className="text-sm mb-6 text-muted-foreground max-w-xs">
                    {t("welcome.description")}
                  </p>
                  <Suggestions />
                </div>
              </ThreadPrimitive.Empty>

              <ThreadPrimitive.Messages
                components={{
                  UserMessage,
                  AssistantMessage,
                }}
              />

              <ThreadPrimitive.ScrollToBottom
                className="sticky bottom-2 mx-auto block size-8 rounded-full bg-muted border border-border shadow-md hover:bg-accent transition-colors cursor-pointer data-[hidden]:hidden"
              />
            </ThreadPrimitive.Viewport>

            <Composer />
          </ThreadPrimitive.Root>
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
}
