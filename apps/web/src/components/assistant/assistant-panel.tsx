/**
 * BidPilot AI Assistant Panel — built with assistant-ui primitives.
 *
 * Uses ThreadPrimitive, ComposerPrimitive, MessagePrimitive from
 * @assistant-ui/react to get streaming, tool calls, and auto-scroll
 * for free. Styled with our design tokens.
 */

import {
  ThreadPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  ActionBarPrimitive,
  AssistantRuntimeProvider,
} from "@assistant-ui/react";
import {
  SparklesIcon,
  PanelRightCloseIcon,
  SendIcon,
  CopyIcon,
  CheckIcon,
  RefreshCwIcon,
  SquareIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useState, type FC } from "react";
import { cn } from "@/lib/utils";
import { useBidPilotRuntime } from "./bidpilot-runtime";
import { useAIAssistant } from "@/lib/ai-assistant-store";
import "./assistant.css";

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

/* ─── Single message ─── */

const Message: FC = () => {
  return (
    <MessagePrimitive.Root className="mb-3">
      <MessagePrimitive.Contents
        components={{
          Text: () => (
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words",
                "[&>:first-child]:mt-0 [&>:last-child]:mb-0",
                "[&_p]:mb-2 [&_p:last-child]:mb-0",
                "[&_ul]:my-2 [&_ol]:my-2 [&_li]:my-1",
                "[&_pre]:my-2 [&_code]:break-words",
                "[&_pre]:rounded-lg [&_pre]:bg-muted-foreground/10 [&_pre]:p-3",
                "[&_code:not(pre_code)]:bg-muted-foreground/10 [&_code:not(pre_code)]:px-1.5 [&_code:not(pre_code)]:py-0.5 [&_code:not(pre_code)]:rounded",
              )}
            >
              <MessagePrimitive.Content />
            </div>
          ),
          // Tool call rendering — inline in the message flow
          ToolCall: () => (
            <div className="my-2 px-3 py-2 rounded-lg bg-muted border border-border text-xs">
              <div className="flex items-center gap-1.5 text-muted-foreground font-medium">
                <RefreshCwIcon className="size-3 animate-spin" />
                <MessagePrimitive.ToolCall />
              </div>
            </div>
          ),
        }}
      />
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
        </ActionBarPrimitive.Root>
      </MessagePrimitive.If>
    </MessagePrimitive.Root>
  );
};

/* ─── User message (styled differently) ─── */

const UserMessage: FC = () => {
  return (
    <MessagePrimitive.Root className="flex justify-end mb-3">
      <div className="max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed bg-gradient-to-br from-primary to-[oklch(from_var(--primary)_calc(l+0.08)_c_h)] text-primary-foreground">
        <MessagePrimitive.Content />
      </div>
    </MessagePrimitive.Root>
  );
};

/* ─── Composer (input area) ─── */

function Composer() {
  const { t } = useTranslation("ai-assistant");
  return (
    <ComposerPrimitive.Root className="shrink-0 px-3 pt-2.5 pb-2 border-t border-border">
      <div className="flex items-center gap-2 rounded-xl px-3 py-1.5 min-h-11 bg-muted border border-border">
        <ComposerPrimitive.Input
          rows={1}
          className="flex-1 bg-transparent text-sm leading-5 outline-none resize-none min-h-5 max-h-24 placeholder:text-muted-foreground overflow-y-auto text-foreground"
          placeholder={t("inputPlaceholder")}
        />
        <ComposerPrimitive.Send asChild>
          <button
            className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 text-muted-foreground data-[enabled]:bg-gradient-to-br data-[enabled]:from-primary data-[enabled]:to-[oklch(from_var(--primary)_calc(l+0.08)_c_h)] data-[enabled]:text-primary-foreground"
            aria-label={t("actions.send")}
          >
            <SendIcon className="w-4 h-4" />
          </button>
        </ComposerPrimitive.Send>
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
          Enter {t("panel.enterToSend")} · Shift+Enter 换行
        </span>
        <span className="text-[10px] text-muted-foreground">
          Esc {t("panel.escToClose")}
        </span>
      </div>
    </ComposerPrimitive.Root>
  );
}

/* ─── Main Panel ─── */

export function AssistantPanel() {
  const { state, close } = useAIAssistant();
  const { t } = useTranslation("ai-assistant");
  const runtime = useBidPilotRuntime({
    projectId: state.currentContext.projectId ?? undefined,
  });

  if (!state.isOpen || state.mode !== "panel") return null;

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="fixed top-0 right-0 z-40 h-full w-full sm:w-[400px] md:w-[480px] lg:w-[520px] flex flex-col animate-slide-in bg-background border-l border-border shadow-[-8px_0_30px_oklch(0_0_0/0.08)]">
        {/* Header */}
        <div className="flex items-center justify-between px-3 h-12 shrink-0 border-b border-border">
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-[oklch(from_var(--primary)_calc(l+0.08)_c_h)]">
              <SparklesIcon className="size-3.5 text-primary-foreground" />
            </div>
            <span className="text-sm font-semibold text-foreground">
              {t("title")}
            </span>
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

        {/* Messages + Composer */}
        <ThreadPrimitive.Root className="flex-1 min-h-0 flex flex-col">
          <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto p-4">
            {/* Empty state */}
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

            {/* Messages */}
            <ThreadPrimitive.Messages
              components={{
                UserMessage: () => <UserMessage />,
                AssistantMessage: () => <Message />,
              }}
            />

            {/* Scroll to bottom button */}
            <ThreadPrimitive.ScrollToBottom className="fixed bottom-24 right-6 z-10 size-8 rounded-full bg-muted border border-border shadow-md flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors cursor-pointer data-[hidden]:hidden" />
          </ThreadPrimitive.Viewport>

          {/* Composer */}
          <Composer />
        </ThreadPrimitive.Root>
      </div>
    </AssistantRuntimeProvider>
  );
}
