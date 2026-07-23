import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { FieldGroup, Field, FieldLabel } from "@/components/ui/field";
import { listProjects, createDemoProject, createProject, updateProjectStatus, deleteProject, type ProjectRead } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { getStoredValue, removeStoredValue, setStoredValue } from "@/lib/browser-storage";
import { ScenarioSelector } from "@/features/scenarios/scenario-selector";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import { SearchIcon, PlusIcon, TrashIcon, ArchiveIcon, CheckCircleIcon, BookOpenIcon, XIcon, FileUpIcon, FileTextIcon, CheckIcon, DownloadIcon, MoreHorizontalIcon } from "lucide-react";
import { OnboardingWizard } from "@/features/onboarding/onboarding-wizard";
import CountUp from "@/components/CountUp";
import { ProductElectricFrame, ProductGlareCard, ProductReveal, ProductShinyText } from "@/components/reactbits-product";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

function ProjectListSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-9 w-32" />
      </div>
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 18rem), 1fr))" }}
      >
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-1/2 mt-2" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-4 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export function ProjectListPage() {
  const { t } = useTranslation(["projects", "common", "onboarding"]);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [name, setName] = useState("");
  const [scenario, setScenario] = useState("bidpilot");
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showGuide, setShowGuide] = useState(() => getStoredValue("guideDismissed") !== "true");
  const [showOnboarding, setShowOnboarding] = useState(() => getStoredValue("onboardingDone") !== "true");
  const [deleteTarget, setDeleteTarget] = useState<ProjectRead | null>(null);

  const dismissGuide = () => {
    setStoredValue("guideDismissed", "true");
    setShowGuide(false);
  };

  const finishOnboarding = () => {
    setStoredValue("onboardingDone", "true");
    setShowOnboarding(false);
  };

  const { data: projects, isLoading } = useQuery<ProjectRead[]>({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 30 * 1000,
  });

  const createMut = useMutation({
    mutationFn: createProject,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setName("");
      setScenario("bidpilot");
      setShowForm(false);
      toast.success(t("create.created"));
      navigate(`/projects/${data.id}`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("plan limit") || msg.includes("403")) {
        toast.error(t("create.limitReached"), {
          action: { label: t("list.upgrade"), onClick: () => navigate("/pricing") },
        });
      } else {
        toast.error(t("create.createFailed"));
      }
    },
  });

  const demoMut = useMutation({
    mutationFn: createDemoProject,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      finishOnboarding();
      toast.success(t("onboarding:demoCreated"));
      navigate(`/projects/${data.id}`);
    },
    onError: () => {
      toast.error(t("onboarding:demoCreateFailed"));
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success(t("delete.deleted"));
    },
    onError: () => {
      toast.error(t("delete.deleteFailed"));
    },
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateProjectStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success(t("status.updated"));
    },
    onError: () => {
      toast.error(t("status.updateFailed"));
    },
  });

  const filtered = useMemo(() => {
    let list = projects ?? [];
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((p) => p.name.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q) || p.scenario_package.toLowerCase().includes(q));
    }
    if (statusFilter !== "all") {
      list = list.filter((p) => p.status === statusFilter);
    }
    return list;
  }, [projects, search, statusFilter]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    (projects ?? []).forEach((p) => { counts[p.status] = (counts[p.status] || 0) + 1; });
    return counts;
  }, [projects]);

  if (isLoading) return <ProjectListSkeleton />;

  return (
    <div className="flex flex-col gap-6">
      <ProductReveal blur={false} className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">
          <ProductShinyText text={t("list.title")} />
        </h1>
        <div className="flex items-center gap-2">
          {!showGuide && (
            <Button variant="outline" size="sm" onClick={() => { removeStoredValue("guideDismissed"); setShowGuide(true); }}>
              <BookOpenIcon className="size-4" />
              {t("list.showGuide")}
            </Button>
          )}
          <ProductElectricFrame active={showForm} radius={12}>
            <Button onClick={() => setShowForm(!showForm)}>
              <PlusIcon className="size-4" />
              {t("list.newProject")}
            </Button>
          </ProductElectricFrame>
        </div>
      </ProductReveal>

      {showForm && (
        <ProductReveal>
          <ProductGlareCard intense>
            <Card className="w-full">
              <CardContent className="pt-6">
                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor="name">{t("create.projectName")}</FieldLabel>
                    <Input
                      id="name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder={t("create.projectNamePlaceholder")}
                    />
                  </Field>
                  <ScenarioSelector value={scenario} onChange={setScenario} />
                  <Button
                    onClick={() => createMut.mutate({ name, scenario_package: scenario })}
                    disabled={!name || createMut.isPending}
                  >
                    {createMut.isPending && <Spinner data-icon="inline-start" />}
                    {t("create.create")}
                  </Button>
                </FieldGroup>
              </CardContent>
            </Card>
          </ProductGlareCard>
        </ProductReveal>
      )}

      {/* Onboarding wizard for first-time users with no projects */}
      {!isLoading && showOnboarding && (projects ?? []).length === 0 && (
        <div className="flex justify-center py-8">
          <div className="w-full max-w-md">
            <OnboardingWizard
              onFinish={finishOnboarding}
              onCreateOwnProject={() => setShowForm(true)}
              onCreateDemo={() => demoMut.mutate()}
              isCreatingDemo={demoMut.isPending}
            />
          </div>
        </div>
      )}

      {/* Quick Start Guide */}
      {showGuide && (
        <ProductGlareCard intense>
          <Card className="w-full border-[rgba(132,204,22,0.2)] bg-gradient-to-br from-[rgba(132,204,22,0.04)] to-transparent">
            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
              <div className="flex items-center gap-2">
                <BookOpenIcon className="size-5 text-primary" />
                <CardTitle className="text-lg">{t("guide.title")}</CardTitle>
              </div>
              <Button variant="ghost" size="icon" onClick={dismissGuide} className="-mt-1 -mr-2 size-7" aria-label={t("guide.dismiss")}>
                <XIcon className="size-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                {t("guide.welcome")}
              </p>
              <div
                className="grid gap-3"
                style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 11rem), 1fr))" }}
              >
                {[
                  { Icon: PlusIcon, title: t("guide.step1Title"), desc: t("guide.step1Desc") },
                  { Icon: FileUpIcon, title: t("guide.step2Title"), desc: t("guide.step2Desc") },
                  { Icon: FileTextIcon, title: t("guide.step3Title"), desc: t("guide.step3Desc") },
                  { Icon: CheckIcon, title: t("guide.step4Title"), desc: t("guide.step4Desc") },
                  { Icon: DownloadIcon, title: t("guide.step5Title"), desc: t("guide.step5Desc") },
                  { Icon: BookOpenIcon, title: t("guide.step6Title"), desc: t("guide.step6Desc") },
                ].map(({ Icon, title, desc }) => (
                  <ProductReveal key={title} blur={false} className="h-full">
                    <div className="flex h-full items-start gap-3 rounded-md border bg-background p-3">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-md" style={{ background: "rgba(132, 204, 22, 0.1)" }}>
                        <Icon className="size-4 text-primary" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">{title}</p>
                        <p className="text-xs text-muted-foreground">{desc}</p>
                      </div>
                    </div>
                  </ProductReveal>
                ))}
              </div>
            </CardContent>
          </Card>
        </ProductGlareCard>
      )}

      {/* Summary cards */}
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 10rem), 1fr))" }}
      >
        {[
          { label: t("list.totalProjects"), value: projects?.length ?? 0 },
          { label: t("list.active"), value: statusCounts["active"] ?? 0 },
          { label: t("list.completed"), value: statusCounts["completed"] ?? 0 },
        ].map((item, index) => (
          <ProductGlareCard key={item.label}>
            <Card className="w-full">
              <CardHeader>
                <CardDescription>{item.label}</CardDescription>
                <CardTitle className="text-2xl tabular-nums">
                  <CountUp to={item.value} duration={1.1} delay={index * 0.08} />
                </CardTitle>
              </CardHeader>
            </Card>
          </ProductGlareCard>
        ))}
      </div>

      {/* Plan quota hint for starter users */}
      {user?.plan === "starter" && (
        <ProductElectricFrame radius={16}>
          <Card className="border-[rgba(132,204,22,0.2)] bg-gradient-to-br from-[rgba(132,204,22,0.04)] to-transparent">
            <CardContent className="flex items-center justify-between pt-6">
              <div>
                <p className="text-sm font-medium">
                  {(projects?.length ?? 0) >= 3
                    ? t("list.projectLimitReached")
                    : t("list.projectsRemaining", { count: 3 - (projects?.length ?? 0) })}
                </p>
                <p className="text-xs text-muted-foreground">{t("list.upgradeHint")}</p>
              </div>
              <Link to="/pricing">
                <Button variant="outline" size="sm">{t("list.upgrade")}</Button>
              </Link>
            </CardContent>
          </Card>
        </ProductElectricFrame>
      )}

      {/* Search + filter bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("list.searchPlaceholder")}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as string)}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder={t("list.statusFilter")} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="all">{t("list.allStatus")}</SelectItem>
              <SelectItem value="active">{t("list.active")}</SelectItem>
              <SelectItem value="completed">{t("list.completed")}</SelectItem>
              <SelectItem value="archived">{t("list.archived")}</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      {filtered.length === 0 && (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <SearchIcon />
            </EmptyMedia>
            <EmptyTitle>{search ? t("list.emptySearchTitle") : t("list.emptyTitle")}</EmptyTitle>
            <EmptyDescription>{search ? t("list.emptySearchDesc") : t("list.emptyDesc")}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}

      {filtered.length > 0 && (
        <Card className="w-full min-w-0 overflow-hidden">
          <div className="w-full min-w-0 overflow-x-auto">
            <Table className="min-w-[36rem] w-full table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40%] min-w-[10rem]">{t("list.name")}</TableHead>
                  <TableHead className="w-[18%]">{t("list.scenario")}</TableHead>
                  <TableHead className="w-[16%]">{t("list.status")}</TableHead>
                  <TableHead className="hidden w-[18%] md:table-cell">{t("list.slug")}</TableHead>
                  <TableHead className="w-12">
                    <span className="sr-only">{t("list.actions")}</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.slice(0, 50).map((p) => (
                  <TableRow
                    key={p.id}
                    className="cursor-pointer hover:bg-accent/50"
                    role="link"
                    tabIndex={0}
                    aria-label={t("list.openProject", { name: p.name })}
                    onClick={() => navigate(`/projects/${p.id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        navigate(`/projects/${p.id}`);
                      }
                    }}
                  >
                    <TableCell className="max-w-0 whitespace-normal">
                      <Link
                        to={`/projects/${p.id}`}
                        className="block truncate font-medium hover:underline"
                        title={p.name}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {p.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="max-w-full truncate">
                        {p.scenario_package}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          p.status === "active"
                            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : p.status === "completed"
                              ? "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400"
                              : p.status === "archived"
                                ? "border-muted-foreground/30 bg-muted/50 text-muted-foreground"
                                : p.status === "draft"
                                  ? "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400"
                                  : ""
                        }
                      >
                        {t(`statusValues.${p.status}`, { defaultValue: p.status })}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden max-w-0 truncate text-xs text-muted-foreground md:table-cell" title={p.slug}>
                      {p.slug}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="size-7" aria-label={t("list.projectActions", { name: p.name })} />}>
                          <MoreHorizontalIcon className="size-4" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => statusMut.mutate({ id: p.id, status: "completed" })}>
                            <CheckCircleIcon className="size-4 mr-2" /> {t("list.markCompleted")}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => statusMut.mutate({ id: p.id, status: "archived" })}>
                            <ArchiveIcon className="size-4 mr-2" /> {t("list.archive")}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => setDeleteTarget(p)} className="text-destructive">
                            <TrashIcon className="size-4 mr-2" /> {t("list.delete")}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {filtered.length > 50 && (
            <CardContent className="pt-4 text-center text-sm text-muted-foreground">
              {t("list.showingCount", { count: filtered.length })}
            </CardContent>
          )}
        </Card>
      )}

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("delete.title")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("delete.description", { name: deleteTarget?.name ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("confirm.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget) deleteMut.mutate(deleteTarget.id);
                setDeleteTarget(null);
              }}
            >
              {t("confirm.delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
