import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIcon,
  BotIcon,
  ChevronDownIcon,
  CircleDotIcon,
  CpuIcon,
  ExternalLinkIcon,
  Globe2Icon,
  Layers3Icon,
  PanelRightCloseIcon,
  ShieldCheckIcon,
  SparklesIcon,
  WorkflowIcon,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Button,
  buttonVariants,
} from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  getPiRuntimeContract,
  listRuntimeRuns,
  type PiRuntimeContract,
  type RuntimeRunListItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const ACTIVE_STATUSES = new Set(["queued", "running", "awaiting_approval", "cancel_requested"]);

interface AgentEnvironmentPanelProps {
  onClose?: () => void;
  onOpenRun: (runId: string) => void;
}

function runLabel(run: RuntimeRunListItem) {
  if (run.kind === "subagent") return "子 Agent";
  if (run.kind === "deep_research") return "深度调研";
  if (run.kind === "workflow_bridge") return "响应工作流";
  if (run.kind === "remote_import") return "资料导入";
  if (run.kind === "assistant_turn") return "助手会话";
  return run.kind.replaceAll("_", " ");
}

function runIcon(run: RuntimeRunListItem): LucideIcon {
  if (run.kind === "subagent") return BotIcon;
  if (run.kind === "deep_research") return Globe2Icon;
  if (run.kind === "workflow_bridge") return WorkflowIcon;
  if (run.kind === "remote_import") return Layers3Icon;
  return ActivityIcon;
}

function statusLabel(status: string) {
  if (status === "queued") return "排队中";
  if (status === "awaiting_approval") return "待确认";
  if (status === "cancel_requested") return "正在收尾";
  if (status === "running") return "运行中";
  if (status === "succeeded" || status === "completed") return "已完成";
  if (status === "failed") return "失败";
  return status;
}

function statusVariant(status: string): "default" | "secondary" | "outline" | "destructive" {
  if (status === "failed") return "destructive";
  if (status === "running") return "default";
  if (status === "awaiting_approval") return "secondary";
  return "outline";
}

function formatElapsed(run: RuntimeRunListItem) {
  const startedAt = run.started_at ? Date.parse(run.started_at) : Date.parse(run.created_at);
  if (!Number.isFinite(startedAt)) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function CapabilitySummary({ contract }: { contract: PiRuntimeContract | null }) {
  if (!contract) {
    return <p className="text-xs text-muted-foreground">正在读取 Pi 运行边界…</p>;
  }
  const sandboxLabel = contract.sandbox.profile === "governed_cloud" ? "受治理云环境" : contract.sandbox.profile;
  const mcpServers = contract.mcp_servers ?? [];
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex min-w-0 items-center gap-2 rounded-md bg-muted/50 px-2.5 py-2">
          <ShieldCheckIcon className="size-3.5 shrink-0 text-muted-foreground" />
          <span className="min-w-0 truncate">{sandboxLabel}</span>
        </div>
        <div className="flex min-w-0 items-center gap-2 rounded-md bg-muted/50 px-2.5 py-2">
          <Globe2Icon className="size-3.5 shrink-0 text-muted-foreground" />
          <span className="min-w-0 truncate">{contract.sandbox.network === "bridge_only" ? "业务桥接网络" : contract.sandbox.network}</span>
        </div>
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">能力目录</span>
        <span className="font-medium tabular-nums">{contract.tool_count} 工具 · {contract.skills.length} Skills</span>
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">并行能力</span>
        <span className="font-medium tabular-nums">{contract.parallel_tool_count} 项</span>
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">MCP</span>
        <span className="font-medium tabular-nums">{mcpServers.length ? `${mcpServers.length} 个服务` : "未配置"}</span>
      </div>
    </div>
  );
}

function ActiveRunRow({ run, onOpen }: { run: RuntimeRunListItem; onOpen: () => void }) {
  const Icon = runIcon(run);
  const isLive = ACTIVE_STATUSES.has(run.status);
  return (
    <Button
      className="h-auto w-full justify-start gap-2.5 px-2.5 py-2 text-left"
      onClick={onOpen}
      size="sm"
      variant="ghost"
    >
      <span className={cn("grid size-7 shrink-0 place-items-center rounded-md bg-muted", isLive && "text-primary")}>
        <Icon className="size-3.5" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="truncate text-xs font-medium">{runLabel(run)}</span>
          <Badge className="shrink-0" variant={statusVariant(run.status)}>{statusLabel(run.status)}</Badge>
        </span>
        <span className="truncate text-[11px] text-muted-foreground">
          {run.latest_event_summary || run.project_name || run.engine}
        </span>
      </span>
      <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
        {isLive ? formatElapsed(run) : ""}
      </span>
    </Button>
  );
}

export function AgentEnvironmentPanel({ onClose, onOpenRun }: AgentEnvironmentPanelProps) {
  const [contract, setContract] = useState<PiRuntimeContract | null>(null);
  const [runs, setRuns] = useState<RuntimeRunListItem[]>([]);
  const [resourcesOpen, setResourcesOpen] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const refreshRuns = useCallback(async () => {
    try {
      const next = await listRuntimeRuns(30);
      setRuns(next);
      setLoadError(false);
    } catch {
      setLoadError(true);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void getPiRuntimeContract().then((response) => {
      if (!cancelled) setContract(response.data);
    }).catch(() => {
      if (!cancelled) setLoadError(true);
    });
    void refreshRuns();
    const timer = window.setInterval(() => void refreshRuns(), 4_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [refreshRuns]);

  const activeRuns = useMemo(() => runs.filter((run) => ACTIVE_STATUSES.has(run.status)), [runs]);
  const completedRuns = useMemo(() => runs.filter((run) => run.status === "succeeded" || run.status === "completed"), [runs]);
  const skills = contract?.skills ?? [];
  const mcpServers = contract?.mcp_servers ?? [];

  return (
    <Card className="agent-environment-panel h-full min-h-0 rounded-xl" size="sm">
      <CardHeader className="border-b px-3.5 pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <CircleDotIcon className="size-3.5 text-primary" />
          运行环境
        </CardTitle>
        <CardDescription className="text-[11px]">Pi Agent 的实时资源与后台运行</CardDescription>
        {onClose ? (
          <CardAction>
            <Button aria-label="收起运行环境" data-icon="inline-start" onClick={onClose} size="icon-sm" title="收起运行环境" variant="ghost">
              <PanelRightCloseIcon />
            </Button>
          </CardAction>
        ) : null}
      </CardHeader>
      <ScrollArea className="min-h-0 flex-1">
        <CardContent className="flex flex-col gap-4 px-3.5 py-3.5">
          <section aria-label="Pi Agent 状态" className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-medium"><CpuIcon className="size-3.5 text-muted-foreground" />Pi Agent</div>
              <Badge variant="secondary">已连接</Badge>
            </div>
            <CapabilitySummary contract={contract} />
          </section>

          <Separator />

          <section aria-label="当前运行" className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-medium"><ActivityIcon className="size-3.5 text-muted-foreground" />当前运行</div>
              <div className="flex items-center gap-1.5">
                <Badge variant={activeRuns.length ? "default" : "outline"}>{activeRuns.length} 个运行中</Badge>
                {completedRuns.length > 0 && <span className="text-[10px] text-muted-foreground">{completedRuns.length} 已结束</span>}
              </div>
            </div>
            {activeRuns.length ? (
              <div className="flex flex-col gap-1">
                {activeRuns.slice(0, 8).map((run) => <ActiveRunRow key={run.id} onOpen={() => onOpenRun(run.id)} run={run} />)}
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-md bg-muted/40 px-2.5 py-2 text-xs text-muted-foreground">
                <SparklesIcon className="size-3.5" />当前没有后台运行
              </div>
            )}
            {activeRuns.length > 8 ? <p className="text-[11px] text-muted-foreground">还有 {activeRuns.length - 8} 个运行，请打开运行中心查看全部。</p> : null}
          </section>

          <Separator />

          <Collapsible onOpenChange={setResourcesOpen} open={resourcesOpen}>
            <CollapsibleTrigger render={<Button className="w-full justify-between px-2.5" size="sm" variant="ghost" />}>
              <span className="flex items-center gap-2"><Layers3Icon className="size-3.5 text-muted-foreground" />已注册资源</span>
              <ChevronDownIcon className={cn("size-3.5 transition-transform", resourcesOpen && "rotate-180")} />
            </CollapsibleTrigger>
            <CollapsibleContent className="flex flex-col gap-2 px-2.5 pt-2">
              <div className="flex items-center justify-between text-[11px]"><span className="text-muted-foreground">Skills</span><span className="font-medium">{skills.length}</span></div>
              {skills.slice(0, 6).map((skill) => <div className="flex min-w-0 items-center justify-between gap-2 text-[11px]" key={skill.name}><span className="truncate">{skill.name}</span><span className="shrink-0 text-muted-foreground">{skill.resources?.length || 0} 资源</span></div>)}
              <div className="flex items-center justify-between text-[11px]"><span className="text-muted-foreground">MCP</span><span className="font-medium">{mcpServers.length}</span></div>
              {mcpServers.map((server) => <div className="flex min-w-0 items-center justify-between gap-2 text-[11px]" key={server.name}><span className="truncate">{server.name}</span><span className="shrink-0 text-muted-foreground">{server.transport}</span></div>)}
            </CollapsibleContent>
          </Collapsible>

          {loadError ? <p className="text-[11px] text-destructive">运行环境暂时无法刷新，正在保留上次状态。</p> : null}
          <a className={cn(buttonVariants({ size: "sm", variant: "outline" }), "w-full justify-center")} href="/runs">
            打开运行中心 <ExternalLinkIcon data-icon="inline-end" />
          </a>
        </CardContent>
      </ScrollArea>
    </Card>
  );
}
