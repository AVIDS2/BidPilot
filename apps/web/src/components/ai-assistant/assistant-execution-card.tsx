import { AlertCircleIcon, CheckCircle2Icon, Loader2Icon, WrenchIcon } from "lucide-react";
import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";
import { cn } from "@/lib/utils";

export function AssistantExecutionCard({ item }: { item: AssistantExecutionItem }) {
  const failed = item.status === "failed";
  const running = item.status === "running";
  const succeeded = item.status === "succeeded";

  return (
    <div
      className="ml-0 max-w-[92%] rounded-2xl rounded-bl-md border px-3 py-2.5 text-xs shadow-sm"
      style={{ background: "var(--card)", borderColor: "var(--border)", color: "var(--foreground)" }}
    >
      <div className="flex items-start gap-2">
        <div
          className={cn("mt-0.5 flex h-6 w-6 items-center justify-center rounded-md", running && "animate-pulse")}
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
            <span className="font-medium truncate">{item.title}</span>
            <span className="shrink-0 capitalize" style={{ color: "var(--muted-foreground)" }}>
              {item.status}
            </span>
          </div>
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
    </div>
  );
}
