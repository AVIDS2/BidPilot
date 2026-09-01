import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node
} from '@xyflow/react';
import {
  CheckCircle2Icon,
  CircleDotIcon,
  ClockIcon,
  FileSearchIcon,
  FileTextIcon,
  SaveIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UserCheckIcon,
  XCircleIcon
} from 'lucide-react';
import { useMemo } from 'react';
import type { AgentNode, AgentNodeStatus } from '@/components/agent-status-stream';
import { useIsMobile } from '@/hooks/use-mobile';
import { cn } from '@/lib/utils';

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
    id: 'supervisor',
    label: '调度规划',
    description: '确认任务目标并决定下一步执行路径',
    position: { x: 40, y: 170 },
    icon: SparklesIcon
  },
  {
    id: 'rfp_parser',
    label: '解析资料',
    description: '从投标材料中提取需求与结构信息',
    position: { x: 320, y: 40 },
    icon: FileSearchIcon
  },
  {
    id: 'memory_context',
    label: '加载项目记忆',
    description: '读取已授权的项目知识与历史决策',
    position: { x: 320, y: 285 },
    icon: FileSearchIcon
  },
  {
    id: 'knowledge_retriever',
    label: '检索证据',
    description: '匹配可引用的知识片段与项目证据',
    position: { x: 600, y: 170 },
    icon: FileSearchIcon
  },
  {
    id: 'content_plan',
    label: '编排响应计划',
    description: '把要求与证据整理为可执行章节结构',
    position: { x: 880, y: 40 },
    icon: SparklesIcon
  },
  {
    id: 'section_drafter',
    label: '起草章节',
    description: '结合需求和证据生成章节草稿',
    position: { x: 880, y: 300 },
    icon: FileTextIcon
  },
  {
    id: 'quality_reviewer',
    label: '质量审核',
    description: '检查草稿完整性、可信度和引用质量',
    position: { x: 1160, y: 170 },
    icon: ShieldCheckIcon
  },
  {
    id: 'human_approval',
    label: '人工确认',
    description: '等待用户批准或驳回生成结果',
    position: { x: 1440, y: 385 },
    icon: UserCheckIcon
  },
  {
    id: 'persist_result',
    label: '保存结果',
    description: '写入版本、证据关系和审计记录',
    position: { x: 1440, y: 170 },
    icon: SaveIcon
  },
  {
    id: 'memory_proposals',
    label: '知识提案',
    description: '将可复用结论作为待审核知识提案保存',
    position: { x: 1720, y: 170 },
    icon: SaveIcon
  }
];

const WORKFLOW_EDGES: Edge[] = [
  { id: 'supervisor-rfp_parser', source: 'supervisor', target: 'rfp_parser', type: 'smoothstep' },
  {
    id: 'rfp_parser-memory_context',
    source: 'rfp_parser',
    target: 'memory_context',
    type: 'smoothstep'
  },
  {
    id: 'memory_context-knowledge_retriever',
    source: 'memory_context',
    target: 'knowledge_retriever',
    type: 'smoothstep'
  },
  {
    id: 'knowledge_retriever-content_plan',
    source: 'knowledge_retriever',
    target: 'content_plan',
    type: 'smoothstep'
  },
  {
    id: 'content_plan-section_drafter',
    source: 'content_plan',
    target: 'section_drafter',
    type: 'smoothstep'
  },
  {
    id: 'section_drafter-quality_reviewer',
    source: 'section_drafter',
    target: 'quality_reviewer',
    type: 'smoothstep'
  },
  {
    id: 'quality_reviewer-persist_result',
    source: 'quality_reviewer',
    target: 'persist_result',
    type: 'smoothstep'
  },
  {
    id: 'quality_reviewer-content_plan',
    source: 'quality_reviewer',
    target: 'content_plan',
    type: 'smoothstep'
  },
  {
    id: 'persist_result-human_approval',
    source: 'persist_result',
    target: 'human_approval',
    type: 'smoothstep'
  },
  {
    id: 'human_approval-persist_result',
    source: 'human_approval',
    target: 'persist_result',
    type: 'smoothstep'
  },
  {
    id: 'persist_result-memory_proposals',
    source: 'persist_result',
    target: 'memory_proposals',
    type: 'smoothstep'
  }
];

const STATUS_LABELS: Record<AgentNodeStatus, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败'
};

const STATUS_DESCRIPTIONS: Record<AgentNodeStatus, string> = {
  pending: '尚未执行',
  running: '当前正在执行',
  completed: '该步骤已完成',
  failed: '该步骤执行失败'
};

function statusTone(status: AgentNodeStatus) {
  switch (status) {
    case 'running':
      return 'border-primary/45 bg-primary/8 text-primary';
    case 'completed':
      return 'border-primary/20 bg-card text-foreground';
    case 'failed':
      return 'border-destructive/50 bg-destructive/10 text-destructive';
    case 'pending':
    default:
      return 'border-border/75 bg-card/75 text-muted-foreground';
  }
}

function statusLightTone(status: AgentNodeStatus) {
  switch (status) {
    case 'running':
      return 'border-primary/30 bg-primary/10 text-primary';
    case 'completed':
      return 'border-primary/20 bg-primary/8 text-primary';
    case 'failed':
      return 'border-destructive/30 bg-destructive/10 text-destructive';
    case 'pending':
    default:
      return 'border-border/80 bg-muted/55 text-muted-foreground';
  }
}

function StatusIcon({ status }: { status: AgentNodeStatus }) {
  if (status === 'completed') return <CheckCircle2Icon className='size-4 text-primary' />;
  if (status === 'failed') return <XCircleIcon className='size-4 text-destructive' />;
  if (status === 'running') return <CircleDotIcon className='size-4 animate-pulse text-primary' />;
  return <ClockIcon className='size-4 text-muted-foreground/60' />;
}

function StatusBeacon({
  status,
  label,
  compact = false
}: {
  status: AgentNodeStatus;
  label: string;
  compact?: boolean;
}) {
  const isBreathing = status === 'running';

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 rounded-full border font-medium tabular-nums',
        compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1 text-[11px]',
        statusLightTone(status)
      )}
      aria-label={label}
    >
      <span
        className={cn('workflow-status-light', isBreathing && 'workflow-status-light-breathing')}
      >
        <span className='workflow-status-light-core' />
      </span>
      <span>{label}</span>
    </span>
  );
}

function getStepStatusLabel(stepId: string, status: AgentNodeStatus, isWaitingApproval: boolean) {
  if (isWaitingApproval && stepId === 'human_approval' && status === 'running') return '等待确认';
  return STATUS_LABELS[status];
}

function getStepStatusDescription(
  stepId: string,
  status: AgentNodeStatus,
  isWaitingApproval: boolean
) {
  if (isWaitingApproval && stepId === 'human_approval' && status === 'running')
    return '需要你确认后继续执行';
  return STATUS_DESCRIPTIONS[status];
}

function WorkflowNode({ data }: { data: WorkflowNodeData }) {
  const Icon = data.icon;

  return (
    <div
      aria-label={`${data.label}：${data.statusLabel}`}
      className={cn(
        'relative w-60 overflow-hidden rounded-lg border p-3 transition-[border-color,background-color]',
        statusTone(data.status)
      )}
    >
      <Handle type='target' position={Position.Left} className='!bg-border' />
      <div
        className={cn(
          'absolute inset-x-3 top-0 h-px bg-border',
          data.status === 'running' && 'bg-primary/70',
          data.status === 'completed' && 'bg-primary/35',
          data.status === 'failed' && 'bg-destructive/60'
        )}
      />
      <div className='flex items-start gap-3'>
        <div className='flex size-9 shrink-0 items-center justify-center rounded-md bg-background ring-1 ring-border/70'>
          <Icon className='size-4' />
        </div>
        <div className='min-w-0 flex-1'>
          <div className='flex items-center justify-between gap-2'>
            <div className='font-medium tracking-[-0.01em] text-foreground'>{data.label}</div>
            <span className='workflow-node-status'>
              <StatusBeacon status={data.status} label={data.statusLabel} compact />
            </span>
          </div>
          <p className='mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground'>
            {data.description}
          </p>
          <p className='mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground'>
            <StatusIcon status={data.status} />
            <span>{data.statusDescription}</span>
          </p>
          {data.summary && (
            <p className='mt-2 line-clamp-2 text-xs text-foreground/80'>{data.summary}</p>
          )}
        </div>
      </div>
      <Handle type='source' position={Position.Right} className='!bg-border' />
    </div>
  );
}

const nodeTypes = {
  workflow: WorkflowNode
};

function getNodeStatus(
  stepId: string,
  nodeMap: Map<string, AgentNode>,
  currentNode: string | null,
  isWaitingApproval: boolean
): AgentNodeStatus {
  const streamedStatus = nodeMap.get(stepId)?.status;
  if (isWaitingApproval && stepId === 'human_approval' && streamedStatus !== 'failed')
    return 'running';
  if (currentNode === stepId && streamedStatus !== 'failed') return 'running';
  return streamedStatus ?? 'pending';
}

export function WorkflowCanvas({
  nodes,
  currentNode,
  isWaitingApproval = false
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
        summary: runtimeNode?.summary ?? runtimeNode?.error
      };
    });
  }, [currentNode, isWaitingApproval, nodes]);

  const activeStep = stepStates.find((step) => step.status === 'running');
  const failedStep = stepStates.find((step) => step.status === 'failed');
  const statusHeadline = activeStep ?? failedStep;

  const flowNodes = useMemo<Node<WorkflowNodeData>[]>(() => {
    return stepStates.map((step) => {
      return {
        id: step.id,
        type: 'workflow',
        position: step.position,
        data: {
          label: step.label,
          description: step.description,
          icon: step.icon,
          status: step.status,
          statusLabel: step.statusLabel,
          statusDescription: step.statusDescription,
          summary: step.summary
        },
        // Repositioning is a personal view preference.  It never changes the
        // durable LangGraph definition or its execution edges.
        draggable: true
      };
    });
  }, [stepStates]);

  const flowEdges = useMemo<Edge[]>(() => {
    const nodeStatus = new Map(flowNodes.map((node) => [node.id, node.data.status]));
    return WORKFLOW_EDGES.map((edge) => {
      const active =
        nodeStatus.get(edge.source) === 'completed' || nodeStatus.get(edge.target) === 'running';
      return {
        ...edge,
        animated: nodeStatus.get(edge.target) === 'running',
        className: active ? 'workflow-edge-active' : 'workflow-edge-idle',
        style: {
          stroke: active ? 'var(--primary)' : 'var(--border)',
          strokeWidth: active ? 2 : 1.5
        }
      };
    });
  }, [flowNodes]);

  if (isMobile) {
    return (
      <div
        className='overflow-hidden rounded-lg border bg-card p-3'
        data-testid='bidpilot-workflow-canvas'
      >
        <div className='flex flex-col'>
          {stepStates.map((step, index) => {
            const Icon = step.icon;
            const isLast = index === stepStates.length - 1;
            return (
              <div key={step.id} className='relative flex gap-3 pb-4 last:pb-0'>
                {!isLast && (
                  <div className='absolute left-5 top-10 h-[calc(100%-2.5rem)] w-px bg-border' />
                )}
                <div
                  className={cn(
                    'relative z-10 flex size-10 shrink-0 items-center justify-center rounded-md border bg-background',
                    step.status === 'running' && 'workflow-node-running',
                    step.status === 'running' && 'border-primary/40 text-primary',
                    step.status === 'completed' && 'border-primary/25 text-primary',
                    step.status === 'failed' && 'border-destructive/40 text-destructive',
                    step.status === 'pending' && 'text-muted-foreground/60'
                  )}
                >
                  <Icon className='size-4' />
                </div>
                <div
                  className={cn(
                    'min-w-0 flex-1 rounded-md border bg-background/70 p-3',
                    step.status === 'running' && 'border-primary/30 bg-primary/5',
                    step.status === 'failed' && 'border-destructive/30 bg-destructive/5'
                  )}
                >
                  <div className='flex min-w-0 items-center justify-between gap-3'>
                    <div className='truncate text-sm font-medium text-foreground'>{step.label}</div>
                    <StatusBeacon status={step.status} label={step.statusLabel} compact />
                  </div>
                  <p className='mt-1 text-xs leading-5 text-muted-foreground'>{step.description}</p>
                  <p className='mt-2 text-[11px] text-muted-foreground'>{step.statusDescription}</p>
                  {step.summary && (
                    <p className='mt-2 line-clamp-2 text-xs text-foreground/80'>{step.summary}</p>
                  )}
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
      className='relative h-[500px] overflow-hidden rounded-lg border bg-card'
      data-testid='bidpilot-workflow-canvas'
    >
      {statusHeadline && (
        <div className='pointer-events-none absolute left-4 top-4 z-10 flex max-w-[min(520px,calc(100%-2rem))] items-center gap-2 rounded-full border bg-card/90 px-3 py-2 text-xs shadow-sm backdrop-blur'>
          <StatusBeacon status={statusHeadline.status} label={statusHeadline.statusLabel} compact />
          <span className='truncate text-muted-foreground'>
            当前节点：<span className='font-medium text-foreground'>{statusHeadline.label}</span>
          </span>
        </div>
      )}
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={22} size={1} color='color-mix(in oklch, var(--border) 70%, transparent)' />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeStrokeWidth={3} className='!bg-card/90 !shadow-sm' />
      </ReactFlow>
    </div>
  );
}
