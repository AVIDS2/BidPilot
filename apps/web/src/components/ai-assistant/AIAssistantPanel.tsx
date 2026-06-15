import { useRef, useEffect, useCallback, useState } from "react";
import {
  HistoryIcon,
  PlusIcon,
  SparklesIcon,
  SendIcon,
  CommandIcon,
  PanelRightCloseIcon,
  CornerDownLeftIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { renameChatConversation } from "@/lib/api";
import { isAssistantBusy, useAIAssistant, type AssistantStatus, type ChatMessage } from "@/lib/ai-assistant-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AssistantConfirmationCard } from "./assistant-confirmation-card";
import { AssistantExecutionCard } from "./assistant-execution-card";
import { AssistantWorkflowCard } from "./assistant-workflow-card";

/* ─── Quick action chips shown in empty state ─── */

function QuickActions({
  onSelect,
}: {
  onSelect: (text: string) => void;
}) {
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
          className="text-xs px-3 py-1.5 rounded-full transition-all duration-200 hover:scale-105"
          style={{
            background: "var(--muted)",
            color: "var(--muted-foreground)",
            border: "1px solid var(--border)",
          }}
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

  // Convert bracket-wrapped display math blocks often returned by the model:
  // [
  //   f'(x_i)=\frac{f(b)-f(a)}{b-a}
  // ]
  normalized = normalized.replace(
    /^\[\s*\n([\s\S]*?\\[a-zA-Z]+[\s\S]*?)\n\]\s*$/gm,
    (_match, expr) => `$$\n${expr.trim()}\n$$`,
  );

  // Convert standalone LaTeX-looking equation lines into display math when
  // the model forgets to add $$ delimiters.
  normalized = normalized
    .split("\n")
    .map((line) => {
      const trimmed = line.trim();
      const looksLikeMath =
        /\\(frac|sum|int|sqrt|alpha|beta|gamma|theta|pi|sin|cos|tan|lim|cdot|times|leq|geq|neq|infty|to)/.test(trimmed) ||
        /[=<>]/.test(trimmed);
      const alreadyDelimited =
        trimmed.startsWith("$") ||
        trimmed.startsWith("\\(") ||
        trimmed.startsWith("\\[");

      if (
        trimmed &&
        looksLikeMath &&
        !alreadyDelimited &&
        !trimmed.startsWith("- ") &&
        !trimmed.startsWith("* ")
      ) {
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
            <Markdown
              className="[&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-1 [&_pre]:my-2 [&_code]:break-words"
            >
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
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages]);

  // focus input when panel opens
  useEffect(() => {
    if (state.isOpen && state.mode === "panel") {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [state.isOpen, state.mode]);

  useEffect(() => {
    if (!state.isOpen) {
      setHistoryOpen(false);
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
    (text: string) => {
      sendMessage(text);
    },
    [sendMessage],
  );

  const beginRenameConversation = useCallback((conversationId: string, currentTitle: string | null) => {
    setEditingConversationId(conversationId);
    setEditingTitle(currentTitle || "");
  }, []);

  const cancelRenameConversation = useCallback(() => {
    setEditingConversationId(null);
    setEditingTitle("");
  }, []);

  const commitRenameConversation = useCallback(async () => {
    if (!editingConversationId) return;

    const normalizedTitle = editingTitle.trim();
    if (!normalizedTitle) {
      cancelRenameConversation();
      return;
    }

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

  if (!state.isOpen || state.mode !== "panel") return null;

  return (
    <div
      className="fixed top-0 right-0 z-40 h-full w-[400px] flex flex-col animate-slide-in"
      style={{
        background: "var(--background)",
        borderLeft: "1px solid var(--border)",
        boxShadow: "-8px 0 30px oklch(0 0 0 / 0.08)",
      }}
    >
      {/* ─── Header ─── */}
      <div
        className="flex items-center justify-between px-4 h-14 shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <button
            className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors"
            style={{ background: "var(--muted)", color: "var(--foreground)" }}
            onClick={() => setHistoryOpen((value) => !value)}
            title={t("panel.history")}
          >
            <HistoryIcon className="w-4 h-4" />
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold truncate" style={{ color: "var(--foreground)" }}>
              {state.currentConversationId
                  ? (Array.isArray(state.conversations)
                    ? state.conversations.find((item) => item.id === state.currentConversationId)?.title
                    : null) || t("panel.untitledConversation")
                  : t("title")}
              </span>
              {isAssistantBusy(state.status) && (
                <span
                  className="text-xs px-2 py-0.5 rounded-full shrink-0"
                  style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}
                >
                  {statusLabel(state.status, t)}
                </span>
              )}
            </div>
            <p className="text-[11px] truncate" style={{ color: "var(--muted-foreground)" }}>
              {state.currentConversationId ? t("panel.historySubtitle") : t("subtitle")}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={startNewConversation}
            title={t("panel.newConversation")}
          >
            <PlusIcon className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={() => toggle("command")}
            title={t("panel.openCommand")}
          >
            <CommandIcon className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={() => {
              /* clear messages by dispatching via store */
              const store = state;
              void store; // keep linter happy
              close();
            }}
            title={t("panel.close")}
          >
            <PanelRightCloseIcon className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {state.status !== "idle" && (
        <div
          className="shrink-0 px-4 py-2 text-xs"
          style={{ borderBottom: "1px solid var(--border)", color: "var(--muted-foreground)" }}
        >
          {statusLabel(state.status, t)}
        </div>
      )}
      {state.sessionError && (
        <div
          className="shrink-0 px-4 py-2 text-xs"
          style={{
            borderBottom: "1px solid var(--border)",
            background: "color-mix(in oklab, var(--destructive) 10%, transparent)",
            color: "var(--destructive)",
          }}
        >
          {state.sessionError}
        </div>
      )}

      <div className="relative flex flex-1 min-h-0 overflow-hidden">
        {historyOpen && (
          <>
            <button
              aria-label={t("panel.closeHistory")}
              className="absolute inset-0 z-10 bg-black/20 backdrop-blur-[1px]"
              onClick={() => setHistoryOpen(false)}
            />
            <div
              className="absolute inset-y-0 left-0 z-20 w-56 border-r shadow-xl"
              style={{ borderColor: "var(--border)", background: "var(--card)" }}
            >
            <div className="p-3 flex items-center justify-between border-b" style={{ borderColor: "var(--border)" }}>
              <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--muted-foreground)" }}>
                {t("panel.history")}
              </span>
              <button
                className="text-xs"
                style={{ color: "var(--primary)" }}
                onClick={startNewConversation}
              >
                {t("panel.newConversation")}
              </button>
            </div>
            <ScrollArea className="h-full">
              <div className="p-2 space-y-1">
                {state.conversations.length === 0 ? (
                  <p className="px-2 py-3 text-xs" style={{ color: "var(--muted-foreground)" }}>
                    {t("panel.noHistory")}
                  </p>
                ) : (
                  state.conversations.map((conversation) => {
                    const active = conversation.id === state.currentConversationId;
                    const isEditing = editingConversationId === conversation.id;
                    const isRenaming = renamingConversationId === conversation.id;
                    return (
                      <button
                        key={conversation.id}
                        onClick={() => {
                          if (isEditing) return;
                          void loadConversation(conversation.id);
                          setHistoryOpen(false);
                        }}
                        className="w-full rounded-lg px-2.5 py-2 text-left transition-colors"
                        style={{
                          background: active ? "var(--muted)" : "transparent",
                          color: "var(--foreground)",
                        }}
                      >
                        {isEditing ? (
                          <input
                            ref={renameInputRef}
                            value={editingTitle}
                            onChange={(event) => setEditingTitle(event.target.value)}
                            onClick={(event) => event.stopPropagation()}
                            onDoubleClick={(event) => event.stopPropagation()}
                            onBlur={() => {
                              void commitRenameConversation();
                            }}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault();
                                void commitRenameConversation();
                              }
                              if (event.key === "Escape") {
                                event.preventDefault();
                                cancelRenameConversation();
                              }
                            }}
                            aria-label={t("panel.renameConversation")}
                            className="w-full rounded-md border bg-background px-2 py-1 text-sm font-medium outline-none"
                            style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
                            placeholder={t("panel.untitledConversation")}
                            disabled={isRenaming}
                          />
                        ) : (
                          <div
                            className="text-sm font-medium truncate"
                            onDoubleClick={(event) => {
                              event.stopPropagation();
                              beginRenameConversation(conversation.id, conversation.title);
                            }}
                            title={t("panel.renameConversationHint")}
                          >
                            {conversation.title || t("panel.untitledConversation")}
                          </div>
                        )}
                        <div className="text-[11px] mt-0.5" style={{ color: "var(--muted-foreground)" }}>
                          {conversation.created_at
                            ? new Date(conversation.created_at).toLocaleString()
                            : t("panel.justNow")}
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </ScrollArea>
            </div>
          </>
        )}

        {/* ─── Messages ─── */}
        <ScrollArea className="flex-1">
          <div className="p-4 space-y-4">
          {state.messages.length === 0 ? (
            <div className="text-center py-10">
              <div
                className="w-14 h-14 rounded-2xl mx-auto mb-4 flex items-center justify-center"
                style={{
                  background:
                    "linear-gradient(135deg, var(--primary), oklch(from var(--primary) calc(l + 0.08) c h))",
                }}
              >
                <SparklesIcon className="w-7 h-7 text-white" />
              </div>
              <h3
                className="text-base font-semibold mb-1"
                style={{ color: "var(--foreground)" }}
              >
                {t("welcome.title")}
              </h3>
              <p className="text-sm mb-6" style={{ color: "var(--muted-foreground)" }}>
                {t("welcome.description")}
              </p>
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
      <div
        className="shrink-0 px-3 pt-2.5 pb-2"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <div
          className="flex items-center gap-2 rounded-xl px-3 py-1.5 min-h-11"
          style={{
            background: "var(--muted)",
            border: "1px solid var(--border)",
          }}
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("inputPlaceholder")}
            rows={1}
            className="flex-1 bg-transparent text-sm leading-5 outline-none resize-none min-h-5 max-h-24 placeholder:text-muted-foreground overflow-y-auto"
            style={{ color: "var(--foreground)" }}
            disabled={isAssistantBusy(state.status)}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isAssistantBusy(state.status)}
            aria-label={t("actions.send")}
            className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 disabled:opacity-40"
            style={{
              background: input.trim()
                ? "linear-gradient(135deg, var(--primary), oklch(from var(--primary) calc(l + 0.08) c h))"
                : "transparent",
              color: input.trim() ? "var(--primary-foreground)" : "var(--muted-foreground)",
            }}
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
