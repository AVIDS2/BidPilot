import {
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  lazy,
  Suspense,
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
  FolderKanbanIcon,
  MessageSquareTextIcon,
  MoreHorizontalIcon,
  PanelRightIcon,
  PanelTopIcon,
  PencilIcon,
  PinIcon,
  PlusIcon,
  StarIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { AttachmentPreviewSelection } from "@/features/agent/components/AIAssistantPanel";
import { WorkflowCanvas } from "@/components/workflow-canvas";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ClaudeAgentThread } from "./claude-agent-thread";
import { AgentEnvironmentPanel } from "./components/agent-environment-panel";
import { useAIAssistant, type AIAssistantState } from "@/features/agent/state/agent-store";
import {
  deleteChatConversation,
  listProjects,
  renameChatConversation,
  setChatConversationPinned,
  type ChatConversationRead,
  type ProjectRead,
} from "@/lib/api";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { loadWithChunkRecovery } from "@/app-route-loaders";
import "./linear-agent-workspace.css";

const LazyAIAssistantPanel = lazy(() =>
  loadWithChunkRecovery(
    () => import("@/features/agent/components/AIAssistantPanel"),
    "assistant-panel",
  ).then(({ AIAssistantPanel }) => ({ default: AIAssistantPanel })),
);

function AgentComposerLoading() {
  return (
    <div className="flex min-h-28 w-full flex-col gap-3 rounded-lg border bg-background p-3" role="status" aria-label="正在加载 Agent 输入框">
      <Skeleton className="h-12 w-full" />
      <div className="flex items-center justify-between gap-3">
        <Skeleton className="h-7 w-20" />
        <Skeleton className="h-7 w-28" />
      </div>
    </div>
  );
}

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
          <Button className="agent-preview-close" aria-label="关闭预览" onClick={onClose} size="icon-sm" type="button" variant="ghost"><XIcon aria-hidden="true" /></Button>
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
          <Button className="agent-preview-close" aria-label="关闭任务编排画布" onClick={onClose} size="icon-sm" type="button" variant="ghost"><XIcon aria-hidden="true" /></Button>
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
        <Button onClick={onOpenProject} size="sm" type="button" variant="ghost"><PanelTopIcon aria-hidden="true" data-icon="inline-start" />在项目工作区打开</Button>
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
  projects,
  currentConversationId,
  onNew,
  onSelect,
  onOpenProject,
  onRename,
  onDelete,
  onTogglePinned,
}: {
  open: boolean;
  conversations: ChatConversationRead[];
  projects: ProjectRead[];
  currentConversationId: string | null;
  onNew: () => void;
  onSelect: (conversationId: string) => void;
  onOpenProject: (projectId: string) => void;
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
      const projectId = conversation.project_id ?? "personal";
      next.set(projectId, [...(next.get(projectId) ?? []), conversation]);
    }
    const currentProjectId = conversations.find((conversation) => conversation.id === currentConversationId)?.project_id ?? "personal";
    return [...next.entries()]
      .map(([id, items]) => ({
        id,
        items,
        project: projects.find((project) => project.id === id) ?? null,
      }))
      .sort((left, right) => {
        if (left.id === currentProjectId) return -1;
        if (right.id === currentProjectId) return 1;
        if (left.id === "personal") return 1;
        if (right.id === "personal") return -1;
        return left.items[0]?.created_at && right.items[0]?.created_at
          ? Date.parse(right.items[0].created_at) - Date.parse(left.items[0].created_at)
          : 0;
      });
  }, [conversations, currentConversationId, projects]);

  return (
    <div className={`bp-linear-history${open ? " is-open" : ""}`} aria-hidden={!open}>
      <div className="bp-linear-history-inner">
        <Button type="button" className="bp-linear-history-new" onClick={onNew} size="sm" variant="ghost">
          <PlusIcon data-icon="inline-start" /> 新对话
        </Button>
        {groups.map(({ id, items, project }) => {
          const label = project?.name ?? "个人会话";
          return (
          <section className="bp-linear-history-group" key={id}>
            <div className="bp-linear-history-project-heading">
              <Button
                type="button"
                className="bp-linear-history-project-main"
                onClick={() => id !== "personal" && onOpenProject(id)}
                disabled={id === "personal"}
                size="sm"
                variant="ghost"
              >
                {id === "personal" ? <MessageSquareTextIcon aria-hidden="true" /> : <FolderKanbanIcon aria-hidden="true" />}
                <span>
                  <strong>{label}</strong>
                  <small>{project?.scenario_package || `${items.length} 个会话`}</small>
                </span>
              </Button>
              <span className="bp-linear-history-project-count">{items.length}</span>
            </div>
            {items.map((conversation) => {
              const isEditing = editingId === conversation.id;
              const title = conversation.title || "未命名对话";
              return (
                <div
                  key={conversation.id}
                  className={`bp-linear-history-row${conversation.id === currentConversationId ? " is-current" : ""}`}
                >
                  {isEditing ? (
                    <Input
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
                    <Button
                      type="button"
                      className="bp-linear-history-row-main"
                      onClick={() => onSelect(conversation.id)}
                      size="sm"
                      variant="ghost"
                    >
                      <strong>{title}</strong>
                      {conversation.id === currentConversationId ? <small>当前</small> : null}
                    </Button>
                  )}
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      render={<Button aria-label="会话操作" className="bp-linear-history-actions" size="icon-xs" variant="ghost" />}
                    >
                      <MoreHorizontalIcon />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-44">
                      <DropdownMenuGroup>
                        <DropdownMenuLabel>会话操作</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() =>
                            void onTogglePinned(conversation.id, !conversation.is_pinned).catch((error) =>
                              console.error("Failed to pin conversation:", error),
                            )
                          }
                        >
                          <PinIcon fill={conversation.is_pinned ? "currentColor" : "none"} />
                          {conversation.is_pinned ? "取消置顶" : "置顶会话"}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => {
                            setEditingId(conversation.id);
                            setEditingTitle(conversation.title || "");
                          }}
                        >
                          <PencilIcon />重命名会话
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() =>
                            void onDelete(conversation.id).catch((error) =>
                              console.error("Failed to delete conversation:", error),
                            )
                          }
                          variant="destructive"
                        >
                          <Trash2Icon />删除会话
                        </DropdownMenuItem>
                      </DropdownMenuGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              );
            })}
          </section>
        );
        })}
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
      <Suspense fallback={<AgentComposerLoading />}>
        <LazyAIAssistantPanel variant="linear-agent" onPreviewAttachment={onPreviewAttachment} />
      </Suspense>
      {examplesVisible ? (
        <section className="agent-examples" aria-label="Agent examples">
          <div className="examples-label">
            <span>从这些常用任务开始</span>
            <Button aria-label="隐藏示例" onClick={() => setExamplesVisible(false)} size="icon-xs" type="button" variant="ghost">
              <XIcon aria-hidden="true" />
            </Button>
          </div>
          <div className="examples-grid">
            {examples.map((example) => {
              const Icon = example.icon;
              return (
              <Button type="button" className="example-card" key={example.title} onClick={() => onExample(example.prompt)} size="sm" variant="outline">
                <Icon size={15} />
                <strong>{example.title}</strong>
                <span>{example.copy}</span>
              </Button>
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
      <Button aria-label="Chat history" onClick={onHistory} size="icon-xs" type="button" variant="ghost"><Clock3Icon aria-hidden="true" /></Button>
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
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [environmentPanelOpen, setEnvironmentPanelOpen] = useState(() =>
    typeof window !== "undefined" ? !window.matchMedia("(max-width: 820px)").matches : true,
  );
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

  useEffect(() => {
    void listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

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
  const showDesktopEnvironment = environmentPanelOpen && !isCompactViewport;
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
        className={`linear-main${showDesktopCanvas ? " has-preview-canvas" : ""}${showDesktopEnvironment ? " has-environment-panel" : ""}`}
        style={{ "--preview-width": `${previewWidth}px` } as CSSProperties}
      >
        <section className="agent-canvas">
          <div className="agent-history-surface" ref={historySurfaceRef}>
            <header className="agent-topbar">
              <Button type="button" className="chat-switch" aria-expanded={historyOpen} onClick={() => setHistoryOpen((value) => !value)} size="sm" variant="ghost">
                <span>{conversationTitle}</span><ChevronDownIcon aria-hidden="true" />
              </Button>
              <Button
                type="button"
                className={`agent-header-icon${currentConversation?.is_pinned ? " is-active" : ""}`}
                aria-label={currentConversation?.is_pinned ? "取消置顶会话" : "置顶会话"}
                onClick={() => {
                  if (currentConversation) {
                    void togglePinnedConversation(currentConversation.id, !currentConversation.is_pinned);
                  }
                }}
                size="icon-sm"
                variant="ghost"
              >
                <StarIcon aria-hidden="true" fill={currentConversation?.is_pinned ? "currentColor" : "none"} />
              </Button>
              <Button type="button" className="agent-header-icon" aria-label="Conversation options" onClick={() => setHistoryOpen((value) => !value)} size="icon-sm" variant="ghost">
                <MoreHorizontalIcon aria-hidden="true" />
              </Button>
              <Button
                type="button"
                className={`agent-header-icon${environmentPanelOpen ? " is-active" : ""}`}
                aria-expanded={environmentPanelOpen}
                aria-label={environmentPanelOpen ? "收起工作概览" : "打开工作概览"}
                title={environmentPanelOpen ? "收起工作概览" : "打开工作概览"}
                onClick={() => setEnvironmentPanelOpen((value) => !value)}
                size="icon-sm"
                variant="ghost"
              >
                <PanelRightIcon aria-hidden="true" />
              </Button>
            </header>
            <AgentHistory
              open={historyOpen}
              conversations={state.conversations}
              projects={projects}
              currentConversationId={state.currentConversationId}
              onNew={handleStartNewConversation}
              onSelect={handleLoadConversation}
              onOpenProject={(projectId) => {
                setHistoryOpen(false);
                navigate(`/projects/${projectId}`);
              }}
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
                  <Suspense fallback={<AgentComposerLoading />}>
                    <LazyAIAssistantPanel
                      variant="linear-agent"
                      onPreviewAttachment={(selection) => {
                        setWorkflowCanvasProjectId(null);
                        setPreviewAttachment(selection);
                      }}
                    />
                  </Suspense>
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
        {showDesktopEnvironment ? (
          <AgentEnvironmentPanel
            currentProjectId={state.currentContext.projectId ?? currentConversation?.project_id}
            onClose={() => setEnvironmentPanelOpen(false)}
            onOpenProject={(projectId) => navigate(`/projects/${projectId}`)}
            onOpenRun={(runId) => navigate(`/runs?run=${runId}`)}
          />
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
      <Sheet
        open={isCompactViewport && environmentPanelOpen}
        onOpenChange={(open) => setEnvironmentPanelOpen(open)}
      >
        <SheetContent
          side="right"
          className="agent-mobile-environment-sheet w-[min(100vw,22rem)] max-w-none gap-0 p-0 sm:max-w-none"
        >
          <SheetHeader className="agent-mobile-side-sheet-header">
            <SheetTitle>工作概览</SheetTitle>
            <SheetDescription>项目、资料和后台工作都在这里继续</SheetDescription>
          </SheetHeader>
          <AgentEnvironmentPanel
            currentProjectId={state.currentContext.projectId ?? currentConversation?.project_id}
            onClose={() => setEnvironmentPanelOpen(false)}
            onOpenProject={(projectId) => {
              setEnvironmentPanelOpen(false);
              navigate(`/projects/${projectId}`);
            }}
            onOpenRun={(runId) => {
              setEnvironmentPanelOpen(false);
              navigate(`/runs?run=${runId}`);
            }}
          />
        </SheetContent>
      </Sheet>
    </div>
  );
}
