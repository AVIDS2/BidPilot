import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  ActivityIcon,
  AlertCircleIcon,
  ArrowRightIcon,
  ArrowUpRightIcon,
  BotIcon,
  CheckCircle2Icon,
  ChevronRightIcon,
  CircleDotIcon,
  DownloadIcon,
  FileIcon,
  FileWarningIcon,
  FileTextIcon,
  FolderKanbanIcon,
  ImageIcon,
  LibraryBigIcon,
  LoaderCircleIcon,
  SearchIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  UploadIcon,
  WorkflowIcon,
} from "lucide-react";
import {
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  createBundle,
  getApiErrorDetail,
  getDocumentBlob,
  listKnowledgePortfolio,
  listBundles,
  listDocuments,
  listProjectMemory,
  listProjects,
  listRuntimeEvents,
  listRuntimeRuns,
  reingestBundle,
  uploadDocument,
  getReadinessSummary,
  type BidReadinessSummary,
  type BundleRead,
  type MemoryRead,
  type ProjectRead,
  type RuntimeEventRead,
  type RuntimeRunListItem,
  type SourceDocumentRead,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { cn } from "@/lib/utils";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";


type RunFilter = "all" | "active" | "approval" | "failed" | "completed";

const ACTIVE_RUN_STATUSES = new Set(["queued", "running", "cancel_requested"]);
const COMPLETED_RUN_STATUSES = new Set(["succeeded", "cancelled", "expired"]);
const EMPTY_DASHBOARD_PROJECTS: ProjectRead[] = [];
const EMPTY_DASHBOARD_RUNS: RuntimeRunListItem[] = [];

function documentQueueErrorMessage(error: unknown) {
  const detail = getApiErrorDetail(error);
  const message = typeof detail === "string" ? detail : "";
  if (/indexing|index|quota|limit/i.test(message)) {
    return "当前工作区的解析额度已用尽。文件已保留，可下载原件，或在额度恢复后重新解析。";
  }
  return "文件已上传，但未能进入解析队列。可在资料页查看处理状态后重新解析。";
}

function formatDate(value: string | null) {
  if (!value) return "未开始";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatInboxTime(value: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  const elapsedMinutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60_000));
  if (elapsedMinutes < 1) return "刚刚";
  if (elapsedMinutes < 60) return `${elapsedMinutes}m`;

  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) return `${elapsedHours}h`;
  if (elapsedHours < 48) return "昨天";

  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(date);
}

function runStatusMeta(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "awaiting_approval") return { label: "等待审批", tone: "approval" };
  if (normalized === "failed") return { label: "失败", tone: "failed" };
  if (ACTIVE_RUN_STATUSES.has(normalized)) return { label: normalized === "queued" ? "排队中" : "运行中", tone: "active" };
  if (COMPLETED_RUN_STATUSES.has(normalized)) return { label: normalized === "succeeded" ? "已完成" : "已停止", tone: "complete" };
  return { label: status, tone: "neutral" };
}

function runKindLabel(kind: string) {
  if (kind === "assistant_turn") return "Agent 执行";
  if (kind === "workflow_bridge") return "工作流执行";
  return "运行记录";
}

function RunState({ status }: { status: string }) {
  const meta = runStatusMeta(status);
  return (
    <span className={cn("wb-run-state", `wb-run-state--${meta.tone}`)}>
      <i aria-hidden="true" />
      {meta.label}
    </span>
  );
}

function RunIcon({ kind }: { kind: string }) {
  if (kind === "assistant_turn") return <BotIcon aria-hidden="true" />;
  if (kind === "workflow_bridge") return <WorkflowIcon aria-hidden="true" />;
  return <ActivityIcon aria-hidden="true" />;
}

function runTitle(run: RuntimeRunListItem) {
  return run.project_name ? `${runKindLabel(run.kind)} · ${run.project_name}` : runKindLabel(run.kind);
}

function filterRuns(runs: RuntimeRunListItem[], filter: RunFilter) {
  if (filter === "all") return runs;
  if (filter === "active") return runs.filter((run) => ACTIVE_RUN_STATUSES.has(run.status));
  if (filter === "approval") return runs.filter((run) => run.status === "awaiting_approval");
  if (filter === "failed") return runs.filter((run) => run.status === "failed");
  return runs.filter((run) => COMPLETED_RUN_STATUSES.has(run.status));
}

function EmptySplitState({
  icon: Icon,
  title,
  detail,
  action,
}: {
  icon: typeof FolderKanbanIcon;
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <Empty className="wb-empty-split-state border-0">
      <EmptyHeader>
        <EmptyMedia variant="icon"><Icon aria-hidden="true" /></EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{detail}</EmptyDescription>
      </EmptyHeader>
      {action ? <EmptyContent>{action}</EmptyContent> : null}
    </Empty>
  );
}

const DASHBOARD_ACTIVE_STATUSES = new Set(["active", "draft", "in_progress"]);

function projectDisplayName(project: ProjectRead) {
  return project.name || project.slug || project.id;
}

type DashboardProjectHealth = {
  project: ProjectRead;
  summary: BidReadinessSummary | null;
  blockerCount: number;
};

function projectHealthTone(row: DashboardProjectHealth) {
  if (!row.summary || row.summary.counts.total === 0) return "neutral";
  if (row.blockerCount > 0 || row.summary.readiness_score < 55) return "risk";
  if (row.summary.readiness_score < 80) return "watch";
  return "healthy";
}

function readinessLabel(summary: BidReadinessSummary | null) {
  if (!summary || summary.counts.total === 0) return "尚未评估";
  return `${Math.round(summary.readiness_score)}%`;
}

const dashboardReadinessChartConfig = {
  readiness: { label: "就绪度", color: "#348463" },
} satisfies ChartConfig;

export function DashboardPageV2() {
  const navigate = useNavigate();
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: listProjects, staleTime: 30_000 });
  const runsQuery = useQuery({ queryKey: ["runtime-runs", 100], queryFn: () => listRuntimeRuns(100), staleTime: 10_000 });
  const projects = projectsQuery.data ?? EMPTY_DASHBOARD_PROJECTS;
  const runs = runsQuery.data ?? EMPTY_DASHBOARD_RUNS;
  const readinessQueries = useQueries({
    queries: projects.map((project) => ({
      queryKey: ["readiness-summary", project.id],
      queryFn: () => getReadinessSummary(project.id),
      staleTime: 30_000,
      retry: false,
    })),
  });

  const healthRows = useMemo<DashboardProjectHealth[]>(() => projects.map((project, index) => {
    const summary = readinessQueries[index]?.data ?? null;
    const blockerIds = new Set([
      ...(summary?.mandatory_gaps ?? []).map((requirement) => requirement.id),
      ...(summary?.evidence_gaps ?? []).map((requirement) => requirement.id),
      ...(summary?.contradictions ?? []).map((requirement) => requirement.id),
      ...(summary?.overdue ?? []).map((requirement) => requirement.id),
    ]);
    return { project, summary, blockerCount: blockerIds.size };
  }).sort((left, right) => right.blockerCount - left.blockerCount || (left.summary?.readiness_score ?? -1) - (right.summary?.readiness_score ?? -1)), [projects, readinessQueries]);

  const activeProjects = projects.filter((project) => DASHBOARD_ACTIVE_STATUSES.has(project.status.toLowerCase()));
  const assessedRows = healthRows.filter((row) => row.summary && row.summary.counts.total > 0);
  const readinessAverage = assessedRows.length
    ? Math.round(assessedRows.reduce((total, row) => total + (row.summary?.readiness_score ?? 0), 0) / assessedRows.length)
    : null;
  const coveredRequirements = assessedRows.reduce((total, row) => total + (row.summary?.counts.covered ?? 0), 0);
  const totalRequirements = assessedRows.reduce((total, row) => total + (row.summary?.counts.total ?? 0), 0);
  const blockerCount = healthRows.reduce((total, row) => total + row.blockerCount, 0);
  const approvalRuns = runs.filter((run) => run.status === "awaiting_approval" && run.project_id);
  const completedProjectCount = projects.filter((project) => project.status.toLowerCase() === "completed").length;
  const leadProject = healthRows.find((row) => DASHBOARD_ACTIVE_STATUSES.has(row.project.status.toLowerCase()))?.project ?? projects[0] ?? null;
  const attentionRows = healthRows.filter((row) => row.blockerCount > 0).slice(0, 3);
  const unassessedProjectCount = Math.max(0, projects.length - assessedRows.length);
  const readinessChartData = useMemo(() => assessedRows
    .slice()
    .sort((left, right) => (left.summary?.readiness_score ?? 0) - (right.summary?.readiness_score ?? 0))
    .slice(0, 6)
    .map((row) => ({
      project: projectDisplayName(row.project),
      readiness: Math.round(row.summary?.readiness_score ?? 0),
      blockers: row.blockerCount,
    })), [assessedRows]);
  const openProject = (projectId: string | null | undefined) => {
    if (projectId) navigate(`/projects/${projectId}`);
    else navigate("/projects");
  };
  const openCreateProject = () => navigate("/projects", { state: { openCreateProject: true } });

  return (
    <section className="wb-dashboard" aria-labelledby="dashboard-title">
      <div className="wb-dashboard-hero">
        <div className="wb-dashboard-intro">
          <header className="wb-dashboard-header">
            <div>
              <h1 id="dashboard-title">投标工作台</h1>
              <p>聚焦正在推进的机会、明确缺口和下一步处理事项。</p>
            </div>
            <div className="wb-dashboard-actions">
              <Button onClick={openCreateProject} size="sm">新建机会 <ArrowUpRightIcon aria-hidden="true" data-icon="inline-end" /></Button>
              <Button onClick={() => navigate("/projects")} size="sm" variant="outline">查看全部</Button>
            </div>
          </header>

          <section className="wb-dashboard-facts" aria-label="当前工作概况">
            <div><span className="wb-dashboard-fact-icon"><FolderKanbanIcon aria-hidden="true" /></span><span><small>进行中的机会</small><strong>{activeProjects.length}</strong><em>{projects.length} 个项目已纳入工作区</em></span></div>
            <div><span className="wb-dashboard-fact-icon"><ShieldCheckIcon aria-hidden="true" /></span><span><small>平均就绪度</small><strong>{readinessAverage === null ? "--" : `${readinessAverage}%`}</strong><em>{assessedRows.length ? `${assessedRows.length} 个项目已有要求基线` : "等待资料解析"}</em></span></div>
            <div><span className="wb-dashboard-fact-icon is-attention"><AlertCircleIcon aria-hidden="true" /></span><span><small>需要团队决定</small><strong>{blockerCount + approvalRuns.length}</strong><em>{blockerCount} 项缺口 · {approvalRuns.length} 项待审核</em></span></div>
            <div><span className="wb-dashboard-fact-icon"><DownloadIcon aria-hidden="true" /></span><span><small>完成交付</small><strong>{completedProjectCount}</strong><em>已完成并归档的项目</em></span></div>
          </section>
        </div>

        <section className="wb-dashboard-readiness-chart" aria-labelledby="portfolio-readiness-title">
          <header className="wb-dashboard-chart-header">
            <div>
              <h2 id="portfolio-readiness-title">项目就绪度</h2>
              <span>基于已识别要求、证据和分配情况计算</span>
            </div>
          </header>
          {readinessChartData.length ? (
            <ChartContainer className="h-[264px] w-full" config={dashboardReadinessChartConfig}>
              <BarChart accessibilityLayer data={readinessChartData} margin={{ top: 12, right: 6, left: -18, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis axisLine={false} dataKey="project" tickLine={false} tickMargin={10} minTickGap={18} />
                <YAxis axisLine={false} domain={[0, 100]} tickFormatter={(value) => `${value}%`} tickLine={false} width={40} />
                <ChartTooltip cursor={{ fill: "#f5f6f6" }} content={<ChartTooltipContent formatter={(value, _name, item) => [`${value}% · ${item.payload.blockers} 项缺口`, "就绪度"]} />} />
                <Bar dataKey="readiness" fill="var(--color-readiness)" maxBarSize={44} radius={[5, 5, 0, 0]} />
              </BarChart>
            </ChartContainer>
          ) : (
            <div className="wb-dashboard-chart-empty">
              <strong>尚无可计算的项目就绪度</strong>
              <span>{unassessedProjectCount ? `${unassessedProjectCount} 个项目尚未识别出要求，上传并解析招标资料后会显示这里。` : "建立项目并完成要求识别后会显示这里。"}</span>
            </div>
          )}
          <footer>{assessedRows.length} 个已评估项目 · {unassessedProjectCount} 个尚未建立要求基线</footer>
        </section>
      </div>

      <div className="wb-dashboard-bottom">
        <section className="wb-dashboard-projects" aria-labelledby="project-progress-title">
          <header className="wb-dashboard-section-header">
            <div><h2 id="project-progress-title">项目推进</h2><p>优先处理就绪度较低或存在明确缺口的项目。</p></div>
            <Button onClick={() => navigate("/projects")} size="xs" variant="ghost">项目列表<ArrowRightIcon aria-hidden="true" data-icon="inline-end" /></Button>
          </header>
          <Card className="wb-dashboard-project-list" size="sm">
            {projectsQuery.isLoading ? <p className="wb-dashboard-project-list-status">正在读取项目与就绪度…</p> : null}
            {!projectsQuery.isLoading && !healthRows.length ? <Empty className="wb-dashboard-list-empty border-0"><EmptyHeader><EmptyTitle>还没有投标机会</EmptyTitle><EmptyDescription>新建机会并上传招标资料后，这里会持续汇总项目进展。</EmptyDescription></EmptyHeader><EmptyContent><Button onClick={openCreateProject} size="sm">新建机会</Button></EmptyContent></Empty> : null}
            {healthRows.slice(0, 6).map((row) => {
              const tone = projectHealthTone(row);
              const total = row.summary?.counts.total ?? 0;
              const covered = row.summary?.counts.covered ?? 0;
              return (
                <button className="wb-dashboard-project-row" key={row.project.id} onClick={() => openProject(row.project.id)} type="button">
                  <span className={`wb-dashboard-project-marker is-${tone}`} aria-hidden="true" />
                  <span className="wb-dashboard-project-copy"><strong>{projectDisplayName(row.project)}</strong><small>{row.project.scenario_package}</small></span>
                  <span className="wb-dashboard-project-metric"><small>就绪度</small><Badge className={`wb-dashboard-readiness is-${tone}`} variant="outline">{readinessLabel(row.summary)}</Badge></span>
                  <span className="wb-dashboard-project-metric"><small>要求承接</small><strong>{total ? `${covered} / ${total}` : "尚未提取"}</strong></span>
                  <span className={`wb-dashboard-project-metric ${row.blockerCount ? "is-risk" : ""}`}><small>待处理</small><strong>{row.blockerCount ? `${row.blockerCount} 项` : "无"}</strong></span>
                  <ChevronRightIcon aria-hidden="true" />
                </button>
              );
            })}
          </Card>
        </section>

        <aside className="wb-dashboard-attention" aria-labelledby="attention-title">
          <header className="wb-dashboard-section-header">
            <div><h2 id="attention-title">需要你处理</h2><p>只显示业务缺口和等待团队确认的事项。</p></div>
            <Button onClick={() => navigate("/my-work")} size="xs" variant="ghost">全部查看<ArrowRightIcon aria-hidden="true" data-icon="inline-end" /></Button>
          </header>
          <div className="wb-dashboard-attention-content">
            {attentionRows.map((row) => (
              <button className="wb-dashboard-attention-row" key={row.project.id} onClick={() => openProject(row.project.id)} type="button">
                <AlertCircleIcon aria-hidden="true" />
                <span><strong>{projectDisplayName(row.project)}</strong><small>{row.blockerCount} 项资料或要求缺口待处理</small></span>
                <ChevronRightIcon aria-hidden="true" />
              </button>
            ))}
            {approvalRuns.slice(0, 3).map((run) => (
              <button className="wb-dashboard-attention-row" key={run.id} onClick={() => openProject(run.project_id)} type="button">
                <ShieldCheckIcon aria-hidden="true" />
                <span><strong>{run.project_name || "项目审核"}</strong><small>有一项响应内容等待团队决定</small></span>
                <ChevronRightIcon aria-hidden="true" />
              </button>
            ))}
            {!attentionRows.length && !approvalRuns.length ? <Empty className="wb-dashboard-empty-state border-0"><EmptyHeader><EmptyMedia variant="icon"><CheckCircle2Icon aria-hidden="true" /></EmptyMedia><EmptyTitle>当前没有待处理事项</EmptyTitle><EmptyDescription>项目中的资料缺口和待审核内容会在这里汇总。</EmptyDescription></EmptyHeader></Empty> : null}
          </div>
        </aside>
      </div>
    </section>
  );
}

export function InboxPageV2() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: listProjects, staleTime: 30_000 });
  const runsQuery = useQuery({ queryKey: ["runtime-runs", 30], queryFn: () => listRuntimeRuns(30), staleTime: 10_000 });
  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data]);
  const inboxRuns = useMemo(() => [...runs].filter((run) => (
    run.status === "awaiting_approval" || run.status === "failed"
  )).sort((left, right) => {
    const leftNeedsApproval = left.status === "awaiting_approval";
    const rightNeedsApproval = right.status === "awaiting_approval";
    if (leftNeedsApproval !== rightNeedsApproval) return leftNeedsApproval ? -1 : 1;
    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  }), [runs]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedRunId((current) => (
      current && inboxRuns.some((run) => run.id === current)
        ? current
        : inboxRuns[0]?.id ?? null
    ));
  }, [inboxRuns]);

  const selectedRun = inboxRuns.find((run) => run.id === selectedRunId) ?? null;
  const project = projectsQuery.data?.find((candidate) => candidate.id === selectedRun?.project_id) ?? null;

  const approvalCount = inboxRuns.filter((run) => run.status === "awaiting_approval").length;
  const failedCount = inboxRuns.filter((run) => run.status === "failed").length;

  return (
    <section className="wb-workboard-page wb-inbox-workboard" aria-labelledby="inbox-title">
      <header className="wb-workboard-header">
        <div><p className="wb-eyebrow">Team attention</p><h1 id="inbox-title">待处理</h1><p>这里不是运行日志。只保留需要团队决策、恢复或核验的事项，已完成记录统一留在“运行”。</p></div>
        <Button onClick={() => void runsQuery.refetch()} size="sm" variant="outline"><RefreshCwIcon aria-hidden="true" data-icon="inline-start" />刷新</Button>
      </header>
      <ScrollArea className="wb-workboard-scroll"><div className="wb-workboard-content">
        <section className="wb-workboard-summary" aria-label="待处理概览"><div><span>待处理事项</span><strong>{inboxRuns.length}</strong><small>等待人工处理</small></div><div><span>等待审批</span><strong>{approvalCount}</strong><small>需要团队决定</small></div><div><span>执行异常</span><strong>{failedCount}</strong><small>需要调查或恢复</small></div><div><span>当前查看</span><strong>{selectedRun ? runStatusMeta(selectedRun.status).label : "无"}</strong><small>选中的事项状态</small></div></section>
        {runsQuery.isLoading ? <p className="wb-list-loading">正在读取运行状态…</p> : null}
        {!runsQuery.isLoading && inboxRuns.length === 0 ? <EmptySplitState detail="后台执行与已完成记录会留在“运行”页；这里只显示需要你处理的事项。" icon={CheckCircle2Icon} title="当前没有待处理事项" action={<Link className="wb-text-action" to="/runs">查看全部运行 <ArrowRightIcon aria-hidden="true" /></Link>} /> : null}
        {inboxRuns.length > 0 ? <section className="wb-workboard-section"><header><div><h2>处理队列</h2><p>按审批优先、异常随后排序。选择一项可查看其公开上下文与后续动作。</p></div></header><div className="wb-inbox-queue">{inboxRuns.map((run) => { const state = runStatusMeta(run.status); return <button className={cn("wb-inbox-queue-row", selectedRun?.id === run.id && "is-selected")} key={run.id} onClick={() => setSelectedRunId(run.id)} type="button"><span className={cn("wb-inbox-queue-marker", `is-${state.tone}`)} aria-hidden="true" /><span><strong>{run.latest_event_summary || runTitle(run)}</strong><small>{run.project_name || "未关联项目"} · {formatInboxTime(run.created_at)}</small></span><RunState status={run.status} /><ChevronRightIcon aria-hidden="true" /></button>; })}</div></section> : null}
        {selectedRun ? <section className="wb-workboard-section wb-inbox-inspector"><header><div><p className="wb-detail-kicker">{selectedRun.project_name || "运行上下文"} · {runStatusMeta(selectedRun.status).label}</p><h2>{selectedRun.latest_event_summary || runTitle(selectedRun)}</h2><p>{runKindLabel(selectedRun.kind)} · {formatDate(selectedRun.created_at)} · {selectedRun.engine}</p></div><RunState status={selectedRun.status} /></header><p className="wb-inbox-inspector-copy">{selectedRun.latest_event_summary || "此运行尚未写入可公开的状态摘要。"}</p><div className="wb-inbox-inspector-actions">{project ? <Button onClick={() => navigate(`/projects/${project.id}`)} size="sm" variant="outline"><FolderKanbanIcon aria-hidden="true" data-icon="inline-start" />打开项目</Button> : null}<Button onClick={() => navigate(`/runs?run=${selectedRun.id}`)} size="sm" variant="outline"><ActivityIcon aria-hidden="true" data-icon="inline-start" />查看运行时间线</Button></div></section> : null}
      </div></ScrollArea>
    </section>
  );
}

export function MyWorkPageV2() {
  const navigate = useNavigate();
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: listProjects, staleTime: 30_000 });
  const runsQuery = useQuery({ queryKey: ["runtime-runs", 50], queryFn: () => listRuntimeRuns(50), staleTime: 10_000 });
  const projects = useMemo(() => projectsQuery.data ?? [], [projectsQuery.data]);
  const readinessQueries = useQueries({
    queries: projects.map((project) => ({
      queryKey: ["readiness", project.id],
      queryFn: () => getReadinessSummary(project.id),
      staleTime: 30_000,
    })),
  });
  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data]);
  const [scope, setScope] = useState<"all" | "compliance" | "approval">("all");
  const approvalRuns = useMemo(
    () => runs.filter((run) => run.status === "awaiting_approval" || run.status === "failed"),
    [runs],
  );
  const readinessItems = useMemo(() => readinessQueries.flatMap((query, index) => {
    const summary = query.data;
    const project = projects[index];
    if (!summary || !project) return [];
    return [
      ...summary.mandatory_gaps.map((requirement) => ({ id: `mandatory-${project.id}-${requirement.id}`, project, requirement, kind: "mandatory" as const })),
      ...summary.evidence_gaps.map((requirement) => ({ id: `evidence-${project.id}-${requirement.id}`, project, requirement, kind: "evidence" as const })),
      ...summary.contradictions.map((requirement) => ({ id: `conflict-${project.id}-${requirement.id}`, project, requirement, kind: "conflict" as const })),
    ];
  }).slice(0, 30), [projects, readinessQueries]);
  const visibleReadinessItems = scope === "approval" ? [] : readinessItems;
  const visibleApprovalRuns = scope === "compliance" ? [] : approvalRuns;
  const totalItems = readinessItems.length + approvalRuns.length;
  const failedCount = approvalRuns.filter((run) => run.status === "failed").length;

  const readinessTitle = (kind: "mandatory" | "evidence" | "conflict", requirement: BidReadinessSummary["requirements"][number]) => {
    if (kind === "mandatory") return "补齐强制要求的响应依据";
    if (kind === "conflict") return "核对互相冲突的要求";
    return "补充要求的证据材料";
  };

  return (
    <section className="wb-workboard-page wb-directory-workboard wb-my-work-workboard" aria-labelledby="my-work-title">
      <header className="wb-workboard-header">
        <div>
          <h1 id="my-work-title">我的工作</h1>
          <p>只显示需要你推动的响应事项：要求与证据缺口、等待确认和需要恢复的异常。</p>
        </div>
        <button className="wb-quiet-button" onClick={() => { void runsQuery.refetch(); void projectsQuery.refetch(); }} type="button">
          <RefreshCwIcon aria-hidden="true" /> 刷新
        </button>
      </header>

      <ScrollArea className="wb-workboard-scroll">
        <div className="wb-workboard-content">
          <Tabs aria-label="我的工作筛选" className="wb-workboard-tabs" onValueChange={(value) => setScope(value as typeof scope)} value={scope}>
            <TabsList className="wb-work-tabs-list" variant="line">
              {([
                ["all", "全部待办", totalItems],
                ["compliance", "要求与合规", readinessItems.length],
                ["approval", "人工确认", approvalRuns.length],
              ] as const).map(([candidate, label, count]) => (
                <TabsTrigger className="wb-work-tab" key={candidate} value={candidate}>{label}<small>{count}</small></TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <section className="wb-workboard-summary" aria-label="我的工作概览">
            <div><span>需要处理</span><strong>{totalItems}</strong><small>跨项目待办</small></div>
            <div><span>要求与合规</span><strong>{readinessItems.length}</strong><small>缺口或冲突</small></div>
            <div><span>等待人工确认</span><strong>{approvalRuns.filter((run) => run.status === "awaiting_approval").length}</strong><small>等待决定</small></div>
            <div><span>执行异常</span><strong>{failedCount}</strong><small>需要恢复</small></div>
          </section>
          {runsQuery.isLoading || projectsQuery.isLoading ? <p className="wb-list-loading">正在整理待办事项…</p> : null}
          {!runsQuery.isLoading && !projectsQuery.isLoading && totalItems === 0 ? (
            <EmptySplitState
              detail="新的要求、审核意见和需要人工确认的项目动作会在这里出现。"
              icon={CheckCircle2Icon}
              title="当前没有需要处理的事项"
              action={<button className="wb-text-action" onClick={() => navigate("/projects")} type="button">查看投标机会 <ArrowRightIcon aria-hidden="true" /></button>}
            />
          ) : null}
          {visibleReadinessItems.length > 0 ? <section className="wb-workboard-section wb-work-section" aria-label="要求与合规待办"><p className="wb-work-section-heading">要求与合规</p><div className="wb-work-table">{visibleReadinessItems.map((item) => <button className="wb-work-row" key={item.id} onClick={() => navigate(`/projects/${item.project.id}`)} type="button"><span className="wb-work-row__icon"><AlertCircleIcon aria-hidden="true" /></span><span className="wb-work-row__title"><strong>{readinessTitle(item.kind, item.requirement)}</strong><small>{item.requirement.requirement_text}</small></span><span className="wb-work-row__project">{item.project.name}</span><RunState status="待处理" /><ChevronRightIcon aria-hidden="true" /></button>)}</div></section> : null}
          {visibleApprovalRuns.length > 0 ? <section className="wb-workboard-section wb-work-section" aria-label="人工确认待办"><p className="wb-work-section-heading">人工确认</p><div className="wb-work-table">{visibleApprovalRuns.map((run) => <button className="wb-work-row" key={run.id} onClick={() => run.project_id ? navigate(`/projects/${run.project_id}`) : navigate("/projects")} type="button"><span className="wb-work-row__icon">{run.status === "failed" ? <AlertCircleIcon aria-hidden="true" /> : <ShieldCheckIcon aria-hidden="true" />}</span><span className="wb-work-row__title"><strong>{run.status === "failed" ? "检查并恢复项目中的异常工作" : "确认项目中的待决操作"}</strong><small>{run.latest_event_summary || "该项目需要人工继续推进。"}</small></span><span className="wb-work-row__project">{run.project_name || "未关联项目"}</span><RunState status={run.status} /><ChevronRightIcon aria-hidden="true" /></button>)}</div></section> : null}
        </div>
      </ScrollArea>
    </section>
  );
}

export function RunsPageV2() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filter, setFilter] = useState<RunFilter>("all");
  const runsQuery = useQuery({ queryKey: ["runtime-runs", 50], queryFn: () => listRuntimeRuns(50), staleTime: 10_000 });
  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data]);
  const visibleRuns = useMemo(() => filterRuns(runs, filter), [filter, runs]);
  const requestedRunId = searchParams.get("run");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(requestedRunId);

  useEffect(() => {
    setSelectedRunId((current) => {
      if (requestedRunId && visibleRuns.some((run) => run.id === requestedRunId)) return requestedRunId;
      return current && visibleRuns.some((run) => run.id === current) ? current : visibleRuns[0]?.id ?? null;
    });
  }, [requestedRunId, visibleRuns]);

  const selectedRun = visibleRuns.find((run) => run.id === selectedRunId) ?? null;
  const eventsQuery = useQuery({
    queryKey: ["runtime-events", selectedRun?.id],
    queryFn: () => listRuntimeEvents(selectedRun!.id),
    enabled: Boolean(selectedRun),
    staleTime: 5_000,
  });
  const counts: Record<RunFilter, number> = {
    all: runs.length,
    active: runs.filter((run) => ACTIVE_RUN_STATUSES.has(run.status)).length,
    approval: runs.filter((run) => run.status === "awaiting_approval").length,
    failed: runs.filter((run) => run.status === "failed").length,
    completed: runs.filter((run) => COMPLETED_RUN_STATUSES.has(run.status)).length,
  };

  const selectRun = (run: RuntimeRunListItem) => {
    setSelectedRunId(run.id);
    setSearchParams({ run: run.id }, { replace: true });
  };

  return (
    <section className="wb-workboard-page wb-runs-workboard" aria-labelledby="runs-title">
      <header className="wb-workboard-header"><div><p className="wb-eyebrow">Execution health</p><h1 id="runs-title">{t("nav.runs")}</h1><p>查看自动化执行、等待审批和需要恢复的异常，而不是逐条翻运行日志。</p></div><Button onClick={() => void runsQuery.refetch()} size="sm" type="button" variant="outline"><RefreshCwIcon data-icon="inline-start" />刷新</Button></header>
      <Tabs className="wb-workboard-tabs" onValueChange={(value) => setFilter(value as RunFilter)} value={filter}><TabsList variant="line">{(["all", "active", "approval", "failed", "completed"] as const).map((candidate) => <TabsTrigger key={candidate} value={candidate}>{{ all: "全部", active: "运行中", approval: "待审批", failed: "失败", completed: "已完成" }[candidate]} <small>{counts[candidate]}</small></TabsTrigger>)}</TabsList></Tabs>
      <ScrollArea className="wb-workboard-scroll"><div className="wb-workboard-content">
        <section className="wb-workboard-summary" aria-label="运行概览"><div><span>全部运行</span><strong>{counts.all}</strong><small>最近 50 条执行</small></div><div><span>正在执行</span><strong>{counts.active}</strong><small>运行中或排队中</small></div><div><span>等待审批</span><strong>{counts.approval}</strong><small>需要人工决策</small></div><div><span>执行异常</span><strong>{counts.failed}</strong><small>需要调查或恢复</small></div></section>
        <section className="wb-workboard-section"><header><div><h2>运行队列</h2><p>选择一条记录，在下方查看它的公开执行轨迹。</p></div></header>{runsQuery.isLoading ? <p className="wb-list-loading">正在加载运行记录…</p> : null}{!runsQuery.isLoading && visibleRuns.length === 0 ? <p className="wb-list-empty">没有匹配的运行记录。</p> : null}<div className="wb-run-workboard-list">{visibleRuns.map((run) => <button className={cn("wb-run-list-row", selectedRun?.id === run.id && "is-selected")} key={run.id} onClick={() => selectRun(run)} type="button"><span className="wb-list-row-icon"><RunIcon kind={run.kind} /></span><span className="wb-list-row-copy"><strong>{run.latest_event_summary || runTitle(run)}</strong><small>{run.project_name || "未关联项目"} · {formatDate(run.created_at)}</small></span><RunState status={run.status} /></button>)}</div></section>
        {selectedRun ? <section className="wb-workboard-section wb-run-inspector"><header><div><p className="wb-detail-kicker">{runKindLabel(selectedRun.kind)}</p><h2>{selectedRun.project_name || "未关联项目运行"}</h2><p>引擎 {selectedRun.engine} · 开始于 {formatDate(selectedRun.started_at || selectedRun.created_at)}{selectedRun.finished_at ? ` · 结束于 ${formatDate(selectedRun.finished_at)}` : ""}</p></div><RunState status={selectedRun.status} /></header>{eventsQuery.isLoading ? <p className="wb-list-loading">正在加载事件…</p> : null}{!eventsQuery.isLoading && (eventsQuery.data?.items.length ?? 0) === 0 ? <p className="wb-list-empty">此运行尚未写入公开事件。</p> : null}<div className="wb-run-event-list">{(eventsQuery.data?.items ?? []).map((event) => <RunEventRow event={event} key={`${event.run_id}-${event.sequence}`} />)}</div></section> : null}
      </div></ScrollArea>
    </section>
  );
}

function RunEventRow({ event }: { event: RuntimeEventRead }) {
  const failed = event.type.includes("failed");
  const awaiting = event.type.startsWith("approval.");
  const completed = event.type.includes("completed") || event.type.includes("succeeded");
  const Icon = failed ? AlertCircleIcon : awaiting ? ShieldCheckIcon : completed ? CheckCircle2Icon : ActivityIcon;
  const phase = runtimeEventPhase(event.type);
  return (
    <div className="wb-run-event-row">
      <span className={cn("wb-run-event-marker", failed && "is-failed", awaiting && "is-approval", completed && "is-complete")}><Icon aria-hidden="true" /></span>
      <div>
        <strong>{event.public_summary || phase}</strong>
        <small>步骤 {event.sequence} · {phase}</small>
      </div>
    </div>
  );
}

function runtimeEventPhase(type: string) {
  const normalized = type.toLowerCase();
  if (normalized.startsWith("plan.")) return "整理执行计划";
  if (normalized.startsWith("reasoning.")) return "分析任务";
  if (normalized.startsWith("capability.")) return "调用平台能力";
  if (normalized.startsWith("approval.")) return "等待操作确认";
  if (normalized.startsWith("workflow.")) return "执行工作流";
  if (normalized.startsWith("message.")) return "生成回复";
  if (normalized.startsWith("run.")) return "更新运行状态";
  return "记录执行进展";
}

type MaterialRecord = {
  document: SourceDocumentRead;
  bundle: BundleRead;
  project: ProjectRead;
};

type SharedKnowledgeRecord = {
  memory: MemoryRead;
  projectId: string;
  projectName: string;
};

type DocumentFilter = "all" | "processing" | "needs-attention";

function documentStatusMeta(document: SourceDocumentRead) {
  if (document.parse_status === "not_applicable") return { label: "已归档（无需解析）", variant: "secondary" as const };
  if (document.parse_status === "failed") return { label: "解析异常", variant: "destructive" as const };
  if (document.parse_status === "parsed" && document.index_status === "indexed") return { label: "可引用", variant: "secondary" as const };
  if (document.parse_status === "parsed" && document.index_status === "indexing") return { label: "正在建立检索索引", variant: "outline" as const };
  if (document.parse_status === "parsed" && ["failed", "degraded"].includes(document.index_status)) return { label: "索引需重试", variant: "destructive" as const };
  if (document.parse_status === "parsed") return { label: "文本已解析", variant: "outline" as const };
  if (document.parse_status === "parsing" || document.index_status === "indexing") return { label: "正在解析", variant: "outline" as const };
  return { label: "等待解析", variant: "outline" as const };
}

function documentMimeLabel(mimeType: string) {
  if (mimeType === "application/pdf") return "PDF";
  if (mimeType.includes("wordprocessingml")) return "DOCX";
  if (mimeType.includes("spreadsheetml")) return "XLSX";
  if (mimeType === "application/zip") return "ZIP";
  if (mimeType === "application/vnd.rar") return "RAR";
  if (mimeType === "application/x-7z-compressed") return "7Z";
  if (mimeType.startsWith("image/")) return "图片";
  if (mimeType === "text/csv") return "CSV";
  if (mimeType === "text/markdown") return "Markdown";
  if (mimeType === "text/plain") return "TXT";
  return "文件";
}

function isPreviewableDocument(document: SourceDocumentRead) {
  return document.mime_type === "application/pdf" || document.mime_type.startsWith("image/") || isTextDocument(document);
}

function isTextDocument(document: SourceDocumentRead) {
  return document.mime_type.startsWith("text/") || /\.(?:txt|md|markdown|csv|json|xml|ya?ml)$/i.test(document.original_filename);
}

function sourceUrlHref(sourceUrl: string | null) {
  if (!sourceUrl || !/^https?:\/\//i.test(sourceUrl)) return null;
  return sourceUrl;
}

function documentIcon(document: SourceDocumentRead) {
  return document.mime_type.startsWith("image/") ? ImageIcon : FileTextIcon;
}

export function KnowledgePageV2() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [surface, setSurface] = useState<"materials" | "knowledge">("materials");
  const [projectFilter, setProjectFilter] = useState("all");
  const [documentFilter, setDocumentFilter] = useState<DocumentFilter>("all");
  const [query, setQuery] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadProjectId, setUploadProjectId] = useState("");
  const [uploadBundleLabel, setUploadBundleLabel] = useState("招标资料");
  const [uploadSourceType, setUploadSourceType] = useState("buyer_rfp");
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [textPreview, setTextPreview] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState(false);
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: listProjects, staleTime: 30_000 });
  const portfolioQuery = useQuery({ queryKey: ["knowledge-portfolio", 50], queryFn: () => listKnowledgePortfolio(50), staleTime: 30_000 });
  const projects = useMemo(() => projectsQuery.data ?? [], [projectsQuery.data]);
  const portfolio = useMemo(() => portfolioQuery.data ?? [], [portfolioQuery.data]);
  const bundleQueries = useQueries({
    queries: projects.map((project) => ({
      queryKey: ["project-bundles", project.id],
      queryFn: () => listBundles(project.id),
      staleTime: 20_000,
    })),
  });
  const bundleRecords = useMemo(() => projects.flatMap((project, index) => (
    (bundleQueries[index]?.data ?? []).map((bundle) => ({ bundle, project }))
  )), [bundleQueries, projects]);
  const documentQueries = useQueries({
    queries: bundleRecords.map(({ bundle }) => ({
      queryKey: ["bundle-documents", bundle.id],
      queryFn: () => listDocuments(bundle.id, 1, 100),
      staleTime: 15_000,
    })),
  });
  const materialRecords = useMemo<MaterialRecord[]>(() => bundleRecords.flatMap(({ bundle, project }, index) => (
    (documentQueries[index]?.data?.items ?? []).map((document) => ({ document, bundle, project }))
  )), [bundleRecords, documentQueries]);
  const memoryQueries = useQueries({
    queries: portfolio.map((item) => ({
      queryKey: ["project-memory", item.project_id],
      queryFn: () => listProjectMemory(item.project_id),
      enabled: surface === "knowledge",
      staleTime: 20_000,
    })),
  });
  const sharedKnowledge = useMemo<SharedKnowledgeRecord[]>(() => portfolio.flatMap((item, index) => (
    (memoryQueries[index]?.data ?? []).map((memory) => ({
      memory,
      projectId: item.project_id,
      projectName: item.project_name,
    }))
  )), [memoryQueries, portfolio]);
  const filteredMaterials = useMemo(() => materialRecords.filter((record) => {
    if (projectFilter !== "all" && record.project.id !== projectFilter) return false;
    if (documentFilter === "processing" && !["pending", "parsing"].includes(record.document.parse_status) && record.document.index_status !== "indexing") return false;
    if (documentFilter === "needs-attention" && record.document.parse_status !== "failed" && !["failed", "degraded"].includes(record.document.index_status)) return false;
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return true;
    return [record.document.original_filename, record.bundle.label, record.project.name]
      .some((value) => value.toLocaleLowerCase().includes(needle));
  }), [documentFilter, materialRecords, projectFilter, query]);
  const filteredKnowledge = useMemo(() => sharedKnowledge.filter((record) => {
    if (projectFilter !== "all" && record.projectId !== projectFilter) return false;
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return true;
    return [record.memory.title, record.memory.body_markdown, record.projectName]
      .some((value) => value.toLocaleLowerCase().includes(needle));
  }), [projectFilter, query, sharedKnowledge]);
  const selectedRecord = materialRecords.find((record) => record.document.id === selectedDocumentId) ?? null;
  const failedCount = materialRecords.filter((record) => record.document.parse_status === "failed" || ["failed", "degraded"].includes(record.document.index_status)).length;
  const processingCount = materialRecords.filter((record) => (record.document.parse_status !== "parsed" && record.document.parse_status !== "failed" && record.document.parse_status !== "not_applicable") || record.document.index_status === "indexing").length;
  const uploadMutation = useMutation({
    mutationFn: async ({ projectId, bundleLabel, sourceType, files }: { projectId: string; bundleLabel: string; sourceType: string; files: File[] }) => {
      const bundle = await createBundle({ project_id: projectId, label: bundleLabel, source_type: sourceType });
      const uploaded = [];
      for (const file of files) uploaded.push(await uploadDocument(bundle.id, file, undefined, undefined, true));
      const queuedForParsing = uploaded.some((document) => document.parse_status !== "not_applicable");
      let queueError: unknown;
      if (queuedForParsing) {
        try {
          await reingestBundle(bundle.id);
        } catch (error) {
          queueError = error;
        }
      }
      return { bundle, count: files.length, queuedForParsing, queueError };
    },
    onSuccess: ({ count, queuedForParsing, queueError }) => {
      void queryClient.invalidateQueries({ queryKey: ["project-bundles"] });
      void queryClient.invalidateQueries({ queryKey: ["bundle-documents"] });
      setUploadOpen(false);
      setUploadFiles([]);
      setUploadBundleLabel("招标资料");
      if (queueError) {
        toast.warning(documentQueueErrorMessage(queueError));
      } else {
        toast.success(queuedForParsing ? `${count} 份资料已上传，正在自动解析。` : `${count} 份附件已归档，可在资料页下载使用。`);
      }
    },
    onError: () => toast.error("资料未能上传。请确认文件类型、大小和项目权限。"),
  });
  const reingestMutation = useMutation({
    mutationFn: reingestBundle,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["project-bundles"] });
      void queryClient.invalidateQueries({ queryKey: ["bundle-documents"] });
      toast.success("资料包已重新进入解析队列。");
    },
    onError: () => toast.error("暂时无法重新解析资料包。"),
  });

  useEffect(() => {
    if (!uploadProjectId && projects[0]) setUploadProjectId(projects[0].id);
  }, [projects, uploadProjectId]);

  useEffect(() => {
    if (!selectedRecord || !isPreviewableDocument(selectedRecord.document)) {
      setPreviewUrl(null);
      setTextPreview(null);
      setPreviewError(false);
      return;
    }
    let active = true;
    let objectUrl: string | null = null;
    setPreviewUrl(null);
    setTextPreview(null);
    setPreviewError(false);
    void getDocumentBlob(selectedRecord.document.id)
      .then((blob) => {
        if (!active) return;
        if (isTextDocument(selectedRecord.document)) {
          return blob.text().then((value) => {
            if (active) setTextPreview(value.slice(0, 100_000));
          });
        }
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      })
      .catch(() => active && setPreviewError(true));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selectedRecord]);

  async function handleDocumentDownload(document: SourceDocumentRead) {
    try {
      const blob = await getDocumentBlob(document.id);
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = document.original_filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("原件暂时无法下载。请稍后重试。");
    }
  }

  function openUploadDialog() {
    if (!projects.length) {
      toast.error("请先创建一个投标机会，再上传资料。");
      navigate("/projects");
      return;
    }
    setUploadOpen(true);
  }

  return (
    <section className="wb-workboard-page wb-directory-workboard wb-knowledge-workboard" aria-labelledby="knowledge-title">
      <header className="wb-workboard-header">
        <div>
          <h1 id="knowledge-title">{t("nav.knowledge")}</h1>
          <p>集中管理投标文件、企业材料与可引用知识。上传后由平台自动解析，团队可直接用于要求核验和响应起草。</p>
        </div>
        <Button onClick={openUploadDialog} size="sm"><UploadIcon aria-hidden="true" data-icon="inline-start" />上传资料</Button>
      </header>

      <ScrollArea className="wb-workboard-scroll">
        <div className="wb-workboard-content">
          <Tabs className="wb-workboard-tabs" onValueChange={(value) => setSurface(value as "materials" | "knowledge")} value={surface}>
            <TabsList aria-label="资料中心视图">
              <TabsTrigger value="materials">资料 <small>{materialRecords.length}</small></TabsTrigger>
              <TabsTrigger value="knowledge">共享知识 <small>{sharedKnowledge.length || portfolio.reduce((total, item) => total + item.active_shared_count, 0)}</small></TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="mb-6 flex flex-wrap items-center gap-2">
            <InputGroup className="min-w-[220px] flex-1 sm:max-w-md">
              <InputGroupAddon><SearchIcon aria-hidden="true" /></InputGroupAddon>
              <InputGroupInput aria-label="搜索资料和共享知识" onChange={(event) => setQuery(event.target.value)} placeholder={surface === "materials" ? "搜索文件、资料包或项目" : "搜索知识标题和内容"} value={query} />
            </InputGroup>
            <Select onValueChange={(value) => value && setProjectFilter(value)} value={projectFilter}>
              <SelectTrigger aria-label="筛选所属项目" size="sm"><SelectValue /></SelectTrigger>
              <SelectContent><SelectGroup><SelectItem value="all">全部项目</SelectItem>{projects.map((project) => <SelectItem key={project.id} value={project.id}>{projectDisplayName(project)}</SelectItem>)}</SelectGroup></SelectContent>
            </Select>
            {surface === "materials" ? <Select onValueChange={(value) => value && setDocumentFilter(value as DocumentFilter)} value={documentFilter}>
              <SelectTrigger aria-label="筛选解析状态" size="sm"><SelectValue /></SelectTrigger>
              <SelectContent><SelectGroup><SelectItem value="all">所有状态</SelectItem><SelectItem value="processing">正在处理 {processingCount ? `(${processingCount})` : ""}</SelectItem><SelectItem value="needs-attention">需要处理 {failedCount ? `(${failedCount})` : ""}</SelectItem></SelectGroup></SelectContent>
            </Select> : null}
          </div>

          {surface === "materials" ? <section aria-label="项目资料">
            {projectsQuery.isLoading || bundleQueries.some((item) => item.isLoading) ? <p className="wb-list-loading">正在整理项目资料…</p> : null}
            {!projectsQuery.isLoading && !materialRecords.length ? <Empty className="border-dashed py-12">
              <EmptyHeader><EmptyMedia variant="icon"><UploadIcon aria-hidden="true" /></EmptyMedia><EmptyTitle>从第一份招标资料开始</EmptyTitle><EmptyDescription>上传 PDF、DOCX、XLSX、CSV、TXT 或 Markdown。平台会自动解析，随后可在项目中提取要求和证据。</EmptyDescription></EmptyHeader>
              <EmptyContent><Button onClick={openUploadDialog} size="sm"><UploadIcon aria-hidden="true" data-icon="inline-start" />上传资料</Button></EmptyContent>
            </Empty> : null}
            {materialRecords.length ? <div className="wb-directory-table-group"><Table>
              <TableHeader><TableRow><TableHead>资料</TableHead><TableHead>所属项目</TableHead><TableHead>资料包</TableHead><TableHead>解析状态</TableHead><TableHead className="w-16" /></TableRow></TableHeader>
              <TableBody>{filteredMaterials.map((record) => {
                const Icon = documentIcon(record.document);
                const status = documentStatusMeta(record.document);
                return <TableRow className="cursor-pointer" data-state={record.document.id === selectedDocumentId ? "selected" : undefined} key={record.document.id} onClick={() => setSelectedDocumentId(record.document.id)} onKeyDown={(event) => event.key === "Enter" && setSelectedDocumentId(record.document.id)} tabIndex={0}>
                  <TableCell><div className="flex min-w-0 items-center gap-2"><Icon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" /><span className="min-w-0"><span className="block truncate font-medium text-foreground">{record.document.original_filename}</span><span className="block text-xs text-muted-foreground">{documentMimeLabel(record.document.mime_type)} · v{record.document.version_number}{sourceUrlHref(record.document.source_url) ? " · 公开来源" : ""}</span></span></div></TableCell>
                  <TableCell className="max-w-48 truncate text-muted-foreground">{projectDisplayName(record.project)}</TableCell>
                  <TableCell className="max-w-44 truncate text-muted-foreground">{record.bundle.label}</TableCell>
                  <TableCell><Badge variant={status.variant}>{record.document.parse_status === "parsing" ? <LoaderCircleIcon className="animate-spin" aria-hidden="true" /> : null}{status.label}</Badge></TableCell>
                  <TableCell><Button aria-label={`打开 ${record.document.original_filename}`} onClick={(event) => { event.stopPropagation(); setSelectedDocumentId(record.document.id); }} size="icon-xs" variant="ghost"><ChevronRightIcon aria-hidden="true" /></Button></TableCell>
                </TableRow>;
              })}</TableBody>
            </Table></div> : null}
            {materialRecords.length && !filteredMaterials.length ? <Empty className="border-dashed py-10"><EmptyHeader><EmptyMedia><SearchIcon aria-hidden="true" /></EmptyMedia><EmptyTitle>没有匹配的资料</EmptyTitle><EmptyDescription>调整项目、状态或关键词后再试。</EmptyDescription></EmptyHeader></Empty> : null}
          </section> : <section aria-label="共享知识">
            {portfolioQuery.isLoading || memoryQueries.some((item) => item.isLoading) ? <p className="wb-list-loading">正在读取可复用知识…</p> : null}
            {!portfolioQuery.isLoading && !filteredKnowledge.length ? <Empty className="border-dashed py-12"><EmptyHeader><EmptyMedia variant="icon"><LibraryBigIcon aria-hidden="true" /></EmptyMedia><EmptyTitle>尚无可复用知识</EmptyTitle><EmptyDescription>资料解析并经团队确认后，能用于响应和核验的结论会在这里出现。</EmptyDescription></EmptyHeader></Empty> : null}
            {filteredKnowledge.length ? <div className="wb-directory-table-group"><Table>
              <TableHeader><TableRow><TableHead>知识</TableHead><TableHead>所属项目</TableHead><TableHead>类型</TableHead><TableHead>来源</TableHead><TableHead className="w-20" /></TableRow></TableHeader>
              <TableBody>{filteredKnowledge.map(({ memory, projectId, projectName }) => <TableRow key={memory.id}>
                <TableCell className="max-w-md"><span className="block truncate font-medium text-foreground">{memory.title}</span><span className="block truncate text-xs text-muted-foreground">{memory.body_markdown.replace(/\s+/g, " ")}</span></TableCell>
                <TableCell className="max-w-44 truncate text-muted-foreground">{projectName}</TableCell>
                <TableCell><Badge variant="outline">{memoryKindLabel(memory.kind)}</Badge></TableCell>
                <TableCell className="text-muted-foreground">{memory.citations.length} 个引用</TableCell>
                <TableCell><Button onClick={() => navigate(`/projects/${projectId}`)} size="sm" variant="ghost">打开项目</Button></TableCell>
              </TableRow>)}</TableBody>
            </Table></div> : null}
          </section>}
        </div>
      </ScrollArea>

      <Dialog onOpenChange={setUploadOpen} open={uploadOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>上传项目资料</DialogTitle><DialogDescription>文件会先进入资料包，再由平台自动解析。请按材料用途选择来源类型，便于后续要求提取与证据核验。</DialogDescription></DialogHeader>
          <FieldGroup>
            <Field><FieldLabel htmlFor="knowledge-upload-project">所属项目</FieldLabel><Select onValueChange={(value) => value && setUploadProjectId(value)} value={uploadProjectId}><SelectTrigger id="knowledge-upload-project"><SelectValue placeholder="选择投标机会" /></SelectTrigger><SelectContent><SelectGroup>{projects.map((project) => <SelectItem key={project.id} value={project.id}>{projectDisplayName(project)}</SelectItem>)}</SelectGroup></SelectContent></Select></Field>
            <Field><FieldLabel htmlFor="knowledge-upload-label">资料包名称</FieldLabel><Input id="knowledge-upload-label" onChange={(event) => setUploadBundleLabel(event.target.value)} placeholder="例如：招标文件与附件" value={uploadBundleLabel} /></Field>
            <Field><FieldLabel htmlFor="knowledge-upload-type">材料用途</FieldLabel><Select onValueChange={(value) => value && setUploadSourceType(value)} value={uploadSourceType}><SelectTrigger id="knowledge-upload-type"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="buyer_rfp">招标文件或采购要求</SelectItem><SelectItem value="supplier_evidence">企业资质、案例或支撑材料</SelectItem></SelectGroup></SelectContent></Select></Field>
            <Field><FieldLabel htmlFor="knowledge-upload-files">选择文件</FieldLabel><Input accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.rar,.7z,.csv,.txt,.md,.markdown" id="knowledge-upload-files" multiple onChange={(event) => setUploadFiles(Array.from(event.target.files ?? []))} ref={fileInputRef} type="file" /><p className="text-xs text-muted-foreground">PDF、DOCX、XLSX、CSV、TXT、Markdown 会自动解析；DOC、XLS、PPT、ZIP、RAR、7Z 会安全归档供下载，单个文件不超过 25 MB。</p>{uploadFiles.length ? <div className="flex flex-wrap gap-1.5">{uploadFiles.map((file) => <Badge key={`${file.name}-${file.lastModified}`} variant="secondary">{file.name}</Badge>)}</div> : null}</Field>
          </FieldGroup>
          <DialogFooter><Button onClick={() => setUploadOpen(false)} type="button" variant="outline">取消</Button><Button disabled={!uploadProjectId || !uploadBundleLabel.trim() || !uploadFiles.length || uploadMutation.isPending} onClick={() => uploadMutation.mutate({ projectId: uploadProjectId, bundleLabel: uploadBundleLabel.trim(), sourceType: uploadSourceType, files: uploadFiles })} type="button">{uploadMutation.isPending ? <LoaderCircleIcon className="animate-spin" aria-hidden="true" /> : <UploadIcon aria-hidden="true" />}上传并解析</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Sheet onOpenChange={(open) => !open && setSelectedDocumentId(null)} open={Boolean(selectedRecord)}>
        <SheetContent className="wb-knowledge-document-sheet gap-0 p-0 sm:max-w-xl" side="right">
          {selectedRecord ? <>
            <SheetHeader className="pr-12"><SheetTitle className="truncate">{selectedRecord.document.original_filename}</SheetTitle><SheetDescription>{projectDisplayName(selectedRecord.project)} · {selectedRecord.bundle.label}</SheetDescription></SheetHeader>
            <div className="min-h-0 flex-1 overflow-auto px-4 pb-4">
              {isPreviewableDocument(selectedRecord.document) ? <div className="min-h-72 overflow-hidden rounded-lg border bg-muted/30">
                {previewUrl && selectedRecord.document.mime_type === "application/pdf" ? <iframe className="h-[calc(100vh-16rem)] min-h-96 w-full bg-background" src={previewUrl} title={`${selectedRecord.document.original_filename} 预览`} /> : null}
                {previewUrl && selectedRecord.document.mime_type.startsWith("image/") ? <img alt={selectedRecord.document.original_filename} className="max-h-[calc(100vh-16rem)] min-h-72 w-full object-contain" src={previewUrl} /> : null}
                {isTextDocument(selectedRecord.document) && textPreview !== null ? <pre className="wb-knowledge-document-sheet__text-preview">{textPreview}</pre> : null}
                {!previewUrl && textPreview === null && !previewError ? <div className="flex min-h-72 items-center justify-center gap-2 text-sm text-muted-foreground"><LoaderCircleIcon className="size-4 animate-spin" aria-hidden="true" />正在加载原件…</div> : null}
                {previewError ? <div className="flex min-h-72 items-center justify-center gap-2 px-8 text-center text-sm text-muted-foreground"><FileWarningIcon className="size-4 shrink-0" aria-hidden="true" />原件暂时无法在此预览，可下载后在本地打开。</div> : null}
              </div> : <Empty className="border-dashed py-10"><EmptyHeader><EmptyMedia variant="icon"><FileIcon aria-hidden="true" /></EmptyMedia><EmptyTitle>此格式不支持在线预览</EmptyTitle><EmptyDescription>下载原件后可在本地应用中继续查看。</EmptyDescription></EmptyHeader></Empty>}
              <dl className="mt-5 grid grid-cols-[96px_minmax(0,1fr)] gap-x-3 gap-y-3 text-sm"><dt className="text-muted-foreground">文件类型</dt><dd>{documentMimeLabel(selectedRecord.document.mime_type)}</dd><dt className="text-muted-foreground">解析状态</dt><dd><Badge variant={documentStatusMeta(selectedRecord.document).variant}>{documentStatusMeta(selectedRecord.document).label}</Badge></dd><dt className="text-muted-foreground">资料包</dt><dd className="truncate">{selectedRecord.bundle.label}</dd>{sourceUrlHref(selectedRecord.document.source_url) ? <><dt className="text-muted-foreground">远程来源</dt><dd className="truncate"><a className="wb-knowledge-document-sheet__source" href={sourceUrlHref(selectedRecord.document.source_url) ?? undefined} rel="noreferrer" target="_blank">查看原始公开资料</a></dd></> : null}{selectedRecord.document.parse_error_detail ? <><dt className="text-muted-foreground">处理说明</dt><dd className="text-destructive">{selectedRecord.document.parse_error_detail}</dd></> : null}</dl>
            </div>
            <SheetFooter className="flex-row justify-between border-t"><Button onClick={() => void handleDocumentDownload(selectedRecord.document)} size="sm" variant="outline"><DownloadIcon aria-hidden="true" data-icon="inline-start" />下载原件</Button>{selectedRecord.document.parse_retryable ? <Button disabled={reingestMutation.isPending} onClick={() => reingestMutation.mutate(selectedRecord.bundle.id)} size="sm" variant="outline"><RefreshCwIcon aria-hidden="true" data-icon="inline-start" />重新解析资料包</Button> : null}</SheetFooter>
          </> : null}
        </SheetContent>
      </Sheet>
    </section>
  );
}

function memoryKindLabel(kind: MemoryRead["kind"]) {
  const labels: Record<MemoryRead["kind"], string> = {
    preference: "工作偏好",
    fact: "已知事实",
    decision: "项目决策",
    procedure: "执行方法",
    risk: "风险提示",
    summary: "资料摘要",
    entity_note: "关系提案",
  };
  return labels[kind];
}
