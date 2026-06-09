import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import {
  listProjects,
  listExecutionRuns,
  listProviderConfigs,
  type ProjectRead,
  type ExecutionRunRead,
} from "@/lib/api";
import {
  FolderIcon,
  FileTextIcon,
  ClipboardCheckIcon,
  CheckCircleIcon,
  PlusIcon,
  EyeIcon,
  DownloadIcon,
  SparklesIcon,
  ClockIcon,
  TrendingUpIcon,
} from "lucide-react";

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-7 w-16 mt-1" />
            </CardHeader>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <Skeleton className="h-5 w-32" />
          </CardHeader>
          <CardContent>
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full mb-2" />
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
          </CardHeader>
          <CardContent>
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full mb-2" />
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function RecentActivityItem({
  event,
}: {
  event: { project: string; action: string; time: string; type: string };
}) {
  const typeColors: Record<string, string> = {
    project_created: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
    status_changed: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    draft_started: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    draft_completed: "bg-green-500/10 text-green-600 dark:text-green-400",
    export: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
  };

  return (
    <div className="flex items-center gap-3 py-2">
      <div
        className={`flex size-8 shrink-0 items-center justify-center rounded-md ${
          typeColors[event.type] ?? "bg-muted"
        }`}
      >
        <ClockIcon className="size-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">
          {event.action}{" "}
          <span className="text-muted-foreground font-normal">
            {event.project}
          </span>
        </p>
      </div>
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {event.time}
      </span>
    </div>
  );
}

export function DashboardPage() {
  const { t } = useTranslation(["dashboard", "common"]);
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data: projects, isLoading: projectsLoading } = useQuery<ProjectRead[]>(
    {
      queryKey: ["projects"],
      queryFn: listProjects,
      staleTime: 30 * 1000,
    },
  );

  // Fetch recent execution runs across all projects
  const { data: allRuns } = useQuery<ExecutionRunRead[]>({
    queryKey: ["dashboard-runs"],
    queryFn: async () => {
      if (!projects || projects.length === 0) return [];
      const results = await Promise.allSettled(
        projects.map((p) => listExecutionRuns(p.id)),
      );
      return results
        .filter(
          (r): r is PromiseFulfilledResult<ExecutionRunRead[]> =>
            r.status === "fulfilled",
        )
        .flatMap((r) => r.value)
        .sort(
          (a, b) =>
            new Date(b.output_json?.created_at as string ?? 0).getTime() -
            new Date(a.output_json?.created_at as string ?? 0).getTime(),
        )
        .slice(0, 10);
    },
    enabled: !!projects && projects.length > 0,
    staleTime: 30 * 1000,
  });

  const { data: providerData } = useQuery({
    queryKey: ["provider-configs"],
    queryFn: listProviderConfigs,
    staleTime: 60 * 1000,
  });

  const statusCounts = projects?.reduce(
    (acc, p) => {
      acc.total += 1;
      if (p.status === "active") acc.active += 1;
      if (p.status === "completed") acc.completed += 1;
      if (p.status === "draft") acc.draft += 1;
      return acc;
    },
    { total: 0, active: 0, completed: 0, draft: 0 },
  ) ?? { total: 0, active: 0, completed: 0, draft: 0 };

  // Build recent activity from projects
  const recentActivity = (projects ?? [])
    .slice()
    .sort((a, b) => (a.id > b.id ? -1 : 1))
    .slice(0, 10)
    .map((p) => ({
      project: p.name,
      action:
        p.status === "active"
          ? t("dashboard:activity.activeProject")
          : p.status === "completed"
            ? t("dashboard:activity.completedProject")
            : t("dashboard:activity.updatedProject"),
      time: p.scenario_package,
      type:
        p.status === "active"
          ? "project_created"
          : p.status === "completed"
            ? "draft_completed"
            : "status_changed",
    }));

  const activeProviders =
    providerData?.data?.filter((p) => p.is_active).length ?? 0;
  const totalProviders = providerData?.data?.length ?? 0;

  if (projectsLoading) return <DashboardSkeleton />;

  const greeting = user?.display_name
    ? t("dashboard:greeting", { name: user.display_name })
    : t("dashboard:greetingDefault");

  return (
    <div className="flex flex-col gap-6">
      {/* Welcome header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{greeting}</h1>
        <p className="text-muted-foreground">{t("dashboard:subtitle")}</p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardDescription>{t("dashboard:stats.totalProjects")}</CardDescription>
              <FolderIcon className="size-4 text-muted-foreground" />
            </div>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {statusCounts.total}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <TrendingUpIcon className="size-3" />
              {t("dashboard:stats.allTime")}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardDescription>{t("dashboard:stats.activeDrafts")}</CardDescription>
              <FileTextIcon className="size-4 text-muted-foreground" />
            </div>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {statusCounts.active}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="secondary" className="text-xs">
              {t("dashboard:stats.inProgress")}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardDescription>{t("dashboard:stats.pendingReviews")}</CardDescription>
              <ClipboardCheckIcon className="size-4 text-muted-foreground" />
            </div>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {statusCounts.draft}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="outline" className="text-xs">
              {t("dashboard:stats.awaitingReview")}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardDescription>{t("dashboard:stats.completed")}</CardDescription>
              <CheckCircleIcon className="size-4 text-muted-foreground" />
            </div>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {statusCounts.completed}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400">
              <CheckCircleIcon className="size-3" />
              {t("dashboard:stats.done")}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main content: activity + quick actions */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Recent Activity */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">
              {t("dashboard:recentActivity.title")}
            </CardTitle>
            <CardDescription>
              {t("dashboard:recentActivity.description")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {recentActivity.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                {t("dashboard:recentActivity.empty")}
              </p>
            ) : (
              <div className="divide-y divide-border">
                {recentActivity.map((event, i) => (
                  <RecentActivityItem key={i} event={event} />
                ))}
              </div>
            )}
            {allRuns && allRuns.length > 0 && (
              <div className="mt-4 pt-4 border-t border-border">
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  {t("dashboard:recentActivity.recentRuns")}
                </p>
                <div className="flex flex-wrap gap-2">
                  {allRuns.slice(0, 5).map((run) => (
                    <Badge key={run.id} variant="secondary" className="text-xs">
                      {run.run_type} &middot; {run.status}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right column: Quick Actions + AI Usage */}
        <div className="flex flex-col gap-4">
          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {t("dashboard:quickActions.title")}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <Button
                className="w-full justify-start"
                onClick={() => navigate("/projects")}
              >
                <PlusIcon className="size-4 mr-2" />
                {t("dashboard:quickActions.newProject")}
              </Button>
              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => navigate("/projects")}
              >
                <EyeIcon className="size-4 mr-2" />
                {t("dashboard:quickActions.viewPendingReviews")}
              </Button>
              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => navigate("/projects")}
              >
                <DownloadIcon className="size-4 mr-2" />
                {t("dashboard:quickActions.exportLatest")}
              </Button>
            </CardContent>
          </Card>

          {/* AI Usage Summary */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <SparklesIcon className="size-4 text-primary" />
                <CardTitle className="text-base">
                  {t("dashboard:aiUsage.title")}
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  {t("dashboard:aiUsage.activeProviders")}
                </span>
                <span className="font-medium">
                  {activeProviders} / {totalProviders}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  {t("dashboard:aiUsage.totalDrafts")}
                </span>
                <span className="font-medium">
                  {allRuns?.filter((r) => r.run_type === "draft").length ?? 0}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  {t("dashboard:aiUsage.totalRuns")}
                </span>
                <span className="font-medium">{allRuns?.length ?? 0}</span>
              </div>
              {totalProviders === 0 && (
                <Link to="/settings/providers">
                  <Button variant="link" size="sm" className="px-0 text-xs">
                    {t("dashboard:aiUsage.configureProviders")}
                  </Button>
                </Link>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
