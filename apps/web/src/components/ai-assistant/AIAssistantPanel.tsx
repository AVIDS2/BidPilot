import { useRef, useEffect, useCallback, useState } from "react";
import {
  SparklesIcon,
  SendIcon,
  CommandIcon,
  PanelRightCloseIcon,
  CornerDownLeftIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAIAssistant, type ChatMessage } from "@/lib/ai-assistant-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

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
        {msg.content || (
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

/* ─── Main Panel Component ─── */

export function AIAssistantPanel() {
  const { state, close, sendMessage, toggle } = useAIAssistant();
  const { t } = useTranslation("ai-assistant");
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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

  const handleSend = useCallback(() => {
    if (!input.trim() || state.status === "processing") return;
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
        <div className="flex items-center gap-2.5">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{
              background:
                "linear-gradient(135deg, var(--primary), oklch(from var(--primary) calc(l + 0.08) c h))",
            }}
          >
            <SparklesIcon className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
            {t("title")}
          </span>
          {state.status === "processing" && (
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}
            >
              {t("thinking")}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
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
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </ScrollArea>

      {/* ─── Input ─── */}
      <div
        className="shrink-0 p-3"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <div
          className="flex items-end gap-2 rounded-xl px-3 py-2"
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
            className="flex-1 bg-transparent text-sm outline-none resize-none max-h-24 placeholder:text-muted-foreground"
            style={{ color: "var(--foreground)" }}
            disabled={state.status === "processing"}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || state.status === "processing"}
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
        <div className="flex items-center justify-between mt-1.5 px-1">
          <span className="text-[11px] text-muted-foreground flex items-center gap-1">
            <CornerDownLeftIcon className="w-3 h-3" /> {t("panel.enterToSend")}
          </span>
          <span className="text-[11px] text-muted-foreground">
            {t("panel.escToClose")}
          </span>
        </div>
      </div>
    </div>
  );
}
