/* oxlint-disable nextjs/no-img-element -- previews use local blob URLs. */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowUpRightIcon,
  BotIcon,
  ChevronDownIcon,
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
  XIcon
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import {
  AIAssistantPanel,
  type AttachmentPreviewSelection
} from '@/features/agent/components/AIAssistantPanel';
import { WorkflowCanvas } from '@/components/workflow-canvas';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from '@/components/ui/accordion';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field';
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle
} from '@/components/ui/item';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ClaudeAgentThread } from './claude-agent-thread';
import { AgentEnvironmentPanel } from './components/agent-environment-panel';
import { AgentSubagentsPanel } from './components/agent-subagents-panel';
import { useAIAssistant, type AIAssistantState } from '@/features/agent/state/agent-store';
import {
  deleteChatConversation,
  createProject,
  listProjects,
  renameChatConversation,
  setChatConversationPinned,
  type ChatConversationRead,
  type ProjectRead,
  type RuntimeRunListItem
} from '@/lib/api';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from '@/components/ui/sheet';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import './linear-agent-workspace.css';

const AGENT_COMPACT_MEDIA_QUERY = '(max-width: 1024px)';

function AgentPreviewCanvas({
  selection,
  onClose,
  showHeader = true
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
    const textLike =
      selection.file.type.startsWith('text/') ||
      /\.(md|txt|json|csv|xml|html?)$/i.test(selection.name);
    if (textLike) {
      void selection.file.text().then((value) => setTextPreview(value.slice(0, 100_000)));
    }
    return () => URL.revokeObjectURL(url);
  }, [selection]);

  if (!selection) return null;
  const isPdf = selection.file?.type === 'application/pdf' || /\.pdf$/i.test(selection.name);
  const isImage = selection.kind === 'image';
  return (
    <aside className='agent-preview-canvas' aria-label='附件预览画布'>
      {showHeader && (
        <header className='agent-preview-header'>
          <div className='agent-preview-heading'>
            <strong title={selection.name}>{selection.name}</strong>
            <span>
              {formatPreviewSize(selection.size)} · {isImage ? '图片' : '文件'}
            </span>
          </div>
          <Button
            className='agent-preview-close'
            aria-label='关闭预览'
            onClick={onClose}
            size='icon-sm'
            type='button'
            variant='ghost'
          >
            <XIcon aria-hidden='true' />
          </Button>
        </header>
      )}
      <div className='agent-preview-body'>
        {isImage && (selection.previewUrl || objectUrl) ? (
          <img src={selection.previewUrl || objectUrl || undefined} alt={selection.name} />
        ) : null}
        {!isImage && isPdf && objectUrl ? <iframe title={selection.name} src={objectUrl} /> : null}
        {!isImage && !isPdf && textPreview !== null ? <pre>{textPreview}</pre> : null}
        {!isImage && !isPdf && textPreview === null ? (
          <div className='agent-preview-placeholder'>
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
  showHeader = true
}: {
  projectId: string;
  state: AIAssistantState;
  onClose: () => void;
  onOpenProject: () => void;
  showHeader?: boolean;
}) {
  const workflow = useMemo(() => {
    const matchesProject = (item: AIAssistantState['executionItems'][number]) => {
      if (item.kind !== 'workflow') return false;
      const resultProjectId =
        typeof item.result?.project_id === 'string' ? item.result.project_id : '';
      const argumentProjectId =
        typeof item.arguments?.project_id === 'string' ? item.arguments.project_id : '';
      return resultProjectId === projectId || argumentProjectId === projectId;
    };
    return [...state.executionItems].reverse().find(matchesProject) ?? null;
  }, [projectId, state.executionItems]);

  return (
    <aside className='agent-preview-canvas agent-workflow-canvas' aria-label='任务编排画布'>
      {showHeader && (
        <header className='agent-preview-header'>
          <div className='agent-preview-heading'>
            <strong>响应工作流</strong>
            <span>
              {workflow?.isWaitingApproval
                ? '当前在等待人工确认'
                : workflow?.summary || '查看本次任务的执行路径与节点状态'}
            </span>
          </div>
          <Button
            className='agent-preview-close'
            aria-label='关闭任务编排画布'
            onClick={onClose}
            size='icon-sm'
            type='button'
            variant='ghost'
          >
            <XIcon aria-hidden='true' />
          </Button>
        </header>
      )}
      <div className='agent-preview-body agent-workflow-body'>
        <WorkflowCanvas
          currentNode={workflow?.currentNode ?? null}
          isWaitingApproval={workflow?.isWaitingApproval ?? false}
          nodes={workflow?.nodes ?? []}
        />
      </div>
      <footer className='agent-workflow-footer'>
        <span>{workflow ? '节点状态会随当前运行实时更新' : '当前项目尚无运行中的编排任务'}</span>
        <Button onClick={onOpenProject} size='sm' type='button' variant='ghost'>
          <PanelTopIcon aria-hidden='true' data-icon='inline-start' />
          在项目工作区打开
        </Button>
      </footer>
    </aside>
  );
}

type AgentSideTab =
  | { type: 'workflow'; projectId: string }
  | { type: 'subagents'; parentRunId: string }
  | { type: 'attachment'; selection: AttachmentPreviewSelection };

type AgentSideTabType = AgentSideTab['type'];

function sideTabLabel(tab: AgentSideTab) {
  if (tab.type === 'workflow') return '响应工作流';
  if (tab.type === 'subagents') return '协作任务';
  return tab.selection.name || '附件预览';
}

function AgentSideSurface({
  tabs,
  activeTab,
  state,
  onChange,
  onCloseTab,
  onOpenProject,
  showContentHeaders = true
}: {
  tabs: AgentSideTab[];
  activeTab: AgentSideTabType;
  state: AIAssistantState;
  onChange: (tab: AgentSideTabType) => void;
  onCloseTab: (tab: AgentSideTabType) => void;
  onOpenProject: (projectId: string) => void;
  showContentHeaders?: boolean;
}) {
  return (
    <Tabs
      value={activeTab}
      onValueChange={(value) => onChange(value as AgentSideTabType)}
      className='agent-side-tabs'
    >
      <div className='agent-side-tabbar'>
        <TabsList aria-label='右侧工作区页面' variant='line' className='agent-side-tab-list'>
          {tabs.map((tab) => (
            <TabsTrigger
              key={tab.type}
              value={tab.type}
              className='agent-side-tab-trigger'
              title={sideTabLabel(tab)}
            >
              <span className='truncate'>{sideTabLabel(tab)}</span>
            </TabsTrigger>
          ))}
        </TabsList>
        <Button
          type='button'
          size='icon-sm'
          variant='ghost'
          className='agent-side-tab-close'
          aria-label='关闭当前侧栏页面'
          title='关闭当前页面'
          onClick={() => onCloseTab(activeTab)}
        >
          <XIcon aria-hidden='true' />
        </Button>
      </div>
      {tabs.map((tab) => (
        <TabsContent key={tab.type} value={tab.type} className='agent-side-tab-content'>
          {tab.type === 'subagents' ? (
            <AgentSubagentsPanel
              parentRunId={tab.parentRunId}
              onClose={() => onCloseTab(tab.type)}
              showHeader={showContentHeaders}
            />
          ) : tab.type === 'workflow' ? (
            <AgentWorkflowCanvas
              projectId={tab.projectId}
              state={state}
              onClose={() => onCloseTab(tab.type)}
              onOpenProject={() => onOpenProject(tab.projectId)}
              showHeader={showContentHeaders}
            />
          ) : (
            <AgentPreviewCanvas
              selection={tab.selection}
              onClose={() => onCloseTab(tab.type)}
              showHeader={showContentHeaders}
            />
          )}
        </TabsContent>
      ))}
    </Tabs>
  );
}

function useCompactViewport() {
  const [isCompact, setIsCompact] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(AGENT_COMPACT_MEDIA_QUERY).matches : false
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia(AGENT_COMPACT_MEDIA_QUERY);
    const sync = () => setIsCompact(mediaQuery.matches);
    sync();
    mediaQuery.addEventListener('change', sync);
    return () => mediaQuery.removeEventListener('change', sync);
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
  projectId
}: {
  conversationId?: string;
  projectId?: string;
}) {
  const params = new URLSearchParams();
  if (projectId) params.set('project_id', projectId);
  if (conversationId) params.set('conversation', conversationId);
  const query = params.toString();
  return query ? `/agent?${query}` : '/agent';
}

function AgentHistory({
  open,
  conversations,
  projects,
  currentConversationId,
  onNew,
  onSelect,
  onOpenProject,
  onCreateProject,
  onRename,
  onDelete,
  onTogglePinned
}: {
  open: boolean;
  conversations: ChatConversationRead[];
  projects: ProjectRead[];
  currentConversationId: string | null;
  onNew: () => void;
  onSelect: (conversationId: string) => void;
  onOpenProject: (projectId: string) => void;
  onCreateProject: (name: string) => Promise<ProjectRead>;
  onRename: (conversationId: string, title: string) => Promise<void>;
  onDelete: (conversationId: string) => Promise<void>;
  onTogglePinned: (conversationId: string, isPinned: boolean) => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [createWorkspaceOpen, setCreateWorkspaceOpen] = useState(false);
  const [workspaceName, setWorkspaceName] = useState('');
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);
  const committingIdRef = useRef<string | null>(null);
  const commitEditing = (conversationId: string) => {
    if (committingIdRef.current === conversationId) return;
    const nextTitle = editingTitle.trim();
    setEditingId(null);
    if (!nextTitle) return;
    committingIdRef.current = conversationId;
    void onRename(conversationId, nextTitle)
      .catch((error) => console.error('Failed to rename conversation:', error))
      .finally(() => {
        if (committingIdRef.current === conversationId) committingIdRef.current = null;
      });
  };
  const groups = useMemo(() => {
    const next = new Map<string, ChatConversationRead[]>();
    for (const conversation of conversations) {
      const projectId = conversation.project_id ?? 'personal';
      next.set(projectId, [...(next.get(projectId) ?? []), conversation]);
    }
    // Show newly created workspaces before their first conversation exists.
    // Conversation history is organized by real project records, not by an
    // inferred date bucket or an automatically invented session group.
    for (const project of projects) {
      if (!next.has(project.id)) next.set(project.id, []);
    }
    const currentProjectId =
      conversations.find((conversation) => conversation.id === currentConversationId)?.project_id ??
      'personal';
    return [...next.entries()]
      .map(([id, items]) => ({
        id,
        items,
        project: projects.find((project) => project.id === id) ?? null
      }))
      .sort((left, right) => {
        if (left.id === currentProjectId) return -1;
        if (right.id === currentProjectId) return 1;
        const leftHasPinned = left.items.some((conversation) => conversation.is_pinned);
        const rightHasPinned = right.items.some((conversation) => conversation.is_pinned);
        if (leftHasPinned !== rightHasPinned) return leftHasPinned ? -1 : 1;
        if (left.id === 'personal') return 1;
        if (right.id === 'personal') return -1;
        return left.items[0]?.created_at && right.items[0]?.created_at
          ? Date.parse(right.items[0].created_at) - Date.parse(left.items[0].created_at)
          : 0;
      });
  }, [conversations, currentConversationId, projects]);

  const submitWorkspace = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = workspaceName.trim();
    if (!name || creatingWorkspace) return;
    setCreatingWorkspace(true);
    setWorkspaceError(null);
    try {
      const project = await onCreateProject(name);
      setWorkspaceName('');
      setCreateWorkspaceOpen(false);
      onOpenProject(project.id);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : '工作区创建失败，请稍后重试。');
    } finally {
      setCreatingWorkspace(false);
    }
  };

  return (
    <div className={`bp-linear-history${open ? ' is-open' : ''}`} aria-hidden={!open}>
      <div className='bp-linear-history-inner'>
        <Button
          type='button'
          className='bp-linear-history-new'
          onClick={onNew}
          size='sm'
          variant='ghost'
        >
          <PlusIcon data-icon='inline-start' /> 新对话
        </Button>
        <div className='mt-2 flex items-center justify-between gap-2 px-2'>
          <span className='text-muted-foreground text-xs font-medium'>工作区</span>
          <Button
            type='button'
            aria-label='新建工作区'
            title='新建工作区'
            size='icon-xs'
            variant='ghost'
            onClick={() => {
              setWorkspaceError(null);
              setCreateWorkspaceOpen(true);
            }}
          >
            <PlusIcon aria-hidden='true' />
          </Button>
        </div>
        {groups.length > 0 ? (
          <Accordion
            multiple
            defaultValue={groups.map(({ id }) => `workspace-${id}`)}
            className='mt-1'
          >
            {groups.map(({ id, items, project }) => {
              const isPersonal = id === 'personal';
              const isUnavailable = !isPersonal && !project;
              const label = project?.name ?? (isPersonal ? '未关联工作区' : '历史工作区');
              const description = project?.scenario_package
                ? '项目会话'
                : isUnavailable
                  ? '工作区已不可用，会话仍保留'
                  : `${items.length} 个会话`;
              return (
                <AccordionItem
                  key={id}
                  value={`workspace-${id}`}
                  className='border-border px-1 last:border-b-0'
                >
                  <div className='flex min-w-0 items-center gap-1'>
                    <AccordionTrigger className='min-w-0 gap-2 px-1.5 py-2 hover:no-underline'>
                      <span className='flex min-w-0 items-center gap-2 text-left'>
                        {isPersonal ? (
                          <MessageSquareTextIcon className='text-muted-foreground size-4 shrink-0' />
                        ) : (
                          <FolderKanbanIcon className='text-muted-foreground size-4 shrink-0' />
                        )}
                        <span className='grid min-w-0 gap-0.5'>
                          <span className='truncate text-sm font-medium'>{label}</span>
                          <span className='text-muted-foreground truncate text-[11px]'>
                            {description}
                          </span>
                        </span>
                      </span>
                    </AccordionTrigger>
                    <Badge variant={isUnavailable ? 'outline' : 'secondary'} className='shrink-0'>
                      {items.length}
                    </Badge>
                    {project ? (
                      <Button
                        type='button'
                        size='icon-xs'
                        variant='ghost'
                        aria-label={`打开工作区 ${project.name}`}
                        title='打开工作区'
                        onClick={() => onOpenProject(project.id)}
                      >
                        <ArrowUpRightIcon aria-hidden='true' />
                      </Button>
                    ) : null}
                  </div>
                  <AccordionContent className='pb-2 pl-4'>
                    {items.length ? (
                      <ItemGroup className='gap-1'>
                        {items.map((conversation) => {
                          const isEditing = editingId === conversation.id;
                          const isCurrent = conversation.id === currentConversationId;
                          const title = conversation.title || '未命名对话';
                          return (
                            <Item
                              key={conversation.id}
                              size='xs'
                              variant={isCurrent ? 'muted' : 'default'}
                              className='min-w-0 gap-1 px-2 py-1'
                            >
                              <ItemMedia variant='icon'>
                                <MessageSquareTextIcon className='text-muted-foreground' />
                              </ItemMedia>
                              <ItemContent className='min-w-0'>
                                {isEditing ? (
                                  <Input
                                    autoFocus
                                    value={editingTitle}
                                    aria-label='会话名称'
                                    className='h-7'
                                    onChange={(event) => setEditingTitle(event.target.value)}
                                    onKeyDown={(event) => {
                                      if (event.key === 'Enter') {
                                        event.preventDefault();
                                        commitEditing(conversation.id);
                                      }
                                      if (event.key === 'Escape') setEditingId(null);
                                    }}
                                    onBlur={() => commitEditing(conversation.id)}
                                  />
                                ) : (
                                  <Button
                                    type='button'
                                    variant='ghost'
                                    size='sm'
                                    className='h-auto min-w-0 justify-start px-0 py-0 text-left hover:bg-transparent'
                                    onClick={() => onSelect(conversation.id)}
                                  >
                                    <ItemTitle className='min-w-0'>{title}</ItemTitle>
                                  </Button>
                                )}
                              </ItemContent>
                              {isCurrent ? (
                                <ItemDescription className='shrink-0'>当前</ItemDescription>
                              ) : null}
                              <ItemActions className='shrink-0 opacity-0 transition-opacity group-hover/item:opacity-100 group-focus-within/item:opacity-100'>
                                <DropdownMenu>
                                  <DropdownMenuTrigger
                                    render={
                                      <Button
                                        aria-label='会话操作'
                                        size='icon-xs'
                                        variant='ghost'
                                      />
                                    }
                                  >
                                    <MoreHorizontalIcon />
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align='end' className='w-44'>
                                    <DropdownMenuGroup>
                                      <DropdownMenuLabel>会话操作</DropdownMenuLabel>
                                      <DropdownMenuSeparator />
                                      <DropdownMenuItem
                                        onClick={() =>
                                          void onTogglePinned(
                                            conversation.id,
                                            !conversation.is_pinned
                                          ).catch((error) =>
                                            console.error('Failed to pin conversation:', error)
                                          )
                                        }
                                      >
                                        <PinIcon
                                          fill={conversation.is_pinned ? 'currentColor' : 'none'}
                                        />
                                        {conversation.is_pinned ? '取消收藏会话' : '收藏会话'}
                                      </DropdownMenuItem>
                                      <DropdownMenuItem
                                        onClick={() => {
                                          setEditingId(conversation.id);
                                          setEditingTitle(conversation.title || '');
                                        }}
                                      >
                                        <PencilIcon />
                                        重命名会话
                                      </DropdownMenuItem>
                                      <DropdownMenuSeparator />
                                      <DropdownMenuItem
                                        onClick={() =>
                                          void onDelete(conversation.id).catch((error) =>
                                            console.error('Failed to delete conversation:', error)
                                          )
                                        }
                                        variant='destructive'
                                      >
                                        <Trash2Icon />
                                        删除会话
                                      </DropdownMenuItem>
                                    </DropdownMenuGroup>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </ItemActions>
                            </Item>
                          );
                        })}
                      </ItemGroup>
                    ) : (
                      <Empty className='border-0 px-2 py-5 text-left'>
                        <EmptyHeader className='items-start gap-1'>
                          <EmptyTitle>还没有会话</EmptyTitle>
                          <EmptyDescription>打开工作区后，从第一条消息开始。</EmptyDescription>
                        </EmptyHeader>
                      </Empty>
                    )}
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        ) : (
          <Empty className='items-start border-0 px-2 py-6 text-left'>
            <EmptyHeader className='items-start'>
              <EmptyTitle>还没有会话记录</EmptyTitle>
              <EmptyDescription>新建一次对话，或先创建一个项目工作区。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </div>
      <Dialog
        open={createWorkspaceOpen}
        onOpenChange={(nextOpen) => {
          setCreateWorkspaceOpen(nextOpen);
          if (!nextOpen) setWorkspaceError(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建项目工作区</DialogTitle>
            <DialogDescription>
              为一组招标资料建立独立工作区，资料、证据和响应版本都会围绕它保存。
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitWorkspace}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor='agent-create-workspace-name'>工作区名称</FieldLabel>
                <Input
                  id='agent-create-workspace-name'
                  autoFocus
                  placeholder='例如：智慧社区治理项目'
                  value={workspaceName}
                  onChange={(event) => setWorkspaceName(event.target.value)}
                  disabled={creatingWorkspace}
                  required
                  minLength={2}
                  maxLength={80}
                />
                <FieldDescription>建议使用招标项目或客户名称，方便团队共同查找。</FieldDescription>
                <FieldError>{workspaceError}</FieldError>
              </Field>
            </FieldGroup>
            <DialogFooter className='mt-5'>
              <Button
                type='button'
                variant='outline'
                disabled={creatingWorkspace}
                onClick={() => setCreateWorkspaceOpen(false)}
              >
                取消
              </Button>
              <Button type='submit' disabled={creatingWorkspace || workspaceName.trim().length < 2}>
                {creatingWorkspace ? (
                  <Spinner data-icon='inline-start' />
                ) : (
                  <PlusIcon data-icon='inline-start' />
                )}
                创建并打开
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AgentWelcome({
  onExample,
  onPreviewAttachment
}: {
  onExample: (prompt: string) => void;
  onPreviewAttachment: (selection: AttachmentPreviewSelection) => void;
}) {
  const [examplesVisible, setExamplesVisible] = useState(true);
  const examples = [
    {
      title: '创建投标项目',
      copy: '从招标资料开始建立响应工作区',
      prompt: '帮我创建一个新的投标项目',
      icon: BotIcon
    },
    {
      title: '检查资料',
      copy: '核对已上传材料与投标要求',
      prompt: '检查当前项目的资料完整度',
      icon: BotIcon
    },
    {
      title: '起草响应',
      copy: '根据已确认的证据开始起草章节',
      prompt: '为当前项目起草技术响应',
      icon: BotIcon
    },
    {
      title: '收集招标附件',
      copy: '先列出公开附件，确认后再加入项目资料包',
      prompt:
        '从公开招标页面查找 PDF、DOCX 或 XLSX 附件，先列出候选文件给我确认；确认后再把选定资料加入当前项目资料包。',
      icon: FileSearchIcon
    }
  ];
  return (
    <div className='agent-welcome' aria-label='BidPilot Agent welcome'>
      <div className='agent-watermark' aria-hidden='true'>
        <i className='watermark-disk' />
        <i className='watermark-slice slice-one' />
        <i className='watermark-slice slice-two' />
        <i className='watermark-slice slice-three' />
      </div>
      <h3>欢迎使用 BidPilot</h3>
      <AIAssistantPanel variant='linear-agent' onPreviewAttachment={onPreviewAttachment} />
      {examplesVisible ? (
        <section className='agent-examples' aria-label='Agent examples'>
          <div className='examples-label'>
            <span>从这些常用任务开始</span>
            <Button
              aria-label='隐藏示例'
              onClick={() => setExamplesVisible(false)}
              size='icon-xs'
              type='button'
              variant='ghost'
            >
              <XIcon aria-hidden='true' />
            </Button>
          </div>
          <div className='examples-grid'>
            {examples.map((example) => {
              const Icon = example.icon;
              return (
                <Button
                  type='button'
                  className='example-card'
                  key={example.title}
                  onClick={() => onExample(example.prompt)}
                  size='sm'
                  variant='outline'
                >
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

export function LinearAgentWorkspace() {
  const router = useRouter();
  const navigate = (href: string, options?: { replace?: boolean }) => {
    if (options?.replace) router.replace(href);
    else router.push(href);
  };
  const {
    state,
    refreshConversations,
    startNewConversation,
    sendMessage,
    retryFromCheckpoint,
    cancelWorkflow,
    confirmAssistantAction
  } = useAIAssistant();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [environmentPanelOpen, setEnvironmentPanelOpen] = useState(false);
  const [sideTabs, setSideTabs] = useState<AgentSideTab[]>([]);
  const [activeSideTab, setActiveSideTab] = useState<AgentSideTabType>('workflow');
  const isCompactViewport = useCompactViewport();
  const historySurfaceRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    void listProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
  }, []);

  const conversationTitle = useMemo(() => {
    if (!state.currentConversationId) return '新对话';
    return (
      state.conversations.find((conversation) => conversation.id === state.currentConversationId)
        ?.title || '未命名对话'
    );
  }, [state.conversations, state.currentConversationId]);
  const currentConversation = useMemo(
    () =>
      state.conversations.find((conversation) => conversation.id === state.currentConversationId),
    [state.conversations, state.currentConversationId]
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
      navigate(agentWorkspacePath({ projectId: state.currentContext.projectId }), {
        replace: true
      });
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
    const selectedConversation = state.conversations.find((item) => item.id === conversationId);
    const selectedProjectId =
      selectedConversation?.project_id &&
      projects.some((project) => project.id === selectedConversation.project_id)
        ? selectedConversation.project_id
        : undefined;
    navigate(
      agentWorkspacePath({
        conversationId,
        // A history item owns its project context. Reusing the currently
        // visible page context can send a valid conversation to a stale or
        // unrelated project and produce a misleading "Project not found".
        projectId: selectedProjectId
      }),
      { replace: true }
    );
    setHistoryOpen(false);
  };
  const handleExample = (prompt: string) => {
    void sendMessage(prompt, { displayContent: prompt });
  };
  const handleCreateProject = async (name: string) => {
    const project = await createProject({ name, scenario_package: 'bidpilot' });
    setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
    await refreshConversations();
    return project;
  };
  const openSideTab = (tab: AgentSideTab) => {
    setSideTabs((current) => {
      const existing = current.findIndex((item) => item.type === tab.type);
      if (existing === -1) return [...current, tab];
      const next = [...current];
      next[existing] = tab;
      return next;
    });
    setActiveSideTab(tab.type);
  };
  const openWorkflowCanvas = (projectId: string) => {
    openSideTab({ type: 'workflow', projectId });
  };
  const openSubagentsPanel = (parentRunId: string) => {
    openSideTab({ type: 'subagents', parentRunId });
  };
  const openAttachmentPreview = (selection: AttachmentPreviewSelection) => {
    openSideTab({ type: 'attachment', selection });
  };
  const closeSideTab = (tabType: AgentSideTabType) => {
    const index = sideTabs.findIndex((tab) => tab.type === tabType);
    if (index === -1) return;
    const next = sideTabs.filter((tab) => tab.type !== tabType);
    setSideTabs(next);
    if (activeSideTab === tabType) {
      setActiveSideTab(next[Math.min(index, next.length - 1)]?.type ?? 'workflow');
    }
  };
  const hasSideSurface = sideTabs.length > 0;
  const showDesktopSideSurface = hasSideSurface && !isCompactViewport;
  const closeSideSurface = () => closeSideTab(activeSideTab);
  const mobileActiveTab = sideTabs.find((tab) => tab.type === activeSideTab) ?? sideTabs[0];
  const mobileSurfaceTitle = mobileActiveTab ? sideTabLabel(mobileActiveTab) : '侧栏';
  const mobileSurfaceDescription =
    mobileActiveTab?.type === 'subagents'
      ? '查看当前对话中协作助理的处理进度'
      : mobileActiveTab?.type === 'workflow'
        ? '查看当前任务的执行路径与节点状态'
        : mobileActiveTab?.type === 'attachment'
          ? `${formatPreviewSize(mobileActiveTab.selection.size)} · ${mobileActiveTab.selection.kind === 'image' ? '图片' : '文件'}`
          : '';

  useEffect(() => {
    if (!historyOpen) return;
    const closeHistoryFromOutside = (event: PointerEvent) => {
      if (historySurfaceRef.current?.contains(event.target as Node)) return;
      setHistoryOpen(false);
    };
    document.addEventListener('pointerdown', closeHistoryFromOutside);
    return () => document.removeEventListener('pointerdown', closeHistoryFromOutside);
  }, [historyOpen]);

  return (
    <div className='linear-agent-embedded bidpilot-linear-agent'>
      <div className='linear-main'>
        <ResizablePanelGroup
          orientation='horizontal'
          className='agent-split-layout'
          data-testid='agent-split-layout'
        >
          <ResizablePanel
            id='agent-conversation-panel'
            defaultSize={showDesktopSideSurface ? '68%' : '100%'}
            minSize='0px'
            className='min-w-0'
          >
            <section className='agent-canvas'>
              <div className='agent-history-surface' ref={historySurfaceRef}>
                <header className='agent-topbar'>
                  <Button
                    type='button'
                    className='chat-switch'
                    aria-expanded={historyOpen}
                    onClick={() => setHistoryOpen((value) => !value)}
                    size='sm'
                    variant='ghost'
                  >
                    <span>{conversationTitle}</span>
                    <ChevronDownIcon aria-hidden='true' />
                  </Button>
                  <Button
                    type='button'
                    className={`agent-header-icon${currentConversation?.is_pinned ? ' is-active' : ''}`}
                    aria-label={currentConversation?.is_pinned ? '取消收藏会话' : '收藏会话'}
                    disabled={!currentConversation}
                    title={
                      currentConversation
                        ? currentConversation.is_pinned
                          ? '取消收藏会话'
                          : '收藏会话'
                        : '新对话暂无可收藏内容'
                    }
                    onClick={() => {
                      if (currentConversation) {
                        void togglePinnedConversation(
                          currentConversation.id,
                          !currentConversation.is_pinned
                        );
                      }
                    }}
                    size='icon-sm'
                    variant='ghost'
                  >
                    <StarIcon
                      aria-hidden='true'
                      fill={currentConversation?.is_pinned ? 'currentColor' : 'none'}
                    />
                  </Button>
                  <Button
                    type='button'
                    className='agent-header-icon'
                    aria-label='Conversation options'
                    onClick={() => setHistoryOpen((value) => !value)}
                    size='icon-sm'
                    variant='ghost'
                  >
                    <MoreHorizontalIcon aria-hidden='true' />
                  </Button>
                  <Popover open={environmentPanelOpen} onOpenChange={setEnvironmentPanelOpen}>
                    <PopoverTrigger
                      render={
                        <Button
                          type='button'
                          className={`agent-header-icon${environmentPanelOpen ? ' is-active' : ''}`}
                          aria-label={environmentPanelOpen ? '收起工作概览' : '打开工作概览'}
                          title={environmentPanelOpen ? '收起工作概览' : '打开工作概览'}
                          size='icon-sm'
                          variant='ghost'
                        />
                      }
                    >
                      <PanelRightIcon aria-hidden='true' />
                    </PopoverTrigger>
                    <PopoverContent
                      align='end'
                      aria-label='工作概览'
                      className='agent-environment-popover w-[min(22rem,calc(100vw-1rem))] max-w-[calc(100vw-1rem)] p-0'
                      side='bottom'
                      sideOffset={8}
                    >
                      <AgentEnvironmentPanel
                        currentProjectId={
                          state.currentContext.projectId ?? currentConversation?.project_id
                        }
                        onOpenProject={(projectId) => {
                          setEnvironmentPanelOpen(false);
                          navigate(`/projects/${projectId}`);
                        }}
                        onOpenRun={(run: RuntimeRunListItem) => {
                          setEnvironmentPanelOpen(false);
                          if (run.conversation_id) {
                            navigate(
                              agentWorkspacePath({
                                conversationId: run.conversation_id,
                                projectId: run.project_id ?? undefined
                              })
                            );
                          } else if (run.project_id) {
                            navigate(`/projects/${run.project_id}`);
                          }
                        }}
                      />
                    </PopoverContent>
                  </Popover>
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
                  onCreateProject={handleCreateProject}
                  onRename={renameConversation}
                  onDelete={deleteConversation}
                  onTogglePinned={togglePinnedConversation}
                />
              </div>
              <div
                className={`agent-content bidpilot-claude-thread${state.messages.length ? ' has-messages' : ''}`}
                data-testid='agent-conversation-pane'
              >
                {state.messages.length ? (
                  <>
                    <ClaudeAgentThread
                      state={state}
                      onCancelWorkflow={cancelWorkflow}
                      onConfigureProvider={() => navigate('/settings/providers')}
                      onConfirm={(confirmationText) =>
                        void confirmAssistantAction(true, confirmationText)
                      }
                      onCancelConfirmation={() => void confirmAssistantAction(false)}
                      onSubmitInput={(content) =>
                        void sendMessage(content, { displayContent: content })
                      }
                      onRetryFromCheckpoint={(checkpointMessageId, content) => {
                        void retryFromCheckpoint(checkpointMessageId, content);
                      }}
                      onOpenWorkflowCanvas={openWorkflowCanvas}
                      onOpenSubagents={openSubagentsPanel}
                    />
                    <div className='bp-linear-agent-composer-slot' aria-label='Agent composer'>
                      <AIAssistantPanel
                        variant='linear-agent'
                        onPreviewAttachment={openAttachmentPreview}
                      />
                    </div>
                  </>
                ) : (
                  <AgentWelcome
                    onExample={handleExample}
                    onPreviewAttachment={openAttachmentPreview}
                  />
                )}
              </div>
            </section>
          </ResizablePanel>
          {showDesktopSideSurface ? (
            <>
              <ResizableHandle withHandle />
              <ResizablePanel
                id='agent-side-surface-panel'
                defaultSize='32%'
                minSize='300px'
                maxSize='640px'
                collapsible
                collapsedSize='0px'
                className='min-w-0'
              >
                <AgentSideSurface
                  tabs={sideTabs}
                  activeTab={activeSideTab}
                  state={state}
                  onChange={setActiveSideTab}
                  onCloseTab={closeSideTab}
                  onOpenProject={(projectId) => navigate(`/projects/${projectId}?surface=workflow`)}
                />
              </ResizablePanel>
            </>
          ) : null}
        </ResizablePanelGroup>
      </div>
      <Sheet
        open={isCompactViewport && hasSideSurface}
        onOpenChange={(open) => {
          if (!open) closeSideSurface();
        }}
      >
        <SheetContent
          side='right'
          className='agent-mobile-side-sheet w-[min(100vw,34rem)] max-w-none gap-0 p-0 sm:max-w-none'
        >
          <SheetHeader className='agent-mobile-side-sheet-header'>
            <SheetTitle>{mobileSurfaceTitle}</SheetTitle>
            <SheetDescription>{mobileSurfaceDescription}</SheetDescription>
          </SheetHeader>
          {mobileActiveTab ? (
            <AgentSideSurface
              tabs={sideTabs}
              activeTab={mobileActiveTab.type}
              state={state}
              onChange={setActiveSideTab}
              onCloseTab={closeSideTab}
              onOpenProject={(projectId) => navigate(`/projects/${projectId}?surface=workflow`)}
              showContentHeaders={false}
            />
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
