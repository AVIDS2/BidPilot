import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { createInvitation, listInvitations, revokeInvitation } from "@/lib/api";
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
import { toast } from "sonner";
import { MailIcon, ShieldIcon, PlusIcon, XIcon } from "lucide-react";

function InvitationSkeleton() {
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

export function InvitationManagementPage() {
  const { t } = useTranslation(["admin", "common"]);
  const { user: currentUser } = useAuth();
  const qc = useQueryClient();
  const [inviteEmail, setInviteEmail] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const { data: invitations, isLoading } = useQuery({
    queryFn: listInvitations,
    queryKey: ["invitations"],
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

  if (isLoading) return <InvitationSkeleton />;

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

  const items = invitations ?? [];

  return (
    <div className="mx-auto max-w-5xl py-8 px-4">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <MailIcon className="size-5 text-muted-foreground" />
          <h1 className="text-xl font-semibold tracking-tight">{t("invitationManagement.title")}</h1>
          <Badge variant="secondary" className="text-xs">{items.length}</Badge>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          <PlusIcon className="size-4 mr-1.5" />
          {t("invitationManagement.inviteUser")}
        </Button>
      </div>

      {showCreate && (
        <Card className="mb-6">
          <CardContent className="py-4">
            <div className="flex items-end gap-3">
              <div className="flex-1 space-y-1.5">
                <label className="text-sm font-medium">{t("invitationManagement.emailLabel")}</label>
                <Input
                  type="email"
                  placeholder={t("invitationManagement.emailPlaceholder")}
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                />
              </div>
              <Button
                disabled={!inviteEmail}
                onClick={() => createMut.mutate({ email: inviteEmail })}
              >
                {t("common:actions.save")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{t("invitationManagement.allInvitations")}</CardTitle>
        </CardHeader>
        <CardContent>
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
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("table.email")}</TableHead>
                    <TableHead>{t("invitationManagement.status")}</TableHead>
                    <TableHead className="w-20 text-right">{t("table.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((inv) => (
                    <TableRow key={inv.id}>
                      <TableCell className="font-medium">{inv.email}</TableCell>
                      <TableCell>
                        <Badge variant={inv.status === "pending" ? "default" : "secondary"}>
                          {t(`invitationManagement.${inv.status}`)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {inv.status === "pending" && (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => revokeMut.mutate(inv.id)}
                          >
                            <XIcon className="size-4 text-muted-foreground" />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
