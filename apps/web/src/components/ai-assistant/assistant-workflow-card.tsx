import {
  CheckCircle2Icon,
  CircleDashedIcon,
  LoaderCircleIcon,
  WorkflowIcon,
  XCircleIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { AssistantExecutionItem, WorkflowNodeProgress } from "@/lib/ai-assistant-store";

function nodeIcon(node: WorkflowNodeProgress) {
  if (node.status === "completed") {
    return <CheckCircle2Icon className="h-3.5 w-3.5" />;
  }
  if (node.status === "failed") {
    return <XCircleIcon className="h-3.5 w-3.5" />;
  }
  if (node.status === "running") {
    return <LoaderCircleIcon className="h-3.5 w-3.5 animate-spin" />;
  }
  return <CircleDashedIcon className="h-3.5 w-3.5" />;
}

export function AssistantWorkflowCard({ item }: { item: AssistantExecutionItem }) {
  const { t } = useTranslation("ai-assistant");
  const runId = item.runId || (typeof item.result?.run_id === "string" ? item.result.run_id : null);
  const nodes = item.nodes ?? [];
  const completedCount = nodes.filter((node) => node.status === "completed").length;
  const progressLabel = nodes.length > 0
    ? t("execution.nodesCompleted", { completed: completedCount, total: nodes.length })
    : t("execution.workflowQueued");
  const tone =
    item.status === "failed"
      ? "var(--destructive)"
      : item.status === "succeeded"
        ? "var(--primary)"
        : "var(--primary)";

  return (
    <div
      className="w-full overflow-hidden rounded-2xl rounded-bl-md border text-xs shadow-sm"
      style={{
        background:
          "linear-gradient(135deg, color-mix(in oklab, var(--primary) 8%, var(--card)), var(--card))",
        borderColor: "color-mix(in oklab, var(--primary) 20%, var(--border))",
        color: "var(--foreground)",
      }}
    >
      <div className="flex items-start gap-3 p-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" style={{ background: "var(--background)", color: tone }}>
          {item.status === "succeeded" ? (
            <CheckCircle2Icon className="h-4.5 w-4.5" />
          ) : item.status === "failed" ? (
            <XCircleIcon className="h-4.5 w-4.5" />
          ) : (
            <WorkflowIcon className="h-4.5 w-4.5" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="font-semibold">{t("execution.workflowStarted")}</div>
            <span
              className="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium"
              style={{
                background: "color-mix(in oklab, var(--primary) 12%, var(--background))",
                color: tone,
              }}
            >
              {t(`execution.status.${item.status}`)}
            </span>
          </div>
          <p className="mt-1.5" style={{ color: "var(--muted-foreground)" }}>
            {progressLabel}
          </p>
          {nodes.length > 0 && (
            <div className="mt-3 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--muted)" }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.max(8, Math.round((completedCount / nodes.length) * 100))}%`,
                  background: tone,
                }}
              />
            </div>
          )}
          {runId && (
            <div
              className="mt-3 truncate rounded-lg px-2.5 py-1.5 font-mono text-[10px]"
              style={{ background: "color-mix(in oklab, var(--background) 78%, transparent)", color: "var(--muted-foreground)" }}
            >
              {t("execution.runId")}: {runId}
            </div>
          )}
          {item.currentNode && (
            <p className="mt-2" style={{ color: "var(--muted-foreground)" }}>
              {t("execution.currentNode", { node: item.currentNode })}
            </p>
          )}
          {item.reviewResult && (
            <p className="mt-2" style={{ color: "var(--muted-foreground)" }}>
              {t("execution.review", {
                result: item.reviewResult.pass
                  ? t("execution.reviewPassed")
                  : t("execution.reviewFailed"),
                score: item.reviewResult.score,
              })}
            </p>
          )}
          {item.isWaitingApproval && (
            <p className="mt-2 max-h-20 overflow-hidden" style={{ color: "var(--primary)" }}>
              {item.approvalMessage || t("execution.waitingApproval")}
            </p>
          )}
          {nodes.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {nodes.map((node) => (
                <div
                  key={node.name}
                  className="flex items-center justify-between gap-2 rounded-xl px-2.5 py-2"
                  style={{ background: "color-mix(in oklab, var(--background) 78%, transparent)", color: "var(--muted-foreground)" }}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span style={{ color: node.status === "failed" ? "var(--destructive)" : tone }}>
                      {nodeIcon(node)}
                    </span>
                    <span className="truncate">{node.name}</span>
                  </span>
                  <span className="shrink-0">{t(`execution.nodeStatus.${node.status}`)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
