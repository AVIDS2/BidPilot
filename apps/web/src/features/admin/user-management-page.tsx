import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { listUsers, updateUserRole, setUserStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import { toast } from "sonner";
import { UsersIcon, ShieldIcon, UserIcon, ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

function UserManagementSkeleton() {
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
        </CardContent>
      </Card>
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

  const users = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  return (
    <div className="mx-auto max-w-5xl py-8 px-4">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <UsersIcon className="size-5 text-muted-foreground" />
          <h1 className="text-xl font-semibold tracking-tight">{t("userManagement.title")}</h1>
          <Badge variant="secondary" className="text-xs">{t("userManagement.usersCount", { count: total })}</Badge>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("userManagement.allUsers")}</CardTitle>
        </CardHeader>
        <CardContent>
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
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("table.user")}</TableHead>
                    <TableHead>{t("table.email")}</TableHead>
                    <TableHead>{t("table.role")}</TableHead>
                    <TableHead>{t("table.plan")}</TableHead>
                    <TableHead>{t("table.status")}</TableHead>
                    <TableHead className="text-right">{t("table.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <UserIcon className="size-4 text-muted-foreground" />
                          {u.display_name}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{u.email}</TableCell>
                      <TableCell>
                        <Select
                          value={u.role}
                          items={roleOptions}
                          onValueChange={(newRole) => { if (newRole) roleMut.mutate({ userId: u.id, role: newRole }); }}
                          disabled={u.id === currentUser?.id}
                        >
                          <SelectTrigger className="w-28">
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
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">
                          {t(`plan.${u.plan ?? "starter"}`, { ns: "admin" })}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {u.id === currentUser?.id ? (
                          <Badge variant="secondary">{t("status.you")}</Badge>
                        ) : (
                          <Badge variant={u.disabled ? "destructive" : "default"}>
                            {u.disabled ? t("status.disabled") : t("status.active")}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {u.id !== currentUser?.id && (
                          <Button
                            variant={u.disabled ? "outline" : "destructive"}
                            size="sm"
                            onClick={() => statusMut.mutate({ userId: u.id, disabled: !u.disabled })}
                          >
                            {u.disabled ? t("status.reenable") : t("status.disable")}
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex items-center justify-between pt-6 border-t border-border mt-4">
                <p className="text-sm text-muted-foreground">
                  {t("common:pagination.pageInfo", { page, totalPages, total })}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => { setPage((p) => p - 1); setJumpInput(""); }}
                  >
                    <ChevronLeftIcon className="size-4" />
                    {t("common:actions.previous")}
                  </Button>
                  <span className="text-sm text-muted-foreground whitespace-nowrap">{t("common:actions.goTo")}</span>
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
                    className="w-20 h-8 text-sm text-center"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => { setPage((p) => p + 1); setJumpInput(""); }}
                  >
                    {t("common:actions.next")}
                    <ChevronRightIcon className="size-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
