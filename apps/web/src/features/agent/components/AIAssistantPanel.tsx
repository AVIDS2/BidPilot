import {
  useRef,
  useEffect,
  useCallback,
  useState,
  useMemo,
  type ChangeEvent,
  type ReactNode,
  type RefObject,
} from "react";
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
  ArrowUpIcon,
  FileIcon,
  FileTextIcon,
  FolderOpenIcon,
  ImageIcon,
  Loader2Icon,
  SquareIcon,
  XIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  createBundle,
  deleteChatConversation,
  listProviderConfigs,
  listBundles,
  renameChatConversation,
  reingestBundle,
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
  type AssistantExecutionItem,
  type AssistantRequestAttachment,
  type AssistantReasoningEffort,
  type AssistantApprovalMode,
  type ChatMessageAttachment,
  type ChatMessage,
} from "@/features/agent/state/agent-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputActions,
  PromptInputAction,
} from "@/components/ui/prompt-input";
import {
  ChatContainerRoot,
  ChatContainerContent,
  ChatContainerScrollAnchor,
} from "@/components/ui/chat-container";
import { Message, MessageContent } from "@/components/ui/message";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ScrollButton } from "@/components/ui/scroll-button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AgentMark } from "@/components/brand";
import FadeContent from "@/components/FadeContent";
import { AssistantConfirmationCard } from "./assistant-confirmation-card";
import { AssistantInputRequestForm } from "./assistant-input-request";
import { ClaudeActivityTimeline } from "./claude-activity-timeline";
import { projectExecutionItemsOntoTranscript } from "@/features/agent/runtime/assistant-transcript";

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

export type ComposerAttachmentKind = "file" | "image";
export interface AttachmentPreviewSelection {
  name: string;
  kind: ComposerAttachmentKind;
  size: number;
  file?: File;
  previewUrl?: string;
}
type ComposerAttachmentStatus = "ready" | "uploading" | "uploaded" | "failed";
type ConfigMenu = "model" | "reasoning" | "approval" | null;

const EMPTY_TRANSCRIPT_PARTS: NonNullable<ChatMessage["transcriptParts"]> = [];

type AssistantComposerMenusProps = {
  variant: "linear" | "panel";
  attachmentMenuOpen: boolean;
  configMenuOpen: ConfigMenu;
  modelLabel: string;
  reasoningLabel: string;
  approvalLabel: string;
  approvalHint: string;
  providerConfigs: ProviderConfig[];
  selectedProviderConfigId: string | null;
  reasoningEffort: AssistantReasoningEffort;
  approvalMode: AssistantApprovalMode;
  onAttachmentMenuOpenChange: (open: boolean) => void;
  onConfigMenuOpenChange: (menu: Exclude<ConfigMenu, null>, open: boolean) => void;
  onSelectProvider: (id: string | null) => void;
  onSelectReasoning: (effort: AssistantReasoningEffort) => void;
  onSelectApproval: (mode: AssistantApprovalMode) => void;
  onUploadFile: () => void;
  onUploadImage: () => void;
  onAddFromProject: () => void;
  showAttachment?: boolean;
  showConfig?: boolean;
};

function AssistantComposerMenus({
  variant,
  attachmentMenuOpen,
  configMenuOpen,
  modelLabel,
  reasoningLabel,
  approvalLabel,
  approvalHint,
  providerConfigs,
  selectedProviderConfigId,
  reasoningEffort,
  approvalMode,
  onAttachmentMenuOpenChange,
  onConfigMenuOpenChange,
  onSelectProvider,
  onSelectReasoning,
  onSelectApproval,
  onUploadFile,
  onUploadImage,
  onAddFromProject,
  showAttachment = true,
  showConfig = true,
}: AssistantComposerMenusProps) {
  const { t } = useTranslation("ai-assistant");
  const textTriggerClass = variant === "linear"
    ? "bp-linear-agent-text-control"
    : "flex max-w-[7.25rem] items-center gap-1 rounded-full px-2 py-1 min-[420px]:max-w-[9.5rem]";
  const attachmentTriggerClass = variant === "linear"
    ? "bp-linear-agent-icon-button"
    : "flex size-8 items-center justify-center rounded-full text-muted-foreground";

  return (
    <>
      {showAttachment ? <DropdownMenu open={attachmentMenuOpen} onOpenChange={onAttachmentMenuOpenChange}>
        <DropdownMenuTrigger render={<Button aria-label={t("attachments.add", { defaultValue: "Add attachment" })} className={attachmentTriggerClass} size="icon-sm" type="button" variant="ghost" />}>
          <PlusIcon aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56" side="top" sideOffset={8}>
          <DropdownMenuGroup>
            <DropdownMenuLabel>{t("attachments.menuTitle", { defaultValue: "Add to this message" })}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onUploadFile}><FileIcon aria-hidden="true" />{t("attachments.uploadFile", { defaultValue: "Upload file" })}</DropdownMenuItem>
            <DropdownMenuItem onClick={onUploadImage}><ImageIcon aria-hidden="true" />{t("attachments.uploadImage", { defaultValue: "Upload image" })}</DropdownMenuItem>
            <DropdownMenuItem onClick={onAddFromProject}><FolderOpenIcon aria-hidden="true" />{t("attachments.addFromProject", { defaultValue: "Add from project" })}</DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu> : null}
      {showConfig ? <>
      <DropdownMenu open={configMenuOpen === "model"} onOpenChange={(open) => onConfigMenuOpenChange("model", open)}>
        <DropdownMenuTrigger render={<Button aria-label={t("model.select", { defaultValue: "Select model" })} className={textTriggerClass} size="sm" type="button" variant="ghost" />}>
          <span className="truncate">{modelLabel}</span><ChevronDownIcon aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64" side="top" sideOffset={8}>
          <DropdownMenuGroup>
            <DropdownMenuLabel>{t("model.menuTitle", { defaultValue: "Model" })}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuRadioGroup value={selectedProviderConfigId ?? "official"} onValueChange={(value) => { onSelectProvider(value === "official" ? null : value); onConfigMenuOpenChange("model", false); }}>
              <DropdownMenuRadioItem value="official">{t("model.platformDefault", { defaultValue: "Platform default" })}</DropdownMenuRadioItem>
              {providerConfigs.map((provider) => <DropdownMenuRadioItem key={provider.id} value={provider.id}><span className="min-w-0 truncate">{provider.label}</span><span className="min-w-0 truncate text-muted-foreground">{provider.model}</span></DropdownMenuRadioItem>)}
            </DropdownMenuRadioGroup>
            {providerConfigs.length === 0 ? <div className="px-1.5 py-1 text-xs text-muted-foreground">{t("model.empty", { defaultValue: "No custom providers yet" })}</div> : null}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <DropdownMenu open={configMenuOpen === "reasoning"} onOpenChange={(open) => onConfigMenuOpenChange("reasoning", open)}>
        <DropdownMenuTrigger render={<Button aria-label={t("reasoning.select", { defaultValue: "Select reasoning effort" })} className={variant === "linear" ? textTriggerClass : "flex items-center gap-1 rounded-full px-2 py-1"} size="sm" type="button" variant="ghost" />}>
          <span>{reasoningLabel}</span><ChevronDownIcon aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44" side="top" sideOffset={8}>
          <DropdownMenuGroup>
            <DropdownMenuLabel>{t("reasoning.menuTitle", { defaultValue: "Reasoning" })}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuRadioGroup value={reasoningEffort} onValueChange={(value) => { onSelectReasoning(value as AssistantReasoningEffort); onConfigMenuOpenChange("reasoning", false); }}>
              {REASONING_OPTIONS.map((effort) => <DropdownMenuRadioItem key={effort} value={effort}>{t(`reasoning.options.${effort}`, { defaultValue: effort })}</DropdownMenuRadioItem>)}
            </DropdownMenuRadioGroup>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <DropdownMenu open={configMenuOpen === "approval"} onOpenChange={(open) => onConfigMenuOpenChange("approval", open)}>
        <DropdownMenuTrigger render={<Button aria-label={t("approval.select", { defaultValue: "Select approval mode" })} className={cn(variant === "linear" ? textTriggerClass : "flex max-w-[6.75rem] items-center gap-1 rounded-full px-2 py-1", approvalMode === "full_access" && "text-amber-600 dark:text-amber-300")} title={approvalHint} size="sm" type="button" variant="ghost" />}>
          <span className="truncate">{approvalLabel}</span><ChevronDownIcon aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-60" side="top" sideOffset={8}>
          <DropdownMenuGroup>
            <DropdownMenuLabel>{t("approval.menuTitle", { defaultValue: "Approval" })}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuRadioGroup value={approvalMode} onValueChange={(value) => { onSelectApproval(value as AssistantApprovalMode); onConfigMenuOpenChange("approval", false); }}>
              {APPROVAL_MODES.map((mode) => <DropdownMenuRadioItem key={mode} value={mode}>{t(`approval.options.${mode}`, { defaultValue: mode })}</DropdownMenuRadioItem>)}
            </DropdownMenuRadioGroup>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      </> : null}
    </>
  );
}

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
  composerAttachments: ComposerAttachment[];
}

const REASONING_OPTIONS: AssistantReasoningEffort[] = [
  "low",
  "medium",
  "high",
  "extra",
  "max",
];
const APPROVAL_MODES: AssistantApprovalMode[] = [
  "request_approval",
  "risky_only",
  "full_access",
  "custom",
];

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

function getAttachmentPreviewTone(
  name: string,
  kind: ComposerAttachmentKind | ChatMessageAttachment["kind"],
) {
  const ext = getFileExtension(name);
  if (kind === "image")
    return { label: ext === "FILE" ? "IMG" : ext, tone: "image" as const };
  if (ext === "PDF") return { label: "PDF", tone: "pdf" as const };
  if (["DOC", "DOCX", "WPS"].includes(ext))
    return { label: ext, tone: "doc" as const };
  if (["XLS", "XLSX", "CSV"].includes(ext))
    return { label: ext, tone: "sheet" as const };
  return { label: ext, tone: "file" as const };
}

function useObjectUrl(file: File | undefined, enabled: boolean) {
  const [url, setUrl] = useState<string | undefined>();

  useEffect(() => {
    if (
      !file ||
      !enabled ||
      typeof URL === "undefined" ||
      typeof URL.createObjectURL !== "function"
    ) {
      setUrl(undefined);
      return;
    }
    const nextUrl = URL.createObjectURL(file);
    setUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [enabled, file]);

  return url;
}

async function ensureAssistantUploadBundle(
  projectId: string,
): Promise<BundleRead> {
  const bundles = await listBundles(projectId);
  const existing =
    bundles.find((bundle) => bundle.label === "AI uploads") ?? bundles[0];
  if (existing) return existing;
  return createBundle({
    project_id: projectId,
    label: "AI uploads",
    source_type: "upload",
  });
}

function buildOutgoingPrompt(
  content: string,
  attachments: ComposerAttachment[],
) {
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
  if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function")
    return undefined;
  return URL.createObjectURL(attachment.file);
}

function toMessageAttachments(
  attachments: ComposerAttachment[],
): ChatMessageAttachment[] {
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

function toRequestAttachments(
  attachments: ComposerAttachment[],
): AssistantRequestAttachment[] {
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

/** Keeps the composer aligned with the conversation column in every layout. */
function ComposerFrame({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={className}>{children}</div>;
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
        /\\(frac|sum|int|sqrt|alpha|beta|gamma|theta|pi|sin|cos|tan|lim|cdot|times|leq|geq|neq|infty|to)/.test(
          trimmed,
        ) || /[=<>]/.test(trimmed);
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

function AttachmentPreviewCard({
  name,
  kind,
  size,
  status,
  previewUrl,
  file,
  error,
  onRemove,
  onPreview,
}: {
  name: string;
  kind: ComposerAttachmentKind | ChatMessageAttachment["kind"];
  size: number;
  status?: ComposerAttachmentStatus | ChatMessageAttachment["status"];
  previewUrl?: string;
  file?: File;
  error?: string;
  onRemove?: () => void;
  onPreview?: (selection: AttachmentPreviewSelection) => void;
}) {
  const { t } = useTranslation("ai-assistant");
  const isImage = kind === "image";
  const [previewOpen, setPreviewOpen] = useState(false);
  const objectUrl = useObjectUrl(file, isImage && !previewUrl);
  const imageUrl = previewUrl ?? objectUrl;
  const fileUrl = useObjectUrl(file, previewOpen && !isImage);
  const { label, tone } = getAttachmentPreviewTone(name, kind);
  const statusLabel = status
    ? t(`attachments.status.${status}`, { defaultValue: status })
    : null;
  const iconTone = {
    image: "bg-emerald-500/12 text-emerald-500 border-emerald-500/20",
    pdf: "bg-red-500/12 text-red-500 border-red-500/20",
    doc: "bg-blue-500/12 text-blue-500 border-blue-500/20",
    sheet: "bg-amber-500/12 text-amber-500 border-amber-500/20",
    file: "bg-muted text-muted-foreground border-border",
  }[tone];

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => {
        if (onPreview) {
          onPreview({ name, kind, size, file, previewUrl: imageUrl });
          return;
        }
        setPreviewOpen(true);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          if (onPreview) onPreview({ name, kind, size, file, previewUrl: imageUrl });
          else setPreviewOpen(true);
        }
      }}
      className={cn(
        "group relative flex h-16 max-w-[13.5rem] shrink-0 cursor-pointer items-center gap-2 overflow-hidden rounded-2xl border px-2.5 text-xs shadow-[0_14px_40px_oklch(0_0_0/0.12)] backdrop-blur-xl transition hover:-translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
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
          <div
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border",
              iconTone,
            )}
          >
            {tone === "pdf" || tone === "doc" ? (
              <FileTextIcon className="h-5 w-5" />
            ) : (
              <FileIcon className="h-5 w-5" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-semibold tracking-[-0.01em]">
              {name}
            </div>
            <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span>{label}</span>
              <span className="h-0.5 w-0.5 rounded-full bg-current opacity-60" />
              <span>{formatFileSize(size)}</span>
            </div>
            {error ? (
              <div className="mt-0.5 truncate text-[10px] text-destructive" title={error}>
                {error}
              </div>
            ) : statusLabel && status !== "ready" && (
              <div className="mt-0.5 truncate text-[10px] text-muted-foreground">
                {statusLabel}
              </div>
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
          onClick={(event) => {
            event.stopPropagation();
            onRemove();
          }}
          className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-background/95 text-muted-foreground shadow-sm transition hover:bg-foreground hover:text-background"
        >
          <XIcon className="h-3 w-3" />
        </button>
      )}
      {isImage ? (
        <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
          <DialogContent
            className="max-w-[min(92vw,900px)] border-0 bg-black/90 p-2"
            onClick={(event) => event.stopPropagation()}
          >
            <DialogTitle className="sr-only">{name}</DialogTitle>
            <DialogDescription className="sr-only">Image preview</DialogDescription>
            {imageUrl ? (
              <img src={imageUrl} alt={name} className="max-h-[82vh] w-full object-contain" />
            ) : (
              <div className="flex min-h-48 items-center justify-center text-sm text-white/70">{name}</div>
            )}
          </DialogContent>
        </Dialog>
      ) : (
        <Sheet open={previewOpen} onOpenChange={setPreviewOpen}>
          <SheetContent
            side="right"
            className="w-full sm:max-w-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <SheetHeader>
              <SheetTitle className="truncate pr-8">{name}</SheetTitle>
              <SheetDescription>{formatFileSize(size)} · {statusLabel ?? label}</SheetDescription>
            </SheetHeader>
            <div className="min-h-0 flex-1 overflow-auto px-4 pb-6">
              {fileUrl && /\.pdf$/i.test(name) ? (
                <iframe title={name} src={fileUrl} className="h-[70vh] w-full rounded-md border" />
              ) : (
                <div className="rounded-md border bg-muted/30 p-4 text-sm leading-6 text-muted-foreground">
                  {statusLabel ?? "文件已预解析并在发送前暂存。"}
                </div>
              )}
            </div>
          </SheetContent>
        </Sheet>
      )}
    </div>
  );
}

function MessageBubble({
  msg,
  activityItems = [],
  onCancelWorkflow,
  onConfigureProvider,
  isStreaming = false,
  isThinking = false,
  sessionError = null,
}: {
  msg: ChatMessage;
  activityItems?: AssistantExecutionItem[];
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
  isStreaming?: boolean;
  isThinking?: boolean;
  sessionError?: string | null;
}) {
  const isUser = msg.role === "user";
  // Keep hook order identical for user and assistant messages. A stable empty
  // value also prevents transcript-derived memo dependencies from churning.
  const parts = msg.transcriptParts ?? EMPTY_TRANSCRIPT_PARTS;
  const hasTurnParts = parts.some((part) => part.kind === "turn");
  const hasNarrativePart = parts.some((part) => part.kind === "narrative" && part.text);
  const executionProjection = useMemo(
    () => projectExecutionItemsOntoTranscript(parts, activityItems),
    [activityItems, parts],
  );

  if (isUser) {
    const hasAttachments = Boolean(
      msg.attachments && msg.attachments.length > 0,
    );
    return (
      <FadeContent
        duration={260}
        threshold={0.02}
        className="flex animate-fade-in flex-col items-end gap-2"
      >
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
          <Message className="w-full max-w-[94%] justify-end sm:max-w-[88%]">
            <MessageContent
              className="rounded-[1.35rem] rounded-br-[0.55rem] border px-4 py-2.5 text-[14px] leading-7 shadow-[0_12px_32px_oklch(0_0_0/0.10)]"
              style={{
                background:
                  "color-mix(in oklch, var(--muted) 82%, var(--background) 18%)",
                color: "var(--foreground)",
                borderColor:
                  "color-mix(in oklch, var(--border) 58%, transparent)",
              }}
            >
              <div className="whitespace-pre-wrap break-words">
                {msg.content}
              </div>
            </MessageContent>
          </Message>
        )}
      </FadeContent>
    );
  }

  const renderNarrative = (text: string, key: string) =>
    text ? (
      <MessageContent
        key={key}
        markdown
        variant="assistant"
        className="bg-transparent p-0 text-[14px] leading-7 text-foreground [&_code]:break-words"
      >
        {normalizeAssistantMarkdown(text)}
      </MessageContent>
    ) : null;

  const thinkingDots = (
    <span
      className="inline-flex items-center gap-1.5 text-muted-foreground"
      data-testid="assistant-thinking-indicator"
    >
      <span
        className="h-1.5 w-1.5 animate-pulse rounded-full bg-current"
        style={{ animationDelay: "0ms" }}
      />
      <span
        className="h-1.5 w-1.5 animate-pulse rounded-full bg-current"
        style={{ animationDelay: "150ms" }}
      />
      <span
        className="h-1.5 w-1.5 animate-pulse rounded-full bg-current"
        style={{ animationDelay: "300ms" }}
      />
    </span>
  );

  if (!msg.content && activityItems.length === 0 && !isStreaming && !sessionError) {
    return null;
  }

  return (
    <Message className="w-full max-w-full animate-fade-in flex-col items-start gap-2 sm:max-w-[92%]">
      <div className="w-full space-y-3 px-1 py-1 text-[14px] leading-7 break-words text-foreground">
        {hasTurnParts ? (
          <>
            {parts.map((part) => {
              if (part.kind === "narrative") {
                return renderNarrative(part.text, part.id);
              }
              if (part.kind === "reasoning") {
                return renderNarrative(part.text, part.id);
              }
              const items = executionProjection.itemsByPartId.get(part.id) ?? [];
              if (items.length === 0) return null;
              return (
                <ClaudeActivityTimeline
                  key={part.id}
                  items={items}
                  onCancelWorkflow={onCancelWorkflow}
                  onConfigureProvider={onConfigureProvider}
                />
              );
            })}
            {executionProjection.orphanItems.length > 0 && (
              <ClaudeActivityTimeline
                items={executionProjection.orphanItems}
                onCancelWorkflow={onCancelWorkflow}
                onConfigureProvider={onConfigureProvider}
              />
            )}
            {msg.content && !hasNarrativePart && renderNarrative(msg.content, `${msg.id}-durable`)}
            {activityItems.length === 0 && isStreaming && isThinking && thinkingDots}
          </>
        ) : (
          <>
            {activityItems.length > 0 && (
              <ClaudeActivityTimeline
                items={activityItems}
                onCancelWorkflow={onCancelWorkflow}
                onConfigureProvider={onConfigureProvider}
              />
            )}
            {msg.content ? (
              <MessageContent
                markdown
                variant="assistant"
                className="bg-transparent p-0 text-[14px] leading-7 text-foreground [&_code]:break-words"
              >
                {normalizeAssistantMarkdown(msg.content)}
              </MessageContent>
            ) : isStreaming && isThinking ? (
              thinkingDots
            ) : null}
          </>
        )}
      </div>
      {sessionError && <p className="cr-session-error" role="alert">{sessionError}</p>}
    </Message>
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
  docked = false,
  isCurrentConversationRunning = false,
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
  docked?: boolean;
  isCurrentConversationRunning?: boolean;
}) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter((c) =>
      (c.title || "").toLowerCase().includes(q),
    );
  }, [conversations, searchQuery]);

  const groups = useMemo(() => groupConversations(filtered), [filtered]);
  const groupLabels: Record<string, string> = {
    today: t("history.today"),
    yesterday: t("history.yesterday"),
    thisWeek: t("history.thisWeek"),
    earlier: t("history.earlier"),
  };

  return (
    <div
      data-testid={
        docked ? "assistant-history-rail" : "assistant-history-drawer"
      }
      className={cn(
        "flex h-full shrink-0 flex-col border-r bg-background",
        docked
          ? "w-[17rem] border-border/70 shadow-none max-lg:hidden"
          : "w-[min(20rem,calc(100vw-1.25rem))] shadow-[20px_0_48px_oklch(0_0_0/0.16)]",
      )}
      style={{ borderColor: "var(--border)" }}
    >
      {/* Header */}
      <div
        className="flex shrink-0 flex-col gap-2.5 border-b px-3 py-3"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <span className="text-[11px] font-semibold text-foreground">
              {t("panel.history")}
            </span>
            <p className="mt-0.5 text-[10px] text-muted-foreground">
              {t("panel.historySubtitle")}
            </p>
          </div>
          {!docked && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onClose}
              title={t("panel.closeHistory")}
            >
              <PanelRightCloseIcon className="size-3" />
            </Button>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          className="h-8 w-full justify-start gap-2 rounded-md border-border/80 bg-transparent px-2.5 text-xs font-medium shadow-none hover:bg-muted/70"
          onClick={onNew}
        >
          <PlusIcon className="size-3.5" />
          {t("panel.newConversation")}
        </Button>
      </div>

      {/* Search */}
      <div className="shrink-0 px-3 pb-2 pt-2.5">
        <div className="relative">
          <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={t("history.searchPlaceholder")}
            className="h-8 rounded-md border-border/70 bg-muted/35 pl-8 text-xs shadow-none placeholder:text-muted-foreground/70 focus-visible:border-ring/70 focus-visible:ring-2 focus-visible:ring-ring/15"
          />
        </div>
      </div>

      {/* Conversation list */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="flex flex-col gap-4 px-2 py-2">
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
                  <p className="mb-1 px-2 text-[10px] font-medium tracking-wide text-muted-foreground/70">
                    {groupLabels[key]}
                  </p>
                  <div className="space-y-0.5">
                    {items.map((conversation) => {
                      const active = conversation.id === currentId;
                      const isRunning = active && isCurrentConversationRunning;
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
                            "group relative min-h-11 cursor-pointer rounded-md px-2.5 py-2 text-left transition-colors",
                            active
                              ? "bg-muted text-foreground shadow-[inset_0_0_0_1px_oklch(0_0_0/0.035)]"
                              : "text-foreground/85 hover:bg-muted/65",
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
                              aria-label={t("history.rename", {
                                defaultValue: "Rename conversation",
                              })}
                              value={editingTitle}
                              onChange={(e) =>
                                onEditTitleChange(e.target.value)
                              }
                              onClick={(e) => e.stopPropagation()}
                              onDoubleClick={(e) => e.stopPropagation()}
                              onBlur={onCommitRename}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  e.preventDefault();
                                  onCommitRename();
                                }
                                if (e.key === "Escape") {
                                  e.preventDefault();
                                  onCancelRename();
                                }
                              }}
                              className="w-full rounded border bg-background px-1.5 py-0.5 text-xs font-medium outline-none"
                              style={{ borderColor: "var(--border)" }}
                              disabled={!!renamingId}
                            />
                          ) : (
                            <>
                              <div className="flex min-w-0 items-center gap-1.5 pr-12">
                                <div
                                  className="min-w-0 truncate text-[13px] font-medium leading-5"
                                  onDoubleClick={(e) => {
                                    e.stopPropagation();
                                    onRename(conversation.id, conversation.title);
                                  }}
                                >
                                  {conversation.title ||
                                    t("panel.untitledConversation")}
                                </div>
                                {isRunning && (
                                  <Loader2Icon
                                    data-testid="conversation-running-indicator"
                                    aria-label={t("history.running")}
                                    className="size-3 shrink-0 animate-spin text-muted-foreground"
                                  />
                                )}
                              </div>
                              <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
                                {isRunning ? (
                                  <span>{t("history.running")}</span>
                                ) : conversation.created_at ? (
                                  <span>
                                    {new Date(
                                      conversation.created_at,
                                    ).toLocaleDateString()}
                                  </span>
                                ) : null}
                              </div>
                              <button
                                className={cn(
                                  "absolute right-7 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground/50 transition-all hover:bg-background hover:text-foreground",
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
                                  "absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground/40 transition-all hover:bg-destructive/10 hover:text-destructive",
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

export function AIAssistantPanel({
  variant = "panel",
  onPreviewAttachment,
}: {
  variant?: "panel" | "workspace" | "linear-agent";
  onPreviewAttachment?: (selection: AttachmentPreviewSelection) => void;
}) {
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
    cancelWorkflow,
    stopAssistantResponse,
  } = useAIAssistant();
  const { t } = useTranslation("ai-assistant");
  const isWorkspace = variant === "workspace";
  const isLinearAgent = variant === "linear-agent";
  const [input, setInput] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  useEffect(() => {
    if (isWorkspace) {
      setHistoryOpen(false);
      void refreshConversations();
    }
  }, [isWorkspace, refreshConversations]);
  const [historySearch, setHistorySearch] = useState("");
  const [editingConversationId, setEditingConversationId] = useState<
    string | null
  >(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [renamingConversationId, setRenamingConversationId] = useState<
    string | null
  >(null);
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  const [configMenuOpen, setConfigMenuOpen] = useState<ConfigMenu>(null);
  const [attachments, setAttachments] = useState<ComposerAttachment[]>([]);
  const [queuedPrompts, setQueuedPrompts] = useState<QueuedPrompt[]>([]);
  const [providerConfigs, setProviderConfigs] = useState<ProviderConfig[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const focusComposer = useCallback(() => {
    if (typeof document === "undefined") return;
    const el =
      inputRef.current ||
      (document.querySelector(
        '[aria-label="' + t("inputPlaceholder") + '"]',
      ) as HTMLTextAreaElement | null);
    el?.focus();
  }, [t]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const queueDrainingRef = useRef(false);
  const isBusy = isAssistantBusy(state.status);
  const isStreaming = state.isStreaming;
  const isUploadingAttachments = attachments.some(
    (attachment) => attachment.status === "uploading",
  );
  const hasFailedAttachments = attachments.some(
    (attachment) => attachment.status === "failed",
  );
  const canSend =
    Boolean(input.trim() || attachments.length > 0) &&
    !isUploadingAttachments &&
    !hasFailedAttachments;
  const selectedProvider = useMemo(
    () =>
      providerConfigs.find(
        (provider) => provider.id === state.selectedProviderConfigId,
      ) ?? null,
    [providerConfigs, state.selectedProviderConfigId],
  );
  const openProviderSettings = useCallback(() => {
    close();
    window.history.pushState({}, "", "/settings/providers");
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, [close]);
  const modelLabel =
    selectedProvider?.model ??
    t("model.platformDefault", { defaultValue: "Platform default" });
  const reasoningLabel = t(`reasoning.options.${state.reasoningEffort}`, {
    defaultValue: state.reasoningEffort,
  });
  const approvalLabel = t(`approval.options.${state.approvalMode}`, {
    defaultValue: state.approvalMode,
  });
  const approvalHint = t(`approval.hints.${state.approvalMode}`, {
    defaultValue: "",
  });
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
  const latestAssistantMessageId = useMemo(
    () => [...state.messages].reverse().find((message) => message.role === "assistant")?.id ?? null,
    [state.messages],
  );
  const currentConversationIsRunning =
    isBusy && Boolean(state.currentConversationId);

  const resizeComposer = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 112)}px`;
  }, []);

  useEffect(() => {
    resizeComposer();
  }, [attachments.length, input, resizeComposer]);

  useEffect(() => {
    const shouldLoadProviderConfigs =
      isLinearAgent || (state.isOpen && state.mode === "panel");
    if (!shouldLoadProviderConfigs) return;
    const timeoutId = window.setTimeout(focusComposer, 150);
    return () => window.clearTimeout(timeoutId);
  }, [focusComposer, isLinearAgent, state.isOpen, state.mode]);

  useEffect(() => {
    if (!state.isOpen || state.mode !== "panel") return;
    let cancelled = false;
    void listProviderConfigs()
      .then((result) => {
        if (cancelled) return;
        setProviderConfigs(result.data);
        if (
          state.selectedProviderConfigId &&
          !result.data.some(
            (provider) => provider.id === state.selectedProviderConfigId,
          )
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
  }, [
    isLinearAgent,
    setSelectedProviderConfig,
    state.isOpen,
    state.mode,
    state.selectedProviderConfigId,
  ]);

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

  const uploadAttachmentRecords = useCallback(
    async (records: ComposerAttachment[], projectId?: string) => {
      let bundlePromise: Promise<BundleRead> | null = projectId
        ? ensureAssistantUploadBundle(projectId)
        : null;
      let targetBundle: BundleRead | null = null;
      let uploadedProjectDocuments = 0;
      for (const record of records) {
        let assistantAttachmentId: string | undefined;
        try {
          const assistantAttachment = await uploadAssistantAttachment(
            record.file,
            record.kind,
          );
          assistantAttachmentId = assistantAttachment.id;
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
          const message =
            error instanceof Error ? error.message : "Attachment upload failed";
          setAttachments((current) =>
            current.map((attachment) =>
              attachment.id === record.id
                ? {
                    ...attachment,
                    status: "failed",
                    extractionStatus: "failed",
                    error: message,
                  }
                : attachment,
            ),
          );
          continue;
        }

        if (!bundlePromise) continue;

        try {
          const bundle = await bundlePromise;
          targetBundle = bundle;
          const document = await uploadDocument(
            bundle.id,
            record.file,
            undefined,
            assistantAttachmentId,
            true,
          );
          uploadedProjectDocuments += 1;
          setAttachments((current) =>
            current.map((attachment) =>
              attachment.id === record.id
                ? { ...attachment, documentId: document.id }
                : attachment,
            ),
          );
        } catch (error) {
          const message =
            error instanceof Error ? error.message : "Upload failed";
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
      if (targetBundle && uploadedProjectDocuments > 0) {
        try {
          await reingestBundle(targetBundle.id);
        } catch (error) {
          const message = error instanceof Error ? error.message : "Attachment parsing could not start";
          setAttachments((current) =>
            current.map((attachment) =>
              attachment.documentId
                ? { ...attachment, error: attachment.error ?? message }
                : attachment,
            ),
          );
        }
      }
    },
    [],
  );

  const handleAttachmentInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>, kind: ComposerAttachmentKind) => {
      const files = Array.from(event.currentTarget.files ?? []);
      event.currentTarget.value = "";
      if (files.length === 0) return;

      const projectId = state.currentContext.projectId;
      const records = files.map(
        (file, index) =>
          ({
            id: createAttachmentId(file, index),
            file,
            kind,
            status: "uploading",
          }) satisfies ComposerAttachment,
      );

      setAttachmentMenuOpen(false);
      setConfigMenuOpen(null);
      setHistoryOpen(false);
      setAttachments((current) => [...current, ...records]);
      void uploadAttachmentRecords(records, projectId);
    },
    [state.currentContext.projectId, uploadAttachmentRecords],
  );

  const handleRemoveAttachment = useCallback((id: string) => {
    setAttachments((current) =>
      current.filter((attachment) => attachment.id !== id),
    );
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
    focusComposer();
  }, [focusComposer, t]);

  const handleSend = useCallback(() => {
    const trimmedInput = input.trim();
    if (attachments.some((attachment) => attachment.status !== "uploaded")) return;
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
      composerAttachments: attachments,
    };

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
      approvalMode: state.approvalMode,
    });
  }, [
    attachments,
    input,
    isBusy,
    isUploadingAttachments,
    sendMessage,
    state.reasoningEffort,
    state.approvalMode,
    state.selectedProviderConfigId,
    t,
  ]);

  const handleEditQueuedPrompt = useCallback((id: string) => {
    setQueuedPrompts((current) => {
      const queued = current.find((item) => item.id === id);
      if (!queued) return current;
      setInput(queued.prompt);
      setAttachments(queued.composerAttachments);
      requestAnimationFrame(() => {
        resizeComposer();
        inputRef.current?.focus();
      });
      return current.filter((item) => item.id !== id);
    });
  }, [resizeComposer]);

  const handleCancelQueuedPrompt = useCallback((id: string) => {
    setQueuedPrompts((current) => current.filter((item) => item.id !== id));
  }, []);

  const handlePrioritizeQueuedPrompt = useCallback((id: string) => {
    setQueuedPrompts((current) => {
      const index = current.findIndex((item) => item.id === id);
      if (index <= 0) return current;
      const next = [...current];
      const [queued] = next.splice(index, 1);
      next.unshift(queued);
      return next;
    });
  }, []);

  useEffect(() => {
    if (
      queueDrainingRef.current ||
      isAssistantBusy(state.status) ||
      queuedPrompts.length === 0
    )
      return;

    const nextPrompt = queuedPrompts[0];
    queueDrainingRef.current = true;
    setQueuedPrompts((current) => current.slice(1));
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

  const handleQuickAction = useCallback(
    (text: string) => {
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
            composerAttachments: [],
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
    [
      isBusy,
      sendMessage,
      state.approvalMode,
      state.reasoningEffort,
      state.selectedProviderConfigId,
    ],
  );

  const beginRenameConversation = useCallback(
    (id: string, title: string | null) => {
      setAttachmentMenuOpen(false);
      setConfigMenuOpen(null);
      setEditingConversationId(id);
      setEditingTitle(title || "");
    },
    [],
  );

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
      updateConversationTitle(editingConversationId, normalizedTitle);
      void refreshConversations();
    } catch (error) {
      console.error("Failed to rename conversation:", error);
    } finally {
      setRenamingConversationId(null);
      cancelRenameConversation();
    }
  }, [
    cancelRenameConversation,
    editingConversationId,
    editingTitle,
    refreshConversations,
    updateConversationTitle,
  ]);

  const startConversationOnSurface = useCallback(() => {
    startNewConversation();
    setHistoryOpen(false);
  }, [startNewConversation]);

  const loadConversationOnSurface = useCallback(
    async (conversationId: string) => {
      await loadConversation(conversationId);
      setHistoryOpen(false);
    },
    [loadConversation],
  );

  const handleDeleteConversation = useCallback(
    async (id: string) => {
      try {
        await deleteChatConversation(id);
        if (state.currentConversationId === id) {
          startConversationOnSurface();
        }
        await refreshConversations();
      } catch (error) {
        console.error("Failed to delete conversation:", error);
      }
    },
    [
      refreshConversations,
      startConversationOnSurface,
      state.currentConversationId,
    ],
  );

  if (!isWorkspace && !isLinearAgent && (!state.isOpen || state.mode !== "panel")) return null;

  if (isLinearAgent) {
    const handleAttachmentMenuOpenChange = (open: boolean) => {
      setConfigMenuOpen(null);
      setAttachmentMenuOpen(open);
    };
    const handleConfigMenuOpenChange = (menu: Exclude<ConfigMenu, null>, open: boolean) => {
      setAttachmentMenuOpen(false);
      setConfigMenuOpen(open ? menu : null);
    };

    return (
      <div className="bp-linear-agent-composer" data-testid="linear-agent-composer">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="sr-only"
          onChange={(event) => handleAttachmentInputChange(event, "file")}
        />
        <input
          ref={imageInputRef}
          type="file"
          multiple
          accept="image/*"
          className="sr-only"
          onChange={(event) => handleAttachmentInputChange(event, "image")}
        />
        {attachments.length > 0 && (
          <div className="bp-linear-agent-attachments" aria-label="Attachments">
            {attachments.map((attachment) => (
              <AttachmentPreviewCard
                key={attachment.id}
                name={attachment.file.name}
                kind={attachment.kind}
                size={attachment.file.size}
                status={attachment.status}
                file={attachment.file}
                error={attachment.error}
                onPreview={isLinearAgent ? onPreviewAttachment : undefined}
                onRemove={() => handleRemoveAttachment(attachment.id)}
              />
            ))}
          </div>
        )}
        {queuedPrompts.length > 0 && (
          <section className="bp-linear-agent-queue" aria-label="待发送队列">
            <header>
              <span>待发送</span>
              <small>{queuedPrompts.length}</small>
            </header>
            <ol>
              {queuedPrompts.map((queued, index) => (
                <li key={queued.id}>
                  <span className="bp-linear-agent-queue-order" aria-hidden="true">{index + 1}</span>
                  <button
                    type="button"
                    className="bp-linear-agent-queue-copy"
                    onClick={() => handleEditQueuedPrompt(queued.id)}
                    title="编辑待发送消息"
                  >
                    {queued.displayContent}
                  </button>
                  <div className="bp-linear-agent-queue-actions">
                    {index > 0 && (
                      <button type="button" onClick={() => handlePrioritizeQueuedPrompt(queued.id)} title="移到队列最前" aria-label="移到队列最前">
                        <ArrowUpIcon size={14} />
                      </button>
                    )}
                    <button type="button" onClick={() => handleEditQueuedPrompt(queued.id)} title="编辑待发送消息" aria-label="编辑待发送消息">
                      <PencilIcon size={13} />
                    </button>
                    <button type="button" onClick={() => handleCancelQueuedPrompt(queued.id)} title="取消待发送消息" aria-label="取消待发送消息">
                      <XIcon size={14} />
                    </button>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        )}
        <Textarea
          ref={inputRef}
          value={input}
          rows={1}
          aria-label={t("inputPlaceholder")}
          placeholder={t("inputPlaceholder", { defaultValue: "Ask BidPilot..." })}
          onChange={(event) => {
            setInput(event.target.value);
            requestAnimationFrame(resizeComposer);
          }}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || event.shiftKey) return;
            event.preventDefault();
            if (isStreaming) stopAssistantResponse();
            else handleSend();
          }}
          className="bp-linear-agent-textarea focus-visible:ring-0 focus-visible:ring-offset-0"
        />
        <div className="bp-linear-agent-composer-footer">
          <div className="bp-linear-agent-composer-left">
            <AssistantComposerMenus
              variant="linear"
              showConfig={false}
              attachmentMenuOpen={attachmentMenuOpen}
              configMenuOpen={configMenuOpen}
              modelLabel={modelLabel}
              reasoningLabel={reasoningLabel}
              approvalLabel={approvalLabel}
              approvalHint={approvalHint}
              providerConfigs={providerConfigs}
              selectedProviderConfigId={state.selectedProviderConfigId}
              reasoningEffort={state.reasoningEffort}
              approvalMode={state.approvalMode}
              onAttachmentMenuOpenChange={handleAttachmentMenuOpenChange}
              onConfigMenuOpenChange={handleConfigMenuOpenChange}
              onSelectProvider={setSelectedProviderConfig}
              onSelectReasoning={setReasoningEffort}
              onSelectApproval={setApprovalMode}
              onUploadFile={() => fileInputRef.current?.click()}
              onUploadImage={() => imageInputRef.current?.click()}
              onAddFromProject={handleAddFromProject}
            />
            <span className="bp-linear-agent-keyhint"><CornerDownLeftIcon size={13} /> {isBusy ? "Enter to queue" : "Enter to send"}</span>
          </div>
          <div className="bp-linear-agent-composer-right">
            <AssistantComposerMenus
              variant="linear"
              showAttachment={false}
              attachmentMenuOpen={attachmentMenuOpen}
              configMenuOpen={configMenuOpen}
              modelLabel={modelLabel}
              reasoningLabel={reasoningLabel}
              approvalLabel={approvalLabel}
              approvalHint={approvalHint}
              providerConfigs={providerConfigs}
              selectedProviderConfigId={state.selectedProviderConfigId}
              reasoningEffort={state.reasoningEffort}
              approvalMode={state.approvalMode}
              onAttachmentMenuOpenChange={handleAttachmentMenuOpenChange}
              onConfigMenuOpenChange={handleConfigMenuOpenChange}
              onSelectProvider={setSelectedProviderConfig}
              onSelectReasoning={setReasoningEffort}
              onSelectApproval={setApprovalMode}
              onUploadFile={() => fileInputRef.current?.click()}
              onUploadImage={() => imageInputRef.current?.click()}
              onAddFromProject={handleAddFromProject}
            />
            <Button
              type="button"
              className="bp-linear-agent-send"
              onClick={isStreaming ? stopAssistantResponse : handleSend}
              disabled={isStreaming ? false : !canSend}
              aria-label={isStreaming ? t("actions.stopGenerating") : t("actions.send")}
              size="icon-sm"
              variant="ghost"
            >
              {isStreaming ? <SquareIcon aria-hidden="true" fill="currentColor" /> : isUploadingAttachments ? <Loader2Icon aria-hidden="true" className="animate-spin" /> : <SendIcon aria-hidden="true" />}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden",
        isWorkspace
          ? "relative h-full min-h-0 w-full min-w-0 flex-1 flex-col bg-background"
          : "fixed inset-0 z-40 h-[100dvh] w-full animate-slide-in border-l bg-background sm:left-auto sm:w-[min(100vw,390px)] md:w-[500px] xl:w-[560px]",
      )}
      style={
        isWorkspace
          ? undefined
          : {
              borderColor: "var(--border)",
              boxShadow: "-20px 0 48px oklch(0 0 0 / 0.18)",
            }
      }
    >
      {/* Compact chat header — no page marketing chrome */}
      <div
        data-testid="assistant-panel-header"
        className={cn(
          "flex shrink-0 items-center justify-between gap-2 border-b px-3",
          isWorkspace ? "h-12" : "min-h-14 px-3.5",
        )}
        style={{
          borderColor: "var(--border)",
          background: "var(--background)",
        }}
      >
        <div className="flex min-w-0 items-center gap-2">
          <Button
            data-testid="assistant-history-toggle"
            variant="ghost"
            size="icon-sm"
            className={cn(
              "text-muted-foreground",
              historyOpen && "bg-muted text-foreground",
              isWorkspace && "lg:hidden",
            )}
            onClick={() => {
              setAttachmentMenuOpen(false);
              setConfigMenuOpen(null);
              setHistoryOpen((v) => !v);
            }}
            title={t("panel.history")}
          >
            <HistoryIcon className="size-4" />
          </Button>
          <AgentMark
            decorative
            className={cn(isWorkspace ? "size-7" : "size-8")}
          />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-foreground">
              {state.currentConversationId
                ? (Array.isArray(state.conversations)
                    ? state.conversations.find(
                        (item) => item.id === state.currentConversationId,
                      )?.title
                    : null) || t("panel.untitledConversation")
                : t("title")}
            </div>
            {!isWorkspace && (
              <div className="truncate text-[11px] text-muted-foreground">
                {state.status === "idle"
                  ? t("status.ready", { defaultValue: "Ready" })
                  : t(`status.${state.status}`, {
                      defaultValue: t("thinking"),
                    })}
              </div>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          {isWorkspace ? (
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-muted-foreground lg:hidden"
              onClick={startConversationOnSurface}
              title={t("panel.newConversation")}
            >
              <PlusIcon className="size-4" />
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-muted-foreground"
              onClick={startConversationOnSurface}
              title={t("panel.newConversation")}
            >
              <PlusIcon className="size-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-sm"
            className="text-muted-foreground"
            onClick={() => toggle("command")}
            title={t("panel.openCommand")}
          >
            <CommandIcon className="size-4" />
          </Button>
          {!isWorkspace && (
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-muted-foreground"
              onClick={close}
              title={t("panel.close")}
            >
              <PanelRightCloseIcon className="size-4" />
            </Button>
          )}
        </div>
      </div>

      {/* The conversation pane owns both scrolling messages and the composer. */}
      <div
        data-testid="assistant-panel-body"
        className={cn(
          "relative flex min-h-0 flex-1 overflow-hidden",
          isWorkspace ? "flex-row" : "flex-col",
        )}
      >
        {isWorkspace && (
          <HistorySidebar
            conversations={
              Array.isArray(state.conversations) ? state.conversations : []
            }
            currentId={state.currentConversationId}
            searchQuery={historySearch}
            onSearchChange={setHistorySearch}
            onSelect={loadConversationOnSurface}
            onNew={startConversationOnSurface}
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
            docked
            isCurrentConversationRunning={currentConversationIsRunning}
          />
        )}

        {historyOpen && (
          <>
            <button
              aria-label={t("panel.closeHistory")}
              className={cn(
                "absolute inset-0 z-10 bg-black/20 backdrop-blur-[1px]",
                isWorkspace && "lg:hidden",
              )}
              onClick={() => setHistoryOpen(false)}
            />
            <div
              className={cn(
                "absolute inset-y-0 left-0 z-20 max-w-full",
                isWorkspace && "lg:hidden",
              )}
            >
              <HistorySidebar
                conversations={
                  Array.isArray(state.conversations) ? state.conversations : []
                }
                currentId={state.currentConversationId}
                searchQuery={historySearch}
                onSearchChange={setHistorySearch}
                onSelect={loadConversationOnSurface}
                onNew={startConversationOnSurface}
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
                isCurrentConversationRunning={currentConversationIsRunning}
              />
            </div>
          </>
        )}

        <div
          data-testid="assistant-conversation-pane"
          className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background"
        >
          <div
            data-testid="assistant-message-pane"
            className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden"
          >
            <ChatContainerRoot className="relative min-h-0 flex-1">
              <ChatContainerContent
                className={cn(
                  "gap-3 px-3 py-3 sm:px-4 sm:py-4",
                  isWorkspace && "mx-auto w-full max-w-4xl px-4 py-5 sm:px-6",
                )}
              >
                {state.messages.length === 0 ? (
                  <div className="flex flex-1 flex-col items-center justify-center py-10 text-center">
                    <AgentMark
                      decorative
                      className="mx-auto mb-4 size-14 shadow-sm"
                    />
                    <h3 className="mb-1 text-base font-semibold text-foreground">
                      {t("welcome.title")}
                    </h3>
                    <p className="mb-6 max-w-[28ch] text-sm leading-6 text-muted-foreground">
                      {t("welcome.description")}
                    </p>
                    <QuickActions onSelect={handleQuickAction} />
                  </div>
                ) : (
                  <>
                    {state.messages.map((msg) => {
                      const turnItems =
                        executionItemsByMessageId.get(msg.id) ?? [];
                      const pendingConfirmation =
                        state.pendingConfirmation?.messageId === msg.id
                          ? state.pendingConfirmation
                          : null;

                      return (
                        <div key={msg.id} className="flex flex-col gap-2">
                          {msg.role === "assistant" && pendingConfirmation && (
                            <AssistantConfirmationCard
                              confirmation={pendingConfirmation}
                              onConfirm={(confirmationText) =>
                                void confirmAssistantAction(
                                  true,
                                  confirmationText,
                                )
                              }
                              onCancel={() =>
                                void confirmAssistantAction(false)
                              }
                            />
                          )}
                          <MessageBubble
                            msg={msg}
                            activityItems={
                              msg.role === "assistant" ? turnItems : []
                            }
                            onCancelWorkflow={
                              msg.role === "assistant"
                                ? cancelWorkflow
                                : undefined
                            }
                            onConfigureProvider={
                              msg.role === "assistant"
                                ? openProviderSettings
                                : undefined
                            }
                            isStreaming={
                              state.isStreaming &&
                              state.activeAssistantMessageId === msg.id
                            }
                            isThinking={
                              state.isThinking &&
                              state.activeAssistantMessageId === msg.id
                            }
                            sessionError={
                              (state.activeAssistantMessageId ?? latestAssistantMessageId) === msg.id
                                ? state.sessionError
                                : null
                            }
                          />
                        </div>
                      );
                    })}
                    {unassignedExecutionItems.length > 0 && (
                      <ClaudeActivityTimeline
                        items={unassignedExecutionItems}
                        onCancelWorkflow={cancelWorkflow}
                        onConfigureProvider={openProviderSettings}
                      />
                    )}
                    {state.pendingConfirmation &&
                      !state.pendingConfirmation.messageId && (
                        <AssistantConfirmationCard
                          confirmation={state.pendingConfirmation}
                          onConfirm={(confirmationText) =>
                            void confirmAssistantAction(true, confirmationText)
                          }
                          onCancel={() => void confirmAssistantAction(false)}
                        />
                      )}
                    {state.pendingInput && (
                      <AssistantInputRequestForm
                        request={state.pendingInput}
                        onSubmit={(content) => void sendMessage(content, { displayContent: content })}
                      />
                    )}
                    <ChatContainerScrollAnchor />
                  </>
                )}
              </ChatContainerContent>
              {!historyOpen && state.messages.length > 0 && (
                <div className="pointer-events-none absolute inset-x-0 bottom-3 z-10 flex justify-center">
                  <ScrollButton
                    aria-label={t("panel.scrollToBottom", {
                      defaultValue: "Scroll to bottom",
                    })}
                    className="pointer-events-auto size-9 border bg-background/95 text-muted-foreground shadow-sm backdrop-blur hover:text-foreground"
                    size="icon"
                    variant="outline"
                  />
                </div>
              )}
            </ChatContainerRoot>
          </div>

          {/* ─── Input ─── */}
          <div
            data-testid="assistant-composer"
            className={cn(
              "shrink-0 border-t bg-background px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3",
              isWorkspace ? "px-4 sm:px-6" : "sm:px-3",
            )}
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
            <ComposerFrame
              className={cn("w-full", isWorkspace && "mx-auto max-w-4xl")}
            >
              <div className="rounded-xl border bg-card px-2 py-2 shadow-sm transition-colors focus-within:border-muted-foreground/35">
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
                        error={attachment.error}
                        onRemove={() => handleRemoveAttachment(attachment.id)}
                      />
                    ))}
                    {queuedPrompts.map((queued) => (
                      <div
                        key={queued.id}
                        className="flex h-16 w-[min(13.5rem,72vw)] shrink-0 items-center gap-2 rounded-2xl border px-2.5 text-xs"
                        style={{
                          background:
                            "color-mix(in oklch, var(--background) 88%, transparent)",
                          borderColor:
                            "color-mix(in oklch, var(--border) 72%, transparent)",
                          color: "var(--muted-foreground)",
                        }}
                      >
                        <Loader2Icon className="h-4 w-4 shrink-0 animate-spin" />
                        <span className="min-w-0 truncate">
                          {t("panel.queuedPrompt", { defaultValue: "Queued" })}:{" "}
                          {queued.displayContent}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex min-h-10 items-center gap-1.5">
                  <DropdownMenu
                    open={attachmentMenuOpen}
                    onOpenChange={(open) => {
                      setHistoryOpen(false);
                      setConfigMenuOpen(null);
                      setAttachmentMenuOpen(open);
                    }}
                  >
                    <DropdownMenuTrigger render={<Button aria-label={t("attachments.add", { defaultValue: "Add attachment" })} className="flex size-8 items-center justify-center rounded-full text-muted-foreground" size="icon-sm" type="button" variant="ghost" />}>
                      <PlusIcon aria-hidden="true" />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-56" side="top" sideOffset={8}>
                      <DropdownMenuGroup>
                        <DropdownMenuLabel>{t("attachments.menuTitle", { defaultValue: "Add to this message" })}</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => fileInputRef.current?.click()}><FileIcon aria-hidden="true" />{t("attachments.uploadFile", { defaultValue: "Upload file" })}</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => imageInputRef.current?.click()}><ImageIcon aria-hidden="true" />{t("attachments.uploadImage", { defaultValue: "Upload image" })}</DropdownMenuItem>
                        <DropdownMenuItem onClick={handleAddFromProject}><FolderOpenIcon aria-hidden="true" />{t("attachments.addFromProject", { defaultValue: "Add from project" })}</DropdownMenuItem>
                      </DropdownMenuGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <PromptInput
                    value={input}
                    onValueChange={(value) => {
                      setInput(value);
                      requestAnimationFrame(resizeComposer);
                    }}
                    onSubmit={handleSend}
                    isLoading={isBusy || isUploadingAttachments}
                    className="min-w-0 flex-1 rounded-lg border-0 bg-transparent p-0 shadow-none"
                  >
                    <PromptInputTextarea
                      aria-label={t("inputPlaceholder")}
                      placeholder={t("inputPlaceholder")}
                      className="min-h-8 max-h-28 min-w-0 flex-1 resize-none overflow-y-auto bg-transparent px-1 py-1.5 text-[16px] leading-6 text-foreground outline-none placeholder:text-muted-foreground sm:text-[14px]"
                    />
                    <PromptInputActions className="shrink-0">
                      <PromptInputAction
                        tooltip={
                          isStreaming
                            ? t("actions.stopGenerating")
                            : t("actions.send")
                        }
                      >
                        <Button
                          type="button"
                          onClick={isStreaming ? stopAssistantResponse : handleSend}
                          disabled={isStreaming ? false : !canSend}
                          aria-label={
                            isStreaming
                              ? t("actions.stopGenerating")
                              : t("actions.send")
                          }
                          className={cn(
                            "relative flex size-8 shrink-0 items-center justify-center rounded-full transition-all duration-200 disabled:opacity-35",
                            isStreaming
                              ? "bg-foreground text-background shadow-[0_8px_20px_oklch(0_0_0/0.2)] hover:scale-[1.03] active:scale-95"
                              : canSend
                              ? "bg-primary text-primary-foreground shadow-[0_10px_28px_oklch(0_0_0/0.18)] hover:scale-[1.03] active:scale-95"
                              : "text-muted-foreground",
                          )}
                          size="icon"
                          variant="ghost"
                        >
                          {isStreaming ? (
                            <>
                              <Loader2Icon className="absolute size-[1.15rem] animate-spin opacity-45" />
                              <SquareIcon className="relative size-2.5 fill-current" />
                            </>
                          ) : isUploadingAttachments ? (
                            <Loader2Icon className="h-4 w-4 animate-spin" />
                          ) : (
                            <SendIcon className="w-4 h-4" />
                          )}
                        </Button>
                      </PromptInputAction>
                    </PromptInputActions>
                  </PromptInput>
                </div>
                <div className="mt-1.5 flex min-h-5 items-center justify-between gap-2 px-1">
                  <span className="hidden items-center gap-1 text-[10px] text-muted-foreground min-[380px]:flex">
                    {isStreaming ? (
                      <>
                        <Loader2Icon className="size-3 animate-spin" />
                        {t("panel.running")}
                      </>
                    ) : (
                      <>
                        <CornerDownLeftIcon className="w-3 h-3" />{" "}
                        {isBusy
                      ? t("panel.enterToQueue", {
                          defaultValue: "Enter queues",
                        })
                      : t("panel.enterToSend")}
                      </>
                    )}
                  </span>
                  <div className="relative ml-auto flex min-w-0 items-center gap-1 text-[10px] text-muted-foreground">
                    <AssistantComposerMenus
                      variant="panel"
                      showAttachment={false}
                      attachmentMenuOpen={attachmentMenuOpen}
                      configMenuOpen={configMenuOpen}
                      modelLabel={modelLabel}
                      reasoningLabel={reasoningLabel}
                      approvalLabel={approvalLabel}
                      approvalHint={approvalHint}
                      providerConfigs={providerConfigs}
                      selectedProviderConfigId={state.selectedProviderConfigId}
                      reasoningEffort={state.reasoningEffort}
                      approvalMode={state.approvalMode}
                      onAttachmentMenuOpenChange={(open) => {
                        setAttachmentMenuOpen(open);
                        setConfigMenuOpen(null);
                      }}
                      onConfigMenuOpenChange={(menu, open) => {
                        setAttachmentMenuOpen(false);
                        setHistoryOpen(false);
                        setConfigMenuOpen(open ? menu : null);
                      }}
                      onSelectProvider={setSelectedProviderConfig}
                      onSelectReasoning={setReasoningEffort}
                      onSelectApproval={setApprovalMode}
                      onUploadFile={() => fileInputRef.current?.click()}
                      onUploadImage={() => imageInputRef.current?.click()}
                      onAddFromProject={handleAddFromProject}
                    />
                  </div>
                </div>
              </div>
            </ComposerFrame>
          </div>
        </div>
      </div>
    </div>
  );
}
