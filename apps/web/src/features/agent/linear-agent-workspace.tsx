import {
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  BotIcon,
  ChevronDownIcon,
  Clock3Icon,
  FileSearchIcon,
  FileTextIcon,
  MoreHorizontalIcon,
  PanelTopIcon,
  PencilIcon,
  PinIcon,
  StarIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  AIAssistantPanel,
  type AttachmentPreviewSelection,
} from "@/features/agent/components/AIAssistantPanel";
import { WorkflowCanvas } from "@/components/workflow-canvas";
import { ClaudeAgentThread } from "./claude-agent-thread";
import { useAIAssistant, type AIAssistantState } from "@/features/agent/state/agent-store";
import {
  deleteChatConversation,
  renameChatConversation,
  setChatConversationPinned,
  type ChatConversationRead,
} from "@/lib/api";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import "./linear-agent-workspace.css";

function AgentPreviewCanvas({
  selection,
  onClose,
  showHeader = true,
}: {
  selection: AttachmentPreviewSelection | null;
  onClose: () => void;
  showHeader?: boolean;
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [textPreview, setTextPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!selection?.file) {
      setObjectUrl(null);
      setTextPreview(null);
      return;
    }
    const url = URL.createObjectURL(selection.file);
    setObjectUrl(url);
    setTextPreview(null);
    const textLike = selection.file.type.startsWith("text/") || /\.(md|txt|json|csv|xml|html?)$/i.test(selection.name);
    if (textLike) {
      void selection.file.text().then((value) => setTextPreview(value.slice(0, 100_000)));
    }
    return () => URL.revokeObjectURL(url);
  }, [selection]);

  if (!selection) return null;
  const isPdf = selection.file?.type === "application/pdf" || /\.pdf$/i.test(selection.name);
  const isImage = selection.kind === "image";
  return (
    <aside className="agent-preview-canvas" aria-label="附件预览画布">
      {showHeader && (
        <header className="agent-preview-header">
          <div className="agent-preview-heading">
            <strong title={selection.name}>{selection.name}</strong>
            <span>{formatPreviewSize(selection.size)} · {isImage ? "图片" : "文件"}</span>
          </div>
          <button type="button" className="agent-preview-close" aria-label="关闭预览" onClick={onClose}><XIcon size={16} /></button>
        </header>
      )}
      <div className="agent-preview-body">
        {isImage && (selection.previewUrl || objectUrl) ? <img src={selection.previewUrl || objectUrl || undefined} alt={selection.name} /> : null}
        {!isImage && isPdf && objectUrl ? <iframe title={selection.name} src={objectUrl} /> : null}
        {!isImage && !isPdf && textPreview !== null ? <pre>{textPreview}</pre> : null}
        {!isImage && !isPdf && textPreview === null ? (
          <div className="agent-preview-placeholder">
            <FileTextIcon size={28} />
            <strong>文件已上传并完成预解析</strong>
            <span>当前格式在浏览器中不能直接渲染，解析结果已可供 Agent 使用。</span>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function AgentWorkflowCanvas({
  projectId,
  state,
  onClose,
  onOpenProject,
  showHeader = true,
}: {
  projectId: string;
  state: AIAssistantState;
  onClose: () => void;
  onOpenProject: () => void;
  showHeader?: boolean;
}) {
  const workflow = useMemo(() => {
    const matchesProject = (item: AIAssistantState["executionItems"][number]) => {
      if (item.kind !== "workflow") return false;
      const resultProjectId = typeof item.result?.project_id === "string" ? item.result.project_id : "";
      const argumentProjectId = typeof item.arguments?.project_id === "string" ? item.arguments.project_id : "";
      return resultProjectId === projectId || argumentProjectId === projectId;
    };
    return [...state.executionItems].reverse().find(matchesProject) ?? null;
  }, [projectId, state.executionItems]);

  return (
    <aside className="agent-preview-canvas agent-workflow-canvas" aria-label="任务编排画布">
      {showHeader && (
        <header className="agent-preview-header">
          <div className="agent-preview-heading">
            <strong>响应工作流</strong>
            <span>{workflow?.isWaitingApproval ? "当前在等待人工确认" : workflow?.summary || "查看本次任务的执行路径与节点状态"}</span>
          </div>
          <button type="button" className="agent-preview-close" aria-label="关闭任务编排画布" onClick={onClose}><XIcon size={16} /></button>
        </header>
      )}
      <div className="agent-preview-body agent-workflow-body">
        <WorkflowCanvas
          currentNode={workflow?.currentNode ?? null}
          isWaitingApproval={workflow?.isWaitingApproval ?? false}
          nodes={workflow?.nodes ?? []}
        />
      </div>
      <footer className="agent-workflow-footer">
        <span>{workflow ? "节点状态会随当前运行实时更新" : "当前项目尚无运行中的编排任务"}</span>
        <button type="button" onClick={onOpenProject}><PanelTopIcon size={14} />在项目工作区打开</button>
      </footer>
    </aside>
  );
}

function useCompactViewport() {
  const [isCompact, setIsCompact] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(max-width: 820px)").matches : false,
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 820px)");
    const sync = () => setIsCompact(mediaQuery.matches);
    sync();
    mediaQuery.addEventListener("change", sync);
    return () => mediaQuery.removeEventListener("change", sync);
  }, []);

  return isCompact;
}

function formatPreviewSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function dayLabel(conversation: ChatConversationRead) {
  const value = conversation.created_at ? new Date(conversation.created_at) : null;
  if (!value) return "更早";
  const today = new Date();
  if (value.toDateString() === today.toDateString()) return "今天";
  return "最近";
}

function agentWorkspacePath({
  conversationId,
  projectId,
}: {
  conversationId?: string;
  projectId?: string;
}) {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  if (conversationId) params.set("conversation", conversationId);
  const query = params.toString();
  return query ? `/agent?${query}` : "/agent";
}

function AgentHistory({
  open,
  conversations,
  currentConversationId,
  onNew,
  onSelect,
  onRename,
  onDelete,
  onTogglePinned,
}: {
  open: boolean;
  conversations: ChatConversationRead[];
  currentConversationId: string | null;
  onNew: () => void;
  onSelect: (conversationId: string) => void;
  onRename: (conversationId: string, title: string) => Promise<void>;
  onDelete: (conversationId: string) => Promise<void>;
  onTogglePinned: (conversationId: string, isPinned: boolean) => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const committingIdRef = useRef<string | null>(null);
  const commitEditing = (conversationId: string) => {
    if (committingIdRef.current === conversationId) return;
    const nextTitle = editingTitle.trim();
    setEditingId(null);
    if (!nextTitle) return;
    committingIdRef.current = conversationId;
    void onRename(conversationId, nextTitle)
      .catch((error) => console.error("Failed to rename conversation:", error))
      .finally(() => {
        if (committingIdRef.current === conversationId) committingIdRef.current = null;
      });
  };
  const groups = useMemo(() => {
    const next = new Map<string, ChatConversationRead[]>();
    for (const conversation of conversations.slice(0, 16)) {
      const label = dayLabel(conversation);
      next.set(label, [...(next.get(label) ?? []), conversation]);
    }
    return [...next.entries()];
  }, [conversations]);

  return (
    <div className={`bp-linear-history${open ? " is-open" : ""}`} aria-hidden={!open}>
      <div className="bp-linear-history-inner">
        <button type="button" className="bp-linear-history-new" onClick={onNew}>
          <span>+</span> 新对话
        </button>
        {groups.map(([label, items]) => (
          <section className="bp-linear-history-group" key={label}>
            <span>{label}</span>
            {items.map((conversation) => {
              const isEditing = editingId === conversation.id;
              const title = conversation.title || "未命名对话";
              return (
                <div
                  key={conversation.id}
                  className={`bp-linear-history-row${conversation.id === currentConversationId ? " is-current" : ""}`}
                >
                  {isEditing ? (
                    <input
                      autoFocus
                      value={editingTitle}
                      aria-label="会话名称"
                      onChange={(event) => setEditingTitle(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          commitEditing(conversation.id);
                        }
                        if (event.key === "Escape") setEditingId(null);
                      }}
                      onBlur={() => commitEditing(conversation.id)}
                    />
                  ) : (
                    <button
                      type="button"
                      className="bp-linear-history-row-main"
                      onClick={() => onSelect(conversation.id)}
                    >
                      <strong>{title}</strong>
                      <small>{conversation.id === currentConversationId ? "当前" : ""}</small>
                    </button>
                  )}
                  <div className="bp-linear-history-actions">
                    <button
                      type="button"
                      aria-label={conversation.is_pinned ? "取消置顶会话" : "置顶会话"}
                      title={conversation.is_pinned ? "取消置顶" : "置顶"}
                      onClick={() =>
                        void onTogglePinned(conversation.id, !conversation.is_pinned).catch((error) =>
                          console.error("Failed to pin conversation:", error),
                        )
                      }
                    >
                      <PinIcon size={13} fill={conversation.is_pinned ? "currentColor" : "none"} />
                    </button>
                    <button
                      type="button"
                      aria-label="重命名会话"
                      title="重命名"
                      onClick={() => {
                        setEditingId(conversation.id);
                        setEditingTitle(conversation.title || "");
                      }}
                    >
                      <PencilIcon size={13} />
                    </button>
                    <button
                      type="button"
                      aria-label="删除会话"
                      title="删除"
                      onClick={() =>
                        void onDelete(conversation.id).catch((error) =>
                          console.error("Failed to delete conversation:", error),
                        )
                      }
                    >
                      <Trash2Icon size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </section>
        ))}
        {groups.length === 0 && <p className="bp-linear-history-empty">还没有会话记录</p>}
      </div>
    </div>
  );
}

function AgentWelcome({ onExample, onPreviewAttachment }: { onExample: (prompt: string) => void; onPreviewAttachment: (selection: AttachmentPreviewSelection) => void }) {
  const [examplesVisible, setExamplesVisible] = useState(true);
  const examples = [
    { title: "创建投标项目", copy: "从招标资料开始建立响应工作区", prompt: "帮我创建一个新的投标项目", icon: BotIcon },
    { title: "检查资料", copy: "核对已上传材料与投标要求", prompt: "检查当前项目的资料完整度", icon: BotIcon },
    { title: "起草响应", copy: "根据已确认的证据开始起草章节", prompt: "为当前项目起草技术响应", icon: BotIcon },
    {
      title: "收集招标附件",
      copy: "先列出公开附件，确认后再加入项目资料包",
      prompt: "从公开招标页面查找 PDF、DOCX 或 XLSX 附件，先列出候选文件给我确认；确认后再把选定资料加入当前项目资料包。",
      icon: FileSearchIcon,
    },
  ];
  return (
    <div className="agent-welcome" aria-label="BidPilot Agent welcome">
      <div className="agent-watermark" aria-hidden="true"><i className="watermark-disk" /><i className="watermark-slice slice-one" /><i className="watermark-slice slice-two" /><i className="watermark-slice slice-three" /></div>
      <h3>欢迎使用 BidPilot</h3>
      <AIAssistantPanel variant="linear-agent" onPreviewAttachment={onPreviewAttachment} />
      {examplesVisible ? (
        <section className="agent-examples" aria-label="Agent examples">
          <div className="examples-label">
            <span>从这些常用任务开始</span>
            <button type="button" aria-label="隐藏示例" onClick={() => setExamplesVisible(false)}>
              <XIcon aria-hidden="true" size={14} />
            </button>
          </div>
          <div className="examples-grid">
            {examples.map((example) => {
              const Icon = example.icon;
              return (
              <button type="button" className="example-card" key={example.title} onClick={() => onExample(example.prompt)}>
                <Icon size={15} />
                <strong>{example.title}</strong>
                <span>{example.copy}</span>
              </button>
              );
            })}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function AgentFooter({ onHistory }: { onHistory: () => void }) {
  return (
    <div className="agent-footer">
      <span><PanelTopIcon size={14} /> Agent</span>
      <button type="button" aria-label="Chat history" onClick={onHistory}><Clock3Icon size={15} /></button>
    </div>
  );
}

export function LinearAgentWorkspace() {
  const navigate = useNavigate();
  const {
    state,
    refreshConversations,
    startNewConversation,
    sendMessage,
    retryFromCheckpoint,
    cancelWorkflow,
    confirmAssistantAction,
  } = useAIAssistant();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState<AttachmentPreviewSelection | null>(null);
  const [workflowCanvasProjectId, setWorkflowCanvasProjectId] = useState<string | null>(null);
  const [previewWidth, setPreviewWidth] = useState(420);
  const [isPreviewResizing, setIsPreviewResizing] = useState(false);
  const isCompactViewport = useCompactViewport();
  const workspaceRef = useRef<HTMLDivElement>(null);
  const historySurfaceRef = useRef<HTMLDivElement>(null);
  const previewResizeStartRef = useRef({ x: 0, width: 420 });

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  const conversationTitle = useMemo(() => {
    if (!state.currentConversationId) return "新对话";
    return state.conversations.find((conversation) => conversation.id === state.currentConversationId)?.title || "未命名对话";
  }, [state.conversations, state.currentConversationId]);
  const currentConversation = useMemo(
    () => state.conversations.find((conversation) => conversation.id === state.currentConversationId),
    [state.conversations, state.currentConversationId],
  );

  const renameConversation = async (conversationId: string, title: string) => {
    await renameChatConversation(conversationId, title);
    await refreshConversations();
  };

  const deleteConversation = async (conversationId: string) => {
    const deletingCurrent = state.currentConversationId === conversationId;
    // Clear the route and invalidate any in-flight restore before the DELETE
    // request finishes; otherwise the old query can reload the just-deleted id.
    if (deletingCurrent) {
      startNewConversation();
      navigate(agentWorkspacePath({ projectId: state.currentContext.projectId }), { replace: true });
    }
    await deleteChatConversation(conversationId);
    await refreshConversations();
  };

  const togglePinnedConversation = async (conversationId: string, isPinned: boolean) => {
    await setChatConversationPinned(conversationId, isPinned);
    await refreshConversations();
  };

  const handleStartNewConversation = () => {
    startNewConversation();
    // The route is part of the conversation state. Leaving the old query
    // parameter in place lets AgentWorkspacePage restore the previous thread.
    navigate(agentWorkspacePath({ projectId: state.currentContext.projectId }), { replace: true });
    setHistoryOpen(false);
  };
  const handleLoadConversation = (conversationId: string) => {
    navigate(
      agentWorkspacePath({
        conversationId,
        projectId: state.currentContext.projectId,
      }),
      { replace: true },
    );
    setHistoryOpen(false);
  };
  const handleExample = (prompt: string) => {
    void sendMessage(prompt, { displayContent: prompt });
  };
  const openWorkflowCanvas = (projectId: string) => {
    setPreviewAttachment(null);
    setWorkflowCanvasProjectId(projectId);
  };
  const hasSideCanvas = Boolean(previewAttachment || workflowCanvasProjectId);
  const showDesktopCanvas = hasSideCanvas && !isCompactViewport;
  const closeSideSurface = () => {
    setPreviewAttachment(null);
    setWorkflowCanvasProjectId(null);
  };
  const mobileSurfaceTitle = workflowCanvasProjectId ? "响应工作流" : previewAttachment?.name || "附件预览";
  const mobileSurfaceDescription = workflowCanvasProjectId
    ? "查看当前任务的执行路径与节点状态"
    : previewAttachment
      ? `${formatPreviewSize(previewAttachment.size)} · ${previewAttachment.kind === "image" ? "图片" : "文件"}`
      : "";

  const handlePreviewResizeStart = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    previewResizeStartRef.current = { x: event.clientX, width: previewWidth };
    setIsPreviewResizing(true);
  };
  const handlePreviewResizeMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!isPreviewResizing) return;
    const delta = previewResizeStartRef.current.x - event.clientX;
    setPreviewWidth(Math.min(640, Math.max(300, previewResizeStartRef.current.width + delta)));
  };
  const handlePreviewResizeEnd = () => setIsPreviewResizing(false);

  useEffect(() => {
    if (!historyOpen) return;
    const closeHistoryFromOutside = (event: PointerEvent) => {
      if (historySurfaceRef.current?.contains(event.target as Node)) return;
      setHistoryOpen(false);
    };
    document.addEventListener("pointerdown", closeHistoryFromOutside);
    return () => document.removeEventListener("pointerdown", closeHistoryFromOutside);
  }, [historyOpen]);

  return (
    <div className={`linear-agent-embedded bidpilot-linear-agent${isPreviewResizing ? " is-preview-resizing" : ""}`} ref={workspaceRef}>
      <main
        className={`linear-main${showDesktopCanvas ? " has-preview-canvas" : ""}`}
        style={{ "--preview-width": `${previewWidth}px` } as CSSProperties}
      >
        <section className="agent-canvas">
          <div className="agent-history-surface" ref={historySurfaceRef}>
            <header className="agent-topbar">
              <button type="button" className="chat-switch" aria-expanded={historyOpen} onClick={() => setHistoryOpen((value) => !value)}>
                <span>{conversationTitle}</span><ChevronDownIcon size={13} />
              </button>
              <button
                type="button"
                className={`agent-header-icon${currentConversation?.is_pinned ? " is-active" : ""}`}
                aria-label={currentConversation?.is_pinned ? "取消置顶会话" : "置顶会话"}
                onClick={() => {
                  if (currentConversation) {
                    void togglePinnedConversation(currentConversation.id, !currentConversation.is_pinned);
                  }
                }}
              >
                <StarIcon size={15} fill={currentConversation?.is_pinned ? "currentColor" : "none"} />
              </button>
              <button type="button" className="agent-header-icon" aria-label="Conversation options" onClick={() => setHistoryOpen((value) => !value)}>
                <MoreHorizontalIcon size={16} />
              </button>
            </header>
            <AgentHistory
              open={historyOpen}
              conversations={state.conversations}
              currentConversationId={state.currentConversationId}
              onNew={handleStartNewConversation}
              onSelect={handleLoadConversation}
              onRename={renameConversation}
              onDelete={deleteConversation}
              onTogglePinned={togglePinnedConversation}
            />
          </div>
          <div
            className={`agent-content bidpilot-claude-thread${state.messages.length ? " has-messages" : ""}`}
            data-testid="agent-conversation-pane"
          >
            {state.messages.length ? (
              <>
                <ClaudeAgentThread
                  state={state}
                  onCancelWorkflow={cancelWorkflow}
                  onConfigureProvider={() => navigate("/settings/providers")}
                  onConfirm={(confirmationText) => void confirmAssistantAction(true, confirmationText)}
                  onCancelConfirmation={() => void confirmAssistantAction(false)}
                  onSubmitInput={(content) => void sendMessage(content, { displayContent: content })}
                  onRetryFromCheckpoint={(checkpointMessageId, content) => {
                    void retryFromCheckpoint(checkpointMessageId, content);
                  }}
                  onOpenWorkflowCanvas={openWorkflowCanvas}
                />
                <div className="bp-linear-agent-composer-slot" aria-label="Agent composer">
                  <AIAssistantPanel
                    variant="linear-agent"
                    onPreviewAttachment={(selection) => {
                      setWorkflowCanvasProjectId(null);
                      setPreviewAttachment(selection);
                    }}
                  />
                </div>
              </>
            ) : (
              <AgentWelcome onExample={handleExample} onPreviewAttachment={setPreviewAttachment} />
            )}
          </div>
        </section>
        {showDesktopCanvas ? (
          <div
            className="agent-preview-resize-handle"
            aria-label="调整预览画布宽度"
            role="separator"
            tabIndex={0}
            onPointerCancel={handlePreviewResizeEnd}
            onPointerDown={handlePreviewResizeStart}
            onPointerMove={handlePreviewResizeMove}
            onPointerUp={handlePreviewResizeEnd}
            onKeyDown={(event) => {
              if (event.key === "ArrowLeft") setPreviewWidth((width) => Math.min(640, width + 16));
              if (event.key === "ArrowRight") setPreviewWidth((width) => Math.max(300, width - 16));
            }}
          />
        ) : null}
        {showDesktopCanvas && workflowCanvasProjectId ? (
          <AgentWorkflowCanvas
            projectId={workflowCanvasProjectId}
            state={state}
            onClose={() => setWorkflowCanvasProjectId(null)}
            onOpenProject={() => navigate(`/projects/${workflowCanvasProjectId}?surface=workflow`)}
          />
        ) : showDesktopCanvas ? (
          <AgentPreviewCanvas selection={previewAttachment} onClose={() => setPreviewAttachment(null)} />
        ) : null}
        <AgentFooter onHistory={() => setHistoryOpen((value) => !value)} />
      </main>
      <Sheet
        open={isCompactViewport && hasSideCanvas}
        onOpenChange={(open) => {
          if (!open) closeSideSurface();
        }}
      >
        <SheetContent
          side="right"
          className="agent-mobile-side-sheet w-[min(100vw,34rem)] max-w-none gap-0 p-0 sm:max-w-none"
        >
          <SheetHeader className="agent-mobile-side-sheet-header">
            <SheetTitle>{mobileSurfaceTitle}</SheetTitle>
            <SheetDescription>{mobileSurfaceDescription}</SheetDescription>
          </SheetHeader>
          {workflowCanvasProjectId ? (
            <AgentWorkflowCanvas
              projectId={workflowCanvasProjectId}
              state={state}
              onClose={closeSideSurface}
              onOpenProject={() => navigate(`/projects/${workflowCanvasProjectId}?surface=workflow`)}
              showHeader={false}
            />
          ) : (
            <AgentPreviewCanvas
              selection={previewAttachment}
              onClose={closeSideSurface}
              showHeader={false}
            />
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
