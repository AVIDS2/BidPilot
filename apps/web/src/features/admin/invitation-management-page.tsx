import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  createInvitation,
  getApiErrorDetail,
  listInvitations,
  listOrganizationMembers,
  removeOrganizationMember,
  revokeInvitation,
  transferOrganizationBillingOwner,
  updateOrganizationMemberRole,
  type OrganizationMemberRead,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { CrownIcon, MailIcon, ShieldIcon, PlusIcon, Trash2Icon, UserCogIcon, XIcon } from "lucide-react";

function InvitationSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Skeleton className="size-6" />
        <Skeleton className="h-7 w-48" />
      </div>
      <div className="rounded-xl p-6" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-8 w-20" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function InvitationManagementPage() {
  const { t } = useTranslation(["admin", "common"]);
  const { user: currentUser } = useAuth();
  const qc = useQueryClient();
  const [inviteEmail, setInviteEmail] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [memberPendingRemoval, setMemberPendingRemoval] = useState<OrganizationMemberRead | null>(null);

  const { data: members, isLoading: isLoadingMembers } = useQuery({
    queryFn: listOrganizationMembers,
    queryKey: ["organization-members"],
  });
  const currentMembership = members?.find((member) => member.id === currentUser?.id);
  const canManageInvitations = currentMembership?.role === "owner" || currentMembership?.role === "admin";
  const { data: invitations, isLoading } = useQuery({
    queryFn: listInvitations,
    queryKey: ["invitations"],
    enabled: canManageInvitations,
  });

  const createMut = useMutation({
    mutationFn: (data: { email: string }) => createInvitation(data),
    onSuccess: () => {
      toast.success(t("invitationManagement.inviteSent"));
      qc.invalidateQueries({ queryKey: ["invitations"] });
      setInviteEmail("");
      setShowCreate(false);
    },
    onError: () => toast.error(t("invitationManagement.inviteFailed")),
  });

  const revokeMut = useMutation({
    mutationFn: (id: string) => revokeInvitation(id),
    onSuccess: () => {
      toast.success(t("invitationManagement.revoked"));
      qc.invalidateQueries({ queryKey: ["invitations"] });
    },
    onError: () => toast.error(t("invitationManagement.revokeFailed")),
  });

  const updateRoleMut = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: OrganizationMemberRead["role"] }) =>
      updateOrganizationMemberRole(userId, role),
    onSuccess: () => {
      toast.success(t("workspaceMembers.roleUpdated"));
      qc.invalidateQueries({ queryKey: ["organization-members"] });
    },
    onError: (error) => toast.error(String(getApiErrorDetail(error) ?? t("workspaceMembers.operationFailed"))),
  });

  const transferBillingOwnerMut = useMutation({
    mutationFn: (userId: string) => transferOrganizationBillingOwner(userId),
    onSuccess: () => {
      toast.success(t("workspaceMembers.billingOwnerTransferred"));
      qc.invalidateQueries({ queryKey: ["organization-members"] });
      qc.invalidateQueries({ queryKey: ["organization-entitlements"] });
    },
    onError: (error) => toast.error(String(getApiErrorDetail(error) ?? t("workspaceMembers.operationFailed"))),
  });

  const removeMemberMut = useMutation({
    mutationFn: (userId: string) => removeOrganizationMember(userId),
    onSuccess: (result) => {
      toast.success(
        result.personal_workspace_created
          ? t("workspaceMembers.memberRemovedWithPersonalWorkspace")
          : t("workspaceMembers.memberRemoved"),
      );
      qc.invalidateQueries({ queryKey: ["organization-members"] });
      qc.invalidateQueries({ queryKey: ["organization-entitlements"] });
      qc.invalidateQueries({ queryKey: ["invitations"] });
      setMemberPendingRemoval(null);
    },
    onError: (error) => toast.error(String(getApiErrorDetail(error) ?? t("workspaceMembers.operationFailed"))),
  });

  if (isLoadingMembers || (canManageInvitations && isLoading)) return <InvitationSkeleton />;

  if (!canManageInvitations) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-col items-center justify-center py-20" style={{ color: "var(--muted-foreground)" }}>
          <ShieldIcon className="size-10 mb-3 opacity-40" />
          <p className="text-sm">{t("invitationManagement.workspaceManagerRequired")}</p>
        </div>
      </div>
    );
  }

  const items = invitations ?? [];
  const isWorkspaceOwner = currentMembership?.role === "owner";
  const isBillingOwner = currentMembership?.is_billing_owner === true;
  const canRemoveMember = (member: OrganizationMemberRead) => {
    if (!canManageInvitations || member.id === currentUser?.id || member.is_billing_owner) return false;
    return currentMembership?.role === "owner" || member.role !== "owner";
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MailIcon className="size-5" style={{ color: "var(--muted-foreground)" }} />
          <h1 className="text-xl font-semibold tracking-tight text-foreground">{t("invitationManagement.title")}</h1>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(132, 204, 22, 0.15)", color: "var(--primary)" }}>
            {items.length}
          </span>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)} className="bg-primary text-primary-foreground hover:bg-primary/90">
          <PlusIcon className="size-4 mr-1.5" />
          {t("invitationManagement.inviteUser")}
        </Button>
      </div>

      <section className="rounded-xl overflow-hidden" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
        <div className="flex flex-col gap-1 px-5 py-4 sm:flex-row sm:items-center sm:justify-between" style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="flex items-center gap-2">
            <UserCogIcon className="size-4" style={{ color: "var(--muted-foreground)" }} />
            <h2 className="text-sm font-medium text-foreground">{t("workspaceMembers.title")}</h2>
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}>
              {t("workspaceMembers.membersCount", { count: members?.length ?? 0 })}
            </span>
          </div>
          <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>{t("workspaceMembers.hint")}</p>
        </div>
        <div className="divide-y" style={{ borderColor: "var(--border)" }}>
          {(members ?? []).map((member) => (
            <div key={member.id} className="flex flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate text-sm font-medium text-foreground">{member.display_name}</span>
                  {member.id === currentUser?.id && (
                    <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>{t("workspaceMembers.you")}</span>
                  )}
                  {member.is_billing_owner && (
                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs" style={{ background: "rgba(132, 204, 22, 0.14)", color: "var(--primary)" }}>
                      <CrownIcon className="size-3" />
                      {t("workspaceMembers.billingOwner")}
                    </span>
                  )}
                </div>
                <p className="mt-1 truncate text-xs" style={{ color: "var(--muted-foreground)" }}>{member.email}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {isWorkspaceOwner ? (
                  <Select
                    value={member.role}
                    onValueChange={(role: string | null) => {
                      if (role && role !== member.role) {
                        updateRoleMut.mutate({ userId: member.id, role: role as OrganizationMemberRead["role"] });
                      }
                    }}
                    disabled={updateRoleMut.isPending || member.is_billing_owner}
                  >
                    <SelectTrigger size="sm" className="min-w-24 bg-background">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="owner">{t("workspaceMembers.roles.owner")}</SelectItem>
                      <SelectItem value="admin">{t("workspaceMembers.roles.admin")}</SelectItem>
                      <SelectItem value="member">{t("workspaceMembers.roles.member")}</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <span className="rounded-md px-2 py-1 text-xs" style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}>
                    {t(`workspaceMembers.roles.${member.role}`)}
                  </span>
                )}
                {isBillingOwner && member.role === "owner" && !member.is_billing_owner && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => transferBillingOwnerMut.mutate(member.id)}
                    disabled={transferBillingOwnerMut.isPending}
                  >
                    {t("workspaceMembers.transferBillingOwner")}
                  </Button>
                )}
                {canRemoveMember(member) && (
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    aria-label={t("workspaceMembers.removeMember")}
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => setMemberPendingRemoval(member)}
                  >
                    <Trash2Icon className="size-4" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Create form */}
      {showCreate && (
        <div className="rounded-xl p-5" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
          <div className="flex items-end gap-3">
            <div className="flex-1 space-y-1.5">
              <label className="text-sm font-medium text-foreground">{t("invitationManagement.emailLabel")}</label>
              <Input
                type="email"
                placeholder={t("invitationManagement.emailPlaceholder")}
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                className="bg-background border-border text-foreground placeholder:text-muted-foreground"
              />
            </div>
            <Button
              disabled={!inviteEmail}
              onClick={() => createMut.mutate({ email: inviteEmail })}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {t("common:actions.save")}
            </Button>
          </div>
        </div>
      )}

      {/* Invitations table */}
      <div className="rounded-xl overflow-hidden" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
        <div className="px-5 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
          <h2 className="text-sm font-medium text-foreground">{t("invitationManagement.allInvitations")}</h2>
        </div>
        <div className="p-5">
          {!items.length ? (
            <Empty className="min-h-32">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <MailIcon />
                </EmptyMedia>
                <EmptyTitle>{t("invitationManagement.noInvitations")}</EmptyTitle>
                <EmptyDescription>{t("invitationManagement.noInvitationsHint")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th className="text-left py-3 px-3 font-medium" style={{ color: "var(--muted-foreground)" }}>{t("table.email")}</th>
                    <th className="text-left py-3 px-3 font-medium" style={{ color: "var(--muted-foreground)" }}>{t("invitationManagement.status")}</th>
                    <th className="text-right py-3 px-3 font-medium" style={{ color: "var(--muted-foreground)" }}>{t("table.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((inv) => (
                    <tr key={inv.id} className="transition-colors" style={{ borderBottom: "1px solid var(--border)" }}>
                      <td className="py-3 px-3 font-medium text-foreground">{inv.email}</td>
                      <td className="py-3 px-3">
                        <span className="text-xs px-2 py-0.5 rounded" style={{
                          background: inv.status === "pending" ? "rgba(132, 204, 22, 0.15)" : "var(--muted)",
                          color: inv.status === "pending" ? "var(--primary)" : "var(--muted-foreground)",
                        }}>
                          {t(`invitationManagement.${inv.status}`)}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        {inv.status === "pending" && (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => revokeMut.mutate(inv.id)}
                            className="text-muted-foreground hover:text-red-400"
                          >
                            <XIcon className="size-4" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <AlertDialog open={Boolean(memberPendingRemoval)} onOpenChange={(open) => !open && setMemberPendingRemoval(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("workspaceMembers.removeTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("workspaceMembers.removeDescription", { name: memberPendingRemoval?.display_name ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("workspaceMembers.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={removeMemberMut.isPending}
              onClick={() => {
                if (memberPendingRemoval) removeMemberMut.mutate(memberPendingRemoval.id);
              }}
            >
              {t("workspaceMembers.removeMember")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
