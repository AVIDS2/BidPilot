import { WorkflowIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";

export function AssistantWorkflowCard({ item }: { item: AssistantExecutionItem }) {
  const { t } = useTranslation("ai-assistant");
  const runId = item.runId || (typeof item.result?.run_id === "string" ? item.result.run_id : null);
  const nodes = item.nodes ?? [];

  return (
    <div
      className="rounded-lg border px-3 py-2.5 text-xs"
      style={{ background: "var(--card)", borderColor: "var(--border)", color: "var(--foreground)" }}
    >
      <div className="flex items-start gap-2">
        <div
          className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-md"
          style={{ background: "var(--muted)", color: "var(--primary)" }}
        >
          <WorkflowIcon className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="font-medium">{t("execution.workflowStarted")}</div>
            <span className="shrink-0" style={{ color: "var(--muted-foreground)" }}>
              {t(`execution.status.${item.status}`)}
            </span>
          </div>
          <p className="mt-1" style={{ color: "var(--muted-foreground)" }}>
            {item.toolName}
          </p>
          {runId && (
            <div
              className="mt-2 truncate rounded-md px-2 py-1 font-mono text-[11px]"
              style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}
            >
              {runId}
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
            <div className="mt-3 space-y-1">
              {nodes.map((node) => (
                <div
                  key={node.name}
                  className="flex items-center justify-between rounded-md px-2 py-1"
                  style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}
                >
                  <span className="truncate">{node.name}</span>
                  <span className="shrink-0 capitalize">{node.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
