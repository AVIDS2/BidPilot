import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  addTeamMember,
  createTeam,
  deleteTeam,
  listOrganizationMembers,
  listTeams,
  removeTeamMember,
  updateTeam,
  type TeamRead,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PlusIcon,
  ShieldIcon,
  TrashIcon,
  UsersIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

const CARDS_PER_PAGE = 6;

function memberInitials(name: string | undefined | null, email?: string | null) {
  const source = (name || email || "?").trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0]![0] ?? ""}${parts[1]![0] ?? ""}`.toUpperCase();
  }
  return source.slice(0, 2).toUpperCase();
}

function TeamManagementSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Skeleton className="size-5 rounded-md" />
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-5 w-10 rounded-full" />
        </div>
        <Skeleton className="h-8 w-28" />
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent className="space-y-3">
              <Skeleton className="h-8 w-28 rounded-full" />
              <Skeleton className="h-4 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function TeamMemberPreview({ team }: { team: TeamRead }) {
  const members = team.members ?? [];
  const visible = members.slice(0, 4);
  const overflow = Math.max(0, members.length - visible.length);

  if (members.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <UsersIcon className="size-3.5" />
        <span>—</span>
      </div>
    );
  }

  return (
    <AvatarGroup className="justify-start">
      {visible.map((member) => (
        <Avatar key={member.id} size="sm" title={member.user_display_name || member.user_email}>
          <AvatarFallback>
            {memberInitials(member.user_display_name, member.user_email)}
          </AvatarFallback>
        </Avatar>
      ))}
      {overflow > 0 && <AvatarGroupCount>+{overflow}</AvatarGroupCount>}
    </AvatarGroup>
  );
}

export function TeamManagementPage() {
  const { t } = useTranslation(["admin", "common"]);
  const { user: currentUser } = useAuth();
  const qc = useQueryClient();
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamSlug, setNewTeamSlug] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedTeamId, setExpandedTeamId] = useState<string | null>(null);

  const { data: teamsData, isLoading } = useQuery({
    queryFn: listTeams,
    queryKey: ["teams"],
  });

  const { data: workspaceMembers, isLoading: isLoadingWorkspaceMembers } = useQuery({
    queryFn: listOrganizationMembers,
    queryKey: ["organization-members"],
  });

  const createMut = useMutation({
    mutationFn: (data: { name: string; slug: string }) => createTeam(data),
    onSuccess: () => {
      toast.success(t("teamManagement.teamCreated"));
      qc.invalidateQueries({ queryKey: ["teams"] });
      setNewTeamName("");
      setNewTeamSlug("");
      setShowCreate(false);
    },
    onError: () => toast.error(t("teamManagement.operationFailed")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteTeam(id),
    onSuccess: () => {
      toast.success(t("teamManagement.teamDeleted"));
      qc.invalidateQueries({ queryKey: ["teams"] });
    },
    onError: () => toast.error(t("teamManagement.operationFailed")),
  });

  const addMemberMut = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: string; userId: string }) =>
      addTeamMember(teamId, { user_id: userId }),
    onSuccess: () => {
      toast.success(t("teamManagement.memberAdded"));
      qc.invalidateQueries({ queryKey: ["teams"] });
    },
    onError: () => toast.error(t("teamManagement.operationFailed")),
  });

  const removeMemberMut = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: string; userId: string }) =>
      removeTeamMember(teamId, userId),
    onSuccess: () => {
      toast.success(t("teamManagement.memberRemoved"));
      qc.invalidateQueries({ queryKey: ["teams"] });
    },
    onError: () => toast.error(t("teamManagement.operationFailed")),
  });

  const teams = teamsData?.items ?? [];
  const users = workspaceMembers ?? [];
  const totalMembers = useMemo(
    () => teams.reduce((sum, team) => sum + (team.members?.length ?? 0), 0),
    [teams],
  );

  if (isLoading || isLoadingWorkspaceMembers) return <TeamManagementSkeleton />;

  const currentMembership = workspaceMembers?.find((member) => member.id === currentUser?.id);
  const canManageTeams = currentMembership?.role === "owner" || currentMembership?.role === "admin";

  if (!canManageTeams) {
    return (
      <div className="flex flex-col gap-4">
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <div className="flex size-10 items-center justify-center rounded-lg bg-muted">
              <ShieldIcon className="size-5 text-muted-foreground" />
            </div>
            <p className="text-sm text-muted-foreground">
              {t("invitationManagement.workspaceManagerRequired")}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(teams.length / CARDS_PER_PAGE));
  const safePage = Math.min(currentPage, totalPages);
  const paginatedTeams = teams.slice((safePage - 1) * CARDS_PER_PAGE, safePage * CARDS_PER_PAGE);

  function commitRename(teamId: string, name: string) {
    const trimmed = name.trim();
    if (!trimmed) {
      setEditingId(null);
      return;
    }
    updateTeam(teamId, { name: trimmed })
      .then(() => {
        toast.success(t("teamManagement.teamUpdated"));
        qc.invalidateQueries({ queryKey: ["teams"] });
      })
      .catch(() => toast.error(t("teamManagement.operationFailed")));
    setEditingId(null);
  }

  function slugifyName(name: string) {
    return name
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9一-鿿]+/g, "-")
      .replace(/[^a-z0-9-]/g, "")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 48);
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <UsersIcon className="size-5 text-muted-foreground" />
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              {t("teamManagement.title")}
            </h1>
            <Badge variant="secondary">{teams.length}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {t("teamManagement.pageHint", {
              defaultValue: "按团队组织成员，控制协作范围与权限边界。",
            })}
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setShowCreate((open) => !open)}
          className="bg-primary text-primary-foreground hover:bg-primary/90"
        >
          <PlusIcon className="size-4" />
          {t("teamManagement.createTeam")}
        </Button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Card size="sm">
          <CardHeader className="border-0">
            <CardDescription>{t("teamManagement.summaryTeams", { defaultValue: "团队数" })}</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{teams.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card size="sm">
          <CardHeader className="border-0">
            <CardDescription>{t("teamManagement.summaryMembers", { defaultValue: "成员席位" })}</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{totalMembers}</CardTitle>
          </CardHeader>
        </Card>
        <Card size="sm">
          <CardHeader className="border-0">
            <CardDescription>{t("teamManagement.summaryWorkspace", { defaultValue: "工作区成员" })}</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{users.length}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Create form */}
      {showCreate && (
        <Card>
          <CardHeader className="border-b">
            <CardTitle>{t("teamManagement.createTeam")}</CardTitle>
            <CardDescription>
              {t("teamManagement.teamSlugDescription")}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 pt-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="team-name">{t("teamManagement.teamNameLabel")}</Label>
              <Input
                id="team-name"
                placeholder={t("teamManagement.teamNamePlaceholder")}
                value={newTeamName}
                onChange={(e) => {
                  const next = e.target.value;
                  setNewTeamName(next);
                  // Only auto-fill slug when user hasn't customized it yet.
                  if (!newTeamSlug || newTeamSlug === slugifyName(newTeamName)) {
                    setNewTeamSlug(slugifyName(next));
                  }
                }}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="team-slug">{t("teamManagement.teamSlugLabel")}</Label>
              <Input
                id="team-slug"
                placeholder={t("teamManagement.teamSlugPlaceholder")}
                value={newTeamSlug}
                onChange={(e) =>
                  setNewTeamSlug(e.target.value.replace(/[^a-z0-9-]/g, "").toLowerCase())
                }
              />
            </div>
          </CardContent>
          <CardFooter className="justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>
              {t("common:actions.cancel", { defaultValue: "取消" })}
            </Button>
            <Button
              size="sm"
              disabled={!newTeamName.trim() || !newTeamSlug.trim() || createMut.isPending}
              onClick={() =>
                createMut.mutate({ name: newTeamName.trim(), slug: newTeamSlug.trim() })
              }
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {t("common:actions.save")}
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Empty / list */}
      {!teams.length ? (
        <Card>
          <CardContent className="py-8">
            <Empty className="border-0 p-0">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <UsersIcon />
                </EmptyMedia>
                <EmptyTitle>{t("teamManagement.noTeams")}</EmptyTitle>
                <EmptyDescription>{t("teamManagement.noTeamsHint")}</EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button
                  size="sm"
                  onClick={() => setShowCreate(true)}
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  <PlusIcon className="size-4" />
                  {t("teamManagement.createTeam")}
                </Button>
              </EmptyContent>
            </Empty>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {paginatedTeams.map((team) => {
              const isExpanded = expandedTeamId === team.id;
              const memberCount = team.members?.length ?? 0;
              const candidates = users.filter(
                (user) => !team.members?.some((member) => member.user_id === user.id),
              );

              return (
                <Card key={team.id} className="h-fit">
                  <CardHeader className="border-b">
                    {editingId === team.id ? (
                      <Input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="h-9"
                        onBlur={() => commitRename(team.id, editName)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") commitRename(team.id, editName);
                          if (e.key === "Escape") setEditingId(null);
                        }}
                        autoFocus
                      />
                    ) : (
                      <CardTitle
                        className="cursor-pointer hover:text-primary"
                        onClick={() => {
                          setEditingId(team.id);
                          setEditName(team.name);
                        }}
                        title={t("teamManagement.renameHint", { defaultValue: "点击重命名" })}
                      >
                        {team.name}
                      </CardTitle>
                    )}
                    <CardDescription className="font-mono text-xs">{team.slug}</CardDescription>
                    <CardAction>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={t("teamManagement.confirmDelete")}
                        onClick={() => {
                          if (window.confirm(t("teamManagement.confirmDelete"))) {
                            deleteMut.mutate(team.id);
                          }
                        }}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <TrashIcon className="size-4" />
                      </Button>
                    </CardAction>
                  </CardHeader>

                  <CardContent className="space-y-4 pt-4">
                    <div className="flex items-center justify-between gap-3">
                      <TeamMemberPreview team={team} />
                      <Badge variant="outline">
                        {t("teamManagement.membersCount", { count: memberCount })}
                      </Badge>
                    </div>

                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full justify-between"
                      onClick={() => setExpandedTeamId(isExpanded ? null : team.id)}
                    >
                      <span>
                        {isExpanded
                          ? t("teamManagement.collapse", { defaultValue: "收起" })
                          : t("teamManagement.manage", { defaultValue: "管理成员" })}
                      </span>
                      <ChevronDownIcon
                        className={cn(
                          "size-4 text-muted-foreground transition-transform",
                          isExpanded && "rotate-180",
                        )}
                      />
                    </Button>

                    {isExpanded && (
                      <div className="space-y-3 rounded-lg border bg-muted/30 p-3">
                        <div className="space-y-1.5">
                          <Label className="text-xs text-muted-foreground">
                            {t("teamManagement.addMember")}
                          </Label>
                          <Select
                            onValueChange={(value: string | null) => {
                              if (value) {
                                addMemberMut.mutate({ teamId: team.id, userId: value });
                              }
                            }}
                          >
                            <SelectTrigger className="w-full bg-background">
                              <SelectValue
                                placeholder={
                                  candidates.length
                                    ? t("teamManagement.addMember")
                                    : t("teamManagement.noCandidates", {
                                        defaultValue: "暂无可添加成员",
                                      })
                                }
                              />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectGroup>
                                {candidates.map((user) => (
                                  <SelectItem key={user.id} value={user.id}>
                                    {user.display_name} ({user.email})
                                  </SelectItem>
                                ))}
                              </SelectGroup>
                            </SelectContent>
                          </Select>
                        </div>

                        <Separator />

                        {memberCount > 0 ? (
                          <div className="flex max-h-56 flex-col gap-2 overflow-y-auto">
                            {team.members!.map((member) => (
                              <div
                                key={member.id}
                                className="flex items-center justify-between gap-2 rounded-md border bg-background px-2.5 py-2"
                              >
                                <div className="flex min-w-0 items-center gap-2">
                                  <Avatar size="sm">
                                    <AvatarFallback>
                                      {memberInitials(
                                        member.user_display_name,
                                        member.user_email,
                                      )}
                                    </AvatarFallback>
                                  </Avatar>
                                  <div className="min-w-0">
                                    <p className="truncate text-sm font-medium text-foreground">
                                      {member.user_display_name}
                                    </p>
                                    <p className="truncate text-xs text-muted-foreground">
                                      {member.user_email}
                                    </p>
                                  </div>
                                </div>
                                <div className="flex shrink-0 items-center gap-1.5">
                                  <Badge
                                    variant={member.role === "admin" ? "default" : "secondary"}
                                  >
                                    {t(`workspaceMembers.roles.${member.role}`, {
                                      defaultValue: member.role,
                                    })}
                                  </Badge>
                                  <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    aria-label={t("teamManagement.removeMember")}
                                    className="text-muted-foreground hover:text-destructive"
                                    onClick={() =>
                                      removeMemberMut.mutate({
                                        teamId: team.id,
                                        userId: member.user_id,
                                      })
                                    }
                                  >
                                    <TrashIcon className="size-3.5" />
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="py-4 text-center text-sm text-muted-foreground">
                            {t("teamManagement.noMembers")}
                          </p>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="icon-sm"
                disabled={safePage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeftIcon className="size-4" />
              </Button>
              {Array.from({ length: totalPages }, (_, i) => (
                <Button
                  key={i}
                  size="sm"
                  variant={safePage === i + 1 ? "default" : "outline"}
                  onClick={() => setCurrentPage(i + 1)}
                  className="min-w-9"
                >
                  {i + 1}
                </Button>
              ))}
              <Button
                variant="outline"
                size="icon-sm"
                disabled={safePage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              >
                <ChevronRightIcon className="size-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
