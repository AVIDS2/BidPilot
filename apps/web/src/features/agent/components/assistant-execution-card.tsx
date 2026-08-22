import { useEffect, useState } from "react";
import {
  AlertCircleIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  Loader2Icon,
  WrenchIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { AssistantExecutionItem } from "@/features/agent/state/agent-store";
import { cn } from "@/lib/utils";
import { getAssistantToolLabel } from "./assistant-tool-metadata";

export function AssistantExecutionCard({ item }: { item: AssistantExecutionItem }) {
  const { t } = useTranslation("ai-assistant");
  const failed = item.status === "failed";
  const running = item.status === "running";
  const succeeded = item.status === "succeeded";
  const defaultExpanded = running || item.status === "pending" || failed;
  const [expanded, setExpanded] = useState(defaultExpanded);
  const hasDetails = Boolean(item.summary || item.errorMessage);
  const title = getAssistantToolLabel(item.toolName ?? item.title, t);

  useEffect(() => {
    setExpanded(defaultExpanded);
  }, [defaultExpanded, item.id, item.status]);

  return (
    <div
      className={cn(
        "w-full rounded-2xl rounded-bl-md border text-xs shadow-sm transition-all",
        succeeded ? "px-2.5 py-2" : "px-3 py-2.5",
      )}
      style={{
        background: succeeded ? "color-mix(in oklab, var(--card) 55%, transparent)" : "var(--card)",
        borderColor: succeeded ? "color-mix(in oklab, var(--border) 70%, transparent)" : "var(--border)",
        color: "var(--foreground)",
      }}
    >
      <div className="flex items-start gap-2">
        <div
          className={cn(
            "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
            running && "animate-pulse",
          )}
          style={{ background: "var(--muted)", color: failed ? "var(--destructive)" : "var(--primary)" }}
        >
          {running ? (
            <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
          ) : failed ? (
            <AlertCircleIcon className="h-3.5 w-3.5" />
          ) : succeeded ? (
            <CheckCircle2Icon className="h-3.5 w-3.5" />
          ) : (
            <WrenchIcon className="h-3.5 w-3.5" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium truncate">{title}</span>
            <div className="flex shrink-0 items-center gap-1.5">
              <span className="capitalize" style={{ color: "var(--muted-foreground)" }}>
                {t(`activity.status.${item.status}`, { defaultValue: item.status })}
              </span>
              {hasDetails && (
                <button
                  type="button"
                  aria-label={expanded ? "Hide tool details" : "Show tool details"}
                  aria-expanded={expanded}
                  onClick={() => setExpanded((value) => !value)}
                  className="rounded-full p-0.5 text-muted-foreground transition hover:bg-muted hover:text-foreground"
                >
                  <ChevronDownIcon
                    className={cn(
                      "h-3.5 w-3.5 transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]",
                      expanded && "rotate-180",
                    )}
                  />
                </button>
              )}
            </div>
          </div>
          {hasDetails && (
            <div
              className={cn(
                "grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] motion-reduce:transition-none",
                expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
              )}
            >
              <div className="min-h-0 overflow-hidden">
                {item.summary && (
                  <p className="mt-1 leading-relaxed" style={{ color: "var(--muted-foreground)" }}>
                    {item.summary}
                  </p>
                )}
                {item.errorMessage && (
                  <p className="mt-1 leading-relaxed" style={{ color: "var(--destructive)" }}>
                    {item.errorMessage}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
