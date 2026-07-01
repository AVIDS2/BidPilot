import { useEffect, useMemo, useState } from "react";
import { ActivityIcon, BotIcon, CheckCircle2Icon, Clock3Icon, GitBranchIcon, XCircleIcon } from "lucide-react";
import { AgentProgress } from "@/components/agent-progress";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ExecutionRunRead } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useTranslation } from "react-i18next";

interface AgentTabProps {
  runs: ExecutionRunRead[];
}

export function AgentTab({ runs }: AgentTabProps) {
  const { t } = useTranslation("projects");
  const sortedRuns = useMemo(() => [...(runs ?? [])].sort(sortRunsForWorkbench), [runs]);
  const activeRuns = sortedRuns.filter((run) => run.status === "running" || run.status === "pending");
  const completedRuns = sortedRuns.filter((run) => run.status !== "running" && run.status !== "pending");
  const [agentRunId, setAgentRunId] = useState<string | null>(() => sortedRuns[0]?.id ?? null);
  const selectedRun = sortedRuns.find((run) => run.id === agentRunId) ?? null;

  useEffect(() => {
    if (!sortedRuns.length) {
      setAgentRunId(null);
      return;
    }
    setAgentRunId((current) => (current && sortedRuns.some((run) => run.id === current) ? current : sortedRuns[0].id));
  }, [sortedRuns]);

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <Card className="border-foreground/10 bg-card/95 shadow-sm">
        <CardHeader className="gap-3 md:flex-row md:items-start md:justify-between">
          <div className="flex min-w-0 gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary ring-1 ring-primary/20">
              <BotIcon className="size-5" />
            </div>
            <div className="min-w-0">
              <CardTitle className="truncate text-lg tracking-[-0.02em]">{t("agent.tabTitle")}</CardTitle>
              <CardDescription>{t("agent.workbenchDesc")}</CardDescription>
            </div>
          </div>
          <div className="grid w-full grid-cols-3 gap-2 text-right text-xs md:w-auto md:min-w-72">
            <RunMetric label={t("agent.metrics.total")} value={sortedRuns.length} />
            <RunMetric label={t("agent.metrics.active")} value={activeRuns.length} />
            <RunMetric label={t("agent.metrics.done")} value={completedRuns.length} />
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {sortedRuns.length > 0 ? (
            <>
              <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_18rem]">
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {sortedRuns.slice(0, 6).map((run) => (
                    <RunCard
                      key={run.id}
                      run={run}
                      statusLabel={t(`statusValues.${run.status}`, { defaultValue: run.status })}
                      typeLabel={getRunTypeLabel(run.run_type, t)}
                      selected={run.id === agentRunId}
                      onSelect={() => setAgentRunId(run.id)}
                    />
                  ))}
                </div>
                <Field className="w-full self-start">
                  <FieldLabel>{t("agent.selectRun")}</FieldLabel>
                  <Select value={agentRunId ?? ""} onValueChange={(v) => setAgentRunId(v || null)}>
                    <SelectTrigger>
                      <SelectValue placeholder={t("agent.selectRunPlaceholder")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {activeRuns.map((run) => (
                          <SelectItem key={run.id} value={run.id}>
                            {formatRunOption(run, t)}
                          </SelectItem>
                        ))}
                        {completedRuns.map((run) => (
                          <SelectItem key={run.id} value={run.id}>
                            {formatRunOption(run, t)}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                  {selectedRun && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      {t("agent.selectedRunHint", {
                        id: selectedRun.id.slice(0, 8),
                        status: t(`statusValues.${selectedRun.status}`, { defaultValue: selectedRun.status }),
                      })}
                    </p>
                  )}
                </Field>
              </div>
            </>
          ) : (
            <div className="rounded-2xl border border-dashed bg-muted/25 px-5 py-8 text-sm text-muted-foreground">
              <div className="mb-2 flex items-center gap-2 font-medium text-foreground">
                <GitBranchIcon className="size-4 text-primary" />
                {t("agent.noRun")}
              </div>
              <p>{t("agent.noRunDesc")}</p>
            </div>
          )}
        </CardContent>
      </Card>
      <AgentProgress runId={agentRunId} />
    </div>
  );
}

function sortRunsForWorkbench(a: ExecutionRunRead, b: ExecutionRunRead) {
  const rank = (status: string) => {
    if (status === "running") return 0;
    if (status === "pending") return 1;
    if (status === "failed") return 2;
    if (status === "succeeded" || status === "completed") return 3;
    return 4;
  };
  return rank(a.status) - rank(b.status);
}

function formatRunOption(run: ExecutionRunRead, t: (key: string, options?: Record<string, unknown>) => string) {
  return `${getRunTypeLabel(run.run_type, t)} · ${t(`statusValues.${run.status}`, { defaultValue: run.status })} · ${run.id.slice(0, 8)}`;
}

function getRunTypeLabel(runType: string, t: (key: string, options?: Record<string, unknown>) => string) {
  return t(`agent.runTypes.${runType}`, { defaultValue: runType });
}

function RunMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-0 rounded-xl border bg-background/60 px-3 py-2">
      <div className="text-lg font-medium tabular-nums tracking-[-0.02em]">{value}</div>
      <div className="truncate text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}

function RunStatusIcon({ status }: { status: string }) {
  if (status === "running") return <ActivityIcon className="size-4 text-primary" />;
  if (status === "failed") return <XCircleIcon className="size-4 text-destructive" />;
  if (status === "succeeded" || status === "completed") return <CheckCircle2Icon className="size-4 text-primary" />;
  return <Clock3Icon className="size-4 text-muted-foreground" />;
}

function RunCard({
  run,
  statusLabel,
  typeLabel,
  selected,
  onSelect,
}: {
  run: ExecutionRunRead;
  statusLabel: string;
  typeLabel: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "group rounded-2xl border bg-background/55 p-3 text-left transition-[border-color,box-shadow,transform,background-color] hover:-translate-y-0.5 hover:border-primary/25 hover:bg-background",
        selected && "border-primary/40 bg-primary/5 shadow-[0_18px_44px_-34px_color-mix(in_oklch,var(--primary)_70%,transparent)]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <RunStatusIcon status={run.status} />
            <span className="truncate text-sm font-medium tracking-[-0.01em]">{typeLabel}</span>
          </div>
          <div className="mt-1 font-mono text-[11px] text-muted-foreground">{run.id.slice(0, 8)}</div>
        </div>
        <Badge variant={selected ? "default" : "outline"} className="shrink-0 capitalize">
          {statusLabel}
        </Badge>
      </div>
    </button>
  );
}
