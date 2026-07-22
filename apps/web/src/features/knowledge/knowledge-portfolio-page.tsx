import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  BookOpenCheckIcon,
  CheckCircle2Icon,
  Clock3Icon,
  FileTextIcon,
  FolderOpenIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { listKnowledgePortfolio, type MemoryPortfolioProjectRead } from "@/lib/api";

type KnowledgeFilter = "all" | "ready" | "review" | "empty";

const FILTERS: KnowledgeFilter[] = ["all", "ready", "review", "empty"];

function formatTimestamp(value: string | null, language: string) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(language === "zh-CN" ? "zh-CN" : "en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function matchesFilter(item: MemoryPortfolioProjectRead, filter: KnowledgeFilter) {
  if (filter === "all") return true;
  if (filter === "ready") return item.active_shared_count > 0;
  if (filter === "review") return typeof item.proposed_shared_count === "number" && item.proposed_shared_count > 0;
  return item.active_shared_count === 0;
}

function compilationTone(status: string | null) {
  if (status === "succeeded") return "border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400";
  if (status === "queued" || status === "running") return "border-primary/25 bg-primary/10 text-primary";
  if (status === "failed" || status === "dispatch_failed") return "border-destructive/25 bg-destructive/10 text-destructive";
  return "border-border bg-muted/50 text-muted-foreground";
}

export function KnowledgePortfolioPage() {
  const { t, i18n } = useTranslation(["knowledge-portfolio", "common"]);
  const [filter, setFilter] = useState<KnowledgeFilter>("all");
  const portfolioQuery = useQuery({
    queryKey: ["knowledge-portfolio", 50],
    queryFn: () => listKnowledgePortfolio(50),
    staleTime: 15_000,
    retry: 1,
  });
  const items = portfolioQuery.data ?? [];
  const visibleItems = useMemo(
    () => items.filter((item) => matchesFilter(item, filter)),
    [filter, items],
  );
  const activeKnowledgeCount = items.reduce((total, item) => total + item.active_shared_count, 0);
  const reviewCount = items.reduce(
    (total, item) => total + (item.proposed_shared_count ?? 0),
    0,
  );
  const filterCounts: Record<KnowledgeFilter, number> = {
    all: items.length,
    ready: items.filter((item) => item.active_shared_count > 0).length,
    review: items.filter((item) => typeof item.proposed_shared_count === "number" && item.proposed_shared_count > 0).length,
    empty: items.filter((item) => item.active_shared_count === 0).length,
  };

  return (
    <section className="mx-auto flex w-full max-w-[1320px] min-w-0 flex-col gap-5" aria-label={t("title")}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex items-center gap-2 text-primary">
            <BookOpenCheckIcon className="size-4" />
            <span className="text-xs font-medium uppercase tracking-[0.16em]">BidPilot Wiki</span>
          </div>
          <h2 className="text-2xl font-semibold tracking-[-0.03em] text-foreground sm:text-3xl">{t("title")}</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button
          variant="outline"
          className="w-fit"
          onClick={() => void portfolioQuery.refetch()}
          disabled={portfolioQuery.isFetching}
        >
          <RefreshCwIcon className={cn("mr-2 size-4", portfolioQuery.isFetching && "animate-spin")} />
          {t("refresh")}
        </Button>
      </div>

      <div className="grid min-w-0 gap-3 sm:grid-cols-3">
        <PortfolioMetric icon={<FolderOpenIcon />} label={t("metrics.projects")} value={items.length} />
        <PortfolioMetric icon={<BookOpenCheckIcon />} label={t("metrics.sharedKnowledge")} value={activeKnowledgeCount} />
        <PortfolioMetric icon={<ShieldCheckIcon />} label={t("metrics.reviewQueue")} value={reviewCount} subdued={reviewCount === 0} />
      </div>

      <div className="flex flex-wrap gap-2" aria-label={t("filters.all")}>
        {FILTERS.map((candidate) => (
          <Button
            key={candidate}
            type="button"
            size="sm"
            variant={filter === candidate ? "default" : "outline"}
            className="gap-2 rounded-full"
            onClick={() => setFilter(candidate)}
          >
            {t(`filters.${candidate}`)}
            <span className="text-xs tabular-nums opacity-80">{filterCounts[candidate]}</span>
          </Button>
        ))}
      </div>

      {portfolioQuery.isLoading ? (
        <PortfolioSkeleton />
      ) : portfolioQuery.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {t("common:error.fallback")}
          </CardContent>
        </Card>
      ) : visibleItems.length === 0 ? (
        <KnowledgeEmptyState filter={filter} t={t} />
      ) : (
        <Card className="min-w-0 overflow-hidden">
          <CardHeader className="border-b pb-4">
            <CardTitle className="text-base">{t("projectsTitle")}</CardTitle>
            <CardDescription>{t("projectsDescription", { count: visibleItems.length })}</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {visibleItems.map((item) => (
                <KnowledgeProjectRow key={item.project_id} item={item} language={i18n.language} t={t} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </section>
  );
}

function PortfolioMetric({
  icon,
  label,
  value,
  subdued = false,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  subdued?: boolean;
}) {
  return (
    <Card className="min-w-0">
      <CardContent className="flex items-center gap-3 p-4">
        <div className={cn("flex size-9 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground", !subdued && "bg-primary/10 text-primary")}>
          {icon}
        </div>
        <div className="min-w-0">
          <p className="truncate text-xs text-muted-foreground">{label}</p>
          <p className="mt-0.5 text-2xl font-semibold tracking-tight text-foreground">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function KnowledgeProjectRow({
  item,
  language,
  t,
}: {
  item: MemoryPortfolioProjectRead;
  language: string;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  const lastUpdate = formatTimestamp(item.latest_shared_memory_at, language);
  const compilationTimestamp = formatTimestamp(item.latest_compilation_at, language);

  return (
    <div className="flex min-w-0 flex-col gap-4 px-4 py-4 sm:px-5 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <BookOpenCheckIcon className="size-4" />
        </div>
        <div className="min-w-0">
          <h3 className="truncate text-sm font-medium text-foreground">{item.project_name}</h3>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="gap-1.5 border-border bg-muted/50 text-[11px] text-muted-foreground">
              <BookOpenCheckIcon className="size-3" />
              {t("sharedCount", { count: item.active_shared_count })}
            </Badge>
            {item.proposed_shared_count !== null && item.proposed_shared_count > 0 && (
              <Badge variant="outline" className="gap-1.5 border-amber-500/25 bg-amber-500/10 text-[11px] text-amber-700 dark:text-amber-400">
                <ShieldCheckIcon className="size-3" />
                {t("proposalCount", { count: item.proposed_shared_count })}
              </Badge>
            )}
            {item.latest_compilation_status ? (
              <Badge variant="outline" className={cn("gap-1.5 border text-[11px]", compilationTone(item.latest_compilation_status))}>
                {item.latest_compilation_status === "succeeded" ? <CheckCircle2Icon className="size-3" /> : <Clock3Icon className="size-3" />}
                {t(`compilationStatuses.${item.latest_compilation_status}`, { defaultValue: item.latest_compilation_status })}
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1.5 border-border bg-muted/50 text-[11px] text-muted-foreground">
                <Clock3Icon className="size-3" />
                {t("notCompiled")}
              </Badge>
            )}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {lastUpdate
              ? t("updatedAt", { date: lastUpdate })
              : t("noSharedKnowledge")}
            {compilationTimestamp ? ` · ${t("compiledAt", { date: compilationTimestamp })}` : ""}
          </p>
        </div>
      </div>
      <Button nativeButton={false} render={<Link to={`/projects/${item.project_id}?tab=knowledge`} />} size="sm" variant="outline" className="w-fit shrink-0">
        <FileTextIcon className="mr-2 size-3.5" />
        {t("openBidWiki")}
      </Button>
    </div>
  );
}

function KnowledgeEmptyState({ filter, t }: { filter: KnowledgeFilter; t: (key: string, options?: Record<string, unknown>) => string }) {
  const noProjects = filter === "all";
  return (
    <Card>
      <CardContent className="py-12">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">{noProjects ? <FolderOpenIcon /> : <SparklesIcon />}</EmptyMedia>
            <EmptyTitle>{noProjects ? t("emptyTitle") : t("emptyFilterTitle")}</EmptyTitle>
            <EmptyDescription>{noProjects ? t("emptyDescription") : t("emptyFilterDescription")}</EmptyDescription>
          </EmptyHeader>
          {noProjects && (
            <Button nativeButton={false} render={<Link to="/projects" />} variant="outline">
              <FolderOpenIcon className="mr-2 size-4" />
              {t("openProjects")}
            </Button>
          )}
        </Empty>
      </CardContent>
    </Card>
  );
}

function PortfolioSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
      <Card>
        <CardContent className="space-y-3 p-5">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-11/12" />
          <Skeleton className="h-14 w-4/5" />
        </CardContent>
      </Card>
    </div>
  );
}
