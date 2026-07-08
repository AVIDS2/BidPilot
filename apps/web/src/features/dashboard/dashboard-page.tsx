import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { useAuth } from "@/lib/auth";
import CountUp from "@/components/CountUp";
import { ProductElectricFrame, ProductGlareCard, ProductReveal, ProductShinyText } from "@/components/reactbits-product";
import {
  listProjects, listExecutionRuns, listProviderConfigs,
  type ProjectRead, type ExecutionRunRead,
} from "@/lib/api";
import {
  FolderIcon, FileTextIcon, ClipboardCheckIcon, CheckCircleIcon,
  PlusIcon, EyeIcon, DownloadIcon, SparklesIcon,
  ArrowRightIcon,
} from "lucide-react";

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}><CardHeader><Skeleton className="h-4 w-24" /><Skeleton className="h-7 w-16 mt-1" /></CardHeader></Card>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardHeader><Skeleton className="h-5 w-32" /></CardHeader><CardContent>{Array.from({ length: 4 }).map((_, i) => (<Skeleton key={i} className="h-10 w-full mb-2" />))}</CardContent></Card>
        <Card><CardHeader><Skeleton className="h-5 w-32" /></CardHeader><CardContent>{Array.from({ length: 3 }).map((_, i) => (<Skeleton key={i} className="h-10 w-full mb-2" />))}</CardContent></Card>
      </div>
    </div>
  );
}

const STAT_ICONS = [
  { Icon: FolderIcon, bg: "bg-blue-500/10", color: "text-blue-500" },
  { Icon: FileTextIcon, bg: "bg-amber-500/10", color: "text-amber-500" },
  { Icon: ClipboardCheckIcon, bg: "bg-violet-500/10", color: "text-violet-500" },
  { Icon: CheckCircleIcon, bg: "bg-emerald-500/10", color: "text-emerald-500" },
];

const dotColors: Record<string, string> = {
  project_created: "bg-blue-500",
  status_changed: "bg-amber-500",
  draft_started: "bg-emerald-500",
  draft_completed: "bg-primary",
  export: "bg-orange-500",
};

function RecentActivityItem({
  event,
  index,
}: {
  event: { project: string; action: string; time: string; type: string };
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: [0.32, 0.72, 0, 1] }}
      className="relative flex items-start gap-4 py-3 pl-6"
    >
      <div className={`absolute left-0 top-4 size-2.5 rounded-full ring-2 ring-background ${dotColors[event.type] ?? "bg-muted-foreground"}`} />
      <div className="absolute left-[4.5px] top-6 bottom-0 w-px bg-border last:hidden" />
      <div className="flex-1 min-w-0">
        <p className="text-sm">
          <span className="font-medium">{event.action}</span>{" "}
          <span className="text-muted-foreground">{event.project}</span>
        </p>
      </div>
      <span className="text-xs text-muted-foreground whitespace-nowrap mt-0.5">
        {event.time}
      </span>
    </motion.div>
  );
}

export function DashboardPage() {
  const { t } = useTranslation(["dashboard", "common"]);
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data: projects, isLoading: projectsLoading } = useQuery<ProjectRead[]>({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 5 * 60 * 1000,
    retry: 2,
  });

  const { data: allRuns } = useQuery<ExecutionRunRead[]>({
    queryKey: ["dashboard-runs"],
    queryFn: async () => {
      if (!projects || projects.length === 0) return [];
      const results: ExecutionRunRead[][] = [];
      for (const project of projects) {
        try {
          const runs = await listExecutionRuns(project.id);
          results.push(runs);
        } catch (error) {
          console.warn(`Failed to fetch runs for project ${project.id}:`, error);
        }
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
      return results
        .flatMap((r) => r)
        .sort((a, b) => new Date(b.output_json?.created_at as string ?? 0).getTime() - new Date(a.output_json?.created_at as string ?? 0).getTime())
        .slice(0, 10);
    },
    enabled: !!projects && projects.length > 0,
    staleTime: 2 * 60 * 1000,
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  const { data: providerData } = useQuery({
    queryKey: ["provider-configs"],
    queryFn: listProviderConfigs,
    staleTime: 5 * 60 * 1000,
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

  const recentActivity = (projects ?? [])
    .slice()
    .sort((a, b) => (a.id > b.id ? -1 : 1))
    .slice(0, 10)
    .map((p) => ({
      project: p.name,
      action: p.status === "active" ? t("dashboard:activity.activeProject") : p.status === "completed" ? t("dashboard:activity.completedProject") : t("dashboard:activity.updatedProject"),
      time: p.scenario_package,
      type: p.status === "active" ? "project_created" : p.status === "completed" ? "draft_completed" : "status_changed",
    }));

  const activeProviders = providerData?.data?.filter((p) => p.is_active).length ?? 0;
  const totalProviders = providerData?.data?.length ?? 0;
  const totalDrafts = allRuns?.filter((r) => r.run_type === "draft").length ?? 0;

  // Plan limits for progress bar
  const planLimit = user?.plan === "starter" ? 3 : -1;
  const projectUsagePct = planLimit > 0 ? Math.min(100, (statusCounts.total / planLimit) * 100) : -1;

  if (projectsLoading) return <DashboardSkeleton />;

  const greeting = user?.display_name ? t("dashboard:greeting", { name: user.display_name }) : t("dashboard:greetingDefault");

  // Empty state
  if (statusCounts.total === 0) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{greeting}</h1>
          <p className="text-muted-foreground">{t("dashboard:subtitle")}</p>
        </div>
        <Empty className="min-h-[400px] border-dashed">
          <EmptyHeader>
            <EmptyMedia variant="icon"><FolderIcon /></EmptyMedia>
            <EmptyTitle>{t("dashboard:empty.title", { defaultValue: "Create your first project" })}</EmptyTitle>
            <EmptyDescription>{t("dashboard:empty.description", { defaultValue: "Start by creating a BidPilot project to manage your bid documents." })}</EmptyDescription>
          </EmptyHeader>
          <Button onClick={() => navigate("/projects")} className="mt-4">
            <PlusIcon className="size-4 mr-2" />
            {t("dashboard:quickActions.newProject")}
          </Button>
        </Empty>
      </div>
    );
  }

  const statCards = [
    { label: t("dashboard:stats.totalProjects"), value: statusCounts.total, sub: t("dashboard:stats.allTime") },
    { label: t("dashboard:stats.activeDrafts"), value: statusCounts.active, sub: t("dashboard:stats.inProgress") },
    { label: t("dashboard:stats.pendingReviews"), value: statusCounts.draft, sub: t("dashboard:stats.awaitingReview") },
    { label: t("dashboard:stats.completed"), value: statusCounts.completed, sub: t("dashboard:stats.done") },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Welcome header - 入场动画 */}
      <ProductReveal blur={false}>
        <h1 className="text-2xl font-bold tracking-tight">
          <ProductShinyText text={greeting} />
        </h1>
        <p className="text-muted-foreground">{t("dashboard:subtitle")}</p>
      </ProductReveal>

      {/* Stats cards - stagger入场 + CountUp数字动画 */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat, i) => {
          const { Icon, bg, color } = STAT_ICONS[i];
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.5, delay: i * 0.08, ease: [0.32, 0.72, 0, 1] }}
            >
              <ProductGlareCard>
                <Card className="h-full w-full transition-shadow hover:shadow-md">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardDescription>{stat.label}</CardDescription>
                      <div className={`flex size-8 items-center justify-center rounded-lg ${bg}`}>
                        <Icon className={`size-4 ${color}`} />
                      </div>
                    </div>
                    <CardTitle className="text-3xl font-bold tabular-nums">
                      <CountUp to={stat.value} duration={1.4} delay={i * 0.1} />
                    </CardTitle>
                  </CardHeader>
                  <CardFooter className="pt-0">
                    <span className="text-xs text-muted-foreground">{stat.sub}</span>
                  </CardFooter>
                </Card>
              </ProductGlareCard>
            </motion.div>
          );
        })}
      </div>

      {/* Usage progress for starter plan */}
      {projectUsagePct >= 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35, ease: [0.32, 0.72, 0, 1] }}
        >
          <ProductElectricFrame radius={16}>
            <Card className="border-primary/20 bg-gradient-to-r from-primary/5 to-transparent">
              <CardContent className="py-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{t("dashboard:usage.planUsage", { defaultValue: "Project usage" })}</span>
                  <span className="text-sm text-muted-foreground">{statusCounts.total} / {planLimit}</span>
                </div>
                <motion.div
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ duration: 0.8, delay: 0.5, ease: [0.32, 0.72, 0, 1] }}
                  style={{ transformOrigin: "left" }}
                >
                  <Progress value={projectUsagePct} />
                </motion.div>
                {projectUsagePct >= 80 && (
                  <p className="text-xs text-amber-500 mt-2">
                    {t("dashboard:usage.nearLimit", { defaultValue: "You're approaching your plan limit. Consider upgrading." })}
                  </p>
                )}
              </CardContent>
            </Card>
          </ProductElectricFrame>
        </motion.div>
      )}

      {/* Main content: activity + quick actions */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Recent Activity with timeline */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4, ease: [0.32, 0.72, 0, 1] }}
          className="lg:col-span-2"
        >
          <ProductGlareCard>
            <Card className="h-full w-full">
              <CardHeader>
                <CardTitle className="text-base">{t("dashboard:recentActivity.title")}</CardTitle>
                <CardDescription>{t("dashboard:recentActivity.description")}</CardDescription>
              </CardHeader>
              <CardContent>
                {recentActivity.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">
                    {t("dashboard:recentActivity.empty")}
                  </p>
                ) : (
                  <div className="relative">
                    {recentActivity.map((event, i) => (
                      <RecentActivityItem key={i} event={event} index={i} />
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
          </ProductGlareCard>
        </motion.div>

        {/* Right column: Quick Actions + AI Usage */}
        <div className="flex flex-col gap-4">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.45, ease: [0.32, 0.72, 0, 1] }}
          >
            <ProductGlareCard intense>
              <Card className="w-full">
                <CardHeader>
                  <CardTitle className="text-base">{t("dashboard:quickActions.title")}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2">
                  <Button className="w-full justify-between group" onClick={() => navigate("/projects")}>
                    <span className="flex items-center gap-2"><PlusIcon className="size-4" />{t("dashboard:quickActions.newProject")}</span>
                    <ArrowRightIcon className="size-4 opacity-0 -translate-x-2 transition-all group-hover:opacity-100 group-hover:translate-x-0" />
                  </Button>
                  <Button variant="outline" className="w-full justify-between group" onClick={() => navigate("/projects")}>
                    <span className="flex items-center gap-2"><EyeIcon className="size-4" />{t("dashboard:quickActions.viewPendingReviews")}</span>
                    <ArrowRightIcon className="size-4 opacity-0 -translate-x-2 transition-all group-hover:opacity-100 group-hover:translate-x-0" />
                  </Button>
                  <Button variant="outline" className="w-full justify-between group" onClick={() => navigate("/projects")}>
                    <span className="flex items-center gap-2"><DownloadIcon className="size-4" />{t("dashboard:quickActions.exportLatest")}</span>
                    <ArrowRightIcon className="size-4 opacity-0 -translate-x-2 transition-all group-hover:opacity-100 group-hover:translate-x-0" />
                  </Button>
                </CardContent>
              </Card>
            </ProductGlareCard>
          </motion.div>

          {/* AI Usage Summary */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5, ease: [0.32, 0.72, 0, 1] }}
          >
            <ProductGlareCard>
              <Card className="h-full w-full">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <div className="flex size-7 items-center justify-center rounded-lg bg-primary/10">
                      <SparklesIcon className="size-3.5 text-primary" />
                    </div>
                    <CardTitle className="text-base">{t("dashboard:aiUsage.title")}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-muted/50 p-3 text-center">
                      <p className="text-2xl font-bold tabular-nums">
                        <CountUp to={activeProviders} duration={1.2} />
                      </p>
                      <p className="text-xs text-muted-foreground">{t("dashboard:aiUsage.activeProviders")}</p>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-3 text-center">
                      <p className="text-2xl font-bold tabular-nums">
                        <CountUp to={totalDrafts} duration={1.2} />
                      </p>
                      <p className="text-xs text-muted-foreground">{t("dashboard:aiUsage.totalDrafts")}</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("dashboard:aiUsage.totalRuns")}</span>
                    <span className="font-medium tabular-nums">{allRuns?.length ?? 0}</span>
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
            </ProductGlareCard>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
