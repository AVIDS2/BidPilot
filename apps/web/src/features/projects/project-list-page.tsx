import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { FieldGroup, Field, FieldLabel } from "@/components/ui/field";
import { listProjects, createProject, updateProjectStatus, deleteProject, type ProjectRead } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
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
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [name, setName] = useState("");
  const [scenario, setScenario] = useState("bidpilot");
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showGuide, setShowGuide] = useState(() => localStorage.getItem("docpilot_guide_dismissed") !== "true");
  const [showOnboarding, setShowOnboarding] = useState(() => localStorage.getItem("docpilot_onboarding_done") !== "true");
  const [deleteTarget, setDeleteTarget] = useState<ProjectRead | null>(null);

  const dismissGuide = () => {
    localStorage.setItem("docpilot_guide_dismissed", "true");
    setShowGuide(false);
  };

  const finishOnboarding = () => {
    localStorage.setItem("docpilot_onboarding_done", "true");
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
      toast.success("Project created");
      navigate(`/projects/${data.id}`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("plan limit") || msg.includes("403")) {
        toast.error("Project limit reached. Upgrade your plan to create more projects.", {
          action: { label: "Upgrade", onClick: () => navigate("/pricing") },
        });
      } else {
        toast.error("Failed to create project");
      }
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project deleted");
    },
    onError: () => {
      toast.error("Failed to delete project");
    },
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateProjectStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Status updated");
    },
    onError: () => {
      toast.error("Failed to update status");
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
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Projects</h1>
        <div className="flex items-center gap-2">
          {!showGuide && (
            <Button variant="outline" size="sm" onClick={() => { localStorage.removeItem("docpilot_guide_dismissed"); setShowGuide(true); }}>
              <BookOpenIcon className="size-4" />
              Show Guide
            </Button>
          )}
          <Button onClick={() => setShowForm(!showForm)}>
            <PlusIcon className="size-4" />
            New Project
          </Button>
        </div>
      </div>

      {showForm && (
        <Card>
          <CardContent className="pt-6">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="name">Project Name</FieldLabel>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Acme Bid"
                />
              </Field>
              <ScenarioSelector value={scenario} onChange={setScenario} />
              <Button
                onClick={() => createMut.mutate({ name, scenario_package: scenario })}
                disabled={!name || createMut.isPending}
              >
                {createMut.isPending && <Spinner data-icon="inline-start" />}
                Create
              </Button>
            </FieldGroup>
          </CardContent>
        </Card>
      )}

      {/* Onboarding wizard for first-time users with no projects */}
      {!isLoading && showOnboarding && (projects ?? []).length === 0 && (
        <div className="flex justify-center py-8">
          <div className="w-full max-w-md">
            <OnboardingWizard onFinish={finishOnboarding} />
          </div>
        </div>
      )}

      {/* Quick Start Guide */}
      {showGuide && (
        <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
            <div className="flex items-center gap-2">
              <BookOpenIcon className="size-5 text-primary" />
              <CardTitle className="text-lg">Quick Start Guide</CardTitle>
            </div>
            <Button variant="ghost" size="icon" onClick={dismissGuide} className="-mt-1 -mr-2 size-7" aria-label="Dismiss">
              <XIcon className="size-4" />
            </Button>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              Welcome to DocPilot! Follow these steps to turn source materials into a reviewable, exported deliverable:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="flex items-start gap-3 rounded-md border bg-background p-3">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                  <PlusIcon className="size-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">1. Create Project</p>
                  <p className="text-xs text-muted-foreground">Click "+ New Project" and pick a scenario package (e.g. BidPilot).</p>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-md border bg-background p-3">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                  <FileUpIcon className="size-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">2. Upload Bundle</p>
                  <p className="text-xs text-muted-foreground">Open project → Bundles tab → register bundle → upload PDF/DOCX.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-md border bg-background p-3">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                  <FileTextIcon className="size-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">3. Draft Sections</p>
                  <p className="text-xs text-muted-foreground">Deliverables → create one. Drafting tab → generate sections with AI.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-md border bg-background p-3">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                  <CheckIcon className="size-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">4. Review & Approve</p>
                  <p className="text-xs text-muted-foreground">Review tab → comment, approve or reject each section.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-md border bg-background p-3">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                  <DownloadIcon className="size-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">5. Export</p>
                  <p className="text-xs text-muted-foreground">When all sections approved, Export tab → download DOCX.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-md border bg-background p-3">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                  <BookOpenIcon className="size-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">6. Inspect Audit</p>
                  <p className="text-xs text-muted-foreground">Audit tab → see every event. System tab → execution traces & costs.</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardDescription>Total Projects</CardDescription>
            <CardTitle className="text-2xl">{projects?.length ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Active</CardDescription>
            <CardTitle className="text-2xl">{statusCounts["active"] ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Completed</CardDescription>
            <CardTitle className="text-2xl">{statusCounts["completed"] ?? 0}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Plan quota hint for starter users */}
      {user?.plan === "starter" && (
        <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
          <CardContent className="flex items-center justify-between pt-6">
            <div>
              <p className="text-sm font-medium">
                {(projects?.length ?? 0) >= 3 ? "Project limit reached" : `${3 - (projects?.length ?? 0)} of 3 projects remaining`}
              </p>
              <p className="text-xs text-muted-foreground">Starter plan allows up to 3 projects. Upgrade for unlimited.</p>
            </div>
            <Link to="/pricing">
              <Button variant="outline" size="sm">Upgrade</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Search + filter bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search projects..."
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as string)}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="archived">Archived</SelectItem>
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
            <EmptyTitle>{search ? "No matching projects" : "No projects yet"}</EmptyTitle>
            <EmptyDescription>{search ? "Try a different search term." : "Create a project to get started."}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}

      {filtered.length > 0 && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Scenario</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Slug</TableHead>
                <TableHead className="w-10">
                  <span className="sr-only">Actions</span>
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
                  aria-label={`Open project ${p.name}`}
                  onClick={() => navigate(`/projects/${p.id}`)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      navigate(`/projects/${p.id}`);
                    }
                  }}
                >
                  <TableCell>
                    <Link
                      to={`/projects/${p.id}`}
                      className="font-medium hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {p.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{p.scenario_package}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={p.status === "active" ? "default" : "secondary"}>
                      {p.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground text-xs">
                    {p.slug}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="size-7" aria-label={`Project actions for ${p.name}`} />}>
                        <MoreHorizontalIcon className="size-4" />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => statusMut.mutate({ id: p.id, status: "completed" })}>
                          <CheckCircleIcon className="size-4 mr-2" /> Mark Completed
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => statusMut.mutate({ id: p.id, status: "archived" })}>
                          <ArchiveIcon className="size-4 mr-2" /> Archive
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setDeleteTarget(p)} className="text-destructive">
                          <TrashIcon className="size-4 mr-2" /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {filtered.length > 50 && (
            <CardContent className="pt-4 text-center text-sm text-muted-foreground">
              Showing 50 of {filtered.length} projects
            </CardContent>
          )}
        </Card>
      )}

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete project?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <span className="font-medium text-foreground">{deleteTarget?.name}</span>? This action cannot be undone and will remove all associated bundles, sections and audit events.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget) deleteMut.mutate(deleteTarget.id);
                setDeleteTarget(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
