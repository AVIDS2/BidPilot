import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArchiveIcon,
  CheckCircle2Icon,
  ChevronRightIcon,
  FolderKanbanIcon,
  MoreHorizontalIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

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
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  createProject,
  deleteProject,
  listProjects,
  type ProjectRead,
  updateProjectStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type StatusFilter = "all" | "active" | "completed" | "archived";

const PROJECT_STATUSES: Array<{ value: Exclude<StatusFilter, "all">; label: string }> = [
  { value: "active", label: "进行中" },
  { value: "completed", label: "已完成" },
  { value: "archived", label: "已归档" },
];

function projectStatusMeta(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "completed") return { label: "已完成", tone: "complete" };
  if (normalized === "archived") return { label: "已归档", tone: "archived" };
  if (normalized === "paused" || normalized === "blocked") return { label: "待处理", tone: "attention" };
  return { label: "进行中", tone: "active" };
}

function scenarioLabel(scenario: string) {
  if (scenario === "bidpilot") return "投标响应";
  return scenario.replace(/[-_]/g, " ");
}

function projectInitial(name: string) {
  return name.trim().slice(0, 1).toUpperCase() || "P";
}

export function BidProjectsPageV2() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ProjectRead | null>(null);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setName("");
      setIsCreating(false);
      toast.success("投标机会已创建");
      navigate(`/projects/${project.id}`);
    },
    onError: () => {
      toast.error("未能创建项目，请检查名称或套餐额度。");
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ projectId, status }: { projectId: string; status: string }) =>
      updateProjectStatus(projectId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: () => {
      toast.error("项目状态未能更新。");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setDeleteTarget(null);
      toast.success("项目已删除");
    },
    onError: () => {
      toast.error("项目未能删除。");
    },
  });

  useEffect(() => {
    const showCreateForm = () => setIsCreating(true);
    window.addEventListener("bidpilot:new-project", showCreateForm);
    return () => window.removeEventListener("bidpilot:new-project", showCreateForm);
  }, []);

  useEffect(() => {
    if ((location.state as { openCreateProject?: boolean } | null)?.openCreateProject) {
      setIsCreating(true);
      navigate("/projects", { replace: true, state: null });
    }
  }, [location.state, navigate]);

  const allProjects = useMemo(() => projectsQuery.data ?? [], [projectsQuery.data]);
  const counts = useMemo(() => {
    return allProjects.reduce<Record<StatusFilter, number>>(
      (accumulator, project) => {
        const status = project.status.toLowerCase() as StatusFilter;
        if (status in accumulator && status !== "all") accumulator[status] += 1;
        return accumulator;
      },
      { all: allProjects.length, active: 0, completed: 0, archived: 0 },
    );
  }, [allProjects]);

  const projects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return allProjects.filter((project) => {
      const matchesFilter = filter === "all" || project.status.toLowerCase() === filter;
      const matchesQuery = !normalizedQuery || [project.name, project.slug, project.scenario_package]
        .some((value) => value.toLowerCase().includes(normalizedQuery));
      return matchesFilter && matchesQuery;
    });
  }, [allProjects, filter, query]);

  const submitCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("请先填写项目名称。");
      return;
    }
    createMutation.mutate({ name: trimmedName, scenario_package: "bidpilot" });
  };

  return (
    <section className="wb-page wb-projects-workbench" aria-labelledby="bid-projects-title">
      <section className="wb-projects-content">
        <div className="wb-projects-fixed-head">
          <header className="wb-page-header">
            <div>
              <h1 id="bid-projects-title">投标机会</h1>
              <p>从机会评估到交付，集中管理团队正在响应的招标项目。</p>
            </div>
            <Button
              className="wb-primary-button"
              onClick={() => setIsCreating(true)}
              size="sm"
              type="button"
            >
              <PlusIcon aria-hidden="true" />
              新建机会
            </Button>
          </header>

          <Tabs aria-label="项目状态筛选" className="wb-project-tabs" onValueChange={(value) => setFilter(value as StatusFilter)} value={filter}>
            <TabsList className="wb-project-tabs-list" variant="line">
              {(["all", "active", "completed", "archived"] as const).map((status) => (
                <TabsTrigger className="wb-project-tab" key={status} value={status}>
                  {status === "all" ? "全部" : PROJECT_STATUSES.find((item) => item.value === status)?.label}
                  <small>{counts[status]}</small>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <div className="wb-list-toolbar">
            <label className="wb-search-field">
              <SearchIcon aria-hidden="true" />
              <Input
                className="wb-input"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索项目…"
                value={query}
              />
            </label>
            <span className="wb-list-summary">按最近更新排序</span>
          </div>
        </div>

        <ScrollArea className="wb-projects-table-scroll">
          <div className="wb-projects-table-wrap">
            <Table className="wb-projects-table" aria-label="投标机会">
              <TableHeader>
                <TableRow className="wb-projects-table__header">
                  <TableHead>机会</TableHead>
                  <TableHead>响应类型</TableHead>
                  <TableHead>推进状态</TableHead>
                  <TableHead>项目标识</TableHead>
                  <TableHead><span className="sr-only">项目操作</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>

                {projectsQuery.isLoading ? (
                  <TableRow><TableCell className="wb-projects-table__state" colSpan={5} role="status">正在加载项目…</TableCell></TableRow>
                ) : null}

                {!projectsQuery.isLoading && projects.length === 0 ? (
                  <TableRow>
                    <TableCell className="wb-projects-table__empty" colSpan={5}>
                      <FolderKanbanIcon aria-hidden="true" />
                      <strong>{allProjects.length === 0 ? "创建第一个投标机会" : "没有匹配的机会"}</strong>
                      <span>{allProjects.length === 0 ? "将一个招标机会转化为可协作、可追溯的响应工作集。" : "调整搜索词或状态筛选。"}</span>
                      {allProjects.length === 0 ? (
                        <button className="wb-text-action" onClick={() => setIsCreating(true)} type="button">
                          新建机会 <ChevronRightIcon aria-hidden="true" />
                        </button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ) : null}

                {projects.map((project) => {
                  const status = projectStatusMeta(project.status);
                  return (
                    <TableRow className="wb-projects-table__row" key={project.id}>
                      <TableCell>
                        <button
                          className="wb-project-row-main"
                          onClick={() => navigate(`/projects/${project.id}`)}
                          type="button"
                        >
                          <span className="wb-project-mark">{projectInitial(project.name)}</span>
                          <span className="wb-project-copy">
                            <strong>{project.name}</strong>
                            <small>{project.slug}</small>
                          </span>
                        </button>
                      </TableCell>
                      <TableCell className="wb-projects-table__cell">{scenarioLabel(project.scenario_package)}</TableCell>
                      <TableCell className="wb-projects-table__cell">
                        <span className={cn("wb-status", `wb-status--${status.tone}`)}>
                          <i aria-hidden="true" />
                          {status.label}
                        </span>
                      </TableCell>
                      <TableCell className="wb-projects-table__cell wb-project-id">{project.id.slice(0, 8)}</TableCell>
                      <TableCell className="wb-projects-table__cell wb-project-actions">
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            render={<button className="wb-row-action" type="button" aria-label={`操作 ${project.name}`} />}
                          >
                            <MoreHorizontalIcon aria-hidden="true" />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="wb-menu-content">
                            <DropdownMenuItem onClick={() => navigate(`/projects/${project.id}`)}>打开项目</DropdownMenuItem>
                            {project.status !== "completed" ? (
                              <DropdownMenuItem onClick={() => statusMutation.mutate({ projectId: project.id, status: "completed" })}>
                                <CheckCircle2Icon aria-hidden="true" />
                                标记完成
                              </DropdownMenuItem>
                            ) : null}
                            {project.status !== "archived" ? (
                              <DropdownMenuItem onClick={() => statusMutation.mutate({ projectId: project.id, status: "archived" })}>
                                <ArchiveIcon aria-hidden="true" />
                                归档项目
                              </DropdownMenuItem>
                            ) : null}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => setDeleteTarget(project)} variant="destructive">
                              <Trash2Icon aria-hidden="true" />
                              删除项目
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </ScrollArea>
      </section>

      <Dialog open={isCreating} onOpenChange={setIsCreating}>
        <DialogContent className="wb-project-create-dialog">
          <form onSubmit={submitCreate}>
            <DialogHeader>
              <DialogTitle>新建投标机会</DialogTitle>
              <DialogDescription>建立机会后，上传招标资料、分派章节并邀请团队协作。</DialogDescription>
            </DialogHeader>
            <FieldGroup className="wb-project-create-fields">
              <Field>
                <FieldLabel htmlFor="project-name">机会名称</FieldLabel>
                <Input
                  autoFocus
                  className="wb-input"
                  id="project-name"
                  onChange={(event) => setName(event.target.value)}
                  placeholder="例如：Northstar 数据平台 RFP"
                  value={name}
                />
              </Field>
            </FieldGroup>
            <DialogFooter className="wb-project-create-footer">
              <Button className="wb-flat-button" onClick={() => setIsCreating(false)} type="button" variant="ghost">取消</Button>
              <Button className="wb-primary-button" disabled={createMutation.isPending} type="submit">
                {createMutation.isPending ? "创建中…" : "创建机会"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent className="wb-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>删除项目？</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget ? `“${deleteTarget.name}”及其资料、章节和交付物将无法恢复。` : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="wb-delete-button"
              disabled={deleteMutation.isPending}
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
            >
              {deleteMutation.isPending ? "删除中…" : "删除项目"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
