import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import {
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CircleOffIcon,
  CrownIcon,
  MailPlusIcon,
  ShieldAlertIcon,
  Trash2Icon,
  UserCogIcon,
  UserMinusIcon,
  UserPlusIcon,
  UsersRoundIcon,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  addTeamMember,
  createInvitation,
  createTeam,
  deleteTeam,
  listInvitations,
  listOrganizationMembers,
  listTeams,
  listUsers,
  removeOrganizationMember,
  removeTeamMember,
  revokeInvitation,
  setUserStatus,
  transferOrganizationBillingOwner,
  updateOrganizationMemberRole,
  updateTeam,
  updateUserRole,
  type OrganizationMemberRead,
  type TeamRead,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

import { ResizableSplitPage } from "./resizable-split-page";
import { displayWorkbenchValue } from "./workbench-labels";

const EMPTY_TEAMS: TeamRead[] = [];
const EMPTY_MEMBERS: OrganizationMemberRead[] = [];
type TeamMemberRemovalTarget = { teamId: string; userId: string; displayName: string; email: string };

function formatDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "short", day: "numeric" }).format(date);
}

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function canManageOrganization(
  members: OrganizationMemberRead[] | undefined,
  userId: string | undefined,
  fallbackRole: string | undefined,
) {
  const membership = members?.find((member) => member.id === userId);
  return membership?.role === "owner" || membership?.role === "admin" || fallbackRole === "admin";
}

function AccessDenied({ title }: { title: string }) {
  return (
    <section className="wb-admin-detail-page wb-admin-restricted" aria-labelledby="admin-restricted-title">
      <ShieldAlertIcon aria-hidden="true" />
      <h1 id="admin-restricted-title">{title}</h1>
      <p>当前账户没有管理此区域的权限。</p>
    </section>
  );
}

export function UserManagementPage() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const usersQuery = useQuery({
    queryKey: ["admin-users", page, pageSize],
    queryFn: () => listUsers(page, pageSize),
    enabled: currentUser?.role === "admin",
    staleTime: 20_000,
  });
  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) => updateUserRole(userId, role),
    onSuccess: () => {
      toast.success("用户角色已更新。");
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => toast.error(errorText(error, "更新用户角色失败。")),
  });
  const statusMutation = useMutation({
    mutationFn: ({ userId, disabled }: { userId: string; disabled: boolean }) => setUserStatus(userId, disabled),
    onSuccess: (_, variables) => {
      toast.success(variables.disabled ? "用户已停用。" : "用户已恢复。");
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => toast.error(errorText(error, "更新用户状态失败。")),
  });

  if (currentUser?.role !== "admin") return <AccessDenied title="用户管理" />;

  const data = usersQuery.data;
  const users = data?.items ?? [];
  const totalPages = data?.pages ?? 1;

  return (
    <section className="wb-admin-detail-page" aria-labelledby="users-page-title">
      <header className="wb-page-header">
        <div>
          <h1 id="users-page-title">用户管理</h1>
          <p>全平台账户、角色和访问状态。</p>
        </div>
        <span className="wb-page-count">{data?.total ?? 0} 位用户</span>
      </header>

      {usersQuery.isLoading ? <p className="wb-list-loading">正在读取用户…</p> : null}
      {usersQuery.isError ? <p className="wb-inline-error">{errorText(usersQuery.error, "用户列表暂时无法读取。")}</p> : null}
      {!usersQuery.isLoading && !usersQuery.isError && users.length === 0 ? <p className="wb-inline-empty">当前还没有可管理的用户。</p> : null}
      {users.length > 0 ? (
        <div className="wb-admin-table-scroll">
          <div className="wb-operations-table wb-user-admin-table">
            <div className="wb-operations-table-head">
              <span>用户</span><span>邮箱</span><span>角色</span><span>套餐</span><span>状态</span><span />
            </div>
            {users.map((user) => {
              const isCurrentUser = user.id === currentUser.id;
              return (
                <div className="wb-operations-table-row" key={user.id}>
                  <span className="wb-operations-primary"><UserCogIcon aria-hidden="true" /> {user.display_name || "未命名用户"}</span>
                  <span className="wb-admin-email">{user.email}</span>
                  <Select
                    disabled={isCurrentUser || roleMutation.isPending}
                    onValueChange={(value) => value && roleMutation.mutate({ userId: user.id, role: value })}
                    value={user.role}
                  >
                    <SelectTrigger aria-label={`${user.display_name || user.email} 的角色`} className="wb-admin-select" size="sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="member">{displayWorkbenchValue("member")}</SelectItem>
                        <SelectItem value="admin">{displayWorkbenchValue("admin")}</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                  <span>{displayWorkbenchValue(user.plan || "starter")}</span>
                  <span className={cn("wb-status-text", user.disabled ? "wb-status-text--failed" : "wb-status-text--complete")}>
                    {isCurrentUser ? "当前账户" : user.disabled ? "已停用" : "正常"}
                  </span>
                  <span className="wb-admin-row-actions">
                    {!isCurrentUser ? (
                      <Button
                        className={cn("h-7 px-2 text-xs", user.disabled && "text-primary")}
                        disabled={statusMutation.isPending}
                        onClick={() => statusMutation.mutate({ userId: user.id, disabled: !user.disabled })}
                        size="sm"
                        type="button"
                        variant="ghost"
                      >
                        {user.disabled ? "恢复" : "停用"}
                      </Button>
                    ) : null}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {totalPages > 1 ? (
        <footer className="wb-pagination" aria-label="用户分页">
          <Button disabled={page <= 1} onClick={() => setPage((current) => current - 1)} size="sm" type="button" variant="outline"><ChevronLeftIcon aria-hidden="true" data-icon="inline-start" /> 上一页</Button>
          <span>{page} / {totalPages}</span>
          <Button disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)} size="sm" type="button" variant="outline">下一页 <ChevronRightIcon aria-hidden="true" data-icon="inline-end" /></Button>
        </footer>
      ) : null}
    </section>
  );
}

export function TeamManagementPage() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const teamsQuery = useQuery({ queryKey: ["teams"], queryFn: listTeams, staleTime: 20_000 });
  const membersQuery = useQuery({ queryKey: ["organization-members"], queryFn: listOrganizationMembers, staleTime: 20_000 });
  const teams = teamsQuery.data?.items ?? EMPTY_TEAMS;
  const members = membersQuery.data ?? EMPTY_MEMBERS;
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [editingName, setEditingName] = useState(false);
  const [nextName, setNextName] = useState("");
  const [nextMemberId, setNextMemberId] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<TeamRead | null>(null);
  const [removeTarget, setRemoveTarget] = useState<TeamMemberRemovalTarget | null>(null);
  const canManage = canManageOrganization(membersQuery.data, currentUser?.id, currentUser?.role);

  useEffect(() => {
    setSelectedTeamId((current) => current && teams.some((team) => team.id === current) ? current : teams[0]?.id ?? null);
  }, [teams]);

  const selectedTeam = teams.find((team) => team.id === selectedTeamId) ?? null;
  const availableMembers = useMemo(() => {
    if (!selectedTeam) return [];
    const memberIds = new Set(selectedTeam.members?.map((member) => member.user_id) ?? []);
    return members.filter((member) => !memberIds.has(member.id));
  }, [members, selectedTeam]);
  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["teams"] });
  const createMutation = useMutation({
    mutationFn: createTeam,
    onSuccess: (created) => {
      setName("");
      setSlug("");
      setShowCreate(false);
      setSelectedTeamId(created.id);
      toast.success("响应团队已创建。");
      invalidate();
    },
    onError: (error) => toast.error(errorText(error, "创建团队失败。")),
  });
  const renameMutation = useMutation({
    mutationFn: ({ id, name: value }: { id: string; name: string }) => updateTeam(id, { name: value }),
    onSuccess: () => {
      setEditingName(false);
      toast.success("团队名称已更新。");
      invalidate();
    },
    onError: (error) => toast.error(errorText(error, "更新团队失败。")),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteTeam,
    onSuccess: () => {
      setSelectedTeamId(null);
      toast.success("团队已删除。");
      invalidate();
    },
    onError: (error) => toast.error(errorText(error, "删除团队失败。")),
  });
  const addMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: string; userId: string }) => addTeamMember(teamId, { user_id: userId }),
    onSuccess: () => {
      setNextMemberId("");
      toast.success("成员已加入团队。");
      invalidate();
    },
    onError: (error) => toast.error(errorText(error, "添加成员失败。")),
  });
  const removeMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: string; userId: string }) => removeTeamMember(teamId, userId),
    onSuccess: () => {
      toast.success("成员已移出团队。");
      invalidate();
    },
    onError: (error) => toast.error(errorText(error, "移除成员失败。")),
  });

  const submitCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = name.trim();
    const trimmedSlug = slug.trim();
    if (!trimmedName || !trimmedSlug) {
      toast.error("请填写团队名称和工作区标识。");
      return;
    }
    createMutation.mutate({ name: trimmedName, slug: trimmedSlug });
  };
  const submitRename = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTeam || !nextName.trim()) return;
    renameMutation.mutate({ id: selectedTeam.id, name: nextName.trim() });
  };

  if (!canManage && !membersQuery.isLoading) return <AccessDenied title="团队管理" />;

  return (
    <>
    <ResizableSplitPage className="wb-admin-team-page" labelledBy="teams-page-title" storageKey="bidpilot.teams.split-width">
      <aside className="wb-split-list wb-admin-team-list">
        <header className="wb-admin-team-list-head">
          <div>
            <h1 id="teams-page-title">响应团队</h1>
            <p>按角色组织投标响应协作。</p>
          </div>
          <Button aria-label="创建团队" className="h-7 w-7" disabled={!canManage} onClick={() => setShowCreate((value) => !value)} size="icon-sm" title="创建团队" type="button" variant="ghost"><UserPlusIcon aria-hidden="true" /></Button>
        </header>
        {showCreate ? (
          <form className="wb-admin-create-form" onSubmit={submitCreate}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="team-name">团队名称</FieldLabel>
                <Input autoFocus id="team-name" onChange={(event) => setName(event.target.value)} value={name} />
              </Field>
              <Field>
                <FieldLabel htmlFor="team-slug">标识</FieldLabel>
                <Input id="team-slug" onChange={(event) => setSlug(event.target.value)} placeholder="proposal-team" value={slug} />
              </Field>
            </FieldGroup>
            <span>
              <Button disabled={createMutation.isPending} size="sm" type="submit">创建</Button>
              <Button onClick={() => setShowCreate(false)} size="sm" type="button" variant="ghost">取消</Button>
            </span>
          </form>
        ) : null}
        {teamsQuery.isLoading ? <p className="wb-list-loading">正在读取团队…</p> : null}
        {teamsQuery.isError ? <p className="wb-inline-error">{errorText(teamsQuery.error, "团队列表暂时无法读取。")}</p> : null}
        {!teamsQuery.isLoading && !teamsQuery.isError && teams.length === 0 ? <p className="wb-side-list-empty">尚未创建响应团队。</p> : null}
        <div className="wb-admin-team-list-rows">
          {teams.map((team) => (
            <Button className={cn("wb-side-list-row h-auto w-full justify-start text-left", selectedTeam?.id === team.id && "is-selected")} key={team.id} onClick={() => setSelectedTeamId(team.id)} size="sm" type="button" variant="ghost">
              <UsersRoundIcon aria-hidden="true" />
              <span><strong>{team.name}</strong><small>{team.slug}</small></span>
              <small className="wb-list-row-count">{team.members?.length ?? 0}</small>
            </Button>
          ))}
        </div>
      </aside>

      <article className="wb-split-detail wb-admin-team-detail">
        {!selectedTeam ? (
          <div className="wb-operations-empty"><UsersRoundIcon aria-hidden="true" /><strong>选择一个团队</strong><span>创建或选择团队后，在此管理成员。</span></div>
        ) : (
          <>
            <header className="wb-admin-team-detail-head">
              {editingName ? (
                <form className="wb-admin-rename-form" onSubmit={submitRename}>
                  <Input aria-label="团队名称" autoFocus onChange={(event) => setNextName(event.target.value)} value={nextName} />
                  <Button disabled={renameMutation.isPending} size="sm" type="submit"><CheckIcon aria-hidden="true" data-icon="inline-start" /> 保存</Button>
                  <Button onClick={() => setEditingName(false)} size="sm" type="button" variant="ghost">取消</Button>
                </form>
              ) : (
                <div><h2>{selectedTeam.name}</h2><p>{selectedTeam.slug}</p></div>
              )}
              <span className="wb-admin-row-actions">
                {!editingName ? <Button className="h-7 px-2 text-xs" disabled={!canManage} onClick={() => { setNextName(selectedTeam.name); setEditingName(true); }} size="sm" type="button" variant="ghost">重命名</Button> : null}
                <Button className="h-7 px-2 text-xs" disabled={!canManage || deleteMutation.isPending} onClick={() => setDeleteTarget(selectedTeam)} size="sm" type="button" variant="destructive"><Trash2Icon aria-hidden="true" data-icon="inline-start" /> 删除</Button>
              </span>
            </header>

            <section className="wb-operations-section">
              <div className="wb-section-heading-row"><p className="wb-section-heading">团队成员</p><span>{selectedTeam.members?.length ?? 0} 人</span></div>
              {selectedTeam.members?.length ? (
                <div className="wb-operations-table wb-team-members-table">
                  <div className="wb-operations-table-head"><span>成员</span><span>邮箱</span><span>角色</span><span /></div>
                  {selectedTeam.members.map((member) => (
                    <div className="wb-operations-table-row" key={member.id}>
                      <span className="wb-operations-primary"><UsersRoundIcon aria-hidden="true" /> {member.user_display_name}</span>
                      <span>{member.user_email}</span>
                      <span>{displayWorkbenchValue(member.role)}</span>
                      <span className="wb-admin-row-actions"><Button className="h-7 px-2 text-xs" disabled={!canManage || removeMemberMutation.isPending} onClick={() => setRemoveTarget({ teamId: selectedTeam.id, userId: member.user_id, displayName: member.user_display_name, email: member.user_email })} size="sm" type="button" variant="destructive"><UserMinusIcon aria-hidden="true" data-icon="inline-start" /> 移出</Button></span>
                    </div>
                  ))}
                </div>
              ) : <p className="wb-inline-empty">该团队尚未配置成员。</p>}
            </section>

            {canManage ? (
              <form className="wb-admin-add-member-form" onSubmit={(event) => {
                event.preventDefault();
                if (nextMemberId) addMemberMutation.mutate({ teamId: selectedTeam.id, userId: nextMemberId });
              }}>
                <UserPlusIcon aria-hidden="true" />
                <Select onValueChange={(value) => value && setNextMemberId(value)} value={nextMemberId || undefined}>
                  <SelectTrigger aria-label="选择要加入的组织成员" className="wb-admin-select" size="sm"><SelectValue placeholder="选择组织成员" /></SelectTrigger>
                  <SelectContent><SelectGroup>{availableMembers.map((member) => <SelectItem key={member.id} value={member.id}>{member.display_name} · {member.email}</SelectItem>)}</SelectGroup></SelectContent>
                </Select>
                <Button disabled={!nextMemberId || addMemberMutation.isPending} size="sm" type="submit">加入团队</Button>
              </form>
            ) : null}
          </>
        )}
      </article>
    </ResizableSplitPage>
    <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>删除响应团队？</AlertDialogTitle>
          <AlertDialogDescription>团队“{deleteTarget?.name}”将被删除，团队成员不会被删除。</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              if (!deleteTarget) return;
              const target = deleteTarget;
              setDeleteTarget(null);
              deleteMutation.mutate(target.id);
            }}
            variant="destructive"
          >
            删除团队
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    <AlertDialog open={Boolean(removeTarget)} onOpenChange={(open) => !open && setRemoveTarget(null)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>移出团队成员？</AlertDialogTitle>
          <AlertDialogDescription>将“{removeTarget?.displayName}”从当前团队移出，不会删除其工作区账户。</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              if (!removeTarget) return;
              const target = removeTarget;
              setRemoveTarget(null);
              removeMemberMutation.mutate({ teamId: target.teamId, userId: target.userId });
            }}
            variant="destructive"
          >
            移出成员
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  );
}

export function InvitationManagementPage() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const membersQuery = useQuery({ queryKey: ["organization-members"], queryFn: listOrganizationMembers, staleTime: 20_000 });
  const canManage = canManageOrganization(membersQuery.data, currentUser?.id, currentUser?.role);
  const invitationsQuery = useQuery({ queryKey: ["invitations"], queryFn: listInvitations, enabled: canManage, staleTime: 20_000 });
  const [email, setEmail] = useState("");
  const [removeTarget, setRemoveTarget] = useState<{ userId: string; displayName: string } | null>(null);
  const invalidateMembers = () => void queryClient.invalidateQueries({ queryKey: ["organization-members"] });
  const invalidateInvitations = () => void queryClient.invalidateQueries({ queryKey: ["invitations"] });
  const inviteMutation = useMutation({
    mutationFn: createInvitation,
    onSuccess: () => { setEmail(""); toast.success("邀请已发送。"); invalidateInvitations(); },
    onError: (error) => toast.error(errorText(error, "发送邀请失败。")),
  });
  const revokeMutation = useMutation({
    mutationFn: revokeInvitation,
    onSuccess: () => { toast.success("邀请已撤销。"); invalidateInvitations(); },
    onError: (error) => toast.error(errorText(error, "撤销邀请失败。")),
  });
  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: OrganizationMemberRead["role"] }) => updateOrganizationMemberRole(userId, role),
    onSuccess: () => { toast.success("成员角色已更新。"); invalidateMembers(); },
    onError: (error) => toast.error(errorText(error, "更新成员角色失败。")),
  });
  const billingOwnerMutation = useMutation({
    mutationFn: transferOrganizationBillingOwner,
    onSuccess: () => { toast.success("账单所有权已转交。"); invalidateMembers(); },
    onError: (error) => toast.error(errorText(error, "转交账单所有权失败。")),
  });
  const removeMemberMutation = useMutation({
    mutationFn: removeOrganizationMember,
    onSuccess: () => { toast.success("成员已从工作区移除。"); invalidateMembers(); },
    onError: (error) => toast.error(errorText(error, "移除成员失败。")),
  });

  const submitInvite = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = email.trim();
    if (!normalized) return;
    inviteMutation.mutate({ email: normalized });
  };

  if (!canManage && !membersQuery.isLoading) return <AccessDenied title="工作区访问" />;

  const members = membersQuery.data ?? [];
  const invitations = invitationsQuery.data ?? [];
  return (
    <>
    <section className="wb-admin-detail-page" aria-labelledby="invitations-page-title">
      <header className="wb-page-header">
        <div><h1 id="invitations-page-title">工作区访问</h1><p>成员角色、账单归属与待接受邀请。</p></div>
        <form className="wb-invite-form" onSubmit={submitInvite}>
          <Input aria-label="邀请成员邮箱" autoComplete="email" onChange={(event) => setEmail(event.target.value)} placeholder="name@company.com" type="email" value={email} />
          <Button disabled={inviteMutation.isPending} size="sm" type="submit"><MailPlusIcon aria-hidden="true" data-icon="inline-start" /> 邀请成员</Button>
        </form>
      </header>

      <section className="wb-operations-section">
        <p className="wb-section-heading">成员</p>
        {membersQuery.isLoading ? <p className="wb-list-loading">正在读取成员…</p> : null}
        {membersQuery.isError ? <p className="wb-inline-error">{errorText(membersQuery.error, "成员列表暂时无法读取。")}</p> : null}
        {members.length > 0 ? (
          <div className="wb-admin-table-scroll"><div className="wb-operations-table wb-workspace-members-table">
            <div className="wb-operations-table-head"><span>成员</span><span>邮箱</span><span>角色</span><span>账单</span><span /></div>
            {members.map((member) => {
              const isCurrentUser = member.id === currentUser?.id;
              return (
                <div className="wb-operations-table-row" key={member.id}>
                  <span className="wb-operations-primary"><UsersRoundIcon aria-hidden="true" /> {member.display_name}</span>
                  <span>{member.email}</span>
                  <Select disabled={isCurrentUser || roleMutation.isPending} onValueChange={(value) => value && roleMutation.mutate({ userId: member.id, role: value as OrganizationMemberRead["role"] })} value={member.role}>
                    <SelectTrigger aria-label={`${member.display_name} 的工作区角色`} className="wb-admin-select" size="sm"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectGroup><SelectItem value="member">{displayWorkbenchValue("member")}</SelectItem><SelectItem value="admin">{displayWorkbenchValue("admin")}</SelectItem><SelectItem value="owner">{displayWorkbenchValue("owner")}</SelectItem></SelectGroup></SelectContent>
                  </Select>
                  <span>{member.is_billing_owner ? <span className="wb-owner-label"><CrownIcon aria-hidden="true" /> 账单负责人</span> : "-"}</span>
                  <span className="wb-admin-row-actions">
                    {!member.is_billing_owner && !isCurrentUser ? <Button className="h-7 px-2 text-xs" disabled={billingOwnerMutation.isPending} onClick={() => billingOwnerMutation.mutate(member.id)} size="sm" type="button" variant="ghost">设为账单 Owner</Button> : null}
                    {!member.is_billing_owner && !isCurrentUser ? <Button className="h-7 px-2 text-xs" disabled={removeMemberMutation.isPending} onClick={() => setRemoveTarget({ userId: member.id, displayName: member.display_name })} size="sm" type="button" variant="destructive">移除</Button> : null}
                  </span>
                </div>
              );
            })}
          </div></div>
        ) : null}
      </section>

      <section className="wb-operations-section">
        <p className="wb-section-heading">待接受邀请</p>
        {invitationsQuery.isLoading ? <p className="wb-list-loading">正在读取邀请…</p> : null}
        {invitationsQuery.isError ? <p className="wb-inline-error">{errorText(invitationsQuery.error, "邀请列表暂时无法读取。")}</p> : null}
        {!invitationsQuery.isLoading && !invitationsQuery.isError && invitations.length === 0 ? <p className="wb-inline-empty">没有待处理的邀请。</p> : null}
        {invitations.length > 0 ? (
          <div className="wb-admin-table-scroll"><div className="wb-operations-table wb-invitation-admin-table">
            <div className="wb-operations-table-head"><span>邮箱</span><span>状态</span><span>创建时间</span><span /></div>
            {invitations.map((invitation) => (
              <div className="wb-operations-table-row" key={invitation.id}>
                <span className="wb-operations-primary"><MailPlusIcon aria-hidden="true" /> {invitation.email}</span>
                <span className="wb-status-text wb-status-text--approval">{displayWorkbenchValue(invitation.status)}</span>
                <span>{formatDate(invitation.created_at)}</span>
                <span className="wb-admin-row-actions"><Button className="h-7 px-2 text-xs" disabled={revokeMutation.isPending} onClick={() => revokeMutation.mutate(invitation.id)} size="sm" type="button" variant="destructive"><CircleOffIcon aria-hidden="true" data-icon="inline-start" /> 撤销</Button></span>
              </div>
            ))}
          </div></div>
        ) : null}
      </section>
    </section>
    <AlertDialog open={Boolean(removeTarget)} onOpenChange={(open) => !open && setRemoveTarget(null)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>移出工作区成员？</AlertDialogTitle>
          <AlertDialogDescription>将“{removeTarget?.displayName}”从当前工作区移出，不会删除其账户数据。</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              if (!removeTarget) return;
              const target = removeTarget;
              setRemoveTarget(null);
              removeMemberMutation.mutate(target.userId);
            }}
            variant="destructive"
          >
            移出成员
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  );
}
