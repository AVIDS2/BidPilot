import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  ActivityIcon,
  BotIcon,
  CheckCircle2Icon,
  CircleAlertIcon,
  Clock3Icon,
  ExternalLinkIcon,
  FileTextIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  WorkflowIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  listRuntimeEvents,
  listRuntimeRuns,
  type RuntimeEventRead,
  type RuntimeRunListItem,
} from "@/lib/api";

type RunFilter = "all" | "active" | "approval" | "failed" | "completed";

const ACTIVE_STATUSES = new Set(["queued", "running", "cancel_requested"]);
const COMPLETED_STATUSES = new Set(["succeeded", "cancelled", "expired"]);

function filterRuns(runs: RuntimeRunListItem[], filter: RunFilter) {
  if (filter === "all") return runs;
  if (filter === "active") return runs.filter((run) => ACTIVE_STATUSES.has(run.status));
  if (filter === "approval") return runs.filter((run) => run.status === "awaiting_approval");
  if (filter === "failed") return runs.filter((run) => run.status === "failed");
  return runs.filter((run) => COMPLETED_STATUSES.has(run.status));
}

function statusIcon(status: string) {
  if (status === "failed") return <CircleAlertIcon className="size-4 text-destructive" />;
  if (status === "awaiting_approval") return <ShieldCheckIcon className="size-4 text-amber-500" />;
  if (ACTIVE_STATUSES.has(status)) return <ActivityIcon className="size-4 text-primary" />;
  if (COMPLETED_STATUSES.has(status)) return <CheckCircle2Icon className="size-4 text-emerald-500" />;
  return <Clock3Icon className="size-4 text-muted-foreground" />;
}

function eventIcon(type: string) {
  if (type.startsWith("approval.")) return <ShieldCheckIcon className="size-3.5 text-amber-500" />;
  if (type.startsWith("workflow.")) return <WorkflowIcon className="size-3.5 text-primary" />;
  if (type.includes("failed")) return <CircleAlertIcon className="size-3.5 text-destructive" />;
  if (type.includes("completed") || type.includes("succeeded")) return <CheckCircle2Icon className="size-3.5 text-emerald-500" />;
  return <ActivityIcon className="size-3.5 text-muted-foreground" />;
}

function formatTimestamp(value: string | null, language: string) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "-";
  return new Intl.DateTimeFormat(language === "zh-CN" ? "zh-CN" : "en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function runKindIcon(kind: string) {
  if (kind === "workflow_bridge") return <WorkflowIcon className="size-4" />;
  if (kind === "assistant_turn") return <BotIcon className="size-4" />;
  return <ActivityIcon className="size-4" />;
}

export function RunCenterPage() {
  const { t, i18n } = useTranslation(["runs", "common"]);
  const [filter, setFilter] = useState<RunFilter>("all");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const runsQuery = useQuery({
    queryKey: ["runtime-runs", 50],
    queryFn: () => listRuntimeRuns(50),
    staleTime: 10_000,
    retry: 1,
  });
  const runs = runsQuery.data ?? [];
  const visibleRuns = useMemo(() => filterRuns(runs, filter), [filter, runs]);
  const selectedRun = visibleRuns.find((run) => run.id === selectedRunId) ?? null;
  const eventsQuery = useQuery({
    queryKey: ["runtime-run-events", selectedRun?.id],
    queryFn: () => listRuntimeEvents(selectedRun!.id),
    enabled: Boolean(selectedRun),
    staleTime: 5_000,
    retry: 1,
  });

  useEffect(() => {
    setSelectedRunId((current) => (
      current && visibleRuns.some((run) => run.id === current)
        ? current
        : visibleRuns[0]?.id ?? null
    ));
  }, [visibleRuns]);

  const filterCounts: Record<RunFilter, number> = {
    all: runs.length,
    active: runs.filter((run) => ACTIVE_STATUSES.has(run.status)).length,
    approval: runs.filter((run) => run.status === "awaiting_approval").length,
    failed: runs.filter((run) => run.status === "failed").length,
    completed: runs.filter((run) => COMPLETED_STATUSES.has(run.status)).length,
  };
  const filters: RunFilter[] = ["all", "active", "approval", "failed", "completed"];

  return (
    <section className="mx-auto flex w-full max-w-[1320px] min-w-0 flex-col gap-5" aria-label={t("runs:title")}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex items-center gap-2 text-primary">
            <ActivityIcon className="size-4" />
            <span className="text-xs font-medium uppercase tracking-[0.16em]">BidPilot Runtime</span>
          </div>
          <h2 className="text-2xl font-semibold tracking-[-0.03em] text-foreground sm:text-3xl">{t("runs:title")}</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">{t("runs:subtitle")}</p>
        </div>
        <Button variant="outline" className="w-fit" onClick={() => void runsQuery.refetch()} disabled={runsQuery.isFetching}>
          <RefreshCwIcon className={cn("mr-2 size-4", runsQuery.isFetching && "animate-spin")} />
          {t("runs:refresh")}
        </Button>
      </div>

      <div className="flex flex-wrap gap-2" aria-label={t("runs:filters.all")}>
        {filters.map((candidate) => (
          <Button
            key={candidate}
            type="button"
            size="sm"
            variant={filter === candidate ? "default" : "outline"}
            className="gap-2 rounded-full"
            onClick={() => setFilter(candidate)}
          >
            {t(`runs:filters.${candidate}`)}
            <span className="text-xs tabular-nums opacity-80">{filterCounts[candidate]}</span>
          </Button>
        ))}
      </div>

      {runsQuery.isLoading ? (
        <RunCenterSkeleton />
      ) : runsQuery.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {t("common:error.fallback")}
          </CardContent>
        </Card>
      ) : (
        <div className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
          <Card className="min-w-0 overflow-hidden">
            <CardHeader className="border-b pb-4">
              <CardTitle className="text-base">{t("runs:recent")}</CardTitle>
              <CardDescription>{t("runs:recentCount", { count: visibleRuns.length })}</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {visibleRuns.length === 0 ? (
                <Empty className="min-h-72 px-6">
                  <EmptyHeader>
                    <EmptyMedia variant="icon"><ActivityIcon /></EmptyMedia>
                    <EmptyTitle>{t("runs:emptyTitle")}</EmptyTitle>
                    <EmptyDescription>{t("runs:emptyDescription")}</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : (
                <div className="divide-y">
                  {visibleRuns.map((run) => (
                    <RunListItem
                      key={run.id}
                      run={run}
                      selected={run.id === selectedRun?.id}
                      onSelect={() => setSelectedRunId(run.id)}
                      language={i18n.language}
                      t={t}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <RunDetail
            run={selectedRun}
            events={eventsQuery.data?.items ?? []}
            eventsLoading={eventsQuery.isLoading}
            language={i18n.language}
            t={t}
          />
        </div>
      )}
    </section>
  );
}

function RunListItem({
  run,
  selected,
  onSelect,
  language,
  t,
}: {
  run: RuntimeRunListItem;
  selected: boolean;
  onSelect: () => void;
  language: string;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        "flex w-full min-w-0 items-start gap-3 px-4 py-4 text-left transition-colors sm:px-5",
        "hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected && "bg-primary/[0.055]",
      )}
    >
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground">
        {runKindIcon(run.kind)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="truncate text-sm font-medium text-foreground">{t(`runs:kinds.${run.kind}`, { defaultValue: run.kind })}</span>
          <StatusBadge status={run.status} t={t} />
        </div>
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {run.project_name ?? t("runs:noProject", { defaultValue: "General Agent task" })}
        </p>
        {run.latest_event_summary && (
          <p className="mt-2 line-clamp-2 text-sm leading-5 text-muted-foreground">{run.latest_event_summary}</p>
        )}
      </div>
      <time className="shrink-0 pt-0.5 text-xs text-muted-foreground" dateTime={run.created_at}>
        {formatTimestamp(run.created_at, language)}
      </time>
    </button>
  );
}

function StatusBadge({ status, t }: { status: string; t: (key: string, options?: Record<string, unknown>) => string }) {
  const className = status === "failed"
    ? "border-destructive/25 bg-destructive/10 text-destructive"
    : status === "awaiting_approval"
      ? "border-amber-500/25 bg-amber-500/10 text-amber-700 dark:text-amber-400"
      : ACTIVE_STATUSES.has(status)
        ? "border-primary/25 bg-primary/10 text-primary"
        : "border-border bg-muted/50 text-muted-foreground";
  return (
    <Badge variant="outline" className={cn("gap-1.5 border text-[11px] font-medium", className)}>
      {statusIcon(status)}
      {t(`common:statusValues.${status}`, { defaultValue: status })}
    </Badge>
  );
}

function RunDetail({
  run,
  events,
  eventsLoading,
  language,
  t,
}: {
  run: RuntimeRunListItem | null;
  events: RuntimeEventRead[];
  eventsLoading: boolean;
  language: string;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  if (!run) {
    return (
      <Card className="min-h-72">
        <CardContent className="flex h-full min-h-72 items-center justify-center px-6 text-center text-sm text-muted-foreground">
          {t("runs:noSelection")}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="min-w-0 overflow-hidden xl:sticky xl:top-6 xl:max-h-[calc(100dvh-8rem)]">
      <CardHeader className="border-b pb-4">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2 text-base">
              {runKindIcon(run.kind)}
              <span className="truncate">{t(`runs:kinds.${run.kind}`, { defaultValue: run.kind })}</span>
            </CardTitle>
            <CardDescription className="mt-1 truncate">
              {run.project_name ?? t("runs:noProject", { defaultValue: "General Agent task" })}
            </CardDescription>
          </div>
          <StatusBadge status={run.status} t={t} />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <DetailMetric label={t("runs:startedAt")} value={formatTimestamp(run.started_at ?? run.created_at, language)} />
          <DetailMetric label={t("runs:completedAt")} value={formatTimestamp(run.finished_at, language)} />
          <DetailMetric label={t("runs:engine", { defaultValue: "Runtime" })} value={t(`runs:engines.${run.engine}`, { defaultValue: run.engine })} />
          <DetailMetric label={t("runs:lastUpdate")} value={run.latest_event_summary ?? "-"} />
        </div>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-col gap-4 p-4 sm:p-5">
        <div className="flex flex-wrap gap-2">
          {run.project_id && (
            <Button nativeButton={false} render={<Link to={`/projects/${run.project_id}?tab=runs`} />} size="sm" variant="outline">
              <>
                <FileTextIcon className="mr-2 size-3.5" />
                {t("runs:openProject")}
              </>
            </Button>
          )}
          <Button nativeButton={false} render={<Link to={run.project_id ? `/agent?project=${encodeURIComponent(run.project_id)}` : "/agent"} />} size="sm" variant="outline">
            <>
              <BotIcon className="mr-2 size-3.5" />
              {t("runs:continueWithAgent")}
              <ExternalLinkIcon className="ml-2 size-3" />
            </>
          </Button>
        </div>
        <div className="min-h-0">
          <h3 className="mb-3 text-sm font-medium text-foreground">{t("runs:events")}</h3>
          {eventsLoading ? (
            <div className="space-y-3"><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-4/5" /><Skeleton className="h-10 w-3/4" /></div>
          ) : events.length === 0 ? (
            <p className="rounded-xl border border-dashed px-3 py-5 text-sm text-muted-foreground">{t("runs:noEvents")}</p>
          ) : (
            <ol className="max-h-[42dvh] space-y-3 overflow-y-auto pr-1 xl:max-h-[calc(100dvh-26rem)]">
              {events.map((event) => <RuntimeEventItem key={`${event.run_id}-${event.sequence}`} event={event} t={t} />)}
            </ol>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg bg-muted/50 px-2.5 py-2">
      <p className="truncate text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-xs font-medium text-foreground" title={value}>{value}</p>
    </div>
  );
}

function RuntimeEventItem({ event, t }: { event: RuntimeEventRead; t: (key: string, options?: Record<string, unknown>) => string }) {
  return (
    <li className="flex min-w-0 gap-3">
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-muted">
        {eventIcon(event.type)}
      </div>
      <div className="min-w-0 pb-1">
        <p className="text-xs font-medium text-foreground">{t(`runs:eventTypes.${event.type}`, { defaultValue: event.type })}</p>
        <p className="mt-0.5 break-words text-sm leading-5 text-muted-foreground">{event.public_summary}</p>
      </div>
    </li>
  );
}

function RunCenterSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
      <Card><CardContent className="space-y-3 p-5"><Skeleton className="h-8 w-40" /><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /></CardContent></Card>
      <Card><CardContent className="space-y-3 p-5"><Skeleton className="h-8 w-32" /><Skeleton className="h-16 w-full" /><Skeleton className="h-40 w-full" /></CardContent></Card>
    </div>
  );
}
