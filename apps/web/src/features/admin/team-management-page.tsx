import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { listTeams, createTeam, deleteTeam, updateTeam, addTeamMember, removeTeamMember, listUsers } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import {
  Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { UsersIcon, ShieldIcon, PlusIcon, TrashIcon, ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

const CARDS_PER_PAGE = 9;

function TeamManagementSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Skeleton className="size-6" />
        <Skeleton className="h-7 w-48" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-xl p-6" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
            <Skeleton className="h-5 w-32 mb-3" />
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
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
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedTeamId, setExpandedTeamId] = useState<string | null>(null);

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
      <div className="flex flex-col gap-6">
        <div className="flex flex-col items-center justify-center py-20" style={{ color: "#a3a3a3" }}>
          <ShieldIcon className="size-10 mb-3 opacity-40" />
          <p className="text-sm">{t("userManagement.adminRequired")}</p>
        </div>
      </div>
    );
  }

  const teams = teamsData?.items ?? [];
  const users = usersData?.items ?? [];
  const totalPages = Math.max(1, Math.ceil(teams.length / CARDS_PER_PAGE));
  const paginatedTeams = teams.slice((currentPage - 1) * CARDS_PER_PAGE, currentPage * CARDS_PER_PAGE);

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <UsersIcon className="size-5" style={{ color: "#a3a3a3" }} />
          <h1 className="text-xl font-semibold tracking-tight text-white">{t("teamManagement.title")}</h1>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(132, 204, 22, 0.15)", color: "#84cc16" }}>
            {teams.length}
          </span>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)} className="bg-[#84cc16] text-[#0a0a0a] hover:bg-[#65a30d]">
          <PlusIcon className="size-4 mr-1.5" />
          {t("teamManagement.createTeam")}
        </Button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="rounded-xl p-5" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
          <div className="flex items-end gap-3">
            <div className="flex-1 space-y-1.5">
              <label className="text-sm font-medium text-white">{t("teamManagement.teamNameLabel")}</label>
              <Input
                placeholder={t("teamManagement.teamNamePlaceholder")}
                value={newTeamName}
                onChange={(e) => setNewTeamName(e.target.value)}
                className="bg-[#0a0a0a] border-[rgba(163,163,163,0.1)] text-white placeholder:text-[#737373]"
              />
            </div>
            <div className="flex-1 space-y-1.5">
              <label className="text-sm font-medium text-white">{t("teamManagement.teamSlugLabel")}</label>
              <Input
                placeholder={t("teamManagement.teamSlugPlaceholder")}
                value={newTeamSlug}
                onChange={(e) => setNewTeamSlug(e.target.value.replace(/[^a-z0-9-]/g, "").toLowerCase())}
                className="bg-[#0a0a0a] border-[rgba(163,163,163,0.1)] text-white placeholder:text-[#737373]"
              />
            </div>
            <Button
              disabled={!newTeamName || !newTeamSlug}
              onClick={() => createMut.mutate({ name: newTeamName, slug: newTeamSlug })}
              className="bg-[#84cc16] text-[#0a0a0a] hover:bg-[#65a30d]"
            >
              {t("common:actions.save")}
            </Button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!teams.length ? (
        <div className="rounded-xl py-20" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
          <Empty className="min-h-32">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <UsersIcon />
              </EmptyMedia>
              <EmptyTitle>{t("teamManagement.noTeams")}</EmptyTitle>
              <EmptyDescription>{t("teamManagement.noTeamsHint")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        </div>
      ) : (
        <>
          {/* Card grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {paginatedTeams.map((team) => (
              <div
                key={team.id}
                className="rounded-xl transition-all duration-200 hover:-translate-y-0.5"
                style={{
                  background: "#171717",
                  border: "1px solid rgba(163, 163, 163, 0.1)",
                }}
              >
                {/* Team header */}
                <div className="p-5 pb-3">
                  <div className="flex items-center justify-between mb-2">
                    {editingId === team.id ? (
                      <Input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="flex-1 mr-2 h-8 text-sm bg-[#0a0a0a] border-[rgba(163,163,163,0.1)] text-white"
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
                    ) : (
                      <h3
                        className="text-base font-medium text-white cursor-pointer hover:text-[#84cc16] transition-colors"
                        onClick={() => { setEditingId(team.id); setEditName(team.name); }}
                      >
                        {team.name}
                      </h3>
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => { if (window.confirm("Delete this team?")) deleteMut.mutate(team.id); }}
                      className="text-[#737373] hover:text-red-400"
                    >
                      <TrashIcon className="size-4" />
                    </Button>
                  </div>
                  <p className="text-xs" style={{ color: "#737373" }}>{team.slug}</p>
                  <div className="flex items-center gap-2 mt-3">
                    <span className="text-xs" style={{ color: "#a3a3a3" }}>
                      {team.members?.length ?? 0} {t("teamManagement.membersCount", { count: team.members?.length ?? 0 }).replace(/\d+\s*/, "")}
                    </span>
                    <button
                      className="text-xs hover:text-[#84cc16] transition-colors"
                      style={{ color: "#84cc16" }}
                      onClick={() => setExpandedTeamId(expandedTeamId === team.id ? null : team.id)}
                    >
                      {expandedTeamId === team.id ? t("teamManagement.collapse", { defaultValue: "收起" }) : t("teamManagement.manage", { defaultValue: "管理成员" })}
                    </button>
                  </div>
                </div>

                {/* Expanded member management */}
                {expandedTeamId === team.id && (
                  <div className="px-5 pb-5 pt-2" style={{ borderTop: "1px solid rgba(163, 163, 163, 0.08)" }}>
                    <div className="mb-3">
                      <Select
                        onValueChange={(value: string | null) => {
                          if (value) addMemberMut.mutate({ teamId: team.id, userId: value });
                        }}
                      >
                        <SelectTrigger className="w-full h-8 text-xs bg-[#0a0a0a] border-[rgba(163,163,163,0.1)] text-white">
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
                    {team.members && team.members.length > 0 ? (
                      <div className="flex flex-col gap-1.5 max-h-40 overflow-y-auto">
                        {team.members.map((m) => (
                          <div
                            key={m.id}
                            className="flex items-center justify-between rounded-md px-3 py-1.5 text-xs"
                            style={{ background: "rgba(163, 163, 163, 0.04)" }}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="font-medium text-white truncate">{m.user_display_name}</span>
                              <span className="truncate" style={{ color: "#737373" }}>{m.user_email}</span>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                                background: m.role === "admin" ? "rgba(132, 204, 22, 0.15)" : "rgba(163, 163, 163, 0.1)",
                                color: m.role === "admin" ? "#84cc16" : "#a3a3a3",
                              }}>
                                {m.role}
                              </span>
                              <button
                                className="text-[#737373] hover:text-red-400 transition-colors"
                                onClick={() => removeMemberMut.mutate({ teamId: team.id, userId: m.user_id })}
                              >
                                <TrashIcon className="size-3" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-center py-4" style={{ color: "#737373" }}>
                        {t("teamManagement.noTeamsHint")}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-2">
              <button
                className="px-3 py-1.5 text-sm rounded-md transition-colors disabled:opacity-30"
                style={{
                  background: "#171717",
                  color: "#a3a3a3",
                  border: "1px solid rgba(163, 163, 163, 0.1)",
                }}
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => p - 1)}
              >
                <ChevronLeftIcon className="size-4" />
              </button>
              {Array.from({ length: totalPages }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentPage(i + 1)}
                  className="px-3 py-1.5 text-sm font-medium rounded-md transition-all duration-200"
                  style={{
                    background: currentPage === i + 1 ? "#84cc16" : "#171717",
                    color: currentPage === i + 1 ? "#0a0a0a" : "#a3a3a3",
                    border: `1px solid ${currentPage === i + 1 ? "#84cc16" : "rgba(163, 163, 163, 0.1)"}`,
                  }}
                >
                  {i + 1}
                </button>
              ))}
              <button
                className="px-3 py-1.5 text-sm rounded-md transition-colors disabled:opacity-30"
                style={{
                  background: "#171717",
                  color: "#a3a3a3",
                  border: "1px solid rgba(163, 163, 163, 0.1)",
                }}
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
              >
                <ChevronRightIcon className="size-4" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
