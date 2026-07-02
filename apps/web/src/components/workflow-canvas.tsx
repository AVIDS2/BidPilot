import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { CheckCircle2Icon, CircleDotIcon, ClockIcon, FileSearchIcon, FileTextIcon, SaveIcon, ShieldCheckIcon, SparklesIcon, UserCheckIcon, XCircleIcon } from "lucide-react";
import { useMemo, useRef } from "react";
import type { AgentNode, AgentNodeStatus } from "@/components/agent-status-stream";
import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";

type WorkflowNodeData = {
  label: string;
  description: string;
  status: AgentNodeStatus;
  statusLabel: string;
  statusDescription: string;
  summary?: string;
  icon: typeof CircleDotIcon;
};

type WorkflowStep = {
  id: string;
  label: string;
  description: string;
  position: { x: number; y: number };
  icon: typeof CircleDotIcon;
};

const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    id: "supervisor",
    label: "调度规划",
    description: "确认任务目标并决定下一步执行路径",
    position: { x: 40, y: 170 },
    icon: SparklesIcon,
  },
  {
    id: "rfp_parser",
    label: "解析资料",
    description: "从投标材料中提取需求与结构信息",
    position: { x: 320, y: 40 },
    icon: FileSearchIcon,
  },
  {
    id: "knowledge_retriever",
    label: "检索证据",
    description: "匹配可引用的知识片段与项目证据",
    position: { x: 600, y: 40 },
    icon: FileSearchIcon,
  },
  {
    id: "section_drafter",
    label: "起草章节",
    description: "结合需求和证据生成章节草稿",
    position: { x: 600, y: 300 },
    icon: FileTextIcon,
  },
  {
    id: "quality_reviewer",
    label: "质量审核",
    description: "检查草稿完整性、可信度和引用质量",
    position: { x: 880, y: 170 },
    icon: ShieldCheckIcon,
  },
  {
    id: "human_approval",
    label: "人工确认",
    description: "等待用户批准或驳回生成结果",
    position: { x: 1160, y: 40 },
    icon: UserCheckIcon,
  },
  {
    id: "persist_result",
    label: "保存结果",
    description: "写入版本、证据关系和审计记录",
    position: { x: 1160, y: 300 },
    icon: SaveIcon,
  },
];

const WORKFLOW_EDGES: Edge[] = [
  { id: "supervisor-rfp_parser", source: "supervisor", target: "rfp_parser", type: "smoothstep" },
  { id: "rfp_parser-knowledge_retriever", source: "rfp_parser", target: "knowledge_retriever", type: "smoothstep" },
  { id: "knowledge_retriever-section_drafter", source: "knowledge_retriever", target: "section_drafter", type: "smoothstep" },
  { id: "section_drafter-quality_reviewer", source: "section_drafter", target: "quality_reviewer", type: "smoothstep" },
  { id: "quality_reviewer-human_approval", source: "quality_reviewer", target: "human_approval", type: "smoothstep" },
  { id: "quality_reviewer-persist_result", source: "quality_reviewer", target: "persist_result", type: "smoothstep" },
];

const STATUS_LABELS: Record<AgentNodeStatus, string> = {
  pending: "等待中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
};

const STATUS_DESCRIPTIONS: Record<AgentNodeStatus, string> = {
  pending: "尚未执行",
  running: "当前正在执行",
  completed: "该步骤已完成",
  failed: "该步骤执行失败",
};

function statusTone(status: AgentNodeStatus) {
  switch (status) {
    case "running":
      return "border-primary/45 bg-primary/8 text-primary shadow-[0_0_0_1px_color-mix(in_oklch,var(--primary)_26%,transparent),0_20px_44px_-32px_color-mix(in_oklch,var(--primary)_55%,transparent)]";
    case "completed":
      return "border-primary/20 bg-card text-foreground";
    case "failed":
      return "border-destructive/50 bg-destructive/10 text-destructive";
    case "pending":
    default:
      return "border-border/75 bg-card/75 text-muted-foreground";
  }
}

function statusLightTone(status: AgentNodeStatus) {
  switch (status) {
    case "running":
      return "border-primary/30 bg-primary/10 text-primary";
    case "completed":
      return "border-primary/20 bg-primary/8 text-primary";
    case "failed":
      return "border-destructive/30 bg-destructive/10 text-destructive";
    case "pending":
    default:
      return "border-border/80 bg-muted/55 text-muted-foreground";
  }
}

function StatusIcon({ status }: { status: AgentNodeStatus }) {
  if (status === "completed") return <CheckCircle2Icon className="size-4 text-primary" />;
  if (status === "failed") return <XCircleIcon className="size-4 text-destructive" />;
  if (status === "running") return <CircleDotIcon className="size-4 animate-pulse text-primary" />;
  return <ClockIcon className="size-4 text-muted-foreground/60" />;
}

function StatusBeacon({ status, label, compact = false }: { status: AgentNodeStatus; label: string; compact?: boolean }) {
  const isBreathing = status === "running";

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border font-medium tabular-nums",
        compact ? "px-2 py-1 text-[10px]" : "px-2.5 py-1 text-[11px]",
        statusLightTone(status),
      )}
      aria-label={label}
    >
      <span className={cn("workflow-status-light", isBreathing && "workflow-status-light-breathing")}>
        <span className="workflow-status-light-core" />
      </span>
      <span>{label}</span>
    </span>
  );
}

function getStepStatusLabel(stepId: string, status: AgentNodeStatus, isWaitingApproval: boolean) {
  if (isWaitingApproval && stepId === "human_approval" && status === "running") return "等待确认";
  return STATUS_LABELS[status];
}

function getStepStatusDescription(stepId: string, status: AgentNodeStatus, isWaitingApproval: boolean) {
  if (isWaitingApproval && stepId === "human_approval" && status === "running") return "需要你确认后继续执行";
  return STATUS_DESCRIPTIONS[status];
}

function WorkflowNode({ data }: { data: WorkflowNodeData }) {
  const Icon = data.icon;
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  useGSAP(
    () => {
      if (prefersReducedMotion || !nodeRef.current) return;

      gsap.fromTo(
        nodeRef.current,
        { autoAlpha: 0, y: 10, scale: 0.985 },
        { autoAlpha: 1, y: 0, scale: 1, duration: 0.42, ease: "power3.out" },
      );

      if (data.status === "running") {
        gsap.to(nodeRef.current, {
          y: -2,
          duration: 1.1,
          ease: "sine.inOut",
          repeat: -1,
          yoyo: true,
        });
        gsap.to(".workflow-node-orb", {
          scale: 1.18,
          autoAlpha: 0.46,
          duration: 1.15,
          ease: "sine.inOut",
          repeat: -1,
          yoyo: true,
        });
      }

      if (data.status === "completed") {
        gsap.fromTo(
          ".workflow-node-status",
          { scale: 0.7, rotate: -16 },
          { scale: 1, rotate: 0, duration: 0.46, ease: "back.out(1.8)" },
        );
      }
    },
    { dependencies: [data.status, prefersReducedMotion], scope: nodeRef },
  );

  return (
    <div
      ref={nodeRef}
      aria-label={`${data.label}：${data.statusLabel}`}
      className={cn(
        "relative w-60 overflow-hidden rounded-[1.15rem] border p-3 shadow-sm transition-[border-color,box-shadow,background-color]",
        data.status === "running" && "workflow-node-running",
        statusTone(data.status),
      )}
    >
      {data.status === "running" && (
        <div className="workflow-node-orb pointer-events-none absolute -right-8 -top-8 size-24 rounded-full bg-primary/15 blur-2xl" />
      )}
      <Handle type="target" position={Position.Left} className="!bg-border" />
      <div
        className={cn(
          "absolute inset-x-3 top-0 h-px bg-border",
          data.status === "running" && "bg-primary/70",
          data.status === "completed" && "bg-primary/35",
          data.status === "failed" && "bg-destructive/60",
        )}
      />
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-background/80 ring-1 ring-border/70">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="font-medium tracking-[-0.01em] text-foreground">{data.label}</div>
            <span className="workflow-node-status">
              <StatusBeacon status={data.status} label={data.statusLabel} compact />
            </span>
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">{data.description}</p>
          <p className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <StatusIcon status={data.status} />
            <span>{data.statusDescription}</span>
          </p>
          {data.summary && <p className="mt-2 line-clamp-2 text-xs text-foreground/80">{data.summary}</p>}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-border" />
    </div>
  );
}

const nodeTypes = {
  workflow: WorkflowNode,
};

function getNodeStatus(
  stepId: string,
  nodeMap: Map<string, AgentNode>,
  currentNode: string | null,
  isWaitingApproval: boolean,
): AgentNodeStatus {
  const streamedStatus = nodeMap.get(stepId)?.status;
  if (isWaitingApproval && stepId === "human_approval" && streamedStatus !== "failed") return "running";
  if (currentNode === stepId && streamedStatus !== "failed") return "running";
  return streamedStatus ?? "pending";
}

export function WorkflowCanvas({
  nodes,
  currentNode,
  isWaitingApproval = false,
}: {
  nodes: AgentNode[];
  currentNode: string | null;
  isWaitingApproval?: boolean;
}) {
  const isMobile = useIsMobile();
  const stepStates = useMemo(() => {
    const nodeMap = new Map(nodes.map((node) => [node.name, node]));
    return WORKFLOW_STEPS.map((step) => {
      const runtimeNode = nodeMap.get(step.id);
      const status = getNodeStatus(step.id, nodeMap, currentNode, isWaitingApproval);
      return {
        ...step,
        status,
        statusLabel: getStepStatusLabel(step.id, status, isWaitingApproval),
        statusDescription: getStepStatusDescription(step.id, status, isWaitingApproval),
        summary: runtimeNode?.summary ?? runtimeNode?.error,
      };
    });
  }, [currentNode, isWaitingApproval, nodes]);

  const activeStep = stepStates.find((step) => step.status === "running");
  const failedStep = stepStates.find((step) => step.status === "failed");
  const statusHeadline = activeStep ?? failedStep;

  const flowNodes = useMemo<Node<WorkflowNodeData>[]>(() => {
    return stepStates.map((step) => {
      return {
        id: step.id,
        type: "workflow",
        position: step.position,
        data: {
          label: step.label,
          description: step.description,
          icon: step.icon,
          status: step.status,
          statusLabel: step.statusLabel,
          statusDescription: step.statusDescription,
          summary: step.summary,
        },
        draggable: false,
      };
    });
  }, [stepStates]);

  const flowEdges = useMemo<Edge[]>(() => {
    const nodeStatus = new Map(flowNodes.map((node) => [node.id, node.data.status]));
    return WORKFLOW_EDGES.map((edge) => {
      const active = nodeStatus.get(edge.source) === "completed" || nodeStatus.get(edge.target) === "running";
      return {
        ...edge,
        animated: nodeStatus.get(edge.target) === "running",
        className: active ? "workflow-edge-active" : "workflow-edge-idle",
        style: {
          stroke: active ? "var(--primary)" : "var(--border)",
          strokeWidth: active ? 2 : 1.5,
        },
      };
    });
  }, [flowNodes]);

  if (isMobile) {
    return (
      <div
        className="overflow-hidden rounded-[1.2rem] border bg-[linear-gradient(180deg,color-mix(in_oklch,var(--card)_96%,var(--background)),color-mix(in_oklch,var(--muted)_45%,transparent))] p-3 shadow-sm"
        data-testid="bidpilot-workflow-canvas"
      >
        <div className="flex flex-col">
          {stepStates.map((step, index) => {
            const Icon = step.icon;
            const isLast = index === stepStates.length - 1;
            return (
              <div key={step.id} className="relative flex gap-3 pb-4 last:pb-0">
                {!isLast && <div className="absolute left-5 top-10 h-[calc(100%-2.5rem)] w-px bg-border" />}
                <div
                  className={cn(
                    "relative z-10 flex size-10 shrink-0 items-center justify-center rounded-2xl border bg-background",
                    step.status === "running" && "workflow-node-running",
                    step.status === "running" && "border-primary/40 text-primary shadow-[0_0_0_4px_color-mix(in_oklch,var(--primary)_12%,transparent)]",
                    step.status === "completed" && "border-primary/25 text-primary",
                    step.status === "failed" && "border-destructive/40 text-destructive",
                    step.status === "pending" && "text-muted-foreground/60",
                  )}
                >
                  <Icon className="size-4" />
                </div>
                <div
                  className={cn(
                    "min-w-0 flex-1 rounded-2xl border bg-background/70 p-3",
                    step.status === "running" && "border-primary/30 bg-primary/5",
                    step.status === "failed" && "border-destructive/30 bg-destructive/5",
                  )}
                >
                  <div className="flex min-w-0 items-center justify-between gap-3">
                    <div className="truncate text-sm font-medium text-foreground">{step.label}</div>
                    <StatusBeacon status={step.status} label={step.statusLabel} compact />
                  </div>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">{step.description}</p>
                  <p className="mt-2 text-[11px] text-muted-foreground">{step.statusDescription}</p>
                  {step.summary && <p className="mt-2 line-clamp-2 text-xs text-foreground/80">{step.summary}</p>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div
      className="relative h-[440px] overflow-hidden rounded-[1.35rem] border bg-[radial-gradient(circle_at_20%_10%,color-mix(in_oklch,var(--primary)_10%,transparent),transparent_34%),linear-gradient(180deg,color-mix(in_oklch,var(--card)_96%,var(--background)),color-mix(in_oklch,var(--muted)_55%,transparent))] shadow-sm"
      data-testid="bidpilot-workflow-canvas"
    >
      {statusHeadline && (
        <div className="pointer-events-none absolute left-4 top-4 z-10 flex max-w-[min(520px,calc(100%-2rem))] items-center gap-2 rounded-full border bg-card/90 px-3 py-2 text-xs shadow-sm backdrop-blur">
          <StatusBeacon status={statusHeadline.status} label={statusHeadline.statusLabel} compact />
          <span className="truncate text-muted-foreground">
            当前节点：<span className="font-medium text-foreground">{statusHeadline.label}</span>
          </span>
        </div>
      )}
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={22} size={1} color="color-mix(in oklch, var(--border) 70%, transparent)" />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeStrokeWidth={3} className="!bg-card/90 !shadow-sm" />
      </ReactFlow>
    </div>
  );
}
