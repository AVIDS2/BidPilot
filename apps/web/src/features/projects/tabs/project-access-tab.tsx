import { useMemo, useState } from "react";
import { Loader2Icon, ShieldCheckIcon, Trash2Icon, UserPlusIcon, UsersRoundIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { OrganizationMemberRead, ProjectMemberRead, ProjectRole } from "@/lib/api";

const PROJECT_ROLES: ProjectRole[] = ["owner", "manager", "contributor", "reviewer", "viewer"];

interface ProjectAccessTabProps {
  projectId: string;
  members: ProjectMemberRead[];
  organizationMembers: OrganizationMemberRead[];
  canManageMembers: boolean;
  onAddMember: (data: { user_id: string; role: ProjectRole }) => Promise<unknown>;
  onUpdateMember: (userId: string, role: ProjectRole) => Promise<unknown>;
  onRemoveMember: (userId: string) => Promise<unknown>;
  adding?: boolean;
  updating?: boolean;
  removing?: boolean;
}

export function ProjectAccessTab({
  projectId: _projectId,
  members,
  organizationMembers,
  canManageMembers,
  onAddMember,
  onUpdateMember,
  onRemoveMember,
  adding = false,
  updating = false,
  removing = false,
}: ProjectAccessTabProps) {
  const { t } = useTranslation("projects");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<ProjectRole>("contributor");
  const [memberPendingRemoval, setMemberPendingRemoval] = useState<ProjectMemberRead | null>(null);

  const candidates = useMemo(() => {
    const existingMemberIds = new Set(members.map((member) => member.user_id));
    return organizationMembers.filter((member) => !existingMemberIds.has(member.id));
  }, [members, organizationMembers]);

  const addMember = async () => {
    if (!selectedUserId) return;
    try {
      await onAddMember({ user_id: selectedUserId, role: selectedRole });
      setSelectedUserId(null);
      setSelectedRole("contributor");
    } catch {
      // The parent mutation provides the user-visible error and retains the selection for retry.
    }
  };

  const removeMember = async () => {
    if (!memberPendingRemoval) return;
    try {
      await onRemoveMember(memberPendingRemoval.user_id);
      setMemberPendingRemoval(null);
    } catch {
      // Keep the confirmation open when the server rejects the removal.
    }
  };

  return (
    <Card className="min-w-0 overflow-hidden">
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-2 text-lg">
            <ShieldCheckIcon className="size-4 text-primary" />
            {t("access.title")}
          </CardTitle>
          <CardDescription className="mt-1 max-w-2xl">
            {t("access.description")}
          </CardDescription>
        </div>
        <Badge variant="outline" className="shrink-0">
          {t("access.memberCount", { count: members.length })}
        </Badge>
      </CardHeader>

      <CardContent className="flex min-w-0 flex-col gap-5">
        {canManageMembers && (
          <FieldGroup className="grid gap-3 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end">
            <Field>
              <FieldLabel>{t("access.addMember")}</FieldLabel>
              <Select value={selectedUserId ?? ""} onValueChange={(value) => setSelectedUserId(value || null)}>
                <SelectTrigger className="w-full" aria-label={t("access.selectMember")}>
                  <SelectValue placeholder={t("access.selectMember")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {candidates.map((member) => (
                      <SelectItem key={member.id} value={member.id}>{member.display_name}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>{t("access.role")}</FieldLabel>
              <RoleSelect value={selectedRole} onValueChange={setSelectedRole} ariaLabel={t("access.selectRole")} />
            </Field>
            <Button disabled={!selectedUserId || adding} onClick={() => void addMember()}>
              {adding && <Loader2Icon data-icon="inline-start" className="animate-spin" />}
              {!adding && <UserPlusIcon data-icon="inline-start" />}
              {t("access.addMember")}
            </Button>
            {candidates.length === 0 && (
              <p className="sm:col-span-3 text-sm text-muted-foreground">{t("access.noCandidates")}</p>
            )}
          </FieldGroup>
        )}

        {members.length === 0 ? (
          <Empty className="min-h-48">
            <EmptyHeader>
              <EmptyMedia variant="icon"><UsersRoundIcon /></EmptyMedia>
              <EmptyTitle>{t("access.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("access.emptyDescription")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <Table className="min-w-[640px]">
            <TableHeader>
              <TableRow>
                <TableHead>{t("access.member")}</TableHead>
                <TableHead>{t("access.role")}</TableHead>
                <TableHead>{t("access.source")}</TableHead>
                {canManageMembers && <TableHead className="w-24 text-right">{t("access.actions")}</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((member) => (
                <TableRow key={member.user_id}>
                  <TableCell>
                    <span className="block max-w-64 truncate font-medium" title={member.display_name}>{member.display_name}</span>
                  </TableCell>
                  <TableCell>
                    {canManageMembers ? (
                      <RoleSelect
                        value={member.role}
                        onValueChange={(role) => void onUpdateMember(member.user_id, role).catch(() => undefined)}
                        ariaLabel={t("access.changeRoleFor", { name: member.display_name })}
                        disabled={updating}
                      />
                    ) : (
                      <RoleBadge role={member.role} />
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{t("access.directMembership")}</TableCell>
                  {canManageMembers && (
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={t("access.removeMemberFor", { name: member.display_name })}
                        disabled={removing}
                        onClick={() => setMemberPendingRemoval(member)}
                      >
                        <Trash2Icon />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <AlertDialog open={Boolean(memberPendingRemoval)} onOpenChange={(open) => !open && setMemberPendingRemoval(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("access.removeTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("access.removeDescription", { name: memberPendingRemoval?.display_name ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("access.cancel")}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={removing} onClick={() => void removeMember()}>
              {removing && <Loader2Icon data-icon="inline-start" className="animate-spin" />}
              {t("access.removeMember")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}

function RoleSelect({
  value,
  onValueChange,
  ariaLabel,
  disabled = false,
}: {
  value: ProjectRole;
  onValueChange: (role: ProjectRole) => void;
  ariaLabel: string;
  disabled?: boolean;
}) {
  const { t } = useTranslation("projects");
  return (
    <Select value={value} onValueChange={(next) => next && onValueChange(next as ProjectRole)}>
      <SelectTrigger size="sm" aria-label={ariaLabel} disabled={disabled}>
        <SelectValue>{t(`access.roles.${value}`)}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {PROJECT_ROLES.map((role) => (
            <SelectItem key={role} value={role}>{t(`access.roles.${role}`)}</SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

function RoleBadge({ role }: { role: ProjectRole }) {
  const { t } = useTranslation("projects");
  return <Badge variant="outline">{t(`access.roles.${role}`)}</Badge>;
}
