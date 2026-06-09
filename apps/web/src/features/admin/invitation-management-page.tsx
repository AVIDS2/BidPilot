import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { createInvitation, listInvitations, revokeInvitation } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { toast } from "sonner";
import { MailIcon, ShieldIcon, PlusIcon, XIcon } from "lucide-react";

function InvitationSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Skeleton className="size-6" />
        <Skeleton className="h-7 w-48" />
      </div>
      <div className="rounded-xl p-6" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
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
      <div className="flex flex-col gap-6">
        <div className="flex flex-col items-center justify-center py-20" style={{ color: "#a3a3a3" }}>
          <ShieldIcon className="size-10 mb-3 opacity-40" />
          <p className="text-sm">{t("userManagement.adminRequired")}</p>
        </div>
      </div>
    );
  }

  const items = invitations ?? [];

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MailIcon className="size-5" style={{ color: "#a3a3a3" }} />
          <h1 className="text-xl font-semibold tracking-tight text-white">{t("invitationManagement.title")}</h1>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(132, 204, 22, 0.15)", color: "#84cc16" }}>
            {items.length}
          </span>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)} className="bg-[#84cc16] text-[#0a0a0a] hover:bg-[#65a30d]">
          <PlusIcon className="size-4 mr-1.5" />
          {t("invitationManagement.inviteUser")}
        </Button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="rounded-xl p-5" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
          <div className="flex items-end gap-3">
            <div className="flex-1 space-y-1.5">
              <label className="text-sm font-medium text-white">{t("invitationManagement.emailLabel")}</label>
              <Input
                type="email"
                placeholder={t("invitationManagement.emailPlaceholder")}
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                className="bg-[#0a0a0a] border-[rgba(163,163,163,0.1)] text-white placeholder:text-[#737373]"
              />
            </div>
            <Button
              disabled={!inviteEmail}
              onClick={() => createMut.mutate({ email: inviteEmail })}
              className="bg-[#84cc16] text-[#0a0a0a] hover:bg-[#65a30d]"
            >
              {t("common:actions.save")}
            </Button>
          </div>
        </div>
      )}

      {/* Invitations table */}
      <div className="rounded-xl overflow-hidden" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
        <div className="px-5 py-4" style={{ borderBottom: "1px solid rgba(163, 163, 163, 0.08)" }}>
          <h2 className="text-sm font-medium text-white">{t("invitationManagement.allInvitations")}</h2>
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
                  <tr style={{ borderBottom: "1px solid rgba(163, 163, 163, 0.08)" }}>
                    <th className="text-left py-3 px-3 font-medium" style={{ color: "#a3a3a3" }}>{t("table.email")}</th>
                    <th className="text-left py-3 px-3 font-medium" style={{ color: "#a3a3a3" }}>{t("invitationManagement.status")}</th>
                    <th className="text-right py-3 px-3 font-medium" style={{ color: "#a3a3a3" }}>{t("table.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((inv) => (
                    <tr key={inv.id} className="transition-colors" style={{ borderBottom: "1px solid rgba(163, 163, 163, 0.05)" }}>
                      <td className="py-3 px-3 font-medium text-white">{inv.email}</td>
                      <td className="py-3 px-3">
                        <span className="text-xs px-2 py-0.5 rounded" style={{
                          background: inv.status === "pending" ? "rgba(132, 204, 22, 0.15)" : "rgba(163, 163, 163, 0.08)",
                          color: inv.status === "pending" ? "#84cc16" : "#a3a3a3",
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
                            className="text-[#737373] hover:text-red-400"
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
    </div>
  );
}
