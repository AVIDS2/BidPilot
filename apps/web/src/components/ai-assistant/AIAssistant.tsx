import { useState, useRef, useEffect, useCallback } from "react";
import {
  MessageCircleIcon,
  XIcon,
  SparklesIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  ChatContainerRoot,
  ChatContainerContent,
  ChatContainerScrollAnchor,
} from "@/components/ui/chat-container";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Markdown } from "@/components/ui/markdown";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputActions,
  PromptInputAction,
} from "@/components/ui/prompt-input";
import { PromptSuggestion } from "@/components/ui/prompt-suggestion";
import { TextDotsLoader } from "@/components/ui/loader";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function AIAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const { t } = useTranslation("ai-assistant");

  const handleSend = useCallback(
    async (text?: string) => {
      const content = text ?? input;
      if (!content.trim() || isLoading) return;

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: content.trim(),
      };

      const assistantId = `assistant-${Date.now()}`;
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setInput("");
      setIsLoading(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: content.trim() }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split("\n");

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.type === "content") {
                    setMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === assistantId
                          ? { ...msg, content: msg.content + data.text }
                          : msg
                      )
                    );
                  }
                } catch {
                  // skip malformed SSE lines
                }
              }
            }
          }
        }
      } catch (error: unknown) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? {
                  ...msg,
                  content:
                    msg.content ||
                    t("error.network", {
                      defaultValue: "Sorry, something went wrong. Please try again later.",
                    }),
                }
              : msg
          )
        );
      } finally {
        setIsLoading(false);
        abortControllerRef.current = null;
      }
    },
    [input, isLoading, t]
  );

  // Abort on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const quickActions = [
    { label: t("actions.createProject"), action: t("actions.createProjectPrompt", { defaultValue: "Create a new project" }) },
    { label: t("actions.uploadDoc"), action: t("actions.uploadDocPrompt", { defaultValue: "Help me upload an RFP document" }) },
    { label: t("actions.generateSection"), action: t("actions.generateSectionPrompt", { defaultValue: "Generate an executive summary" }) },
    { label: t("actions.howToUse"), action: t("actions.howToUsePrompt", { defaultValue: "How to use DocPilot?" }) },
  ];

  return (
    <>
      {/* Floating trigger button */}
      <Button
        size="icon"
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "fixed bottom-6 right-6 z-50 h-14 w-14 rounded-full shadow-lg",
          "transition-all duration-300 hover:scale-110",
          isOpen && "rotate-90"
        )}
      >
        {isOpen ? (
          <XIcon className="h-6 w-6" />
        ) : (
          <MessageCircleIcon className="h-6 w-6" />
        )}
      </Button>

      {/* Chat panel */}
      <div
        className={cn(
          "fixed bottom-24 right-6 z-50 flex w-[400px] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl",
          "transition-all duration-300 ease-out",
          isOpen
            ? "pointer-events-auto scale-100 opacity-100"
            : "pointer-events-none scale-95 opacity-0"
        )}
        style={{ height: "min(520px, calc(100vh - 140px))" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border bg-primary px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-foreground/15">
              <SparklesIcon className="h-4 w-4 text-primary-foreground" />
            </div>
            <div>
              <span className="text-sm font-semibold text-primary-foreground">
                {t("title", { defaultValue: "DocPilot AI" })}
              </span>
              <p className="text-[11px] leading-tight text-primary-foreground/70">
                {t("subtitle", { defaultValue: "Your document assistant" })}
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsOpen(false)}
            className="h-8 w-8 text-primary-foreground hover:bg-primary-foreground/15"
          >
            <XIcon className="h-4 w-4" />
          </Button>
        </div>

        {/* Messages area */}
        <ChatContainerRoot className="flex-1">
          <ChatContainerContent className="p-4">
            {messages.length === 0 ? (
              /* Welcome screen */
              <div className="flex flex-col items-center justify-center py-12">
                <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
                  <SparklesIcon className="h-8 w-8 text-primary" />
                </div>
                <h3 className="text-base font-semibold text-foreground">
                  {t("welcome.title", { defaultValue: "Welcome to DocPilot!" })}
                </h3>
                <p className="mt-1.5 max-w-[280px] text-center text-sm leading-relaxed text-muted-foreground">
                  {t("welcome.description", {
                    defaultValue:
                      "I can help you create projects, upload documents, generate sections, and more.",
                  })}
                </p>
              </div>
            ) : (
              messages.map((message) => {
                const isUser = message.role === "user";
                const hasContent = !!message.content;

                return (
                  <div
                    key={message.id}
                    className={cn(
                      "flex gap-3 mb-4",
                      isUser ? "flex-row-reverse" : "flex-row"
                    )}
                  >
                    <Avatar className="h-8 w-8 shrink-0">
                      <AvatarFallback
                        className={cn(
                          "text-xs font-medium",
                          isUser
                            ? "bg-secondary text-secondary-foreground"
                            : "bg-primary/10 text-primary"
                        )}
                      >
                        {isUser ? "U" : "AI"}
                      </AvatarFallback>
                    </Avatar>
                    <div
                      className={cn(
                        "max-w-[320px] rounded-lg p-2 break-words whitespace-normal",
                        isUser
                          ? "bg-primary text-primary-foreground"
                          : "bg-secondary text-secondary-foreground"
                      )}
                    >
                      {hasContent ? (
                        isUser ? (
                          <span>{message.content}</span>
                        ) : (
                          <Markdown className="prose text-secondary-foreground">
                            {message.content}
                          </Markdown>
                        )
                      ) : (
                        <TextDotsLoader size="sm" text="..." />
                      )}
                    </div>
                  </div>
                );
              })
            )}
            <ChatContainerScrollAnchor />
          </ChatContainerContent>
        </ChatContainerRoot>

        {/* Quick actions (shown when no messages) */}
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2 px-4 pb-2">
            {quickActions.map((action, index) => (
              <PromptSuggestion
                key={index}
                variant="outline"
                size="sm"
                onClick={() => handleSend(action.action)}
              >
                {action.label}
              </PromptSuggestion>
            ))}
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-border p-3">
          <PromptInput
            isLoading={isLoading}
            value={input}
            onValueChange={setInput}
            onSubmit={() => handleSend()}
            className="rounded-2xl"
          >
            <PromptInputTextarea
              placeholder={t("inputPlaceholder", {
                defaultValue: "Ask me anything...",
              })}
              disableAutosize={false}
            />
            <PromptInputActions className="justify-end p-1.5">
              <PromptInputAction
                tooltip={
                  isLoading
                    ? t("actions.stop", { defaultValue: "Stop" })
                    : t("actions.send", { defaultValue: "Send" })
                }
              >
                <Button
                  variant="default"
                  size="icon"
                  className="h-9 w-9 rounded-xl"
                  disabled={(!input.trim() && !isLoading) || isLoading}
                  onClick={() => {
                    if (isLoading) {
                      abortControllerRef.current?.abort();
                    } else {
                      handleSend();
                    }
                  }}
                >
                  {isLoading ? (
                    <XIcon className="h-4 w-4" />
                  ) : (
                    <MessageCircleIcon className="h-4 w-4" />
                  )}
                </Button>
              </PromptInputAction>
            </PromptInputActions>
          </PromptInput>
        </div>
      </div>
    </>
  );
}
