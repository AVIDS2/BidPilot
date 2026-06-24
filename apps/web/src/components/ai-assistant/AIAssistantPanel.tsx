import { useRef, useEffect, useCallback, useState, useMemo } from "react";
import {
  HistoryIcon,
  PlusIcon,
  SparklesIcon,
  SendIcon,
  CommandIcon,
  PanelRightCloseIcon,
  CornerDownLeftIcon,
  SearchIcon,
  Trash2Icon,
  MessageSquareIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { renameChatConversation, deleteChatConversation, type ChatConversationRead } from "@/lib/api";
import { isAssistantBusy, useAIAssistant, type AssistantStatus, type ChatMessage } from "@/lib/ai-assistant-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Markdown } from "@/components/ui/markdown";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AssistantConfirmationCard } from "./assistant-confirmation-card";
import { AssistantExecutionCard } from "./assistant-execution-card";
import { AssistantWorkflowCard } from "./assistant-workflow-card";

/* ─── Date grouping helpers ─── */

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

function groupConversations(conversations: ChatConversationRead[]) {
  const groups: Record<string, ChatConversationRead[]> = {
    today: [],
    yesterday: [],
    thisWeek: [],
    earlier: [],
  };
  for (const c of conversations) {
    const group = getDateGroup(c.created_at);
    groups[group].push(c);
  }
  return groups;
}

/* ─── Quick action chips shown in empty state ─── */

function QuickActions({ onSelect }: { onSelect: (text: string) => void }) {
  const { t } = useTranslation("ai-assistant");
  const actions = [
    { key: "createProject", text: t("actions.createProjectPrompt") },
    { key: "uploadDoc", text: t("actions.uploadDocPrompt") },
    { key: "generateSection", text: t("actions.generateSectionPrompt") },
    { key: "howToUse", text: t("actions.howToUsePrompt") },
  ];
  return (
    <div className="flex flex-wrap gap-2 px-1">
      {actions.map((a) => (
        <button
          key={a.key}
          onClick={() => onSelect(a.text)}
          className="text-xs px-3 py-1.5 rounded-full transition-all duration-200 hover:scale-105 bg-muted text-muted-foreground border border-border"
        >
          {t(`actions.${a.key}`)}
        </button>
      ))}
    </div>
  );
}

/* ─── Single message bubble ─── */

function normalizeAssistantMarkdown(content: string): string {
  if (!content.includes("\\")) return content;
  let normalized = content;
  normalized = normalized.replace(
    /^\[\s*\n([\s\S]*?\\[a-zA-Z]+[\s\S]*?)\n\]\s*$/gm,
    (_match, expr) => `$$\n${expr.trim()}\n$$`,
  );
  normalized = normalized
    .split("\n")
    .map((line) => {
      const trimmed = line.trim();
      const looksLikeMath =
        /\\(frac|sum|int|sqrt|alpha|beta|gamma|theta|pi|sin|cos|tan|lim|cdot|times|leq|geq|neq|infty|to)/.test(trimmed) ||
        /[=<>]/.test(trimmed);
      const alreadyDelimited = trimmed.startsWith("$") || trimmed.startsWith("\\(") || trimmed.startsWith("\\[");
      if (trimmed && looksLikeMath && !alreadyDelimited && !trimmed.startsWith("- ") && !trimmed.startsWith("* ")) {
        return `$$${trimmed}$$`;
      }
      return line;
    })
    .join("\n");
  return normalized;
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words",
          isUser ? "rounded-br-md" : "rounded-bl-md",
        )}
        style={{
          background: isUser
            ? "linear-gradient(135deg, var(--primary), oklch(from var(--primary) calc(l + 0.08) c h))"
            : "var(--muted)",
          color: isUser ? "var(--primary-foreground)" : "var(--foreground)",
        }}
      >
        {msg.content ? (
          isUser ? (
            <span>{msg.content}</span>
          ) : (
            <Markdown className="[&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-1 [&_pre]:my-2 [&_code]:break-words">
              {normalizeAssistantMarkdown(msg.content)}
            </Markdown>
          )
        ) : (
          <span className="inline-flex gap-1 items-center text-muted-foreground">
            <span className="animate-pulse" style={{ animationDelay: "0ms" }}>●</span>
            <span className="animate-pulse" style={{ animationDelay: "150ms" }}>●</span>
            <span className="animate-pulse" style={{ animationDelay: "300ms" }}>●</span>
          </span>
        )}
      </div>
    </div>
  );
}

function statusLabel(status: AssistantStatus, t: (key: string) => string) {
  if (status === "idle") return "";
  return t(`status.${status}`);
}

/* ─── History Sidebar ─── */

function HistorySidebar({
  conversations,
  currentId,
  searchQuery,
  onSearchChange,
  onSelect,
  onNew,
  onRename,
  onDelete,
  onClose,
  editingId,
  editingTitle,
  onEditTitleChange,
  onCommitRename,
  onCancelRename,
  renamingId,
  renameInputRef,
  t,
}: {
  conversations: ChatConversationRead[];
  currentId: string | null;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string | null) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  editingId: string | null;
  editingTitle: string;
  onEditTitleChange: (v: string) => void;
  onCommitRename: () => void;
  onCancelRename: () => void;
  renamingId: string | null;
  renameInputRef: React.RefObject<HTMLInputElement | null>;
  t: (key: string) => string;
}) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter((c) => (c.title || "").toLowerCase().includes(q));
  }, [conversations, searchQuery]);

  const groups = useMemo(() => groupConversations(filtered), [filtered]);
  const groupLabels: Record<string, string> = {
    today: t("history.today"),
    yesterday: t("history.yesterday"),
    thisWeek: t("history.thisWeek"),
    earlier: t("history.earlier"),
  };

  return (
    <div className="w-64 h-full shrink-0 flex flex-col border-r bg-card shadow-xl" style={{ borderColor: "var(--border)" }}>
      {/* Header */}
      <div className="p-3 flex items-center justify-between border-b shrink-0" style={{ borderColor: "var(--border)" }}>
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {t("panel.history")}
        </span>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon-xs" onClick={onNew} title={t("panel.newConversation")}>
            <PlusIcon className="size-3" />
          </Button>
          <Button variant="ghost" size="icon-xs" onClick={onClose} title={t("panel.closeHistory")}>
            <PanelRightCloseIcon className="size-3" />
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="px-3 pt-2 pb-1 shrink-0">
        <div className="relative">
          <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={t("history.searchPlaceholder")}
            className="h-7 pl-8 text-xs"
          />
        </div>
      </div>

      {/* Conversation list */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-2 space-y-3">
          {filtered.length === 0 ? (
            <div className="text-center py-8">
              <MessageSquareIcon className="size-8 mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-xs text-muted-foreground">
                {searchQuery ? t("history.noResults") : t("panel.noHistory")}
              </p>
            </div>
          ) : (
            Object.entries(groups).map(([key, items]) => {
              if (items.length === 0) return null;
              return (
                <div key={key}>
                  <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60 px-2 mb-1">
                    {groupLabels[key]}
                  </p>
                  <div className="space-y-0.5">
                    {items.map((conversation) => {
                      const active = conversation.id === currentId;
                      const isEditing = editingId === conversation.id;
                      const isHovered = hoveredId === conversation.id;
                      return (
                        <div
                          key={conversation.id}
                          className={cn(
                            "group relative rounded-lg px-2.5 py-2 text-left transition-colors cursor-pointer",
                            active ? "bg-muted" : "hover:bg-muted/50",
                          )}
                          onMouseEnter={() => setHoveredId(conversation.id)}
                          onMouseLeave={() => setHoveredId(null)}
                          onClick={() => {
                            if (!isEditing) {
                              onSelect(conversation.id);
                              onClose();
                            }
                          }}
                        >
                          {isEditing ? (
                            <input
                              ref={renameInputRef}
                              value={editingTitle}
                              onChange={(e) => onEditTitleChange(e.target.value)}
                              onClick={(e) => e.stopPropagation()}
                              onDoubleClick={(e) => e.stopPropagation()}
                              onBlur={onCommitRename}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") { e.preventDefault(); onCommitRename(); }
                                if (e.key === "Escape") { e.preventDefault(); onCancelRename(); }
                              }}
                              className="w-full rounded border bg-background px-1.5 py-0.5 text-xs font-medium outline-none"
                              style={{ borderColor: "var(--border)" }}
                              disabled={!!renamingId}
                            />
                          ) : (
                            <>
                              <div
                                className="text-xs font-medium truncate pr-6"
                                onDoubleClick={(e) => {
                                  e.stopPropagation();
                                  onRename(conversation.id, conversation.title);
                                }}
                              >
                                {conversation.title || t("panel.untitledConversation")}
                              </div>
                              <div className="text-[10px] mt-0.5 text-muted-foreground/60">
                                {conversation.created_at
                                  ? new Date(conversation.created_at).toLocaleDateString()
                                  : ""}
                              </div>
                              {/* Delete button on hover */}
                              {isHovered && !active && (
                                <button
                                  className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onDelete(conversation.id);
                                  }}
                                  title={t("history.delete")}
                                >
                                  <Trash2Icon className="size-3" />
                                </button>
                              )}
                            </>
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
      </ScrollArea>
    </div>
  );
}

/* ─── Main Panel Component ─── */

export function AIAssistantPanel() {
  const {
    state,
    close,
    sendMessage,
    toggle,
    loadConversation,
    refreshConversations,
    startNewConversation,
    confirmAssistantAction,
  } = useAIAssistant();
  const { t } = useTranslation("ai-assistant");
  const [input, setInput] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historySearch, setHistorySearch] = useState("");
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages]);

  useEffect(() => {
    if (state.isOpen && state.mode === "panel") {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [state.isOpen, state.mode]);

  useEffect(() => {
    if (!state.isOpen) {
      setHistoryOpen(false);
      setHistorySearch("");
    }
  }, [state.isOpen]);

  useEffect(() => {
    if (editingConversationId) {
      setTimeout(() => {
        renameInputRef.current?.focus();
        renameInputRef.current?.select();
      }, 0);
    }
  }, [editingConversationId]);

  const handleSend = useCallback(() => {
    if (!input.trim() || isAssistantBusy(state.status)) return;
    sendMessage(input);
    setInput("");
  }, [input, state.status, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleQuickAction = useCallback(
    (text: string) => { sendMessage(text); },
    [sendMessage],
  );

  const beginRenameConversation = useCallback((id: string, title: string | null) => {
    setEditingConversationId(id);
    setEditingTitle(title || "");
  }, []);

  const cancelRenameConversation = useCallback(() => {
    setEditingConversationId(null);
    setEditingTitle("");
  }, []);

  const commitRenameConversation = useCallback(async () => {
    if (!editingConversationId) return;
    const normalizedTitle = editingTitle.trim();
    if (!normalizedTitle) { cancelRenameConversation(); return; }
    try {
      setRenamingConversationId(editingConversationId);
      await renameChatConversation(editingConversationId, normalizedTitle);
      await refreshConversations();
    } catch (error) {
      console.error("Failed to rename conversation:", error);
    } finally {
      setRenamingConversationId(null);
      cancelRenameConversation();
    }
  }, [cancelRenameConversation, editingConversationId, editingTitle, refreshConversations]);

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
    <div
      className="fixed top-0 right-0 z-40 h-full w-full sm:w-[320px] md:w-[400px] flex flex-col animate-slide-in bg-background border-l border-border shadow-[-8px_0_30px_oklch(0_0_0/0.08)]"
    >
      {/* ─── Header ─── */}
      <div className="flex items-center justify-between px-3 h-12 shrink-0 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          <Button
            variant="ghost"
            size="icon-sm"
            className={cn("text-muted-foreground", historyOpen && "bg-muted text-foreground")}
            onClick={() => setHistoryOpen((v) => !v)}
            title={t("panel.history")}
          >
            <HistoryIcon className="size-4" />
          </Button>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold truncate text-foreground">
                {state.currentConversationId
                  ? (Array.isArray(state.conversations)
                    ? state.conversations.find((item) => item.id === state.currentConversationId)?.title
                    : null) || t("panel.untitledConversation")
                  : t("title")}
              </span>
              {isAssistantBusy(state.status) && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground shrink-0">
                  {statusLabel(state.status, t)}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon-sm" className="text-muted-foreground" onClick={startNewConversation} title={t("panel.newConversation")}>
            <PlusIcon className="size-4" />
          </Button>
          <Button variant="ghost" size="icon-sm" className="text-muted-foreground" onClick={() => toggle("command")} title={t("panel.openCommand")}>
            <CommandIcon className="size-4" />
          </Button>
          <Button variant="ghost" size="icon-sm" className="text-muted-foreground" onClick={close} title={t("panel.close")}>
            <PanelRightCloseIcon className="size-4" />
          </Button>
        </div>
      </div>

      {state.sessionError && (
        <div className="shrink-0 px-4 py-2 text-xs border-b border-border bg-destructive/10 text-destructive">
          {state.sessionError}
        </div>
      )}

      {/* ─── Content: Messages with floating history overlay ─── */}
      <div className="relative flex-1 min-h-0 overflow-hidden">
        {historyOpen && (
          <>
            <button
              aria-label={t("panel.closeHistory")}
              className="absolute inset-0 z-10 bg-black/20 backdrop-blur-[1px]"
              onClick={() => setHistoryOpen(false)}
            />
            <div className="absolute inset-y-0 left-0 z-20">
              <HistorySidebar
                conversations={Array.isArray(state.conversations) ? state.conversations : []}
                currentId={state.currentConversationId}
                searchQuery={historySearch}
                onSearchChange={setHistorySearch}
                onSelect={loadConversation}
                onNew={startNewConversation}
                onRename={beginRenameConversation}
                onDelete={handleDeleteConversation}
                onClose={() => setHistoryOpen(false)}
                editingId={editingConversationId}
                editingTitle={editingTitle}
                onEditTitleChange={setEditingTitle}
                onCommitRename={commitRenameConversation}
                onCancelRename={cancelRenameConversation}
                renamingId={renamingConversationId}
                renameInputRef={renameInputRef}
                t={t}
              />
            </div>
          </>
        )}

        {/* ─── Messages ─── */}
        <ScrollArea className="h-full">
          <div className="p-4 space-y-4">
            {state.messages.length === 0 ? (
              <div className="text-center py-10">
                <div className="w-14 h-14 rounded-2xl mx-auto mb-4 flex items-center justify-center bg-gradient-to-br from-primary to-[oklch(from_var(--primary)_calc(l+0.08)_c_h)]">
                  <SparklesIcon className="w-7 h-7 text-primary-foreground" />
                </div>
                <h3 className="text-base font-semibold mb-1 text-foreground">{t("welcome.title")}</h3>
                <p className="text-sm mb-6 text-muted-foreground">{t("welcome.description")}</p>
                <QuickActions onSelect={handleQuickAction} />
              </div>
            ) : (
              <>
                {state.messages.map((msg) => (
                  <MessageBubble key={msg.id} msg={msg} />
                ))}
                {state.executionItems.map((item) =>
                  item.kind === "workflow" ? (
                    <AssistantWorkflowCard key={item.id} item={item} />
                  ) : (
                    <AssistantExecutionCard key={item.id} item={item} />
                  ),
                )}
                {state.pendingConfirmation && (
                  <AssistantConfirmationCard
                    confirmation={state.pendingConfirmation}
                    onConfirm={() => void confirmAssistantAction(true)}
                    onCancel={() => void confirmAssistantAction(false)}
                  />
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* ─── Input ─── */}
      <div className="shrink-0 px-3 pt-2 pb-2 border-t border-border">
        <div className="flex items-center gap-2 rounded-xl px-3 py-1.5 min-h-11 bg-muted border border-border">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("inputPlaceholder")}
            rows={1}
            className="flex-1 bg-transparent text-sm leading-5 outline-none resize-none min-h-5 max-h-24 placeholder:text-muted-foreground overflow-y-auto text-foreground"
            disabled={isAssistantBusy(state.status)}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isAssistantBusy(state.status)}
            aria-label={t("actions.send")}
            className={cn(
              "shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 disabled:opacity-40",
              input.trim()
                ? "bg-gradient-to-br from-primary to-[oklch(from_var(--primary)_calc(l+0.08)_c_h)] text-primary-foreground"
                : "text-muted-foreground"
            )}
          >
            <SendIcon className="w-4 h-4" />
          </button>
        </div>
        <div className="flex items-center justify-between mt-1 px-1">
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <CornerDownLeftIcon className="w-3 h-3" /> {t("panel.enterToSend")}
          </span>
          <span className="text-[10px] text-muted-foreground">
            {t("panel.escToClose")}
          </span>
        </div>
      </div>
    </div>
  );
}
