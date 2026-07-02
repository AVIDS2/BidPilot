import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAgentStream, type AgentNode, type AgentStreamState } from "@/components/agent-status-stream";
import { WorkflowCanvas } from "@/components/workflow-canvas";
import { CheckCircle2Icon, XCircleIcon, CircleDotIcon, ClockIcon, ShieldQuestionIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

const NODE_LABELS: Record<string, string> = {
  supervisor: "调度规划",
  rfp_parser: "解析资料",
  knowledge_retriever: "检索证据",
  section_drafter: "起草章节",
  quality_reviewer: "质量审核",
  human_approval: "人工确认",
  persist_result: "保存结果",
  workflow: "工作流",
};

function getNodeLabel(name: string) {
  return NODE_LABELS[name] ?? name;
}

function NodeStatusIcon({ status }: { status: AgentNode["status"] }) {
  switch (status) {
    case "running":
      return <Spinner className="size-4 text-primary" />;
    case "completed":
      return <CheckCircle2Icon className="size-4 text-primary" />;
    case "failed":
      return <XCircleIcon className="size-4 text-destructive" />;
    case "pending":
    default:
      return <ClockIcon className="size-4 text-muted-foreground/40" />;
  }
}

function ReviewScoreCard({ reviewResult }: { reviewResult: AgentStreamState["reviewResult"] }) {
  const { t } = useTranslation(["projects"]);
  if (!reviewResult) return null;

  const scorePercent = Math.round(reviewResult.score * 100);
  const scoreColor = reviewResult.pass ? "text-primary" : "text-destructive";

  return (
    <Card size="sm" className="border-primary/20 bg-card/95">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">{t("agent.reviewTitle")}</CardTitle>
          <Badge variant={reviewResult.pass ? "default" : "destructive"}>
            {reviewResult.pass ? t("agent.pass") : t("agent.fail")}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-baseline gap-2">
          <span className={cn("text-3xl font-bold tabular-nums", scoreColor)}>
            {scorePercent}
          </span>
          <span className="text-sm text-muted-foreground">/ 100</span>
        </div>
        <Progress value={scorePercent}>
          <ProgressLabel>{t("agent.score")}</ProgressLabel>
          <ProgressValue />
        </Progress>
        {reviewResult.feedback && (
          <p className="text-xs text-muted-foreground whitespace-pre-wrap">
            {reviewResult.feedback}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function ApprovalPrompt({
  message,
  onApprove,
  onReject,
}: {
  message: string | null;
  onApprove?: () => void;
  onReject?: () => void;
}) {
  const { t } = useTranslation(["projects"]);
  return (
    <Card size="sm" className="border-primary/25 bg-primary/5">
      <CardContent className="flex flex-col gap-3 py-3">
        <div className="flex items-center gap-2">
          <ShieldQuestionIcon className="size-5 text-primary" />
          <span className="text-sm font-medium">{t("agent.approvalRequired")}</span>
        </div>
        {message && <p className="text-xs text-muted-foreground">{message}</p>}
        <div className="flex gap-2">
          <Button size="sm" onClick={onApprove}>
            {t("agent.approve")}
          </Button>
          <Button size="sm" variant="outline" onClick={onReject}>
            {t("agent.reject")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export interface AgentProgressProps {
  runId: string | null;
  onApprove?: () => void;
  onReject?: () => void;
}

export function AgentProgress({ runId, onApprove, onReject }: AgentProgressProps) {
  const { t } = useTranslation(["projects"]);
  const stream = useAgentStream(runId);

  if (!runId) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <CircleDotIcon className="size-8 mb-3 opacity-40" />
          <p className="text-sm">{t("agent.noRun")}</p>
          <p className="text-xs mt-1">{t("agent.noRunDesc")}</p>
        </CardContent>
      </Card>
    );
  }

  const totalNodes = stream.nodes.length;
  const completedCount = stream.completedNodes.length;
  const progressPercent = totalNodes > 0 ? Math.round((completedCount / totalNodes) * 100) : 0;

  return (
    <div className="flex min-w-0 flex-col gap-4">
      {/* Overall progress */}
      <Card className="border-foreground/10 bg-card/95 shadow-sm">
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <CardTitle className="text-lg">{t("agent.title")}</CardTitle>
              <CardDescription className="truncate">{t("agent.runId", { id: runId.slice(0, 8) })}</CardDescription>
            </div>
            <Badge className="w-fit" variant={stream.isRunning ? "default" : stream.error ? "destructive" : "outline"}>
              {stream.isRunning ? t("agent.running") : stream.error ? t("agent.failed") : t("agent.idle")}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {totalNodes > 0 && (
            <div className="flex flex-col gap-2">
              <Progress value={progressPercent}>
                <ProgressLabel>{t("agent.progress")}</ProgressLabel>
                <ProgressValue />
              </Progress>
              <p className="text-xs text-muted-foreground">
                {t("agent.nodesComplete", { done: completedCount, total: totalNodes })}
              </p>
            </div>
          )}

          <WorkflowCanvas
            nodes={stream.nodes}
            currentNode={stream.currentNode}
            isWaitingApproval={stream.isWaitingApproval}
          />

          {stream.error && (
            <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2">
              <XCircleIcon className="size-4 text-destructive shrink-0" />
              <p className="text-xs text-destructive">{stream.error}</p>
            </div>
          )}

          {/* Node timeline */}
          <div className="flex flex-col gap-1">
            {stream.nodes.map((node) => (
              <div
                key={node.name}
                className={cn(
                  "flex min-w-0 items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors",
                  node.status === "running" && "bg-primary/5 border border-primary/20",
                  node.status === "completed" && "opacity-80",
                  node.status === "failed" && "bg-destructive/5 border border-destructive/20",
                  node.status === "pending" && "opacity-50",
                )}
              >
                <NodeStatusIcon status={node.status} />
                <span className={cn("min-w-0 flex-1 truncate", node.status === "pending" && "text-muted-foreground")}>
                  {getNodeLabel(node.name)}
                </span>
                {node.status === "completed" && node.completed_at && (
                  <span className="text-xs text-muted-foreground">
                    {new Date(node.completed_at).toLocaleTimeString()}
                  </span>
                )}
                {node.status === "failed" && node.error && (
                  <span className="max-w-[45%] truncate text-xs text-destructive sm:max-w-[200px]">{node.error}</span>
                )}
              </div>
            ))}
          </div>

          {stream.currentNode && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Spinner className="size-3" />
              <span>{t("agent.executing", { node: stream.currentNode })}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Review score */}
      <ReviewScoreCard reviewResult={stream.reviewResult} />

      {/* Approval prompt */}
      {stream.isWaitingApproval && (
        <ApprovalPrompt
          message={stream.approvalMessage}
          onApprove={onApprove}
          onReject={onReject}
        />
      )}
    </div>
  );
}
