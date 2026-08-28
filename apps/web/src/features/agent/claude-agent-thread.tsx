import { useEffect, useMemo, useRef, useState } from "react";
import { CheckIcon, ChevronDownIcon, CopyIcon, FileIcon, ImageIcon, PencilIcon, RotateCcwIcon, XIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { MessageContent } from "@/components/ui/message";
import { ClaudeActivityTimeline } from "@/features/agent/components/claude-activity-timeline";
import { AssistantInputRequestForm } from "@/features/agent/components/assistant-input-request";
import type {
  AIAssistantState,
  AssistantConfirmationRequest,
  AssistantExecutionItem,
  ChatMessage,
} from "@/features/agent/state/agent-store";
import type { AssistantTranscriptPart } from "@/features/agent/runtime/assistant-transcript";
import "./claude-agent-thread.css";

const EMPTY_TRANSCRIPT_PARTS: NonNullable<ChatMessage["transcriptParts"]> = [];

function normalizeAssistantMarkdown(content: string): string {
  if (!content.includes("\\")) return content;
  let normalized = content;
  normalized = normalized.replace(
    /^\[\s*\n([\s\S]*?\\[a-zA-Z]+[\s\S]*?)\n\]\s*$/gm,
    (_match, expression) => `$$\n${String(expression).trim()}\n$$`,
  );
  return normalized
    .split("\n")
    .map((line) => {
      const trimmed = line.trim();
      const looksLikeMath =
        /\\(frac|sum|int|sqrt|alpha|beta|gamma|theta|pi|sin|cos|tan|lim|cdot|times|leq|geq|neq|infty|to)/.test(trimmed) ||
        /[=<>]/.test(trimmed);
      const alreadyDelimited =
        trimmed.startsWith("$") || trimmed.startsWith("\\(") || trimmed.startsWith("\\[");
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
}

function UserAttachments({ message }: { message: ChatMessage }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  if (!message.attachments?.length) return null;
  return (
    <>
      <div className="cr-user-attachments" aria-label="Attached files">
        {message.attachments.map((attachment) => (
          <button
            type="button"
            className="cr-user-attachment"
            key={attachment.id}
            onClick={() => attachment.previewUrl && setPreviewUrl(attachment.previewUrl)}
            aria-label={attachment.previewUrl ? `预览 ${attachment.name}` : attachment.name}
          >
            {attachment.kind === "image" && attachment.previewUrl ? (
              <img alt="" src={attachment.previewUrl} />
            ) : attachment.kind === "image" ? (
              <ImageIcon size={15} />
            ) : (
              <FileIcon size={15} />
            )}
            <span>{attachment.name}</span>
          </button>
        ))}
      </div>
      {previewUrl && (
        <div
          className="cr-image-lightbox"
          role="dialog"
          aria-label="图片预览"
          onClick={() => setPreviewUrl(null)}
        >
          <img src={previewUrl} alt="图片预览" />
        </div>
      )}
    </>
  );
}

function ClaudeUserMessage({
  message,
  canRetryFromCheckpoint,
  onRetryFromCheckpoint,
}: {
  message: ChatMessage;
  canRetryFromCheckpoint: boolean;
  onRetryFromCheckpoint?: (checkpointMessageId: string, content: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(message.content);
  }, [editing, message.content]);

  const retry = (content: string) => {
    if (!message.durableId || !onRetryFromCheckpoint) return;
    onRetryFromCheckpoint(message.durableId, content);
  };

  const saveEdit = () => {
    const nextContent = draft.trim();
    if (!nextContent) return;
    setEditing(false);
    retry(nextContent);
  };

  const copyMessage = () => {
    if (!message.content || !navigator.clipboard) return;
    void navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    });
  };

  return (
    <div className="cr-user-message-wrap">
      <UserAttachments message={message} />
      {editing ? (
        <div className="cr-user-message-editor">
          <textarea
            aria-label="编辑此消息"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                event.preventDefault();
                saveEdit();
              }
              if (event.key === "Escape") {
                event.preventDefault();
                setDraft(message.content);
                setEditing(false);
              }
            }}
            autoFocus
          />
          <div className="cr-user-message-editor-actions">
            <button type="button" title="保存并重新执行" aria-label="保存并重新执行" onClick={saveEdit}>
              <CheckIcon size={14} />
            </button>
            <button
              type="button"
              title="取消编辑"
              aria-label="取消编辑"
              onClick={() => {
                setDraft(message.content);
                setEditing(false);
              }}
            >
              <XIcon size={14} />
            </button>
          </div>
        </div>
      ) : (
        message.content && <div className="cr-user-message">{message.content}</div>
      )}
      {!editing && (message.content || canRetryFromCheckpoint) && (
        <div className="cr-user-message-actions" aria-label="消息操作">
          {message.content && (
            <button
              type="button"
              title={copied ? "已复制" : "复制"}
              aria-label={copied ? "已复制" : "复制消息"}
              onClick={copyMessage}
            >
              {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
            </button>
          )}
          {canRetryFromCheckpoint && (
            <>
          <button
            type="button"
            title="从此处重新执行"
            aria-label="从此处重新执行"
            onClick={() => retry(message.content)}
          >
            <RotateCcwIcon size={14} />
          </button>
          <button
            type="button"
            title="编辑并重新执行"
            aria-label="编辑并重新执行"
            onClick={() => setEditing(true)}
          >
            <PencilIcon size={14} />
          </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ThinkingIndicator({ started = false }: { started?: boolean }) {
  if (started) {
    return (
      <span className="cr-thinking-copy" aria-label="正在思考">
        正在思考
      </span>
    );
  }
  return (
    <span className="cr-thinking-indicator" aria-label="等待首个响应">
      <i />
      <i />
      <i />
    </span>
  );
}

function ClaudeReasoning({
  part,
  forceCompleted = false,
}: {
  part: Extract<AssistantTranscriptPart, { kind: "reasoning" }>;
  forceCompleted?: boolean;
}) {
  const completed = part.completed || forceCompleted;
  const [open, setOpen] = useState(() => !completed);
  // A live stream stays open while reasoning; the moment it completes the
  // block collapses. After that the reader is free to expand/collapse.
  const wasCompleted = useRef(completed);
  useEffect(() => {
    if (completed && !wasCompleted.current) {
      setOpen(false);
    }
    wasCompleted.current = completed;
  }, [completed]);

  return (
    <section
      className={`cr-reasoning${completed ? " is-complete" : ""}${open ? " is-open" : ""}`}
      aria-label={completed ? "思考过程" : "正在思考"}
    >
      <button
        type="button"
        className="cr-reasoning-heading"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="cr-reasoning-status" aria-hidden="true"><i /></span>
        <span className={completed ? undefined : "cr-thinking-copy"}>
          {part.title || (completed ? "思考过程" : "正在思考")}
        </span>
        <ChevronDownIcon size={12} className="cr-reasoning-chevron" />
      </button>
      <div className="cr-reasoning-collapse">
        <div className="cr-reasoning-collapse-inner">
          {part.title !== part.text && <div className="cr-reasoning-text">{part.text}</div>}
        </div>
      </div>
    </section>
  );
}

function ClaudeApproval({
  confirmation,
  onConfirm,
  onCancel,
}: {
  confirmation: AssistantConfirmationRequest;
  onConfirm: (confirmationText?: string) => void;
  onCancel: () => void;
}) {
  const [typedConfirmation, setTypedConfirmation] = useState("");
  const requiresTypedConfirmation = Boolean(confirmation.requiresTypedConfirmation);
  const canConfirm =
    !requiresTypedConfirmation ||
    typedConfirmation.trim() === (confirmation.expectedText ?? "").trim();

  useEffect(() => setTypedConfirmation(""), [confirmation.approvalId, confirmation.message]);

  return (
    <section className="cr-approval" aria-label="Approval required">
      <div className="cr-approval-copy">
        <span>需要确认</span>
        <p>{confirmation.message}</p>
      </div>
      {requiresTypedConfirmation && (
        <input
          value={typedConfirmation}
          onChange={(event) => setTypedConfirmation(event.target.value)}
          placeholder={confirmation.expectedText ?? ""}
          aria-label="Confirmation text"
          className="cr-approval-input"
        />
      )}
      <div className="cr-approval-actions">
        <button type="button" disabled={!canConfirm} onClick={() => onConfirm(typedConfirmation)}>
          <CheckIcon size={14} />
          确认执行
        </button>
        <button type="button" onClick={onCancel}>
          <XIcon size={14} />
          取消
        </button>
      </div>
    </section>
  );
}

function ClaudeAssistantMessage({
  message,
  activityItems,
  isStreaming,
  isThinking,
  sessionError,
  onCancelWorkflow,
  onConfigureProvider,
  onOpenWorkflowCanvas,
}: {
  message: ChatMessage;
  activityItems: AssistantExecutionItem[];
  isStreaming: boolean;
  isThinking: boolean;
  sessionError?: string | null;
  onCancelWorkflow: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider: () => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
}) {
  const { t } = useTranslation("ai-assistant");
  const [copied, setCopied] = useState(false);
  const parts = message.transcriptParts ?? EMPTY_TRANSCRIPT_PARTS;
  const hasTranscriptParts = parts.length > 0;
  const hasNarrativePart = parts.some((part) => part.kind === "narrative" && part.text);
  const isTimelineTitle = (part: Extract<AssistantTranscriptPart, { kind: "reasoning" }>) =>
    Boolean(part.title && part.title.trim() === part.text.trim());
  const turnIds = useMemo(
    () => new Set(parts.flatMap((part) => (part.kind === "turn" ? [part.turnId] : []))),
    [parts],
  );
  const toolsByTurn = useMemo(() => {
    const groups = new Map<string, AssistantExecutionItem[]>();
    for (const item of activityItems) {
      if (!item.turnId) continue;
      const items = groups.get(item.turnId) ?? [];
      items.push(item);
      groups.set(item.turnId, items);
    }
    return groups;
  }, [activityItems]);
  const orphanTools = useMemo(
    () => activityItems.filter((item) => !item.turnId || !turnIds.has(item.turnId)),
    [activityItems, turnIds],
  );
  const titlesByTurn = useMemo(() => {
    const titles = new Map<string, string>();
    for (const part of parts) {
      if (part.kind !== "reasoning" || !part.turnId || !part.title) continue;
      titles.set(part.turnId, part.title);
    }
    return titles;
  }, [parts]);
  const orphanTaskTitle = useMemo(
    () => parts.find(
      (part): part is Extract<AssistantTranscriptPart, { kind: "reasoning" }> =>
        part.kind === "reasoning" && Boolean(part.title),
    )?.title,
    [parts],
  );
  const hasLiveTrace =
    activityItems.some((item) => item.status === "pending" || item.status === "running") ||
    parts.some(
      (part) =>
        part.kind === "reasoning" && !part.completed,
    );
  const hasActiveExecution = activityItems.some(
    (item) => item.status === "pending" || item.status === "running",
  );
  const hasAssistantOutput = Boolean(message.content || hasNarrativePart);

  const copyResponse = () => {
    const value = message.content || parts
      .filter((part): part is Extract<typeof part, { kind: "narrative" }> => part.kind === "narrative")
      .map((part) => part.text)
      .join("");
    if (!value || !navigator.clipboard) return;
    void navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    });
  };

  const renderNarrative = (content: string, key: string) => {
    if (!content) return null;
    return (
      <MessageContent
        key={key}
        markdown
        variant="assistant"
        className="cr-analysis-answer cr-prose-answer"
      >
        {normalizeAssistantMarkdown(content)}
      </MessageContent>
    );
  };

  if (!message.content && activityItems.length === 0 && parts.length === 0 && !isStreaming && !sessionError) return null;

  return (
    <article
      className={`cr-agent-message cr-analysis-message${hasTranscriptParts ? " cr-task-trace" : ""}`}
      aria-label={hasTranscriptParts ? "任务执行轨迹" : undefined}
    >
      {hasTranscriptParts ? (
        <>
          {parts.map((part) => {
            if (part.kind === "narrative") return renderNarrative(part.text, part.id);
            // A titled public narration names the next tool turn. The timeline
            // owns that title, so rendering it here as well creates a duplicate
            // trace row. Untitled or explanatory narration remains visible.
            if (part.kind === "reasoning") {
              return isTimelineTitle(part) ? null : (
                <ClaudeReasoning
                  key={part.id}
                  part={part}
                  forceCompleted={hasActiveExecution || !isStreaming || !isThinking || Boolean(sessionError)}
                />
              );
            }
            const items = toolsByTurn.get(part.turnId) ?? [];
            return items.length ? (
                <ClaudeActivityTimeline
                  key={part.id}
                  items={items}
                  taskTitle={titlesByTurn.get(part.turnId)}
                nested
                onCancelWorkflow={onCancelWorkflow}
                onConfigureProvider={onConfigureProvider}
                onOpenWorkflowCanvas={onOpenWorkflowCanvas}
              />
            ) : null;
          })}
          {orphanTools.length > 0 && (
            <ClaudeActivityTimeline
              items={orphanTools}
              taskTitle={orphanTaskTitle}
              nested
              onCancelWorkflow={onCancelWorkflow}
              onConfigureProvider={onConfigureProvider}
              onOpenWorkflowCanvas={onOpenWorkflowCanvas}
            />
          )}
          {message.content && !hasNarrativePart && renderNarrative(message.content, `${message.id}-durable`) }
          {isStreaming && isThinking && !hasLiveTrace && <ThinkingIndicator started={hasAssistantOutput} />}
        </>
      ) : (
        <>
          {activityItems.length > 0 && (
            <ClaudeActivityTimeline
              items={activityItems}
              onCancelWorkflow={onCancelWorkflow}
              onConfigureProvider={onConfigureProvider}
              onOpenWorkflowCanvas={onOpenWorkflowCanvas}
            />
          )}
          {message.content ? renderNarrative(message.content, message.id) : null}
          {isStreaming && isThinking && !hasLiveTrace ? <ThinkingIndicator started={hasAssistantOutput} /> : null}
        </>
      )}
      {sessionError && <p className="cr-session-error" role="alert">{sessionError}</p>}
      {!isStreaming && (message.content || parts.some((part) => part.kind === "narrative" && part.text)) && (
        <div className="cr-message-actions" aria-label="Message actions">
          <button type="button" title="Copy" onClick={copyResponse}>
            {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
          </button>
          <span>{copied ? t("actions.copied", { defaultValue: "Copied" }) : ""}</span>
        </div>
      )}
    </article>
  );
}

export function ClaudeAgentThread({
  state,
  onCancelWorkflow,
  onConfigureProvider,
  onConfirm,
  onCancelConfirmation,
  onSubmitInput,
  onRetryFromCheckpoint,
  onOpenWorkflowCanvas,
}: {
  state: AIAssistantState;
  onCancelWorkflow: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider: () => void;
  onConfirm: (confirmationText?: string) => void;
  onCancelConfirmation: () => void;
  onSubmitInput?: (content: string) => void;
  onRetryFromCheckpoint?: (checkpointMessageId: string, content: string) => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
}) {
  const threadRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const executionItemsByMessageId = useMemo(() => {
    const grouped = new Map<string, AssistantExecutionItem[]>();
    for (const item of state.executionItems) {
      if (!item.messageId) continue;
      const items = grouped.get(item.messageId) ?? [];
      items.push(item);
      grouped.set(item.messageId, items);
    }
    return grouped;
  }, [state.executionItems]);
  const unassignedExecutionItems = useMemo(
    () => state.executionItems.filter((item) => !item.messageId),
    [state.executionItems],
  );
  const latestAssistantMessageId = useMemo(
    () => [...state.messages].reverse().find((message) => message.role === "assistant")?.id ?? null,
    [state.messages],
  );

  const scrollToBottom = (behavior: ScrollBehavior = "auto") => {
    const node = threadRef.current;
    if (!node) return;
    node.scrollTo({ top: node.scrollHeight, behavior });
    stickToBottomRef.current = true;
    setShowScrollToBottom(false);
  };

  useEffect(() => {
    stickToBottomRef.current = true;
    setShowScrollToBottom(false);
    const frame = window.requestAnimationFrame(() => scrollToBottom());
    return () => window.cancelAnimationFrame(frame);
  }, [state.currentConversationId]);

  useEffect(() => {
    if (!stickToBottomRef.current) return;
    const frame = window.requestAnimationFrame(() => scrollToBottom());
    return () => window.cancelAnimationFrame(frame);
  }, [state.activeAssistantMessageId, state.executionItems, state.isStreaming, state.messages]);

  useEffect(() => {
    const node = threadRef.current;
    const content = node?.firstElementChild;
    if (!node || !content || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (stickToBottomRef.current) scrollToBottom();
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, [state.currentConversationId]);

  const handleThreadScroll = () => {
    const node = threadRef.current;
    if (!node) return;
    const distanceFromBottom = node.scrollHeight - node.clientHeight - node.scrollTop;
    const atBottom = distanceFromBottom <= 48;
    stickToBottomRef.current = atBottom;
    setShowScrollToBottom(!atBottom && node.scrollHeight > node.clientHeight);
  };

  return (
    <div ref={threadRef} className="cr-thread" data-testid="claude-agent-thread" onScroll={handleThreadScroll}>
      <div className="cr-thread-inner">
        {state.messages.map((message) => {
          const confirmation =
            message.role === "assistant" && state.pendingConfirmation?.messageId === message.id
              ? state.pendingConfirmation
              : null;
          if (message.role === "user") {
            return (
              <ClaudeUserMessage
                key={message.id}
                message={message}
                canRetryFromCheckpoint={Boolean(message.durableId) && !state.isStreaming}
                onRetryFromCheckpoint={onRetryFromCheckpoint}
              />
            );
          }
          return (
            <div key={message.id}>
              <ClaudeAssistantMessage
                message={message}
                activityItems={executionItemsByMessageId.get(message.id) ?? []}
                isStreaming={state.isStreaming && state.activeAssistantMessageId === message.id}
                isThinking={state.isThinking && state.activeAssistantMessageId === message.id}
                sessionError={
                  state.sessionError &&
                  (state.activeAssistantMessageId ?? latestAssistantMessageId) === message.id
                    ? state.sessionError
                    : null
                }
                onCancelWorkflow={onCancelWorkflow}
                onConfigureProvider={onConfigureProvider}
                onOpenWorkflowCanvas={onOpenWorkflowCanvas}
              />
              {confirmation && (
                <ClaudeApproval
                  confirmation={confirmation}
                  onConfirm={onConfirm}
                  onCancel={onCancelConfirmation}
                />
              )}
            </div>
          );
        })}
        {unassignedExecutionItems.length > 0 && (
          <article className="cr-agent-message cr-analysis-message">
            <ClaudeActivityTimeline
              items={unassignedExecutionItems}
              onCancelWorkflow={onCancelWorkflow}
              onConfigureProvider={onConfigureProvider}
              onOpenWorkflowCanvas={onOpenWorkflowCanvas}
            />
          </article>
        )}
        {state.pendingConfirmation && !state.pendingConfirmation.messageId && (
          <ClaudeApproval
            confirmation={state.pendingConfirmation}
            onConfirm={onConfirm}
            onCancel={onCancelConfirmation}
          />
        )}
        {state.pendingInput && (
          <AssistantInputRequestForm
            request={state.pendingInput}
            onSubmit={(content) => onSubmitInput?.(content)}
          />
        )}
      </div>
      <Button
        aria-label="回到底部"
        className={`cr-scroll-to-bottom${showScrollToBottom ? " is-visible" : ""}`}
        data-testid="claude-scroll-to-bottom"
        onClick={() => scrollToBottom()}
        size="icon"
        type="button"
        variant="outline"
      >
        <ChevronDownIcon data-icon="inline-start" />
      </Button>
    </div>
  );
}
