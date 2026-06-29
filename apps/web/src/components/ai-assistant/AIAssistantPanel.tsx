import { useRef, useEffect, useCallback, useState, useMemo, type ChangeEvent, type RefObject } from "react";
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
  ChevronDownIcon,
  FileIcon,
  FolderOpenIcon,
  ImageIcon,
  Loader2Icon,
  PaperclipIcon,
  XIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  createBundle,
  deleteChatConversation,
  listBundles,
  renameChatConversation,
  uploadDocument,
  type BundleRead,
  type ChatConversationRead,
} from "@/lib/api";
import {
  isAssistantBusy,
  useAIAssistant,
  type AssistantConfirmationRequest,
  type AssistantExecutionItem,
  type ChatMessageAttachment,
  type ChatMessage,
} from "@/lib/ai-assistant-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Markdown } from "@/components/ui/markdown";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AssistantConfirmationCard } from "./assistant-confirmation-card";
import { AssistantActivityTimeline } from "./assistant-activity-timeline";

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

type ComposerAttachmentKind = "file" | "image";
type ComposerAttachmentStatus = "ready" | "uploading" | "uploaded" | "failed";

interface ComposerAttachment {
  id: string;
  file: File;
  kind: ComposerAttachmentKind;
  status: ComposerAttachmentStatus;
  documentId?: string;
  error?: string;
}

interface QueuedPrompt {
  id: string;
  prompt: string;
  displayContent: string;
  attachments: ChatMessageAttachment[];
}

function createAttachmentId(file: File, index: number) {
  return `att-${Date.now()}-${index}-${file.name.replace(/[^a-zA-Z0-9]/g, "")}`;
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function ensureAssistantUploadBundle(projectId: string): Promise<BundleRead> {
  const bundles = await listBundles(projectId);
  const existing = bundles.find((bundle) => bundle.label === "AI uploads") ?? bundles[0];
  if (existing) return existing;
  return createBundle({ project_id: projectId, label: "AI uploads", source_type: "upload" });
}

function buildOutgoingPrompt(content: string, attachments: ComposerAttachment[]) {
  if (attachments.length === 0) return content;
  const attachmentLines = attachments.map((attachment) => {
    if (attachment.status === "uploaded" && attachment.documentId) {
      return `- ${attachment.file.name} (${attachment.kind}, document_id: ${attachment.documentId})`;
    }
    if (attachment.status === "failed") {
      return `- ${attachment.file.name} (${attachment.kind}, upload failed: ${attachment.error ?? "unknown error"})`;
    }
    return `- ${attachment.file.name} (${attachment.kind}, selected locally)`;
  });
  const attachmentBlock = `附件上下文：\n${attachmentLines.join("\n")}`;
  return [content, attachmentBlock].filter(Boolean).join("\n\n");
}

function buildDisplayContent(
  content: string,
  attachments: ComposerAttachment[],
  t: (key: string, options?: Record<string, unknown>) => string,
) {
  if (content.trim()) return content.trim();
  if (attachments.length === 1) {
    return t("attachments.addedOne", {
      name: attachments[0].file.name,
      defaultValue: `Added ${attachments[0].file.name}`,
    });
  }
  return t("attachments.addedMany", {
    count: attachments.length,
    defaultValue: `Added ${attachments.length} attachments`,
  });
}

function createAttachmentPreviewUrl(attachment: ComposerAttachment) {
  if (attachment.kind !== "image") return undefined;
  if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") return undefined;
  return URL.createObjectURL(attachment.file);
}

function toMessageAttachments(attachments: ComposerAttachment[]): ChatMessageAttachment[] {
  return attachments.map((attachment) => ({
    id: attachment.id,
    name: attachment.file.name,
    kind: attachment.kind,
    size: attachment.file.size,
    status: attachment.status === "uploading" ? "ready" : attachment.status,
    documentId: attachment.documentId,
    previewUrl: createAttachmentPreviewUrl(attachment),
  }));
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

function MessageAttachmentPreview({ attachment }: { attachment: ChatMessageAttachment }) {
  const { t } = useTranslation("ai-assistant");
  const isImage = attachment.kind === "image";
  const statusLabel = t(`attachments.status.${attachment.status}`, { defaultValue: attachment.status });
  return (
    <div
      className={cn(
        "overflow-hidden border text-xs shadow-[0_10px_30px_oklch(0_0_0/0.12)] backdrop-blur-xl",
        isImage ? "w-20 rounded-2xl" : "max-w-52 rounded-2xl px-2.5 py-2",
      )}
      style={{
        background: "color-mix(in oklch, var(--background) 88%, transparent)",
        borderColor: "color-mix(in oklch, var(--border) 70%, transparent)",
        color: "var(--foreground)",
      }}
    >
      {isImage ? (
        <div className="flex aspect-[4/3] items-center justify-center bg-muted">
          {attachment.previewUrl ? (
            <img src={attachment.previewUrl} alt="" className="h-full w-full object-cover" />
          ) : (
            <ImageIcon className="h-5 w-5 text-muted-foreground" />
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <FileIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <div className="truncate font-medium">{attachment.name}</div>
            <div className="text-[10px] text-muted-foreground">{formatFileSize(attachment.size)}</div>
          </div>
        </div>
      )}
      {isImage && (
        <div className="truncate px-2 py-1 text-[10px] text-muted-foreground">
          {attachment.name}
        </div>
      )}
      <div className="border-t px-2 py-1 text-[10px] text-muted-foreground" style={{ borderColor: "var(--border)" }}>
        {statusLabel}
      </div>
    </div>
  );
}

function MessageBubble({ msg, activityItems = [] }: { msg: ChatMessage; activityItems?: AssistantExecutionItem[] }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex flex-col gap-2 animate-fade-in", isUser ? "items-end" : "items-start")}>
      {isUser && msg.attachments && msg.attachments.length > 0 && (
        <div className="flex max-w-[85%] flex-wrap justify-end gap-2">
          {msg.attachments.map((attachment) => (
            <MessageAttachmentPreview key={attachment.id} attachment={attachment} />
          ))}
        </div>
      )}
      <div
        className={cn(
          "text-[14px] leading-7 break-words",
          isUser
            ? "max-w-[82%] rounded-[1.35rem] rounded-br-[0.55rem] border px-4 py-2.5 shadow-[0_14px_36px_oklch(0_0_0/0.16)]"
            : "w-full max-w-[92%] px-1 py-1",
        )}
        style={{
          background: isUser
            ? "linear-gradient(180deg, color-mix(in oklch, var(--primary) 88%, white 12%), var(--primary))"
            : "transparent",
          color: isUser ? "var(--primary-foreground)" : "var(--foreground)",
          borderColor: isUser ? "color-mix(in oklch, var(--primary) 68%, white 24%)" : "transparent",
        }}
      >
        {!isUser && activityItems.length > 0 && <AssistantActivityTimeline items={activityItems} />}
        {msg.content ? (
          isUser ? (
            <span className="whitespace-pre-wrap">{msg.content}</span>
          ) : (
            <Markdown className="[&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-1 [&_pre]:my-2 [&_code]:break-words">
              {normalizeAssistantMarkdown(msg.content)}
            </Markdown>
          )
        ) : (
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" style={{ animationDelay: "0ms" }} />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" style={{ animationDelay: "150ms" }} />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" style={{ animationDelay: "300ms" }} />
          </span>
        )}
      </div>
    </div>
  );
}

function ComposerAttachmentChip({
  attachment,
  onRemove,
}: {
  attachment: ComposerAttachment;
  onRemove: (id: string) => void;
}) {
  const statusIcon =
    attachment.status === "uploading" ? (
      <Loader2Icon className="h-3 w-3 animate-spin" />
    ) : attachment.kind === "image" ? (
      <ImageIcon className="h-3 w-3" />
    ) : (
      <FileIcon className="h-3 w-3" />
    );

  return (
    <div
      className="flex max-w-full items-center gap-1.5 rounded-full border px-2 py-1 text-[11px]"
      style={{ background: "var(--muted)", borderColor: "var(--border)", color: "var(--foreground)" }}
    >
      <span className="shrink-0 text-muted-foreground">{statusIcon}</span>
      <span className="truncate">{attachment.file.name}</span>
      <span className="shrink-0 text-muted-foreground">{formatFileSize(attachment.file.size)}</span>
      {attachment.status === "failed" && <span className="shrink-0 text-destructive">failed</span>}
      <button
        type="button"
        aria-label={`Remove ${attachment.file.name}`}
        onClick={() => onRemove(attachment.id)}
        className="shrink-0 rounded-full p-0.5 text-muted-foreground transition hover:bg-background hover:text-foreground"
      >
        <XIcon className="h-3 w-3" />
      </button>
    </div>
  );
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
  renameInputRef: RefObject<HTMLInputElement | null>;
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
                              aria-label={t("history.rename", { defaultValue: "Rename conversation" })}
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
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  const [attachments, setAttachments] = useState<ComposerAttachment[]>([]);
  const [queuedPrompts, setQueuedPrompts] = useState<QueuedPrompt[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const queueDrainingRef = useRef(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const isBusy = isAssistantBusy(state.status);
  const isUploadingAttachments = attachments.some((attachment) => attachment.status === "uploading");
  const canSend = Boolean(input.trim() || attachments.length > 0) && !isUploadingAttachments;
  const executionItemsByMessageId = useMemo(() => {
    const grouped = new Map<string, AssistantExecutionItem[]>();
    for (const item of state.executionItems) {
      if (!item.messageId) continue;
      const current = grouped.get(item.messageId) ?? [];
      current.push(item);
      grouped.set(item.messageId, current);
    }
    return grouped;
  }, [state.executionItems]);
  const unassignedExecutionItems = useMemo(
    () => state.executionItems.filter((item) => !item.messageId),
    [state.executionItems],
  );

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior, block: "end" });
    });
  }, []);

  const handleMessagesScroll = useCallback(() => {
    const viewport = scrollContainerRef.current;
    if (!viewport) return;
    const distanceFromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    const isNearBottom = distanceFromBottom < 120;
    shouldAutoScrollRef.current = isNearBottom;
    setShowScrollToBottom(!isNearBottom);
  }, []);

  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      scrollToBottom("smooth");
    }
  }, [scrollToBottom, state.messages, state.executionItems, state.pendingConfirmation]);

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

  const uploadAttachmentRecords = useCallback(async (records: ComposerAttachment[], projectId: string) => {
    let bundle: BundleRead;
    try {
      bundle = await ensureAssistantUploadBundle(projectId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to prepare upload bundle";
      setAttachments((current) =>
        current.map((attachment) =>
          records.some((record) => record.id === attachment.id)
            ? { ...attachment, status: "failed", error: message }
            : attachment,
        ),
      );
      return;
    }

    for (const record of records) {
      try {
        const document = await uploadDocument(bundle.id, record.file);
        setAttachments((current) =>
          current.map((attachment) =>
            attachment.id === record.id
              ? { ...attachment, status: "uploaded", documentId: document.id }
              : attachment,
          ),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : "Upload failed";
        setAttachments((current) =>
          current.map((attachment) =>
            attachment.id === record.id
              ? { ...attachment, status: "failed", error: message }
              : attachment,
          ),
        );
      }
    }
  }, []);

  const handleAttachmentInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>, kind: ComposerAttachmentKind) => {
      const files = Array.from(event.currentTarget.files ?? []);
      event.currentTarget.value = "";
      if (files.length === 0) return;

      const projectId = state.currentContext.projectId;
      const records = files.map((file, index) => ({
        id: createAttachmentId(file, index),
        file,
        kind,
        status: projectId ? "uploading" : "ready",
      }) satisfies ComposerAttachment);

      setAttachmentMenuOpen(false);
      setAttachments((current) => [...current, ...records]);
      if (projectId) {
        void uploadAttachmentRecords(records, projectId);
      }
    },
    [state.currentContext.projectId, uploadAttachmentRecords],
  );

  const handleRemoveAttachment = useCallback((id: string) => {
    setAttachments((current) => current.filter((attachment) => attachment.id !== id));
  }, []);

  const handleAddFromProject = useCallback(() => {
    setAttachmentMenuOpen(false);
    setInput((current) => {
      const prompt = t("attachments.addFromProjectPrompt", {
        defaultValue: "请从当前项目资料库中检索并添加相关材料。",
      });
      return current.trim() ? `${current.trim()}\n${prompt}` : prompt;
    });
    inputRef.current?.focus();
  }, [t]);

  const handleSend = useCallback(() => {
    const trimmedInput = input.trim();
    const outgoing = buildOutgoingPrompt(trimmedInput, attachments);
    if (!outgoing.trim() || isUploadingAttachments) return;
    const displayContent = buildDisplayContent(trimmedInput, attachments, t);
    const messageAttachments = toMessageAttachments(attachments);
    const queuedPrompt: QueuedPrompt = {
      id: `queued-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      prompt: outgoing,
      displayContent,
      attachments: messageAttachments,
    };

    shouldAutoScrollRef.current = true;
    setShowScrollToBottom(false);
    setInput("");
    setAttachments([]);

    if (isBusy) {
      setQueuedPrompts((current) => [...current, queuedPrompt]);
      return;
    }

    void sendMessage(outgoing, { displayContent, attachments: messageAttachments });
  }, [attachments, input, isBusy, isUploadingAttachments, sendMessage, t]);

  useEffect(() => {
    if (queueDrainingRef.current || isAssistantBusy(state.status) || queuedPrompts.length === 0) return;

    const nextPrompt = queuedPrompts[0];
    queueDrainingRef.current = true;
    setQueuedPrompts((current) => current.slice(1));
    shouldAutoScrollRef.current = true;
    setShowScrollToBottom(false);
    void sendMessage(nextPrompt.prompt, {
      displayContent: nextPrompt.displayContent,
      attachments: nextPrompt.attachments,
    }).finally(() => {
      queueDrainingRef.current = false;
    });
  }, [queuedPrompts, sendMessage, state.status]);

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
      shouldAutoScrollRef.current = true;
      setShowScrollToBottom(false);
      if (isBusy) {
        setQueuedPrompts((current) => [
          ...current,
          {
            id: `queued-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            prompt: text,
            displayContent: text,
            attachments: [],
          },
        ]);
        return;
      }
      void sendMessage(text);
    },
    [isBusy, sendMessage],
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
      className="fixed top-0 right-0 z-40 flex h-full w-full flex-col animate-slide-in border-l sm:w-[360px] md:w-[440px] lg:w-[480px]"
      style={{
        background: "color-mix(in oklch, var(--background) 94%, transparent)",
        borderColor: "color-mix(in oklch, var(--border) 78%, transparent)",
        boxShadow: "-28px 0 72px oklch(0 0 0 / 0.34), inset 1px 0 0 color-mix(in oklch, white 5%, transparent)",
        backdropFilter: "blur(22px) saturate(1.18)",
      }}
    >
      {/* ─── Header ─── */}
      <div
        className="flex h-14 shrink-0 items-center justify-between border-b px-3.5"
        style={{
          borderColor: "color-mix(in oklch, var(--border) 64%, transparent)",
          background: "linear-gradient(180deg, color-mix(in oklch, var(--background) 96%, white 4%), color-mix(in oklch, var(--background) 86%, transparent))",
        }}
      >
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
          <div
            className="flex size-8 shrink-0 items-center justify-center rounded-2xl border shadow-sm"
            style={{
              background: "linear-gradient(145deg, color-mix(in oklch, var(--primary) 88%, white 12%), var(--primary))",
              borderColor: "color-mix(in oklch, var(--primary) 55%, white 20%)",
              color: "var(--primary-foreground)",
            }}
          >
            <SparklesIcon className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold truncate text-foreground">
                {state.currentConversationId
                  ? (Array.isArray(state.conversations)
                    ? state.conversations.find((item) => item.id === state.currentConversationId)?.title
                    : null) || t("panel.untitledConversation")
                  : t("title")}
              </span>
            </div>
            <div className="truncate text-[11px] text-muted-foreground">
              {state.status === "idle"
                ? t("status.ready", { defaultValue: "Ready" })
                : t(`status.${state.status}`, { defaultValue: t("thinking") })}
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
        <div
          ref={scrollContainerRef}
          onScroll={handleMessagesScroll}
          className="h-full overflow-y-auto"
        >
          <div className="flex flex-col gap-5 px-4 py-5">
            {state.messages.length === 0 ? (
              <div className="flex min-h-[55vh] flex-col items-center justify-center text-center">
                <div
                  className="mx-auto mb-4 flex size-14 items-center justify-center rounded-[1.4rem] border shadow-[0_18px_50px_oklch(0_0_0/0.16)]"
                  style={{
                    background: "linear-gradient(145deg, color-mix(in oklch, var(--primary) 86%, white 14%), var(--primary))",
                    borderColor: "color-mix(in oklch, var(--primary) 56%, white 20%)",
                  }}
                >
                  <SparklesIcon className="size-7 text-primary-foreground" />
                </div>
                <h3 className="text-base font-semibold mb-1 text-foreground">{t("welcome.title")}</h3>
                <p className="mb-6 max-w-[28ch] text-sm leading-6 text-muted-foreground">{t("welcome.description")}</p>
                <QuickActions onSelect={handleQuickAction} />
              </div>
            ) : (
              <>
                {state.messages.map((msg) => {
                  const turnItems = executionItemsByMessageId.get(msg.id) ?? [];
                  const pendingConfirmation =
                    state.pendingConfirmation?.messageId === msg.id ? state.pendingConfirmation : null;

                  return (
                    <div key={msg.id} className="flex flex-col gap-2">
                      {msg.role === "assistant" && pendingConfirmation && (
                        <AssistantConfirmationCard
                          confirmation={pendingConfirmation}
                          onConfirm={() => void confirmAssistantAction(true)}
                          onCancel={() => void confirmAssistantAction(false)}
                        />
                      )}
                      <MessageBubble msg={msg} activityItems={msg.role === "assistant" ? turnItems : []} />
                    </div>
                  );
                })}
                {unassignedExecutionItems.length > 0 && <AssistantActivityTimeline items={unassignedExecutionItems} />}
                {state.pendingConfirmation && !state.pendingConfirmation.messageId && (
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
        </div>

        {showScrollToBottom && state.messages.length > 0 && !historyOpen && (
          <button
            type="button"
            aria-label={t("panel.scrollToBottom", { defaultValue: "Scroll to bottom" })}
            onClick={() => {
              shouldAutoScrollRef.current = true;
              setShowScrollToBottom(false);
              scrollToBottom("smooth");
            }}
            className="absolute bottom-3 left-1/2 z-10 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border bg-background/95 text-muted-foreground shadow-lg backdrop-blur transition hover:text-foreground"
            style={{ borderColor: "var(--border)" }}
          >
            <ChevronDownIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* ─── Input ─── */}
      <div
        className="shrink-0 px-3 pb-3 pt-2"
        style={{
          background: "linear-gradient(180deg, transparent, color-mix(in oklch, var(--background) 96%, transparent) 28%)",
        }}
      >
        {(attachments.length > 0 || queuedPrompts.length > 0) && (
          <div className="mb-2 flex max-h-24 flex-col gap-1.5 overflow-y-auto">
            {attachments.map((attachment) => (
              <ComposerAttachmentChip
                key={attachment.id}
                attachment={attachment}
                onRemove={handleRemoveAttachment}
              />
            ))}
            {queuedPrompts.map((queued) => (
              <div
                key={queued.id}
                className="flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px]"
                style={{ background: "var(--muted)", borderColor: "var(--border)", color: "var(--muted-foreground)" }}
              >
                <Loader2Icon className="h-3 w-3 animate-spin" />
                <span className="truncate">
                  {t("panel.queuedPrompt", { defaultValue: "Queued" })}: {queued.displayContent}
                </span>
              </div>
            ))}
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(event) => handleAttachmentInputChange(event, "file")}
        />
        <input
          ref={imageInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(event) => handleAttachmentInputChange(event, "image")}
        />
        <div
          className="flex min-h-12 items-end gap-1.5 rounded-[1.65rem] border px-2 py-2 shadow-[0_18px_55px_oklch(0_0_0/0.18),inset_0_1px_0_oklch(1_0_0/0.08)]"
          style={{
            background: "color-mix(in oklch, var(--card) 92%, transparent)",
            borderColor: "color-mix(in oklch, var(--border) 72%, transparent)",
            backdropFilter: "blur(18px) saturate(1.08)",
          }}
        >
          <div className="relative shrink-0">
            <button
              type="button"
              aria-label={t("attachments.add", { defaultValue: "Add attachment" })}
              aria-expanded={attachmentMenuOpen}
              onClick={() => setAttachmentMenuOpen((value) => !value)}
              className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-foreground"
            >
              <PlusIcon className="h-4 w-4" />
            </button>
            {attachmentMenuOpen && (
              <div
                role="menu"
                className="absolute bottom-11 left-0 z-30 w-60 overflow-hidden rounded-3xl border bg-popover/95 p-1.5 text-sm shadow-[0_24px_70px_oklch(0_0_0/0.26)] backdrop-blur-xl"
                style={{
                  borderColor: "color-mix(in oklch, var(--border) 72%, transparent)",
                  color: "var(--popover-foreground)",
                }}
              >
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left transition hover:bg-muted"
                >
                  <FileIcon className="h-4 w-4 text-muted-foreground" />
                  <span>{t("attachments.uploadFile", { defaultValue: "Upload file" })}</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => imageInputRef.current?.click()}
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left transition hover:bg-muted"
                >
                  <ImageIcon className="h-4 w-4 text-muted-foreground" />
                  <span>{t("attachments.uploadImage", { defaultValue: "Upload image" })}</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={handleAddFromProject}
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left transition hover:bg-muted"
                >
                  <FolderOpenIcon className="h-4 w-4 text-muted-foreground" />
                  <span>{t("attachments.addFromProject", { defaultValue: "Add from project" })}</span>
                </button>
              </div>
            )}
          </div>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("inputPlaceholder")}
            rows={1}
            className="min-h-8 max-h-28 flex-1 resize-none overflow-y-auto bg-transparent px-1 py-1.5 text-[14px] leading-6 text-foreground outline-none placeholder:text-muted-foreground"
          />
          <button
            onClick={handleSend}
            disabled={!canSend}
            aria-label={t("actions.send")}
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-full transition-all duration-200 disabled:opacity-35",
              canSend
                ? "bg-primary text-primary-foreground shadow-[0_10px_28px_oklch(0_0_0/0.18)] hover:scale-[1.03] active:scale-95"
                : "text-muted-foreground"
            )}
          >
            {isUploadingAttachments ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <SendIcon className="w-4 h-4" />}
          </button>
        </div>
        <div className="mt-1 flex items-center justify-between px-1">
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <CornerDownLeftIcon className="w-3 h-3" /> {isBusy ? t("panel.enterToQueue", { defaultValue: "Enter queues" }) : t("panel.enterToSend")}
          </span>
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <PaperclipIcon className="h-3 w-3" />
            {t("attachments.hint", { defaultValue: "Files stay server-side" })}
          </span>
        </div>
      </div>
    </div>
  );
}
