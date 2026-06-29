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
import { CheckCircle2Icon, CircleDotIcon, ClockIcon, FileSearchIcon, FileTextIcon, SaveIcon, ShieldCheckIcon, SparklesIcon, UserCheckIcon, XCircleIcon } from "lucide-react";
import { useMemo } from "react";
import type { AgentNode, AgentNodeStatus } from "@/components/agent-status-stream";
import { cn } from "@/lib/utils";

type WorkflowNodeData = {
  label: string;
  description: string;
  status: AgentNodeStatus;
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
    position: { x: 0, y: 140 },
    icon: SparklesIcon,
  },
  {
    id: "rfp_parser",
    label: "解析资料",
    description: "从投标材料中提取需求与结构信息",
    position: { x: 260, y: 40 },
    icon: FileSearchIcon,
  },
  {
    id: "knowledge_retriever",
    label: "检索证据",
    description: "匹配可引用的知识片段与项目证据",
    position: { x: 520, y: 40 },
    icon: FileSearchIcon,
  },
  {
    id: "section_drafter",
    label: "起草章节",
    description: "结合需求和证据生成章节草稿",
    position: { x: 780, y: 140 },
    icon: FileTextIcon,
  },
  {
    id: "quality_reviewer",
    label: "质量审核",
    description: "检查草稿完整性、可信度和引用质量",
    position: { x: 1040, y: 40 },
    icon: ShieldCheckIcon,
  },
  {
    id: "human_approval",
    label: "人工确认",
    description: "等待用户批准或驳回生成结果",
    position: { x: 1300, y: 140 },
    icon: UserCheckIcon,
  },
  {
    id: "persist_result",
    label: "保存结果",
    description: "写入版本、证据关系和审计记录",
    position: { x: 1560, y: 140 },
    icon: SaveIcon,
  },
];

const WORKFLOW_EDGES: Edge[] = [
  { id: "supervisor-rfp_parser", source: "supervisor", target: "rfp_parser", type: "smoothstep" },
  { id: "rfp_parser-knowledge_retriever", source: "rfp_parser", target: "knowledge_retriever", type: "smoothstep" },
  { id: "knowledge_retriever-section_drafter", source: "knowledge_retriever", target: "section_drafter", type: "smoothstep" },
  { id: "section_drafter-quality_reviewer", source: "section_drafter", target: "quality_reviewer", type: "smoothstep" },
  { id: "quality_reviewer-human_approval", source: "quality_reviewer", target: "human_approval", type: "smoothstep" },
  { id: "human_approval-persist_result", source: "human_approval", target: "persist_result", type: "smoothstep" },
];

function statusTone(status: AgentNodeStatus) {
  switch (status) {
    case "running":
      return "border-primary/70 bg-primary/10 text-primary shadow-[0_0_0_4px_color-mix(in_oklch,var(--primary)_14%,transparent)]";
    case "completed":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "failed":
      return "border-destructive/50 bg-destructive/10 text-destructive";
    case "pending":
    default:
      return "border-border bg-card text-muted-foreground";
  }
}

function StatusIcon({ status }: { status: AgentNodeStatus }) {
  if (status === "completed") return <CheckCircle2Icon className="size-4 text-emerald-600" />;
  if (status === "failed") return <XCircleIcon className="size-4 text-destructive" />;
  if (status === "running") return <CircleDotIcon className="size-4 animate-pulse text-primary" />;
  return <ClockIcon className="size-4 text-muted-foreground/60" />;
}

function WorkflowNode({ data }: { data: WorkflowNodeData }) {
  const Icon = data.icon;
  return (
    <div
      className={cn(
        "w-56 rounded-2xl border p-3 shadow-sm backdrop-blur transition-colors",
        statusTone(data.status),
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-border" />
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-background/75">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="font-medium text-foreground">{data.label}</div>
            <StatusIcon status={data.status} />
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">{data.description}</p>
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

function getNodeStatus(stepId: string, nodeMap: Map<string, AgentNode>, currentNode: string | null): AgentNodeStatus {
  const streamedStatus = nodeMap.get(stepId)?.status;
  if (currentNode === stepId && streamedStatus !== "failed") return "running";
  return streamedStatus ?? "pending";
}

export function WorkflowCanvas({ nodes, currentNode }: { nodes: AgentNode[]; currentNode: string | null }) {
  const flowNodes = useMemo<Node<WorkflowNodeData>[]>(() => {
    const nodeMap = new Map(nodes.map((node) => [node.name, node]));
    return WORKFLOW_STEPS.map((step) => {
      const runtimeNode = nodeMap.get(step.id);
      return {
        id: step.id,
        type: "workflow",
        position: step.position,
        data: {
          label: step.label,
          description: step.description,
          icon: step.icon,
          status: getNodeStatus(step.id, nodeMap, currentNode),
          summary: runtimeNode?.summary ?? runtimeNode?.error,
        },
        draggable: false,
      };
    });
  }, [currentNode, nodes]);

  const flowEdges = useMemo<Edge[]>(() => {
    const nodeStatus = new Map(flowNodes.map((node) => [node.id, node.data.status]));
    return WORKFLOW_EDGES.map((edge) => {
      const active = nodeStatus.get(edge.source) === "completed" || nodeStatus.get(edge.target) === "running";
      return {
        ...edge,
        animated: nodeStatus.get(edge.target) === "running",
        style: {
          stroke: active ? "var(--primary)" : "var(--border)",
          strokeWidth: active ? 2 : 1.5,
        },
      };
    });
  }, [flowNodes]);

  return (
    <div className="h-[420px] overflow-hidden rounded-2xl border bg-muted/20" data-testid="bidpilot-workflow-canvas">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={18} size={1} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeStrokeWidth={3} className="!bg-card/80" />
      </ReactFlow>
    </div>
  );
}
