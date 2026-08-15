import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleDashedIcon,
  CircleXIcon,
  DownloadIcon,
  ExternalLinkIcon,
  FileCheck2Icon,
  FileSearchIcon,
  FolderOpenIcon,
  Globe2Icon,
  Loader2Icon,
  TimerIcon,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { downloadAssistantArtifact } from "@/lib/api";
import type {
  AssistantExecutionItem,
  WorkflowNodeProgress,
} from "@/lib/ai-assistant-store";
import {
  getAssistantToolIcon,
  getAssistantToolLabel,
} from "./assistant-tool-metadata";
import "./claude-activity-timeline.css";

type ActivityStatus = AssistantExecutionItem["status"];
type Translate = (key: string, options?: Record<string, unknown>) => string;

interface ClaudeActivityTimelineProps {
  items: AssistantExecutionItem[];
  taskTitle?: string;
  nested?: boolean;
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
}

function statusIsActive(status: ActivityStatus) {
  return status === "running" || status === "pending";
}

function aggregateStatus(items: AssistantExecutionItem[]): ActivityStatus {
  if (items.some((item) => item.status === "failed")) return "failed";
  if (items.some((item) => statusIsActive(item.status))) return "running";
  if (items.some((item) => item.status === "cancelled")) return "cancelled";
  return "succeeded";
}

function statusText(status: ActivityStatus, t: Translate) {
  return t(`activity.status.${status}`, { defaultValue: status });
}

function publicText(value: string | undefined) {
  if (!value) return "";
  // Runtime summaries are already redacted at the API boundary. This second
  // guard prevents legacy raw tool envelopes from reaching the UI.
  if (/tool_call_id=|content=['"]?\{|name=['"]?[a-z_]+['"]?/i.test(value)) {
    return "";
  }
  return value.trim();
}

function displaySummary(item: AssistantExecutionItem, t: Translate) {
  const summary = publicText(item.summary);
  if (summary) return summary;
  if (item.errorCode) {
    return t(`activity.failure.${item.errorCode}`, {
      defaultValue: t("activity.failure.workflow_internal_error", {
        defaultValue: "The workflow could not finish safely. Please try again later.",
      }),
    });
  }
  if (item.status === "failed") {
    return t("activity.failure.workflow_internal_error", {
      defaultValue: "The operation could not finish safely. Please try again later.",
    });
  }
  return "";
}

interface SearchSource {
  title: string;
  url: string;
  snippet: string;
  domain: string;
}

function searchSources(item: AssistantExecutionItem): SearchSource[] {
  if (item.toolName !== "web_search" || !Array.isArray(item.result?.items)) return [];

  return item.result.items.flatMap((candidate) => {
    if (!candidate || typeof candidate !== "object") return [];
    const source = candidate as Record<string, unknown>;
    const title = typeof source.title === "string" ? source.title.trim() : "";
    const url = typeof source.url === "string" ? source.url.trim() : "";
    const snippet = typeof source.snippet === "string" ? source.snippet.trim() : "";

    try {
      const parsed = new URL(url);
      if ((parsed.protocol !== "http:" && parsed.protocol !== "https:") || !title) return [];
      return [{ title, url: parsed.href, snippet, domain: parsed.hostname.replace(/^www\./, "") }];
    } catch {
      return [];
    }
  });
}

function WebSearchSources({ item, t }: { item: AssistantExecutionItem; t: Translate }) {
  const sources = searchSources(item);
  if (sources.length === 0) return null;

  const query = typeof item.result?.query === "string" ? item.result.query : "";
  const count = typeof item.result?.count === "number" ? item.result.count : sources.length;

  return (
    <section
      className="cr-search-evidence"
      aria-label={t("activity.searchSources", { defaultValue: "Search sources" })}
    >
      <header className="cr-search-evidence-header">
        <span>
          <Globe2Icon size={14} />
          {query
            ? t("activity.searchSourcesFor", {
              query,
              defaultValue: `Search results for "${query}"`,
            })
            : t("activity.searchSources", { defaultValue: "Search sources" })}
        </span>
        <small>{t("activity.searchResultCount", { count, defaultValue: `${count} results` })}</small>
      </header>
      <div className="cr-search-source-list">
        {sources.map((source) => (
          <a
            className="cr-search-source"
            href={source.url}
            key={source.url}
            rel="noreferrer"
            target="_blank"
          >
            <Globe2Icon aria-hidden="true" size={13} />
            <span className="cr-search-source-title">{source.title}</span>
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
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed : null;
  } catch {
    return null;
  }
}

// Timeline entries are also rendered in embedded previews that do not mount a
// React Router. Keep structured actions functional in both places.
function navigateToInternalRoute(route: string) {
  if (typeof window === "undefined") return;
  window.history.pushState({}, "", route);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function remoteDocumentCandidates(item: AssistantExecutionItem): RemoteDocumentCandidate[] {
  if (item.toolName !== "discover_remote_documents" || !Array.isArray(item.result?.items)) return [];
  return item.result.items.flatMap((candidate) => {
    if (!candidate || typeof candidate !== "object") return [];
    const raw = candidate as Record<string, unknown>;
    const parsed = publicUrl(raw.url);
    const filename = typeof raw.filename === "string" ? raw.filename.trim() : "";
    const title = typeof raw.title === "string" ? raw.title.trim() : "";
    if (!parsed || !filename) return [];
    return [{
      filename,
      title,
      url: parsed.href,
      contentTypeHint: typeof raw.content_type_hint === "string" ? raw.content_type_hint.trim() : "",
      domain: parsed.hostname.replace(/^www\./, ""),
    }];
  });
}

function RemoteDocumentDiscovery({ item }: { item: AssistantExecutionItem }) {
  const candidates = remoteDocumentCandidates(item);
  if (!candidates.length) return null;
  return (
    <section className="cr-remote-materials" aria-label="发现的远程资料附件">
      <header>
        <span><FileSearchIcon size={14} />发现 {candidates.length} 个可入库附件</span>
        <small>尚未下载</small>
      </header>
      <p>确认具体文件后，Agent 才会将它保存到项目资料包并启动解析。</p>
      <div className="cr-remote-material-list">
        {candidates.map((candidate) => (
          <a href={candidate.url} key={candidate.url} rel="noreferrer" target="_blank">
            <FileSearchIcon aria-hidden="true" size={13} />
            <span>
              <strong>{candidate.filename}</strong>
              <small>{candidate.title || candidate.domain}{candidate.contentTypeHint ? ` · ${candidate.contentTypeHint}` : ""}</small>
            </span>
            <ExternalLinkIcon aria-hidden="true" size={13} />
          </a>
        ))}
      </div>
    </section>
  );
}

function remoteParseStatus(value: unknown) {
  if (value === "not_applicable") return "已归档，无需解析";
  if (value === "parsed") return "已完成解析";
  if (value === "failed") return "解析需要处理";
  if (value === "parsing") return "正在解析";
  return "等待解析";
}

function RemoteDocumentImport({ item }: { item: AssistantExecutionItem }) {
  if (item.toolName !== "fetch_url_to_project" || !item.result) return null;
  const filename = typeof item.result.filename === "string" ? item.result.filename.trim() : "";
  const documentId = typeof item.result.document_id === "string" ? item.result.document_id : "";
  const queued = item.result.status === "queued";
  if (!filename && !documentId && !queued) return null;
  const source = publicUrl(item.result.source_url);
  const bundle = typeof item.result.bundle_label === "string" && item.result.bundle_label.trim()
    ? item.result.bundle_label.trim()
    : "项目资料包";
  const parsingQueued = item.result.ingest_queued !== false;
  const storedWithoutParsing = item.result.storage_status === "stored_no_parse" || item.result.parse_status === "not_applicable";
  return (
    <section className="cr-remote-import" aria-label="远程资料导入状态">
      <header>
        <span><FileCheck2Icon size={14} />{queued ? "后台导入已排队" : "已加入项目资料包"}</span>
        <small className={queued || storedWithoutParsing || parsingQueued ? "is-ready" : "is-attention"}>{queued ? "下载中，完成后自动入库" : (storedWithoutParsing ? "已归档，无需解析" : (parsingQueued ? remoteParseStatus(item.result.parse_status) : "待重新投递解析"))}</small>
      </header>
      <strong>{filename || "远程资料下载任务"}</strong>
      <p><FolderOpenIcon aria-hidden="true" size={13} />资料包：{bundle}{storedWithoutParsing ? " · 可下载附件" : ""}</p>
      <div className="cr-remote-import-actions">
        <a href="/knowledge"><FolderOpenIcon aria-hidden="true" size={13} />查看资料中心</a>
        {source ? <a href={source.href} rel="noreferrer" target="_blank"><ExternalLinkIcon aria-hidden="true" size={13} />原始公开来源</a> : null}
      </div>
    </section>
  );
}

function displayGroupSummary(items: AssistantExecutionItem[], t: Translate) {
  const active = aggregateStatus(items);
  if (items.length === 1) {
    const item = items[0];
    const label = item.toolName
      ? getAssistantToolLabel(item.toolName, t)
      : t("activity.workflow.default", { defaultValue: "Workflow" });
    if (active === "succeeded") {
      // A turn heading should identify the action. Its returned explanation
      // belongs in the expandable trace, otherwise a raw provider summary
      // leaks into the collapsed chronology and turns it into a status card.
      return label;
    }
    return `${label} ${statusText(active, t).toLowerCase()}`;
  }
  if (active === "succeeded") {
    const latestSummary = [...items]
      .reverse()
      .map((item) => displaySummary(item, t))
      .find(Boolean);
    return latestSummary || t("activity.countTools", { count: items.length, tools: items.length });
  }
  return t("activity.groupSummary", {
    count: items.length,
    defaultValue: `${items.length} operations ${statusText(active, t).toLowerCase()}`,
  });
}

type ResultFact = {
  label: string;
  value: string;
};

function valueText(value: unknown) {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  return "";
}

function publicStatusText(value: unknown) {
  const status = valueText(value).toLowerCase();
  const labels: Record<string, string> = {
    ready: "已就绪",
    queued: "等待处理",
    pending: "等待处理",
    running: "处理中",
    processing: "处理中",
    succeeded: "已完成",
    completed: "已完成",
    failed: "失败",
    parsed: "已解析",
    indexed: "已可检索",
    stored: "已入库",
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
  add("交付物", "deliverable_title");
  add("文件", "filename");
  add("资料包", "bundle_label");
  add("导出格式", "format", (value) => {
    const text = valueText(value);
    return text ? text.toUpperCase() : "";
  });
  add("处理状态", "status", publicStatusText);
  add("解析状态", "parse_status", publicStatusText);
  add("入库状态", "storage_status", publicStatusText);
  add("附件数量", "attachment_count");
  add("已处理章节", "processed_count");
  add("待处理章节", "remaining_count");
  return facts;
}

function ResultFacts({ item }: { item: AssistantExecutionItem }) {
  const facts = resultFacts(item);
  const error = publicText(item.errorMessage) || (item.status === "failed" ? displaySummary(item, () => "") : "");
  if (!facts.length && !error && !item.errorCode) return null;
  return (
    <section className={`cr-result-facts${item.status === "failed" ? " is-failed" : ""}`} aria-label="本次操作结果">
      <header>{item.status === "failed" ? "失败详情" : "本次操作结果"}</header>
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
    </section>
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
  if (item.status === "succeeded") {
    return <span className="cr-step-symbol is-done"><CheckCircle2Icon size={14} /></span>;
  }
  if (item.status === "failed") {
    return <span className="cr-step-symbol is-note"><CircleXIcon size={14} /></span>;
  }
  if (item.status === "cancelled") {
    return <span className="cr-step-symbol is-note"><CircleDashedIcon size={14} /></span>;
  }
  return (
    <span className="cr-step-symbol cr-step-symbol-active" aria-hidden="true">
      <Loader2Icon size={13} />
    </span>
  );
}

function NodeSymbol({ node }: { node: WorkflowNodeProgress }) {
  if (node.status === "completed") return <CheckCircle2Icon className="cr-node-symbol is-complete" size={14} />;
  if (node.status === "failed") return <CircleXIcon className="cr-node-symbol is-failed" size={14} />;
  if (node.status === "running") return <Loader2Icon className="cr-node-symbol cr-node-spinner is-running" size={14} />;
  return <CircleDashedIcon className="cr-node-symbol is-pending" size={14} />;
}

function nodeLabel(node: WorkflowNodeProgress, t: Translate) {
  const labels: Record<string, string> = {
    supervisor: "Coordinate task",
    rfp_parser: "Parse requirements",
    memory_context: "Load memory context",
    knowledge_retriever: "Retrieve evidence",
    content_plan: "Plan content",
    section_drafter: "Draft section",
    quality_reviewer: "Review quality",
    human_approval: "Wait for approval",
    persist_result: "Save result",
    memory_proposals: "Propose memory updates",
  };
  return t(`activity.node.${node.name}`, {
    defaultValue: labels[node.name] ?? "Workflow step",
  });
}

function RuntimeTimeline({
  item,
  nodes,
  t,
}: {
  item: AssistantExecutionItem;
  nodes: WorkflowNodeProgress[];
  t: Translate;
}) {
  const hasRunningNode = nodes.some((node) => node.status === "running");
  const active = statusIsActive(item.status) || hasRunningNode;
  const [open, setOpen] = useState(() => active || item.status === "failed");
  const completed = nodes.filter((node) => node.status === "completed").length;
  const summary = t("activity.workflowProgress", { defaultValue: "Workflow steps" });

  useEffect(() => {
    if (active || item.status === "failed") setOpen(true);
  }, [active, item.status]);

  if (nodes.length === 0) return null;

  return (
    <section className="cr-analysis-runtime" data-testid={`assistant-runtime-${item.id}`}>
      <button
        type="button"
        className="cr-runtime-summary"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>
          <TimerIcon size={15} />
          {summary}
          <small className="cr-runtime-count">
            {completed}/{nodes.length}
          </small>
          <small className="cr-runtime-completion">
            {t("execution.nodesCompleted", {
              completed,
              total: nodes.length,
              defaultValue: `${completed} of ${nodes.length} steps completed`,
            })}
          </small>
        </span>
        <ChevronDownIcon size={14} />
      </button>
      <div className={`cr-runtime-grid${open ? " is-open" : ""}`}>
        <div className="cr-runtime-grid-inner">
          <div className={`cr-runtime-timeline${hasRunningNode ? " is-running" : ""}`}>
            {nodes.map((node) => (
              <div className={`cr-runtime-node is-thought${node.status === "running" ? " is-running" : ""}`} key={`${item.id}-${node.name}`}>
                <span className="cr-runtime-marker"><NodeSymbol node={node} /></span>
                <div className="cr-runtime-node-body">
                  <div className="cr-thought-copy">
                    <p>
                      <span>{nodeLabel(node, t)}</span>
                      <small>{statusText(node.status === "completed" ? "succeeded" : node.status === "failed" ? "failed" : node.status, t)}</small>
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
    ["DOCX", result.docx_download_path],
    ["XLSX", result.xlsx_download_path],
    [typeof result.format === "string" ? result.format.toUpperCase() : "PDF", result.download_path],
  ].filter((entry): entry is [string, string] => typeof entry[1] === "string");
  const [downloading, setDownloading] = useState<string | null>(null);
  const projectId = typeof result.project_id === "string" ? result.project_id : "";
  const deliverableId = typeof result.deliverable_id === "string" ? result.deliverable_id : "";
  const title = typeof result.deliverable_title === "string" && result.deliverable_title.trim()
    ? result.deliverable_title.trim()
    : "交付物";
  if (actions.length === 0 && !deliverableId) return null;
  return (
    <section className="cr-artifact-actions" aria-label="交付物操作">
      <header>
        <FileCheck2Icon size={14} />
        <span>{title}</span>
        <small>{actions.length > 0 ? "文件已生成" : "可在项目工作区查看"}</small>
      </header>
      <div className="cr-inline-actions">
      {actions.map(([format, path]) => (
        <button
          key={path}
          type="button"
          disabled={downloading !== null}
          onClick={() => {
            setDownloading(path);
            void downloadAssistantArtifact(path, `bidpilot-${format.toLowerCase()}.${format.toLowerCase()}`)
              .finally(() => setDownloading(null));
          }}
        >
          <DownloadIcon size={13} />
          {downloading === path
            ? t("activity.downloading", { defaultValue: "Downloading" })
            : t(`activity.download.${format.toLowerCase()}`, { defaultValue: `Download ${format}` })}
        </button>
      ))}
      {projectId && deliverableId && (
        <button
          type="button"
          onClick={() => navigateToInternalRoute(`/projects/${projectId}?surface=deliverables${deliverableId ? `&deliverable_id=${deliverableId}` : ""}`)}
        >
          <FolderOpenIcon size={13} />
          查看交付物
        </button>
      )}
      </div>
    </section>
  );
}

function WorkflowCanvasAction({
  item,
  onOpenWorkflowCanvas,
}: {
  item: AssistantExecutionItem;
  onOpenWorkflowCanvas?: (projectId: string) => void;
}) {
  const result = item.result ?? {};
  const projectId = typeof result.project_id === "string" ? result.project_id : "";
  if (item.kind !== "workflow" || !projectId) return null;
  const sectionKey = typeof result.section_key === "string" ? result.section_key : "";
  return (
    <section className="cr-artifact-actions" aria-label="响应工作流操作">
      <header>
        <TimerIcon size={14} />
        <span>响应工作流</span>
        <small>{sectionKey ? `章节：${sectionKey}` : "项目任务编排"}</small>
      </header>
      <div className="cr-inline-actions">
        <button
          type="button"
          onClick={() => {
            if (onOpenWorkflowCanvas) {
              onOpenWorkflowCanvas(projectId);
              return;
            }
            navigateToInternalRoute(`/projects/${projectId}?surface=workflow`);
          }}
        >
          <TimerIcon size={13} />
          打开任务编排画布
        </button>
      </div>
    </section>
  );
}

function StructuredUiAction({
  item,
  onOpenWorkflowCanvas,
}: {
  item: AssistantExecutionItem;
  onOpenWorkflowCanvas?: (projectId: string) => void;
}) {
  const rawAction = item.result?.ui_action;
  if (!rawAction || typeof rawAction !== "object" || Array.isArray(rawAction)) return null;
  const action = rawAction as Record<string, unknown>;
  const type = typeof action.type === "string" ? action.type : "";
  const label = typeof action.label === "string" && action.label.trim()
    ? action.label.trim()
    : "继续";
  const route = typeof action.route === "string" ? action.route : "";
  const href = publicUrl(action.href);

  // This is intentionally a small allow-list. Agent output can describe a
  // UI action, never inject arbitrary markup or event handlers into the app.
  if (type === "canvas" && route.startsWith("/projects")) {
    const projectId = /^\/projects\/([^?/#]+)/.exec(route)?.[1];
    return (
      <div className="cr-inline-actions cr-structured-action">
        <button
          type="button"
          onClick={() => {
            if (projectId && onOpenWorkflowCanvas) {
              onOpenWorkflowCanvas(projectId);
              return;
            }
            navigateToInternalRoute(route);
          }}
        >
          <TimerIcon size={13} />
          {label}
        </button>
      </div>
    );
  }
  if (type === "link" && href) {
    return (
      <div className="cr-inline-actions cr-structured-action">
        <a href={href.href} rel="noreferrer" target="_blank">
          <ExternalLinkIcon size={13} />
          {label}
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
  isCancelling,
}: {
  item: AssistantExecutionItem;
  t: Translate;
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
  isCancelling: boolean;
}) {
  const summary = displaySummary(item, t);
  const nodes = item.kind === "workflow" ? item.nodes ?? [] : [];
  const providerFailure = item.status === "failed" && Boolean(item.errorCode?.startsWith("provider_"));
  const canCancel = Boolean(item.runtimeRunId) && item.kind === "workflow" && statusIsActive(item.status) && !item.isCancellationRequested;

  return (
    <div className="cr-run-step-expand">
      {summary && <p className="cr-public-summary">{summary}</p>}
      {providerFailure && onConfigureProvider && (
        <button type="button" className="cr-inline-action" onClick={onConfigureProvider}>
          {t("activity.openProviderSettings", { defaultValue: "Open model settings" })}
        </button>
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
        <button
          type="button"
          className="cr-inline-action"
          disabled={isCancelling}
          onClick={() => void onCancelWorkflow(item.runtimeRunId!)}
        >
          {isCancelling
            ? t("activity.cancelling", { defaultValue: "Cancelling..." })
            : t("activity.cancelWorkflow", { defaultValue: "Cancel workflow" })}
        </button>
      )}
      {item.isCancellationRequested && item.status !== "cancelled" && (
        <p className="cr-public-muted">
          {t("activity.cancellationRequested", {
            defaultValue: "Cancellation requested. Stopping at a safe boundary.",
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
  isCancelling,
}: {
  item: AssistantExecutionItem;
  t: Translate;
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
  isCancelling: boolean;
}) {
  const [open, setOpen] = useState(() => statusIsActive(item.status) || item.status === "failed");
  const [renderDetail, setRenderDetail] = useState(() => statusIsActive(item.status) || item.status === "failed");
  const detailCloseTimer = useRef<number | null>(null);
  const previousStatus = useRef(item.status);
  const Icon: LucideIcon = getAssistantToolIcon(item);
  const label = item.toolName
    ? getAssistantToolLabel(item.toolName, t)
    : t("activity.workflow.default", { defaultValue: "Workflow" });
  const active = statusIsActive(item.status);

  useEffect(() => {
    if (active || item.status === "failed") {
      if (detailCloseTimer.current !== null) window.clearTimeout(detailCloseTimer.current);
      setRenderDetail(true);
      setOpen(true);
    } else if (statusIsActive(previousStatus.current)) {
      setOpen(false);
      detailCloseTimer.current = window.setTimeout(() => setRenderDetail(false), 320);
    }
    previousStatus.current = item.status;
    return () => {
      if (detailCloseTimer.current !== null) window.clearTimeout(detailCloseTimer.current);
    };
  }, [active, item.status]);

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
    <div className={`cr-run-step${open ? " is-expanded" : ""}`} data-testid={`assistant-activity-step-${item.toolCallId || item.id}`} data-status={item.status}>
      <div className="cr-run-step-row">
        <StepSymbol item={item} />
        <button
          type="button"
          className="cr-run-step-button"
          aria-expanded={open}
          aria-busy={active || undefined}
          aria-label={open ? `Hide ${label} details` : `Show ${label} details`}
          onClick={toggleDetail}
        >
          <span>
            <Icon className="cr-step-icon" size={13} />
            {label}
            <em className={`cr-step-status is-${item.status}`}>{statusText(item.status, t)}</em>
          </span>
          <ChevronDownIcon size={14} />
        </button>
      </div>
      <div className={`cr-command-grid${open ? " is-open" : ""}`}>
        <div className="cr-command-grid-inner">
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

function TaskTurn({
  turn,
  index,
  title,
  t,
  onCancelWorkflow,
  onConfigureProvider,
  onOpenWorkflowCanvas,
  cancellingRunId,
}: {
  turn: ActivityTurn;
  index: number;
  title?: string;
  t: Translate;
  onCancelWorkflow?: (runtimeRunId: string) => Promise<void>;
  onConfigureProvider?: () => void;
  onOpenWorkflowCanvas?: (projectId: string) => void;
  cancellingRunId: string | null;
}) {
  const tone = aggregateStatus(turn.items);
  const active = statusIsActive(tone);
  const [open, setOpen] = useState(() => active || tone === "failed");
  const previousTone = useRef(tone);
  const summary = displayGroupSummary(turn.items, t);
  const actionTitle = title;

  useEffect(() => {
    if (active || tone === "failed") setOpen(true);
    else if (statusIsActive(previousTone.current)) setOpen(false);
    previousTone.current = tone;
  }, [active, tone]);

  return (
    <section className={`cr-task-turn is-${tone}`}>
      <button
        type="button"
        className="cr-task-turn-summary"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>
          {actionTitle || t("activity.turnLabel", { index: index + 1, defaultValue: `执行回合 ${index + 1}` })}
          <small>{summary}</small>
        </span>
        <span className={`cr-group-status is-${tone}`}>
          {active && <Loader2Icon className="cr-group-spinner" size={13} />}
          {statusText(tone, t)}
          <ChevronDownIcon size={14} />
        </span>
      </button>
      <div className={`cr-command-grid${open ? " is-open" : ""}`}>
        <div className="cr-command-grid-inner">
          <div className="cr-run-detail">
            {turn.items.map((item) => (
              <ToolStep
                key={item.toolCallId || item.id}
                item={item}
                t={t}
                onCancelWorkflow={onCancelWorkflow}
                onConfigureProvider={onConfigureProvider}
                onOpenWorkflowCanvas={onOpenWorkflowCanvas}
                isCancelling={cancellingRunId === item.runtimeRunId}
              />
            ))}
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
}: ClaudeActivityTimelineProps) {
  const { t } = useTranslation("ai-assistant");
  const tone = aggregateStatus(items);
  const active = statusIsActive(tone);
  const [open, setOpen] = useState(() => active || tone === "failed");
  const previousTone = useRef(tone);
  const [cancellingRunId, setCancellingRunId] = useState<string | null>(null);
  const turns = useMemo(() => groupActivityTurns(items), [items]);
  const summary = useMemo(
    () => taskTitle || t("activity.taskSummary", {
      turns: turns.length,
      defaultValue: `任务执行 · ${turns.length} 个回合`,
    }),
    [taskTitle, t, turns.length],
  );

  useEffect(() => {
    if (active || tone === "failed") setOpen(true);
    else if (statusIsActive(previousTone.current)) setOpen(false);
    previousTone.current = tone;
  }, [active, tone]);

  if (items.length === 0) return null;

  const requestCancellation = async (runtimeRunId: string) => {
    if (!onCancelWorkflow || cancellingRunId) return;
    setCancellingRunId(runtimeRunId);
    try {
      await onCancelWorkflow(runtimeRunId);
    } finally {
      setCancellingRunId(null);
    }
  };

  if (nested) {
    return (
      <div className="assistant-claude-timeline cr-tool-group cr-tool-group-nested" data-testid="assistant-activity-timeline" data-status={tone}>
        <div className="cr-task-turns">
          {turns.map((turn, index) => (
            <TaskTurn
              key={turn.id}
              turn={turn}
              index={index}
              title={taskTitle}
              t={t}
              onCancelWorkflow={onCancelWorkflow ? requestCancellation : undefined}
              onConfigureProvider={onConfigureProvider}
              onOpenWorkflowCanvas={onOpenWorkflowCanvas}
              cancellingRunId={cancellingRunId}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <section className={`assistant-claude-timeline cr-tool-group${tone === "succeeded" ? " is-quiet" : ""}`} data-testid="assistant-activity-timeline" data-status={tone}>
      <button
        type="button"
        className="cr-tool-summary"
        aria-expanded={open}
        aria-label={open ? "Collapse activity details" : "Expand activity details"}
        aria-live={active ? "polite" : "off"}
        onClick={() => setOpen((current) => !current)}
      >
        <span>
          <TimerIcon size={15} />
          {summary}
        </span>
        <span className={`cr-group-status is-${tone}`}>
          {active && <Loader2Icon className="cr-group-spinner" size={13} />}
          {statusText(tone, t)}
          <ChevronDownIcon size={14} />
        </span>
      </button>
      <div className={`cr-tool-grid${open ? " is-open" : ""}`}>
        <div className="cr-tool-grid-inner">
          <div className="cr-task-turns">
            {turns.map((turn, index) => (
              <TaskTurn
                key={turn.id}
                turn={turn}
                index={index}
                title={taskTitle}
                t={t}
              onCancelWorkflow={onCancelWorkflow ? requestCancellation : undefined}
              onConfigureProvider={onConfigureProvider}
              onOpenWorkflowCanvas={onOpenWorkflowCanvas}
              cancellingRunId={cancellingRunId}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export { ClaudeActivityTimeline as AssistantActivityTimeline };
