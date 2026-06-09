import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { listUsers, updateUserRole, setUserStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { UsersIcon, ShieldIcon, UserIcon, ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

function UserManagementSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Skeleton className="size-6" />
        <Skeleton className="h-7 w-48" />
      </div>
      <div className="rounded-xl p-6" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-8 w-20" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function UserManagementPage() {
  const { t } = useTranslation(["admin", "common"]);
  const { user: currentUser } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [jumpInput, setJumpInput] = useState("");
  const pageSize = 20;

  const roleOptions = useMemo(() => [
    { label: t("role.admin"), value: "admin" },
    { label: t("role.member"), value: "member" },
  ], [t]);

  const { data, isLoading } = useQuery({
    queryFn: () => listUsers(page, pageSize),
    queryKey: ["admin-users", page],
  });

  const roleMut = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      updateUserRole(userId, role),
    onSuccess: () => {
      toast.success(t("role.updated"));
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => toast.error(t("role.updateFailed")),
  });

  const statusMut = useMutation({
    mutationFn: ({ userId, disabled }: { userId: string; disabled: boolean }) =>
      setUserStatus(userId, disabled),
    onSuccess: (_, vars) => {
      toast.success(vars.disabled ? t("status.disabledAction") : t("status.reenabledAction"));
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => toast.error(t("status.updateFailed")),
  });

  if (isLoading) return <UserManagementSkeleton />;

  if (currentUser?.role !== "admin") {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-col items-center justify-center py-20" style={{ color: "var(--muted-foreground)" }}>
          <ShieldIcon className="size-10 mb-3 opacity-40" />
          <p className="text-sm">{t("userManagement.adminRequired")}</p>
        </div>
      </div>
    );
  }

  const users = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <UsersIcon className="size-5" style={{ color: "var(--muted-foreground)" }} />
          <h1 className="text-xl font-semibold tracking-tight text-foreground">{t("userManagement.title")}</h1>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(132, 204, 22, 0.15)", color: "var(--primary)" }}>
            {total}
          </span>
        </div>
      </div>

      {/* Users table */}
      <div className="rounded-xl overflow-hidden" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
        <div className="px-5 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
          <h2 className="text-sm font-medium text-foreground">{t("userManagement.allUsers")}</h2>
        </div>
        <div className="p-5">
          {!users.length ? (
            <Empty className="min-h-32">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <UsersIcon />
                </EmptyMedia>
                <EmptyTitle>{t("userManagement.noUsers")}</EmptyTitle>
                <EmptyDescription>{t("userManagement.noUsersHint")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th className="text-left py-3 px-3 font-medium" style={{ color: "var(--muted-foreground)" }}>{t("table.user")}</th>
                    <th className="text-left py-3 px-3 font-medium" style={{ color: "var(--muted-foreground)" }}>{t("table.email")}</th>
                    <th className="text-left py-3 px-3 font-medium" style={{ color: "var(--muted-foreground)" }}>{t("table.role")}</th>
                    <th className="text-left py-3 px-3 font-medium" style={{ color: "var(--muted-foreground)" }}>{t("table.plan")}</th>
                    <th className="text-left py-3 px-3 font-medium" style={{ color: "var(--muted-foreground)" }}>{t("table.status")}</th>
                    <th className="text-right py-3 px-3 font-medium" style={{ color: "var(--muted-foreground)" }}>{t("table.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="transition-colors" style={{ borderBottom: "1px solid var(--border)" }}>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-2">
                          <UserIcon className="size-4" style={{ color: "var(--text-tertiary)" }} />
                          <span className="font-medium text-foreground">{u.display_name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3" style={{ color: "var(--muted-foreground)" }}>{u.email}</td>
                      <td className="py-3 px-3">
                        <Select
                          value={u.role}
                          items={roleOptions}
                          onValueChange={(newRole) => { if (newRole) roleMut.mutate({ userId: u.id, role: newRole }); }}
                          disabled={u.id === currentUser?.id}
                        >
                          <SelectTrigger className="w-28 h-8 text-xs bg-background border-border text-foreground">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              {roleOptions.map((opt) => (
                                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                              ))}
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-xs px-2 py-0.5 rounded capitalize" style={{
                          background: "var(--muted)",
                          color: "var(--muted-foreground)",
                          border: "1px solid var(--border)",
                        }}>
                          {t(`plan.${u.plan ?? "starter"}`, { ns: "admin" })}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        {u.id === currentUser?.id ? (
                          <span className="text-xs px-2 py-0.5 rounded" style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}>
                            {t("status.you")}
                          </span>
                        ) : (
                          <span className="text-xs px-2 py-0.5 rounded" style={{
                            background: u.disabled ? "rgba(239, 68, 68, 0.15)" : "rgba(132, 204, 22, 0.15)",
                            color: u.disabled ? "var(--destructive)" : "var(--primary)",
                          }}>
                            {u.disabled ? t("status.disabled") : t("status.active")}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right">
                        {u.id !== currentUser?.id && (
                          <Button
                            variant={u.disabled ? "outline" : "destructive"}
                            size="sm"
                            onClick={() => statusMut.mutate({ userId: u.id, disabled: !u.disabled })}
                            className={u.disabled ? "border-border text-muted-foreground hover:text-foreground" : ""}
                          >
                            {u.disabled ? t("status.reenable") : t("status.disable")}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              <div className="flex items-center justify-between pt-5 mt-4" style={{ borderTop: "1px solid var(--border)" }}>
                <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                  {t("common:pagination.pageInfo", { page, totalPages, total })}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => { setPage((p) => p - 1); setJumpInput(""); }}
                    className="border-border text-muted-foreground hover:text-foreground hover:border-primary"
                  >
                    <ChevronLeftIcon className="size-4" />
                    {t("common:actions.previous")}
                  </Button>
                  <span className="text-sm whitespace-nowrap" style={{ color: "var(--text-tertiary)" }}>{t("common:actions.goTo")}</span>
                  <Input
                    type="number"
                    min={1}
                    max={totalPages}
                    value={jumpInput}
                    onChange={(e) => setJumpInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const n = parseInt(jumpInput, 10);
                        if (n >= 1 && n <= totalPages) { setPage(n); setJumpInput(""); }
                      }
                    }}
                    placeholder={`1-${totalPages}`}
                    className="w-20 h-8 text-sm text-center bg-background border-border text-foreground"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => { setPage((p) => p + 1); setJumpInput(""); }}
                    className="border-border text-muted-foreground hover:text-foreground hover:border-primary"
                  >
                    {t("common:actions.next")}
                    <ChevronRightIcon className="size-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
