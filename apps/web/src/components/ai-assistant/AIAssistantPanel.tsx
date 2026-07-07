import { useRef, useEffect, useCallback, useState, useMemo, type ChangeEvent, type RefObject } from "react";
import {
  HistoryIcon,
  PlusIcon,
  SendIcon,
  CommandIcon,
  PanelRightCloseIcon,
  CornerDownLeftIcon,
  SearchIcon,
  Trash2Icon,
  MessageSquareIcon,
  ChevronDownIcon,
  PencilIcon,
  FileIcon,
  FileTextIcon,
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
  listProviderConfigs,
  listBundles,
  renameChatConversation,
  uploadAssistantAttachment,
  uploadDocument,
  type AssistantAttachmentUploadResponse,
  type BundleRead,
  type ChatConversationRead,
  type ProviderConfig,
} from "@/lib/api";
import {
  isAssistantBusy,
  useAIAssistant,
  type AssistantConfirmationRequest,
  type AssistantExecutionItem,
  type AssistantRequestAttachment,
  type AssistantReasoningEffort,
  type AssistantApprovalMode,
  type ChatMessageAttachment,
  type ChatMessage,
} from "@/lib/ai-assistant-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Markdown } from "@/components/ui/markdown";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AgentMark } from "@/components/brand";
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
type ConfigMenu = "model" | "reasoning" | "approval" | null;

interface ComposerAttachment {
  id: string;
  file: File;
  kind: ComposerAttachmentKind;
  status: ComposerAttachmentStatus;
  assistantAttachmentId?: string;
  mimeType?: string;
  extractionStatus?: AssistantAttachmentUploadResponse["extraction_status"];
  extractedText?: string;
  documentId?: string;
  error?: string;
}

interface QueuedPrompt {
  id: string;
  prompt: string;
  displayContent: string;
  attachments: ChatMessageAttachment[];
  requestAttachments: AssistantRequestAttachment[];
  providerConfigId: string | null;
  reasoningEffort: AssistantReasoningEffort;
  approvalMode: AssistantApprovalMode;
}

const REASONING_OPTIONS: AssistantReasoningEffort[] = ["low", "medium", "high", "ultra", "max"];
const APPROVAL_MODES: AssistantApprovalMode[] = ["request_approval", "risky_only", "full_access", "custom"];

function createAttachmentId(file: File, index: number) {
  return `att-${Date.now()}-${index}-${file.name.replace(/[^a-zA-Z0-9]/g, "")}`;
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function getFileExtension(name: string) {
  const ext = name.split(".").pop()?.trim().toUpperCase();
  return ext && ext !== name.toUpperCase() ? ext : "FILE";
}

function getAttachmentPreviewTone(name: string, kind: ComposerAttachmentKind | ChatMessageAttachment["kind"]) {
  const ext = getFileExtension(name);
  if (kind === "image") return { label: ext === "FILE" ? "IMG" : ext, tone: "image" as const };
  if (ext === "PDF") return { label: "PDF", tone: "pdf" as const };
  if (["DOC", "DOCX", "WPS"].includes(ext)) return { label: ext, tone: "doc" as const };
  if (["XLS", "XLSX", "CSV"].includes(ext)) return { label: ext, tone: "sheet" as const };
  return { label: ext, tone: "file" as const };
}

function useObjectUrl(file: File | undefined, enabled: boolean) {
  const [url, setUrl] = useState<string | undefined>();

  useEffect(() => {
    if (!file || !enabled || typeof URL === "undefined" || typeof URL.createObjectURL !== "function") {
      setUrl(undefined);
      return;
    }
    const nextUrl = URL.createObjectURL(file);
    setUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [enabled, file]);

  return url;
}

async function ensureAssistantUploadBundle(projectId: string): Promise<BundleRead> {
  const bundles = await listBundles(projectId);
  const existing = bundles.find((bundle) => bundle.label === "AI uploads") ?? bundles[0];
  if (existing) return existing;
  return createBundle({ project_id: projectId, label: "AI uploads", source_type: "upload" });
}

function buildOutgoingPrompt(content: string, attachments: ComposerAttachment[]) {
  const trimmed = content.trim();
  if (trimmed) return trimmed;
  if (attachments.length > 0) return "请结合我上传的附件进行分析。";
  return "";
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

function toRequestAttachments(attachments: ComposerAttachment[]): AssistantRequestAttachment[] {
  return attachments.map((attachment) => ({
    id: attachment.assistantAttachmentId ?? attachment.id,
    name: attachment.file.name,
    kind: attachment.kind,
    mime_type: attachment.mimeType ?? attachment.file.type,
    size: attachment.file.size,
    extraction_status: attachment.extractionStatus,
    extracted_text: attachment.extractedText,
    document_id: attachment.documentId,
    error: attachment.error ?? null,
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

function AttachmentPreviewCard({
  name,
  kind,
  size,
  status,
  previewUrl,
  file,
  onRemove,
}: {
  name: string;
  kind: ComposerAttachmentKind | ChatMessageAttachment["kind"];
  size: number;
  status?: ComposerAttachmentStatus | ChatMessageAttachment["status"];
  previewUrl?: string;
  file?: File;
  onRemove?: () => void;
}) {
  const { t } = useTranslation("ai-assistant");
  const isImage = kind === "image";
  const objectUrl = useObjectUrl(file, isImage && !previewUrl);
  const imageUrl = previewUrl ?? objectUrl;
  const { label, tone } = getAttachmentPreviewTone(name, kind);
  const statusLabel = status ? t(`attachments.status.${status}`, { defaultValue: status }) : null;
  const iconTone = {
    image: "bg-emerald-500/12 text-emerald-500 border-emerald-500/20",
    pdf: "bg-red-500/12 text-red-500 border-red-500/20",
    doc: "bg-blue-500/12 text-blue-500 border-blue-500/20",
    sheet: "bg-amber-500/12 text-amber-500 border-amber-500/20",
    file: "bg-muted text-muted-foreground border-border",
  }[tone];

  return (
    <div
      className={cn(
        "group relative flex h-16 max-w-[13.5rem] shrink-0 items-center gap-2 overflow-hidden rounded-2xl border px-2.5 text-xs shadow-[0_14px_40px_oklch(0_0_0/0.12)] backdrop-blur-xl transition hover:-translate-y-px",
        isImage ? "w-20 justify-center p-1.5" : "w-[min(13.5rem,72vw)]",
      )}
      style={{
        background: "color-mix(in oklch, var(--background) 92%, transparent)",
        borderColor: "color-mix(in oklch, var(--border) 72%, transparent)",
        color: "var(--foreground)",
      }}
    >
      {isImage ? (
        <div className="h-full w-full overflow-hidden rounded-xl bg-muted">
          {imageUrl ? (
            <img src={imageUrl} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <ImageIcon className="h-5 w-5 text-muted-foreground" />
            </div>
          )}
        </div>
      ) : (
        <>
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border", iconTone)}>
            {tone === "pdf" || tone === "doc" ? <FileTextIcon className="h-5 w-5" /> : <FileIcon className="h-5 w-5" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-semibold tracking-[-0.01em]">{name}</div>
            <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span>{label}</span>
              <span className="h-0.5 w-0.5 rounded-full bg-current opacity-60" />
              <span>{formatFileSize(size)}</span>
            </div>
            {statusLabel && status !== "ready" && (
              <div className="mt-0.5 truncate text-[10px] text-muted-foreground">{statusLabel}</div>
            )}
          </div>
        </>
      )}
      {isImage && (
        <div className="pointer-events-none absolute inset-x-1.5 bottom-1.5 truncate rounded-b-xl bg-black/45 px-1.5 py-0.5 text-[10px] text-white/90 opacity-0 transition group-hover:opacity-100">
          {name}
        </div>
      )}
      {onRemove && (
        <button
          type="button"
          aria-label={`Remove ${name}`}
          onClick={onRemove}
          className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-background/95 text-muted-foreground shadow-sm transition hover:bg-foreground hover:text-background"
        >
          <XIcon className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}

function MessageBubble({ msg, activityItems = [] }: { msg: ChatMessage; activityItems?: AssistantExecutionItem[] }) {
  const isUser = msg.role === "user";
  if (isUser) {
    const hasAttachments = Boolean(msg.attachments && msg.attachments.length > 0);
    return (
      <div className="flex animate-fade-in flex-col items-end gap-2">
        {hasAttachments && (
          <div className="flex max-w-[94%] flex-wrap justify-end gap-2 sm:max-w-[88%]">
            {msg.attachments?.map((attachment) => (
              <AttachmentPreviewCard
                key={attachment.id}
                name={attachment.name}
                kind={attachment.kind}
                size={attachment.size}
                status={attachment.status}
                previewUrl={attachment.previewUrl}
              />
            ))}
          </div>
        )}
        {msg.content && (
          <div
            className="max-w-[94%] rounded-[1.35rem] rounded-br-[0.55rem] border px-4 py-2.5 text-[14px] leading-7 shadow-[0_12px_32px_oklch(0_0_0/0.10)] sm:max-w-[88%]"
            style={{
              background: "color-mix(in oklch, var(--muted) 82%, var(--background) 18%)",
              color: "var(--foreground)",
              borderColor: "color-mix(in oklch, var(--border) 58%, transparent)",
            }}
          >
            <div className="whitespace-pre-wrap break-words">{msg.content}</div>
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="flex flex-col items-start gap-2 animate-fade-in">
      <div
        className="w-full max-w-full px-1 py-1 text-[14px] leading-7 break-words sm:max-w-[92%]"
        style={{
          background: "transparent",
          color: "var(--foreground)",
          borderColor: "transparent",
        }}
      >
        {activityItems.length > 0 && <AssistantActivityTimeline items={activityItems} />}
        {msg.content ? (
          <Markdown variant="assistant" className="[&_code]:break-words">
            {normalizeAssistantMarkdown(msg.content)}
          </Markdown>
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
  t: (key: string, options?: Record<string, unknown>) => string;
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
    <div className="flex h-full w-[min(20rem,calc(100vw-1.25rem))] shrink-0 flex-col border-r bg-card shadow-xl" style={{ borderColor: "var(--border)" }}>
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
      <div className="shrink-0 px-3 pb-1 pt-2">
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
        <div className="flex flex-col gap-3 p-2">
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
                      const actionVisibility = isHovered
                        ? "opacity-100"
                        : "opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100";
                      return (
                        <div
                          key={conversation.id}
                          data-conversation-row
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
                                className="text-xs font-medium truncate pr-12"
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
                              <button
                                className={cn(
                                  "absolute right-7 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground/50 transition-all hover:bg-muted hover:text-foreground",
                                  actionVisibility,
                                )}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onRename(conversation.id, conversation.title);
                                }}
                                title={t("panel.renameConversation")}
                                aria-label={t("panel.renameConversation")}
                              >
                                <PencilIcon className="size-3" />
                              </button>
                              <button
                                className={cn(
                                  "absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground/40 transition-all hover:bg-destructive/10 hover:text-destructive",
                                  actionVisibility,
                                )}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onDelete(conversation.id);
                                }}
                                title={t("history.delete")}
                                aria-label={t("history.delete")}
                              >
                                <Trash2Icon className="size-3" />
                              </button>
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
    updateConversationTitle,
    confirmAssistantAction,
    setSelectedProviderConfig,
    setReasoningEffort,
    setApprovalMode,
  } = useAIAssistant();
  const { t } = useTranslation("ai-assistant");
  const [input, setInput] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historySearch, setHistorySearch] = useState("");
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(null);
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  const [configMenuOpen, setConfigMenuOpen] = useState<ConfigMenu>(null);
  const [attachments, setAttachments] = useState<ComposerAttachment[]>([]);
  const [queuedPrompts, setQueuedPrompts] = useState<QueuedPrompt[]>([]);
  const [providerConfigs, setProviderConfigs] = useState<ProviderConfig[]>([]);
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
  const selectedProvider = useMemo(
    () => providerConfigs.find((provider) => provider.id === state.selectedProviderConfigId) ?? null,
    [providerConfigs, state.selectedProviderConfigId],
  );
  const modelLabel = selectedProvider?.model ?? t("model.platformDefault", { defaultValue: "Platform default" });
  const reasoningLabel = t(`reasoning.options.${state.reasoningEffort}`, { defaultValue: state.reasoningEffort });
  const approvalLabel = t(`approval.options.${state.approvalMode}`, { defaultValue: state.approvalMode });
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

  const resizeComposer = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 112)}px`;
  }, []);

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
    resizeComposer();
  }, [input, resizeComposer]);

  useEffect(() => {
    if (state.isOpen && state.mode === "panel") {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [state.isOpen, state.mode]);

  useEffect(() => {
    if (!state.isOpen || state.mode !== "panel") return;
    let cancelled = false;
    void listProviderConfigs()
      .then((result) => {
        if (cancelled) return;
        setProviderConfigs(result.data);
        if (
          state.selectedProviderConfigId &&
          !result.data.some((provider) => provider.id === state.selectedProviderConfigId)
        ) {
          setSelectedProviderConfig(null);
        }
      })
      .catch((error) => {
        console.error("Failed to load assistant model configs:", error);
      });
    return () => {
      cancelled = true;
    };
  }, [setSelectedProviderConfig, state.isOpen, state.mode, state.selectedProviderConfigId]);

  useEffect(() => {
    if (!state.isOpen) {
      setHistoryOpen(false);
      setHistorySearch("");
      setConfigMenuOpen(null);
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

  const uploadAttachmentRecords = useCallback(async (records: ComposerAttachment[], projectId?: string) => {
    let bundlePromise: Promise<BundleRead> | null = projectId ? ensureAssistantUploadBundle(projectId) : null;
    for (const record of records) {
      try {
        const assistantAttachment = await uploadAssistantAttachment(record.file, record.kind);
        setAttachments((current) =>
          current.map((attachment) =>
            attachment.id === record.id
              ? {
                  ...attachment,
                  status: "uploaded",
                  assistantAttachmentId: assistantAttachment.id,
                  mimeType: assistantAttachment.mime_type,
                  extractionStatus: assistantAttachment.extraction_status,
                  extractedText: assistantAttachment.extracted_text,
                  error: assistantAttachment.error ?? undefined,
                }
              : attachment,
          ),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : "Attachment upload failed";
        setAttachments((current) =>
          current.map((attachment) =>
            attachment.id === record.id
              ? { ...attachment, status: "failed", extractionStatus: "failed", error: message }
              : attachment,
          ),
        );
        continue;
      }

      if (!bundlePromise) continue;

      try {
        const bundle = await bundlePromise;
        const document = await uploadDocument(bundle.id, record.file);
        setAttachments((current) =>
          current.map((attachment) =>
            attachment.id === record.id
              ? { ...attachment, documentId: document.id }
              : attachment,
          ),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : "Upload failed";
        bundlePromise = null;
        setAttachments((current) =>
          current.map((attachment) =>
            attachment.id === record.id
              ? { ...attachment, error: attachment.error ?? message }
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
        status: "uploading",
      }) satisfies ComposerAttachment);

      setAttachmentMenuOpen(false);
      setConfigMenuOpen(null);
      setHistoryOpen(false);
      setAttachments((current) => [...current, ...records]);
      void uploadAttachmentRecords(records, projectId);
    },
    [state.currentContext.projectId, uploadAttachmentRecords],
  );

  const handleRemoveAttachment = useCallback((id: string) => {
    setAttachments((current) => current.filter((attachment) => attachment.id !== id));
  }, []);

  const handleAddFromProject = useCallback(() => {
    setAttachmentMenuOpen(false);
    setConfigMenuOpen(null);
    setHistoryOpen(false);
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
    const requestAttachments = toRequestAttachments(attachments);
    const queuedPrompt: QueuedPrompt = {
      id: `queued-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      prompt: outgoing,
      displayContent,
      attachments: messageAttachments,
      requestAttachments,
      providerConfigId: state.selectedProviderConfigId,
      reasoningEffort: state.reasoningEffort,
      approvalMode: state.approvalMode,
    };

    shouldAutoScrollRef.current = true;
    setShowScrollToBottom(false);
    setInput("");
    setAttachments([]);

    if (isBusy) {
      setQueuedPrompts((current) => [...current, queuedPrompt]);
      return;
    }

    void sendMessage(outgoing, {
      displayContent,
      attachments: messageAttachments,
      requestAttachments,
      providerConfigId: state.selectedProviderConfigId,
      reasoningEffort: state.reasoningEffort,
    });
  }, [attachments, input, isBusy, isUploadingAttachments, sendMessage, state.reasoningEffort, state.selectedProviderConfigId, t]);

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
      requestAttachments: nextPrompt.requestAttachments,
      providerConfigId: nextPrompt.providerConfigId,
      reasoningEffort: nextPrompt.reasoningEffort,
      approvalMode: nextPrompt.approvalMode,
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
            requestAttachments: [],
            providerConfigId: state.selectedProviderConfigId,
            reasoningEffort: state.reasoningEffort,
            approvalMode: state.approvalMode,
          },
        ]);
        return;
      }
      void sendMessage(text, {
        providerConfigId: state.selectedProviderConfigId,
        reasoningEffort: state.reasoningEffort,
        approvalMode: state.approvalMode,
      });
    },
    [isBusy, sendMessage, state.approvalMode, state.reasoningEffort, state.selectedProviderConfigId],
  );

  const beginRenameConversation = useCallback((id: string, title: string | null) => {
    setAttachmentMenuOpen(false);
    setConfigMenuOpen(null);
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
      updateConversationTitle(editingConversationId, normalizedTitle);
      void refreshConversations();
    } catch (error) {
      console.error("Failed to rename conversation:", error);
    } finally {
      setRenamingConversationId(null);
      cancelRenameConversation();
    }
  }, [cancelRenameConversation, editingConversationId, editingTitle, refreshConversations, updateConversationTitle]);

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
      className="fixed inset-0 z-40 flex h-[100dvh] w-full flex-col animate-slide-in border-l sm:left-auto sm:w-[390px] md:w-[500px] xl:w-[560px]"
      style={{
        background: "color-mix(in oklch, var(--background) 94%, transparent)",
        borderColor: "color-mix(in oklch, var(--border) 78%, transparent)",
        boxShadow: "-28px 0 72px oklch(0 0 0 / 0.34), inset 1px 0 0 color-mix(in oklch, white 5%, transparent)",
        backdropFilter: "blur(22px) saturate(1.18)",
      }}
    >
      {/* ─── Header ─── */}
      <div
        className="flex min-h-14 shrink-0 items-center justify-between gap-2 border-b px-3.5"
        style={{
          borderColor: "color-mix(in oklch, var(--border) 64%, transparent)",
          background: "linear-gradient(180deg, color-mix(in oklch, var(--background) 96%, white 4%), color-mix(in oklch, var(--background) 86%, transparent))",
        }}
      >
        <div className="flex min-w-0 items-center gap-2">
          <Button
            variant="ghost"
            size="icon-sm"
            className={cn("text-muted-foreground", historyOpen && "bg-muted text-foreground")}
            onClick={() => {
              setAttachmentMenuOpen(false);
              setConfigMenuOpen(null);
              setHistoryOpen((v) => !v);
            }}
            title={t("panel.history")}
          >
            <HistoryIcon className="size-4" />
          </Button>
          <AgentMark decorative className="size-8" />
          <div className="min-w-0 flex-1">
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
        <div className="flex shrink-0 items-center gap-0.5">
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
            <div className="absolute inset-y-0 left-0 z-20 max-w-full">
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
          <div className="flex flex-col gap-5 px-3 py-4 sm:px-4 sm:py-5">
            {state.messages.length === 0 ? (
              <div className="flex min-h-[55vh] flex-col items-center justify-center text-center">
                <AgentMark decorative className="mx-auto mb-4 size-14 drop-shadow-[0_18px_50px_oklch(0_0_0/0.16)]" />
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
                          onConfirm={(confirmationText) => void confirmAssistantAction(true, confirmationText)}
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
                    onConfirm={(confirmationText) => void confirmAssistantAction(true, confirmationText)}
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
        className="shrink-0 px-2 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 sm:px-3"
        style={{
          background: "linear-gradient(180deg, transparent, color-mix(in oklch, var(--background) 96%, transparent) 28%)",
        }}
      >
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
          className="rounded-[1.6rem] border px-2 py-2 shadow-[0_18px_55px_oklch(0_0_0/0.18),inset_0_1px_0_oklch(1_0_0/0.08)] sm:rounded-[1.85rem]"
          style={{
            background: "color-mix(in oklch, var(--card) 92%, transparent)",
            borderColor: "color-mix(in oklch, var(--border) 72%, transparent)",
            backdropFilter: "blur(18px) saturate(1.08)",
          }}
        >
          {(attachments.length > 0 || queuedPrompts.length > 0) && (
            <div className="mb-2 flex max-h-40 gap-2 overflow-x-auto overflow-y-hidden px-1 pb-2 pt-1">
              {attachments.map((attachment) => (
                <AttachmentPreviewCard
                  key={attachment.id}
                  name={attachment.file.name}
                  kind={attachment.kind}
                  size={attachment.file.size}
                  status={attachment.status}
                  file={attachment.file}
                  onRemove={() => handleRemoveAttachment(attachment.id)}
                />
              ))}
              {queuedPrompts.map((queued) => (
                <div
                  key={queued.id}
                  className="flex h-16 w-[min(13.5rem,72vw)] shrink-0 items-center gap-2 rounded-2xl border px-2.5 text-xs"
                  style={{
                    background: "color-mix(in oklch, var(--background) 88%, transparent)",
                    borderColor: "color-mix(in oklch, var(--border) 72%, transparent)",
                    color: "var(--muted-foreground)",
                  }}
                >
                  <Loader2Icon className="h-4 w-4 shrink-0 animate-spin" />
                  <span className="min-w-0 truncate">
                    {t("panel.queuedPrompt", { defaultValue: "Queued" })}: {queued.displayContent}
                  </span>
                </div>
              ))}
            </div>
          )}
          <div className="flex min-h-10 items-center gap-1.5">
            <div className="relative shrink-0">
              <button
                type="button"
                aria-label={t("attachments.add", { defaultValue: "Add attachment" })}
                aria-expanded={attachmentMenuOpen}
                onClick={() => {
                  setHistoryOpen(false);
                  setConfigMenuOpen(null);
                  setAttachmentMenuOpen((value) => !value);
                }}
                className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-foreground"
              >
                <PlusIcon className="h-4 w-4" />
              </button>
              {attachmentMenuOpen && (
                <div
                  role="menu"
                  className="absolute bottom-11 left-0 z-30 w-[min(15rem,calc(100vw-2.25rem))] overflow-hidden rounded-3xl border bg-popover/95 p-1.5 text-sm shadow-[0_24px_70px_oklch(0_0_0/0.26)] backdrop-blur-xl"
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
              onChange={(e) => {
                setInput(e.target.value);
                requestAnimationFrame(resizeComposer);
              }}
              onKeyDown={handleKeyDown}
              placeholder={t("inputPlaceholder")}
              rows={1}
              className="min-h-8 max-h-28 min-w-0 flex-1 resize-none overflow-y-auto bg-transparent px-1 py-1.5 text-[16px] leading-6 text-foreground outline-none placeholder:text-muted-foreground sm:text-[14px]"
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
        </div>
        <div className="mt-1 flex items-center justify-between gap-2 px-1">
          <span className="hidden items-center gap-1 text-[10px] text-muted-foreground min-[380px]:flex">
            <CornerDownLeftIcon className="w-3 h-3" /> {isBusy ? t("panel.enterToQueue", { defaultValue: "Enter queues" }) : t("panel.enterToSend")}
          </span>
          <div className="relative ml-auto flex min-w-0 items-center gap-1 text-[10px] text-muted-foreground">
            <button
              type="button"
              aria-label={t("model.select", { defaultValue: "Select model" })}
              onClick={() => {
                setAttachmentMenuOpen(false);
                setHistoryOpen(false);
                setConfigMenuOpen((value) => (value === "model" ? null : "model"));
              }}
              className="flex max-w-[7.25rem] items-center gap-1 rounded-full px-2 py-1 transition hover:bg-muted hover:text-foreground min-[420px]:max-w-[9.5rem]"
            >
              <span className="truncate">{modelLabel}</span>
              <ChevronDownIcon className="h-3 w-3 shrink-0" />
            </button>
            <button
              type="button"
              aria-label={t("reasoning.select", { defaultValue: "Select reasoning effort" })}
              onClick={() => {
                setAttachmentMenuOpen(false);
                setHistoryOpen(false);
                setConfigMenuOpen((value) => (value === "reasoning" ? null : "reasoning"));
              }}
              className="flex items-center gap-1 rounded-full px-2 py-1 transition hover:bg-muted hover:text-foreground"
            >
              <span>{reasoningLabel}</span>
              <ChevronDownIcon className="h-3 w-3" />
            </button>
            <button
              type="button"
              aria-label={t("approval.select", { defaultValue: "Select approval mode" })}
              onClick={() => {
                setAttachmentMenuOpen(false);
                setHistoryOpen(false);
                setConfigMenuOpen((value) => (value === "approval" ? null : "approval"));
              }}
              className={cn(
                "flex max-w-[6.75rem] items-center gap-1 rounded-full px-2 py-1 transition hover:bg-muted hover:text-foreground",
                state.approvalMode === "full_access" && "text-amber-600 dark:text-amber-300",
              )}
            >
              <span className="truncate">{approvalLabel}</span>
              <ChevronDownIcon className="h-3 w-3 shrink-0" />
            </button>
            {configMenuOpen && (
              <div
                role="menu"
                className="absolute bottom-7 right-0 z-30 w-[min(16rem,calc(100vw-2.25rem))] overflow-hidden rounded-3xl border bg-popover/95 p-1.5 text-sm shadow-[0_24px_70px_oklch(0_0_0/0.26)] backdrop-blur-xl"
                style={{
                  borderColor: "color-mix(in oklch, var(--border) 72%, transparent)",
                  color: "var(--popover-foreground)",
                }}
              >
                {configMenuOpen === "model" ? (
                  <>
                    <div className="px-3 pb-1.5 pt-2 text-[11px] font-medium text-muted-foreground">
                      {t("model.menuTitle", { defaultValue: "Model" })}
                    </div>
                    <button
                      type="button"
                      role="menuitemradio"
                      aria-checked={!state.selectedProviderConfigId}
                      onClick={() => {
                        setSelectedProviderConfig(null);
                        setConfigMenuOpen(null);
                      }}
                      className={cn(
                        "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left transition hover:bg-muted",
                        !state.selectedProviderConfigId && "bg-muted text-foreground",
                      )}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">
                          {t("model.platformDefault", { defaultValue: "Platform default" })}
                        </span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {t("model.platformHint", { defaultValue: "Use BidPilot official model" })}
                        </span>
                      </span>
                      {!state.selectedProviderConfigId && <span className="text-xs">✓</span>}
                    </button>
                    {providerConfigs.map((provider) => (
                      <button
                        key={provider.id}
                        type="button"
                        role="menuitemradio"
                        aria-checked={state.selectedProviderConfigId === provider.id}
                        onClick={() => {
                          setSelectedProviderConfig(provider.id);
                          setConfigMenuOpen(null);
                        }}
                        className={cn(
                          "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left transition hover:bg-muted",
                          state.selectedProviderConfigId === provider.id && "bg-muted text-foreground",
                        )}
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium">{provider.label}</span>
                          <span className="block truncate text-xs text-muted-foreground">{provider.model}</span>
                        </span>
                        {state.selectedProviderConfigId === provider.id && <span className="text-xs">✓</span>}
                      </button>
                    ))}
                    {providerConfigs.length === 0 && (
                      <div className="px-3 py-2 text-xs text-muted-foreground">
                        {t("model.empty", { defaultValue: "No custom providers yet" })}
                      </div>
                    )}
                  </>
                ) : configMenuOpen === "reasoning" ? (
                  <>
                    <div className="px-3 pb-1.5 pt-2 text-[11px] font-medium text-muted-foreground">
                      {t("reasoning.menuTitle", { defaultValue: "Reasoning" })}
                    </div>
                    {REASONING_OPTIONS.map((effort) => (
                      <button
                        key={effort}
                        type="button"
                        role="menuitemradio"
                        aria-checked={state.reasoningEffort === effort}
                        onClick={() => {
                          setReasoningEffort(effort);
                          setConfigMenuOpen(null);
                        }}
                        className={cn(
                          "flex w-full items-center justify-between rounded-xl px-3 py-2 text-left transition hover:bg-muted",
                          state.reasoningEffort === effort && "bg-muted text-foreground",
                        )}
                      >
                        <span>{t(`reasoning.options.${effort}`, { defaultValue: effort })}</span>
                        {state.reasoningEffort === effort && <span className="text-xs">✓</span>}
                      </button>
                    ))}
                  </>
                ) : (
                  <>
                    <div className="px-3 pb-1.5 pt-2 text-[11px] font-medium text-muted-foreground">
                      {t("approval.menuTitle", { defaultValue: "Approval" })}
                    </div>
                    {APPROVAL_MODES.map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        role="menuitemradio"
                        aria-checked={state.approvalMode === mode}
                        onClick={() => {
                          setApprovalMode(mode);
                          setConfigMenuOpen(null);
                        }}
                        className={cn(
                          "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left transition hover:bg-muted",
                          state.approvalMode === mode && "bg-muted text-foreground",
                        )}
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium">
                            {t(`approval.options.${mode}`, { defaultValue: mode })}
                          </span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {t(`approval.hints.${mode}`, { defaultValue: "" })}
                          </span>
                        </span>
                        {state.approvalMode === mode && <span className="text-xs">✓</span>}
                      </button>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
