import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleDashedIcon,
  CircleXIcon,
  DownloadIcon,
  ExternalLinkIcon,
  FileCheck2Icon,
  FileSearchIcon,
  FileTextIcon,
  FolderOpenIcon,
  Globe2Icon,
  Loader2Icon,
  PanelRightIcon,
  TimerIcon,
  type LucideIcon
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  downloadAssistantArtifact,
  listRuntimeChildRuns,
  listRuntimeEvents,
  type RuntimeChildRunRead
} from '@/lib/api';
import type {
  AssistantExecutionItem,
  WorkflowNodeProgress
} from '@/features/agent/state/agent-store';
import { getAssistantActivityLabel, getAssistantToolIcon } from './assistant-tool-metadata';
import { parseAgentUiAction } from './agent-ui-action';
import './claude-activity-timeline.css';

type ActivityStatus = AssistantExecutionItem['status'];
type Translate = (key: string, options?: Record<string, unknown>) => string;

interface ClaudeActivityTimelineProps {
  items: AssistantExecutionItem[];
  taskTitle?: string;
  nested?: boolean;
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
  onOpenSubagents?: (parentRunId: string) => void;
}

function statusIsActive(status: ActivityStatus) {
  return status === 'running' || status === 'pending';
}

function aggregateStatus(items: AssistantExecutionItem[]): ActivityStatus {
  if (items.some((item) => item.status === 'failed')) return 'failed';
  if (items.some((item) => statusIsActive(item.status))) return 'running';
  if (items.some((item) => item.status === 'cancelled')) return 'cancelled';
  return 'succeeded';
}

function publicText(value: string | undefined) {
  if (!value) return '';
  // Runtime summaries are already redacted at the API boundary. This second
  // guard prevents legacy raw tool envelopes from reaching the UI.
  if (/tool_call_id=|content=['"]?\{|name=['"]?[a-z_]+['"]?/i.test(value)) {
    return '';
  }
  return value.trim();
}

function displaySummary(item: AssistantExecutionItem, t: Translate) {
  const summary = publicText(item.summary);
  if (summary) return summary;
  if (item.errorCode) {
    return t(`activity.failure.${item.errorCode}`, {
      defaultValue: t('activity.failure.workflow_internal_error', {
        defaultValue: 'The workflow could not finish safely. Please try again later.'
      })
    });
  }
  if (item.status === 'failed') {
    return t('activity.failure.workflow_internal_error', {
      defaultValue: 'The operation could not finish safely. Please try again later.'
    });
  }
  return '';
}

interface SearchSource {
  title: string;
  url: string;
  snippet: string;
  domain: string;
}

function searchSources(item: AssistantExecutionItem): SearchSource[] {
  if (item.toolName !== 'web_search' || !Array.isArray(item.result?.items)) return [];

  return item.result.items.flatMap((candidate) => {
    if (!candidate || typeof candidate !== 'object') return [];
    const source = candidate as Record<string, unknown>;
    const title = typeof source.title === 'string' ? source.title.trim() : '';
    const url = typeof source.url === 'string' ? source.url.trim() : '';
    const snippet = typeof source.snippet === 'string' ? source.snippet.trim() : '';

    try {
      const parsed = new URL(url);
      if ((parsed.protocol !== 'http:' && parsed.protocol !== 'https:') || !title) return [];
      return [{ title, url: parsed.href, snippet, domain: parsed.hostname.replace(/^www\./, '') }];
    } catch {
      return [];
    }
  });
}

function WebSearchSources({ item, t }: { item: AssistantExecutionItem; t: Translate }) {
  const sources = searchSources(item);
  if (sources.length === 0) return null;

  const query = typeof item.result?.query === 'string' ? item.result.query : '';

  return (
    <section
      className='cr-search-evidence'
      aria-label={t('activity.searchSources', { defaultValue: 'Search sources' })}
    >
      <header className='cr-search-evidence-header'>
        <span>
          <Globe2Icon size={14} />
          {query
            ? t('activity.searchSourcesFor', {
                query,
                defaultValue: `Search results for "${query}"`
              })
            : t('activity.searchSources', { defaultValue: 'Search sources' })}
        </span>
      </header>
      <div className='cr-search-source-list'>
        {sources.map((source) => (
          <a
            className='cr-search-source'
            href={source.url}
            key={source.url}
            rel='noreferrer'
            target='_blank'
          >
            <Globe2Icon aria-hidden='true' size={13} />
            <span className='cr-search-source-title'>{source.title}</span>
            <small>{source.domain}</small>
            {source.snippet && <p>{source.snippet}</p>}
          </a>
        ))}
      </div>
    </section>
  );
}

interface RemoteDocumentCandidate {
  filename: string;
  title: string;
  url: string;
  contentTypeHint: string;
  domain: string;
}

function publicUrl(value: unknown) {
  if (typeof value !== 'string' || !value.trim()) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed : null;
  } catch {
    return null;
  }
}

// Timeline entries are also rendered in embedded previews that do not mount a
// React Router. Keep structured actions functional in both places.
function navigateToInternalRoute(route: string) {
  if (typeof window === 'undefined') return;
  window.history.pushState({}, '', route);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function remoteDocumentCandidates(item: AssistantExecutionItem): RemoteDocumentCandidate[] {
  if (item.toolName !== 'discover_remote_documents' || !Array.isArray(item.result?.items))
    return [];
  return item.result.items.flatMap((candidate) => {
    if (!candidate || typeof candidate !== 'object') return [];
    const raw = candidate as Record<string, unknown>;
    const parsed = publicUrl(raw.url);
    const filename = typeof raw.filename === 'string' ? raw.filename.trim() : '';
    const title = typeof raw.title === 'string' ? raw.title.trim() : '';
    if (!parsed || !filename) return [];
    return [
      {
        filename,
        title,
        url: parsed.href,
        contentTypeHint:
          typeof raw.content_type_hint === 'string' ? raw.content_type_hint.trim() : '',
        domain: parsed.hostname.replace(/^www\./, '')
      }
    ];
  });
}

function RemoteDocumentDiscovery({ item }: { item: AssistantExecutionItem }) {
  const candidates = remoteDocumentCandidates(item);
  if (!candidates.length) return null;
  return (
    <section className='cr-remote-materials' aria-label='发现的远程资料附件'>
      <header>
        <span>
          <FileSearchIcon size={14} />
          发现 {candidates.length} 个可入库附件
        </span>
        <small>尚未下载</small>
      </header>
      <p>确认具体文件后，Agent 才会将它保存到项目资料包并启动解析。</p>
      <div className='cr-remote-material-list'>
        {candidates.map((candidate) => (
          <a href={candidate.url} key={candidate.url} rel='noreferrer' target='_blank'>
            <FileSearchIcon aria-hidden='true' size={13} />
            <span>
              <strong>{candidate.filename}</strong>
              <small>
                {candidate.title || candidate.domain}
                {candidate.contentTypeHint ? ` · ${candidate.contentTypeHint}` : ''}
              </small>
            </span>
            <ExternalLinkIcon aria-hidden='true' size={13} />
          </a>
        ))}
      </div>
    </section>
  );
}

function remoteParseStatus(value: unknown) {
  if (value === 'not_applicable') return '已归档，无需解析';
  if (value === 'parsed') return '已完成解析';
  if (value === 'failed') return '解析需要处理';
  if (value === 'parsing') return '正在解析';
  return '等待解析';
}

function RemoteDocumentImport({ item }: { item: AssistantExecutionItem }) {
  if (item.toolName !== 'fetch_url_to_project' || !item.result) return null;
  const filename = typeof item.result.filename === 'string' ? item.result.filename.trim() : '';
  const documentId = typeof item.result.document_id === 'string' ? item.result.document_id : '';
  const queued = item.result.status === 'queued';
  if (!filename && !documentId && !queued) return null;
  const source = publicUrl(item.result.source_url);
  const bundle =
    typeof item.result.bundle_label === 'string' && item.result.bundle_label.trim()
      ? item.result.bundle_label.trim()
      : '项目资料包';
  const parsingQueued = item.result.ingest_queued !== false;
  const storedWithoutParsing =
    item.result.storage_status === 'stored_no_parse' ||
    item.result.parse_status === 'not_applicable';
  return (
    <section className='cr-remote-import' aria-label='远程资料导入状态'>
      <header>
        <span>
          <FileCheck2Icon size={14} />
          {queued ? '后台导入已开始' : '已加入项目资料包'}
        </span>
        <small
          className={queued || storedWithoutParsing || parsingQueued ? 'is-ready' : 'is-attention'}
        >
          {queued
            ? '下载中，完成后自动入库'
            : storedWithoutParsing
              ? '已归档，无需解析'
              : parsingQueued
                ? remoteParseStatus(item.result.parse_status)
                : '待重新投递解析'}
        </small>
      </header>
      <strong>{filename || '远程资料下载任务'}</strong>
      <p>
        <FolderOpenIcon aria-hidden='true' size={13} />
        资料包：{bundle}
        {storedWithoutParsing ? ' · 可下载附件' : ''}
      </p>
      <div className='cr-remote-import-actions'>
        <Link href='/knowledge'>
          <FolderOpenIcon aria-hidden='true' size={13} />
          查看资料中心
        </Link>
        {source ? (
          <a href={source.href} rel='noreferrer' target='_blank'>
            <ExternalLinkIcon aria-hidden='true' size={13} />
            原始公开来源
          </a>
        ) : null}
      </div>
    </section>
  );
}

function displayGroupSummary(items: AssistantExecutionItem[], t: Translate) {
  const active = aggregateStatus(items);
  const mcpProviders = [
    ...new Set(
      items
        .filter((item) => item.resourceKind === 'mcp')
        .map((item) => item.provider?.replace(/^mcp:/i, '').trim())
        .filter((value): value is string => Boolean(value))
    )
  ];
  if (items.length > 1 && mcpProviders.length > 0) {
    const provider = mcpProviders.length === 1 ? mcpProviders[0] : '多个来源';
    return `${provider} · ${items.length} 项外部调用`;
  }
  if (items.length === 1) {
    const item = items[0];
    const label = item.toolName
      ? getAssistantActivityLabel(item, t)
      : t('activity.workflow.default', { defaultValue: 'Workflow' });
    if (active === 'succeeded') {
      // A turn heading should identify the action. Its returned explanation
      // belongs in the expandable trace, otherwise a raw provider summary
      // leaks into the collapsed chronology and turns it into a status card.
      return label;
    }
    return label;
  }
  if (active === 'succeeded') {
    const latestSummary = [...items]
      .reverse()
      .map((item) => displaySummary(item, t))
      .find(Boolean);
    return latestSummary || t('activity.countTools', { count: items.length, tools: items.length });
  }
  return t('activity.countTools', {
    count: items.length,
    tools: items.length,
    defaultValue: `${items.length} actions`
  });
}

type ResultFact = {
  label: string;
  value: string;
};

function valueText(value: unknown) {
  if (typeof value === 'string') return value.trim();
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? '是' : '否';
  return '';
}

function publicStatusText(value: unknown) {
  const status = valueText(value).toLowerCase();
  const labels: Record<string, string> = {
    ready: '已就绪',
    queued: '等待处理',
    pending: '等待处理',
    running: '处理中',
    processing: '处理中',
    succeeded: '已完成',
    completed: '已完成',
    failed: '失败',
    parsed: '已解析',
    indexed: '已可检索',
    stored: '已入库'
  };
  return labels[status] ?? valueText(value);
}

function resultFacts(item: AssistantExecutionItem): ResultFact[] {
  const result = item.result ?? {};
  const facts: ResultFact[] = [];
  const add = (label: string, key: string, transform?: (value: unknown) => string) => {
    const text = transform ? transform(result[key]) : valueText(result[key]);
    if (text) facts.push({ label, value: text });
  };
  add('交付物', 'deliverable_title');
  add('文件', 'filename');
  add('资料包', 'bundle_label');
  add('导出格式', 'format', (value) => {
    const text = valueText(value);
    return text ? text.toUpperCase() : '';
  });
  add('处理状态', 'status', publicStatusText);
  add('解析状态', 'parse_status', publicStatusText);
  add('入库状态', 'storage_status', publicStatusText);
  return facts;
}

function ResultFacts({ item }: { item: AssistantExecutionItem }) {
  const facts = resultFacts(item);
  const error =
    publicText(item.errorMessage) ||
    (item.status === 'failed' ? displaySummary(item, () => '') : '');
  if (!facts.length && !error && !item.errorCode) return null;
  return (
    <div
      className={`cr-result-facts${item.status === 'failed' ? ' is-failed' : ''}`}
      aria-label={item.status === 'failed' ? '失败详情' : '相关资源'}
    >
      {facts.length > 0 && (
        <dl>
          {facts.map((fact) => (
            <div key={`${fact.label}-${fact.value}`}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {error && <p>{error}</p>}
      {item.errorCode && <small>错误代码：{item.errorCode}</small>}
    </div>
  );
}

interface ActivityTurn {
  id: string;
  items: AssistantExecutionItem[];
}

function groupActivityTurns(items: AssistantExecutionItem[]): ActivityTurn[] {
  const grouped = new Map<string, AssistantExecutionItem[]>();
  for (const item of items) {
    const id = item.turnId || item.runtimeRunId || item.runId || item.id;
    const group = grouped.get(id) ?? [];
    group.push(item);
    grouped.set(id, group);
  }
  return [...grouped.entries()].map(([id, groupedItems]) => ({ id, items: groupedItems }));
}

function StepSymbol({ item }: { item: AssistantExecutionItem }) {
  if (item.status === 'succeeded') {
    return (
      <span className='cr-step-symbol is-done'>
        <CheckCircle2Icon size={14} />
      </span>
    );
  }
  if (item.status === 'failed') {
    return (
      <span className='cr-step-symbol is-note'>
        <CircleXIcon size={14} />
      </span>
    );
  }
  if (item.status === 'cancelled') {
    return (
      <span className='cr-step-symbol is-note'>
        <CircleDashedIcon size={14} />
      </span>
    );
  }
  return (
    <span className='cr-step-symbol cr-step-symbol-active' aria-hidden='true'>
      <Loader2Icon size={13} />
    </span>
  );
}

function NodeSymbol({ node }: { node: WorkflowNodeProgress }) {
  if (node.status === 'completed')
    return <CheckCircle2Icon className='cr-node-symbol is-complete' size={14} />;
  if (node.status === 'failed')
    return <CircleXIcon className='cr-node-symbol is-failed' size={14} />;
  if (node.status === 'running')
    return <Loader2Icon className='cr-node-symbol cr-node-spinner is-running' size={14} />;
  return <CircleDashedIcon className='cr-node-symbol is-pending' size={14} />;
}

function nodeLabel(node: WorkflowNodeProgress, t: Translate) {
  const labels: Record<string, string> = {
    supervisor: 'Coordinate task',
    rfp_parser: 'Parse requirements',
    memory_context: 'Load memory context',
    knowledge_retriever: 'Retrieve evidence',
    content_plan: 'Plan content',
    section_drafter: 'Draft section',
    quality_reviewer: 'Review quality',
    human_approval: 'Wait for approval',
    persist_result: 'Save result',
    memory_proposals: 'Propose memory updates'
  };
  return t(`activity.node.${node.name}`, {
    defaultValue: labels[node.name] ?? 'Workflow step'
  });
}

function RuntimeTimeline({
  item,
  nodes,
  t
}: {
  item: AssistantExecutionItem;
  nodes: WorkflowNodeProgress[];
  t: Translate;
}) {
  const hasRunningNode = nodes.some((node) => node.status === 'running');
  const [open, setOpen] = useState(false);
  const completed = nodes.filter((node) => node.status === 'completed').length;
  const summary = t('activity.workflowProgress', { defaultValue: 'Workflow steps' });

  if (nodes.length === 0) return null;

  return (
    <section className='cr-analysis-runtime' data-testid={`assistant-runtime-${item.id}`}>
      <Button
        type='button'
        className='cr-runtime-summary'
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        size='default'
        variant='ghost'
      >
        <span>
          <TimerIcon size={15} />
          {summary}
          <small className='cr-runtime-count'>
            {completed}/{nodes.length}
          </small>
        </span>
        <ChevronDownIcon size={14} />
      </Button>
      <div className={`cr-runtime-grid${open ? ' is-open' : ''}`}>
        <div className='cr-runtime-grid-inner'>
          <div className={`cr-runtime-timeline${hasRunningNode ? ' is-running' : ''}`}>
            {nodes.map((node) => (
              <div
                className={`cr-runtime-node is-thought${node.status === 'running' ? ' is-running' : ''}`}
                key={`${item.id}-${node.name}`}
              >
                <span className='cr-runtime-marker'>
                  <NodeSymbol node={node} />
                </span>
                <div className='cr-runtime-node-body'>
                  <div className='cr-thought-copy'>
                    <p>
                      <span>{nodeLabel(node, t)}</span>
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function ArtifactActions({ item, t }: { item: AssistantExecutionItem; t: Translate }) {
  const result = item.result ?? {};
  const actions = [
    ['DOCX', result.docx_download_path],
    ['XLSX', result.xlsx_download_path],
    [typeof result.format === 'string' ? result.format.toUpperCase() : 'PDF', result.download_path]
  ].filter((entry): entry is [string, string] => typeof entry[1] === 'string');
  const [downloading, setDownloading] = useState<string | null>(null);
  const projectId = typeof result.project_id === 'string' ? result.project_id : '';
  const deliverableId = typeof result.deliverable_id === 'string' ? result.deliverable_id : '';
  const title =
    typeof result.deliverable_title === 'string' && result.deliverable_title.trim()
      ? result.deliverable_title.trim()
      : '交付物';
  if (actions.length === 0 && !deliverableId) return null;
  return (
    <div className='cr-artifact-actions cr-resource-row' aria-label='交付物操作'>
      <div className='cr-resource-row-copy'>
        <FileCheck2Icon size={14} />
        <span>
          <strong>{title}</strong>
          <small>{actions.length > 0 ? '文件已生成，可下载或查看' : '可在项目工作区查看'}</small>
        </span>
      </div>
      <div className='cr-inline-actions'>
        {actions.map(([format, path]) => (
          <Button
            key={path}
            type='button'
            disabled={downloading !== null}
            onClick={() => {
              setDownloading(path);
              void downloadAssistantArtifact(
                path,
                `bidpilot-${format.toLowerCase()}.${format.toLowerCase()}`
              ).finally(() => setDownloading(null));
            }}
            size='sm'
            variant='ghost'
          >
            <DownloadIcon size={13} />
            {downloading === path
              ? t('activity.downloading', { defaultValue: 'Downloading' })
              : t(`activity.download.${format.toLowerCase()}`, {
                  defaultValue: `Download ${format}`
                })}
          </Button>
        ))}
        {projectId && deliverableId && (
          <Button
            type='button'
            onClick={() =>
              navigateToInternalRoute(
                `/projects/${projectId}?surface=deliverables${deliverableId ? `&deliverable_id=${deliverableId}` : ''}`
              )
            }
            size='sm'
            variant='ghost'
          >
            <FolderOpenIcon size={13} />
            查看交付物
          </Button>
        )}
      </div>
    </div>
  );
}

function WorkflowCanvasAction({
  item,
  onOpenWorkflowCanvas
}: {
  item: AssistantExecutionItem;
  onOpenWorkflowCanvas?: (projectId: string) => void;
}) {
  const result = item.result ?? {};
  const projectId = typeof result.project_id === 'string' ? result.project_id : '';
  if (item.kind !== 'workflow' || !projectId) return null;
  const sectionKey = typeof result.section_key === 'string' ? result.section_key : '';
  return (
    <div className='cr-artifact-actions cr-resource-row' aria-label='响应工作流操作'>
      <div className='cr-resource-row-copy'>
        <TimerIcon size={14} />
        <span>
          <strong>响应工作流</strong>
          <small>{sectionKey ? `章节：${sectionKey}` : '项目任务编排'}</small>
        </span>
      </div>
      <div className='cr-inline-actions'>
        <Button
          type='button'
          onClick={() => {
            if (onOpenWorkflowCanvas) {
              onOpenWorkflowCanvas(projectId);
              return;
            }
            navigateToInternalRoute(`/projects/${projectId}?surface=workflow`);
          }}
          size='sm'
          variant='ghost'
        >
          <TimerIcon size={13} />
          打开响应工作流
        </Button>
      </div>
    </div>
  );
}

function StructuredUiAction({
  item,
  onOpenWorkflowCanvas
}: {
  item: AssistantExecutionItem;
  onOpenWorkflowCanvas?: (projectId: string) => void;
}) {
  const action = parseAgentUiAction(item.result?.ui_action);
  if (!action) return null;

  if (action.type === 'canvas') {
    return (
      <div className='cr-inline-actions cr-structured-action'>
        <Button
          type='button'
          onClick={() => {
            if (onOpenWorkflowCanvas) {
              onOpenWorkflowCanvas(action.projectId);
              return;
            }
            navigateToInternalRoute(action.route);
          }}
          size='sm'
          variant='outline'
        >
          <TimerIcon size={13} />
          {action.label}
        </Button>
      </div>
    );
  }
  if (action.type === 'external-link') {
    return (
      <div className='cr-inline-actions cr-structured-action'>
        <a href={action.href} rel='noreferrer' target='_blank'>
          <ExternalLinkIcon size={13} />
          {action.label}
        </a>
      </div>
    );
  }
  return null;
}

function StepDetail({
  item,
  t,
  onCancelWorkflow,
  onConfigureProvider,
  onOpenWorkflowCanvas,
  isCancelling
}: {
  item: AssistantExecutionItem;
  t: Translate;
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
  isCancelling: boolean;
}) {
  const summary = displaySummary(item, t);
  const nodes = item.kind === 'workflow' ? (item.nodes ?? []) : [];
  const providerFailure =
    item.status === 'failed' && Boolean(item.errorCode?.startsWith('provider_'));
  const canCancel =
    Boolean(item.runtimeRunId) &&
    item.kind === 'workflow' &&
    statusIsActive(item.status) &&
    !item.isCancellationRequested;

  return (
    <div className='cr-run-step-expand'>
      {summary && <p className='cr-public-summary'>{summary}</p>}
      {providerFailure && onConfigureProvider && (
        <Button
          type='button'
          className='cr-inline-action'
          onClick={onConfigureProvider}
          size='sm'
          variant='ghost'
        >
          {t('activity.openProviderSettings', { defaultValue: 'Open model settings' })}
        </Button>
      )}
      <RuntimeTimeline item={item} nodes={nodes} t={t} />
      <WebSearchSources item={item} t={t} />
      <RemoteDocumentDiscovery item={item} />
      <RemoteDocumentImport item={item} />
      <ResultFacts item={item} />
      <StructuredUiAction item={item} onOpenWorkflowCanvas={onOpenWorkflowCanvas} />
      <ArtifactActions item={item} t={t} />
      <WorkflowCanvasAction item={item} onOpenWorkflowCanvas={onOpenWorkflowCanvas} />
      {canCancel && onCancelWorkflow && (
        <Button
          type='button'
          className='cr-inline-action'
          disabled={isCancelling}
          onClick={() => void onCancelWorkflow(item.runtimeRunId!)}
          size='sm'
          variant='ghost'
        >
          {isCancelling
            ? t('activity.cancelling', { defaultValue: 'Cancelling...' })
            : t('activity.cancelWorkflow', { defaultValue: 'Cancel workflow' })}
        </Button>
      )}
      {item.isCancellationRequested && item.status !== 'cancelled' && (
        <p className='cr-public-muted'>
          {t('activity.cancellationRequested', {
            defaultValue: 'Cancellation requested. Stopping at a safe boundary.'
          })}
        </p>
      )}
    </div>
  );
}

function ToolStep({
  item,
  t,
  onCancelWorkflow,
  onConfigureProvider,
  onOpenWorkflowCanvas,
  isCancelling
}: {
  item: AssistantExecutionItem;
  t: Translate;
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
  isCancelling: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [renderDetail, setRenderDetail] = useState(false);
  const detailCloseTimer = useRef<number | null>(null);
  const Icon: LucideIcon = getAssistantToolIcon(item);
  const label = item.toolName
    ? getAssistantActivityLabel(item, t)
    : t('activity.workflow.default', { defaultValue: 'Workflow' });
  const active = statusIsActive(item.status);

  useEffect(() => {
    return () => {
      if (detailCloseTimer.current !== null) window.clearTimeout(detailCloseTimer.current);
    };
  }, []);

  const toggleDetail = () => {
    if (!open) {
      if (detailCloseTimer.current !== null) window.clearTimeout(detailCloseTimer.current);
      setRenderDetail(true);
      setOpen(true);
      return;
    }
    setOpen(false);
    detailCloseTimer.current = window.setTimeout(() => setRenderDetail(false), 320);
  };

  return (
    <div
      className={`cr-run-step${open ? ' is-expanded' : ''}${active ? ' is-live' : ''}`}
      data-testid={`assistant-activity-step-${item.toolCallId || item.id}`}
      data-status={item.status}
    >
      <div className='cr-run-step-row'>
        <StepSymbol item={item} />
        <Button
          type='button'
          className='cr-run-step-button'
          aria-expanded={open}
          aria-busy={active || undefined}
          aria-label={open ? `Hide ${label} details` : `Show ${label} details`}
          onClick={toggleDetail}
          size='default'
          variant='ghost'
        >
          <span>
            <Icon className='cr-step-icon' size={13} />
            <span className={active ? 'cr-live-label' : undefined}>{label}</span>
          </span>
          <ChevronDownIcon size={14} />
        </Button>
      </div>
      <div className={`cr-command-grid${open ? ' is-open' : ''}`}>
        <div className='cr-command-grid-inner'>
          {renderDetail && (
            <StepDetail
              item={item}
              t={t}
              onCancelWorkflow={onCancelWorkflow}
              onConfigureProvider={onConfigureProvider}
              onOpenWorkflowCanvas={onOpenWorkflowCanvas}
              isCancelling={isCancelling}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function SubagentExecutionViewer({
  item,
  onOpenSubagents
}: {
  item: AssistantExecutionItem;
  onOpenSubagents?: (parentRunId: string) => void;
}) {
  const [children, setChildren] = useState<RuntimeChildRunRead[]>([]);
  const [selected, setSelected] = useState(0);
  const [events, setEvents] = useState<Array<{ type: string; public_summary: string }>>([]);
  const parentRunId = item.runtimeRunId;

  useEffect(() => {
    if (item.toolName !== 'spawn_subagents' || !parentRunId) return;
    let cancelled = false;
    const refresh = () => {
      void listRuntimeChildRuns(parentRunId, 20)
        .then((rows) => {
          if (!cancelled) {
            setChildren(rows);
            setSelected((value) => Math.min(value, Math.max(0, rows.length - 1)));
          }
        })
        .catch(() => {
          if (!cancelled) setChildren([]);
        });
    };
    refresh();
    if (['succeeded', 'failed', 'cancelled', 'expired'].includes(item.status)) {
      return () => {
        cancelled = true;
      };
    }
    const timer = window.setInterval(refresh, 2_500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [item.toolName, parentRunId, item.status]);

  const child = children[selected];
  useEffect(() => {
    if (!child) {
      setEvents([]);
      return;
    }
    let cancelled = false;
    const refresh = () => {
      void listRuntimeEvents(child.id, 0)
        .then((response) => {
          if (!cancelled)
            setEvents(
              response.items.map((event) => ({
                type: event.type,
                public_summary: event.public_summary
              }))
            );
        })
        .catch(() => {
          if (!cancelled) setEvents([]);
        });
    };
    refresh();
    if (['completed', 'succeeded', 'failed', 'cancelled', 'expired'].includes(child.status)) {
      return () => {
        cancelled = true;
      };
    }
    const timer = window.setInterval(refresh, 2_500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [child]);

  if (item.toolName !== 'spawn_subagents' || children.length === 0) return null;
  return (
    <section className='cr-subagent-viewer' aria-label='子 Agent 执行记录'>
      <header className='cr-subagent-viewer-header'>
        <span>子 Agent</span>
        <span>
          {selected + 1} / {children.length}
        </span>
      </header>
      {child && (
        <div className='cr-subagent-viewer-body'>
          <strong>{child.profile || '子 Agent'} 子 Agent</strong>
          <small>
            {child.status === 'completed' || child.status === 'succeeded'
              ? '已完成'
              : child.status === 'failed'
                ? '失败'
                : child.status === 'cancelled'
                  ? '已取消'
                  : '执行中'}
          </small>
          {events
            .filter((event) => event.type.startsWith('capability.'))
            .map((event, index) => (
              <p key={`${child.id}-${index}`}>{event.public_summary}</p>
            ))}
        </div>
      )}
      {children.length > 1 && (
        <div className='cr-subagent-viewer-actions'>
          <Button
            type='button'
            disabled={selected === 0}
            onClick={() => setSelected((value) => Math.max(0, value - 1))}
            size='sm'
            variant='outline'
          >
            查看上一个子 Agent
          </Button>
          <Button
            type='button'
            disabled={selected === children.length - 1}
            onClick={() => setSelected((value) => Math.min(children.length - 1, value + 1))}
            size='sm'
            variant='outline'
          >
            查看下一个子 Agent
          </Button>
        </div>
      )}
      {onOpenSubagents && parentRunId ? (
        <Button
          type='button'
          size='sm'
          variant='outline'
          onClick={() => onOpenSubagents(parentRunId)}
        >
          <PanelRightIcon data-icon='inline-start' aria-hidden='true' />
          在右侧查看协作任务
        </Button>
      ) : null}
    </section>
  );
}

function DeepResearchRuntime({ items }: { items: AssistantExecutionItem[] }) {
  const [open, setOpen] = useState(false);
  const research = items.find(
    (item) => item.toolName === 'start_deep_research' || item.presentationKind === 'deep_research'
  );
  const result: Record<string, unknown> =
    research?.result && typeof research.result === 'object' ? research.result : {};
  const phase =
    research?.status === 'failed'
      ? 'failed'
      : typeof result.phase === 'string'
        ? result.phase
        : 'scope';
  const active = research ? statusIsActive(research.status) : false;
  const phaseLabels: Record<string, string> = {
    scope: '确定范围',
    plan: '制定计划',
    retrieve: '检索来源',
    read: '读取正文',
    verify: '核验证据',
    synthesize: '综合结论',
    package: '整理报告',
    completed: '报告可查看',
    failed: '需要处理'
  };
  const phases = ['scope', 'plan', 'retrieve', 'read', 'verify', 'synthesize', 'package'];
  const phaseIndex = Math.max(0, phases.indexOf(phase));
  const fallbackSources = items
    .filter((item) => item.toolName === 'web_search')
    .flatMap((item) => {
      const candidate =
        item.result && typeof item.result === 'object'
          ? (item.result as Record<string, unknown>).items
          : null;
      return Array.isArray(candidate)
        ? candidate.filter((value): value is Record<string, unknown> =>
            Boolean(value && typeof value === 'object')
          )
        : [];
    })
    .map((source, index) => ({
      source_id: valueText(source.source_id) || `S${index + 1}`,
      title: source.title,
      url: source.url,
      status: 'candidate'
    }));
  const sources: Record<string, unknown>[] = Array.isArray(result.sources)
    ? result.sources.filter((value): value is Record<string, unknown> =>
        Boolean(value && typeof value === 'object')
      )
    : fallbackSources;
  const claims = Array.isArray(result.claims)
    ? result.claims.filter((value): value is Record<string, unknown> =>
        Boolean(value && typeof value === 'object')
      )
    : [];
  const report = typeof result.report === 'string' ? result.report.trim() : '';
  const sourceCount =
    typeof result.source_count === 'number' ? result.source_count : sources.length;
  const claimCount = typeof result.claim_count === 'number' ? result.claim_count : claims.length;

  return (
    <section
      className={`cr-deep-research-runtime${active ? ' is-live' : ''}`}
      aria-label='深度调研运行状态'
    >
      <header>
        <span className={active ? 'cr-live-label' : undefined}>深度调研</span>
        <small className={active ? 'cr-live-label' : undefined}>
          {phaseLabels[phase] || '研究结果'}
        </small>
      </header>
      <ol className='cr-deep-research-stages' aria-label='调研阶段'>
        {phases.map((name, index) => (
          <li
            className={
              index < phaseIndex || phase === 'completed'
                ? 'is-complete'
                : index === phaseIndex && active
                  ? 'is-active'
                  : undefined
            }
            key={name}
          >
            <span>{phaseLabels[name]}</span>
          </li>
        ))}
      </ol>
      {(sourceCount > 0 || claimCount > 0) && (
        <div className='cr-deep-research-counts'>
          {sourceCount > 0 && (
            <span>
              <Globe2Icon size={13} />
              {sourceCount} 个来源
            </span>
          )}
          {claimCount > 0 && (
            <span>
              <FileCheck2Icon size={13} />
              {claimCount} 条主张
            </span>
          )}
        </div>
      )}
      {sources.length > 0 && (
        <details
          className='cr-deep-research-process'
          open={open}
          onToggle={(event) => setOpen(event.currentTarget.open)}
        >
          <summary>查看调研过程</summary>
          <div className='cr-deep-research-sources'>
            {sources.map((source) => {
              const url = publicUrl(source.url)?.href;
              const title = valueText(source.title) || url || '公开来源';
              return (
                <a
                  href={url || undefined}
                  key={valueText(source.source_id) || title}
                  rel='noreferrer'
                  target='_blank'
                >
                  <Globe2Icon size={13} />
                  <span>
                    <strong>{title}</strong>
                    <small>{valueText(source.domain) || (url ? new URL(url).hostname : '')}</small>
                  </span>
                </a>
              );
            })}
          </div>
        </details>
      )}
      {claims.length > 0 && (
        <details className='cr-deep-research-process'>
          <summary>查看核验主张</summary>
          <ul className='cr-deep-research-claims'>
            {claims.map((claim, index) => (
              <li key={valueText(claim.claim_id) || `${index}-${valueText(claim.claim)}`}>
                <FileCheck2Icon size={13} />
                <span>{valueText(claim.claim)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
      {report && (
        <details className='cr-deep-research-process'>
          <summary>
            <FileTextIcon size={13} />
            打开研究报告
          </summary>
          <article className='cr-deep-research-report'>{report}</article>
        </details>
      )}
    </section>
  );
}

function TaskTurn({
  turn,
  title,
  t,
  onCancelWorkflow,
  onConfigureProvider,
  onOpenWorkflowCanvas,
  onOpenSubagents,
  cancellingRunId
}: {
  turn: ActivityTurn;
  title?: string;
  t: Translate;
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
  onOpenSubagents?: (parentRunId: string) => void;
  cancellingRunId: string | null;
}) {
  const tone = aggregateStatus(turn.items);
  const active = statusIsActive(tone);
  const [open, setOpen] = useState(false);
  const summary = displayGroupSummary(turn.items, t);
  const presentation = turn.items.find((item) => item.presentationKind);
  const deepResearch = presentation?.presentationKind === 'deep_research';
  const actionTitle = title || presentation?.presentationTitle || summary;
  const secondarySummary = title || presentation?.presentationTitle ? summary : '';

  return (
    <section className={`cr-task-turn is-${tone}${active ? ' is-live' : ''}`} data-status={tone}>
      <Button
        type='button'
        className={`cr-task-turn-summary${active ? ' is-live' : ''}`}
        aria-expanded={open}
        aria-busy={active || undefined}
        onClick={() => setOpen((current) => !current)}
        size='default'
        variant='ghost'
      >
        <span>
          <span className={active ? 'cr-live-label' : undefined}>{actionTitle}</span>
          {secondarySummary && <small>{secondarySummary}</small>}
        </span>
        <span className={`cr-group-status is-${tone}`}>
          {active && <Loader2Icon className='cr-group-spinner' size={13} />}
          <ChevronDownIcon size={14} />
        </span>
      </Button>
      <div className={`cr-command-grid${open ? ' is-open' : ''}`}>
        <div className='cr-command-grid-inner'>
          <div className='cr-run-detail'>
            {deepResearch ? (
              <DeepResearchRuntime items={turn.items} />
            ) : (
              turn.items.map((item) => (
                <div key={item.toolCallId || item.id}>
                  <SubagentExecutionViewer item={item} onOpenSubagents={onOpenSubagents} />
                  <ToolStep
                    item={item}
                    t={t}
                    onCancelWorkflow={onCancelWorkflow}
                    onConfigureProvider={onConfigureProvider}
                    onOpenWorkflowCanvas={onOpenWorkflowCanvas}
                    isCancelling={cancellingRunId === item.runtimeRunId}
                  />
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export function ClaudeActivityTimeline({
  items,
  taskTitle,
  nested = false,
  onCancelWorkflow,
  onConfigureProvider,
  onOpenWorkflowCanvas,
  onOpenSubagents
}: ClaudeActivityTimelineProps) {
  const { t } = useTranslation('ai-assistant');
  // Child runs have their own environment surface. Keeping them out of the
  // parent chronology prevents parallel work from becoming a second flattened
  // conversation inside the same timeline.
  const timelineItems = useMemo(
    () => (nested ? items : items.filter((item) => !item.parentRuntimeRunId)),
    [items, nested]
  );
  const tone = aggregateStatus(timelineItems);
  const [cancellingRunId, setCancellingRunId] = useState<string | null>(null);
  const turns = useMemo(() => groupActivityTurns(timelineItems), [timelineItems]);

  if (timelineItems.length === 0) return null;

  const requestCancellation = async (runtimeRunId: string) => {
    if (!onCancelWorkflow || cancellingRunId) return;
    setCancellingRunId(runtimeRunId);
    try {
      await onCancelWorkflow(runtimeRunId);
    } finally {
      setCancellingRunId(null);
    }
  };

  return (
    <div
      className={`assistant-claude-timeline cr-tool-group${nested ? ' cr-tool-group-nested' : ''}${tone === 'succeeded' ? ' is-quiet' : ''}`}
      data-testid='assistant-activity-timeline'
      data-status={tone}
    >
      <div className='cr-task-turns'>
        {turns.map((turn) => (
          <TaskTurn
            key={turn.id}
            turn={turn}
            title={taskTitle}
            t={t}
            onCancelWorkflow={onCancelWorkflow ? requestCancellation : undefined}
            onConfigureProvider={onConfigureProvider}
            onOpenWorkflowCanvas={onOpenWorkflowCanvas}
            onOpenSubagents={onOpenSubagents}
            cancellingRunId={cancellingRunId}
          />
        ))}
      </div>
    </div>
  );
}

export { ClaudeActivityTimeline as AssistantActivityTimeline };
