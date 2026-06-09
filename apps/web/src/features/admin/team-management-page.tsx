import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { listTeams, createTeam, deleteTeam, updateTeam, addTeamMember, removeTeamMember, listUsers } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { UsersIcon, ShieldIcon, PlusIcon, TrashIcon } from "lucide-react";

function TeamManagementSkeleton() {
  return (
    <div className="mx-auto max-w-5xl py-8 px-4">
      <div className="flex items-center gap-3 mb-8">
        <Skeleton className="size-6" />
        <Skeleton className="h-7 w-48" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-24" />
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-8 w-32" />
                <Skeleton className="h-8 w-20" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
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

  const { data: teamsData, isLoading } = useQuery({
    queryFn: listTeams,
    queryKey: ["teams"],
  });

  const { data: usersData } = useQuery({
    queryFn: () => listUsers(1, 100),
    queryKey: ["admin-users", 1],
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

  if (isLoading) return <TeamManagementSkeleton />;

  if (currentUser?.role !== "admin") {
    return (
      <div className="mx-auto max-w-5xl py-8 px-4">
        <Card>
          <CardContent className="py-16 text-center text-muted-foreground">
            <ShieldIcon className="mx-auto size-10 mb-3 opacity-40" />
            <p className="text-sm">{t("userManagement.adminRequired")}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const teams = teamsData?.items ?? [];
  const users = usersData?.items ?? [];

  return (
    <div className="mx-auto max-w-5xl py-8 px-4">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <UsersIcon className="size-5 text-muted-foreground" />
          <h1 className="text-xl font-semibold tracking-tight">{t("teamManagement.title")}</h1>
          <Badge variant="secondary" className="text-xs">{t("teamManagement.membersCount", { count: teams.length })}</Badge>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          <PlusIcon className="size-4 mr-1.5" />
          {t("teamManagement.createTeam")}
        </Button>
      </div>

      {showCreate && (
        <Card className="mb-6">
          <CardContent className="py-4">
            <div className="flex items-end gap-3">
              <div className="flex-1 space-y-1.5">
                <label className="text-sm font-medium">{t("teamManagement.teamNameLabel")}</label>
                <Input
                  placeholder={t("teamManagement.teamNamePlaceholder")}
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                />
              </div>
              <div className="flex-1 space-y-1.5">
                <label className="text-sm font-medium">{t("teamManagement.teamSlugLabel")}</label>
                <Input
                  placeholder={t("teamManagement.teamSlugPlaceholder")}
                  value={newTeamSlug}
                  onChange={(e) => setNewTeamSlug(e.target.value.replace(/[^a-z0-9-]/g, "").toLowerCase())}
                />
              </div>
              <Button
                disabled={!newTeamName || !newTeamSlug}
                onClick={() => createMut.mutate({ name: newTeamName, slug: newTeamSlug })}
              >
                {t("common:actions.save")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {!teams.length ? (
        <Card>
          <CardContent className="py-16">
            <Empty className="min-h-32">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <UsersIcon />
                </EmptyMedia>
                <EmptyTitle>{t("teamManagement.noTeams")}</EmptyTitle>
                <EmptyDescription>{t("teamManagement.noTeamsHint")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {teams.map((team) => (
            <Card key={team.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    {editingId === team.id ? (
                      <div className="flex items-center gap-2">
                        <Input
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="w-48"
                          onBlur={() => {
                            updateTeam(team.id, { name: editName }).then(() => {
                              toast.success(t("teamManagement.teamUpdated"));
                              qc.invalidateQueries({ queryKey: ["teams"] });
                            }).catch(() => toast.error(t("teamManagement.operationFailed")));
                            setEditingId(null);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              updateTeam(team.id, { name: editName }).then(() => {
                                toast.success(t("teamManagement.teamUpdated"));
                                qc.invalidateQueries({ queryKey: ["teams"] });
                              }).catch(() => toast.error(t("teamManagement.operationFailed")));
                              setEditingId(null);
                            }
                          }}
                          autoFocus
                        />
                      </div>
                    ) : (
                      <span
                        className="cursor-pointer hover:text-foreground/80 transition-colors"
                        onClick={() => { setEditingId(team.id); setEditName(team.name); }}
                      >
                        {team.name} <span className="text-xs text-muted-foreground font-normal">({team.slug})</span>
                      </span>
                    )}
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => { if (window.confirm("Delete this team?")) deleteMut.mutate(team.id); }}
                  >
                    <TrashIcon className="size-4 text-muted-foreground" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <div className="max-w-xs space-y-1.5">
                    <label className="text-sm font-medium">{t("teamManagement.addMember")}</label>
                    <Select
                      onValueChange={(value: string | null) => {
                        if (value) addMemberMut.mutate({ teamId: team.id, userId: value });
                      }}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder={t("teamManagement.addMember")} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          {users.map((u) => (
                            <SelectItem key={u.id} value={u.id}>
                              {u.display_name} ({u.email})
                            </SelectItem>
                          ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {team.members && team.members.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("table.user")}</TableHead>
                        <TableHead>{t("table.email")}</TableHead>
                        <TableHead>{t("table.role")}</TableHead>
                        <TableHead className="w-20 text-right">{t("table.actions")}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {team.members.map((m) => (
                        <TableRow key={m.id}>
                          <TableCell className="font-medium">{m.user_display_name}</TableCell>
                          <TableCell className="text-muted-foreground">{m.user_email}</TableCell>
                          <TableCell>
                            <Badge variant={m.role === "admin" ? "default" : "outline"}>{m.role}</Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeMemberMut.mutate({ teamId: team.id, userId: m.user_id })}
                            >
                              <TrashIcon className="size-3.5 text-muted-foreground" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-sm text-muted-foreground py-6 text-center">
                    {t("teamManagement.noTeamsHint")}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
