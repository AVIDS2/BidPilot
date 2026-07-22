import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Spinner } from "@/components/ui/spinner"
import { useNavigate, Link } from "react-router-dom"
import { UserIcon, ShieldIcon, BellIcon, KeyIcon, LogOutIcon, MailIcon, CreditCardIcon, UsersRoundIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  createBillingPortal,
  getBillingSummary,
  getOrganizationEntitlements,
  updateCurrentUser,
} from "@/lib/api"
import { toast } from "sonner"
import { useTranslation } from "react-i18next"
import { isStrongPassword } from "@/lib/password"

const sidebarNavItems = [
  { titleKey: "nav.profile" as const, href: "profile", icon: UserIcon },
  { titleKey: "nav.security" as const, href: "security", icon: KeyIcon },
  { titleKey: "nav.notifications" as const, href: "notifications", icon: BellIcon },
]

function AccountPageSkeleton() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64 mt-2" />
      </div>
      <Separator />
      <div className="flex flex-col space-y-8 lg:flex-row lg:space-y-0 lg:space-x-12">
        <aside className="lg:w-1/5">
          <div className="flex space-x-2 lg:flex-col lg:space-y-1 lg:space-x-0">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-24 lg:w-full" />
            ))}
          </div>
        </aside>
        <div className="flex-1 max-w-3xl space-y-8">
          <Card>
            <CardHeader>
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-64" />
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex items-center gap-4">
                <Skeleton className="size-16 rounded-full" />
                <div className="space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-3 w-36" />
                </div>
              </div>
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-9 w-32" />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function getPlanLabel(plan: string | undefined, t: (key: string) => string): string {
  switch (plan) {
    case "starter":
      return t("plan.starterFree");
    case "professional":
      return t("plan.professional");
    case "enterprise":
      return t("plan.enterprise");
    default:
      return t("plan.starterFree");
  }
}

function quotaText(
  t: (key: string, options?: Record<string, unknown>) => string,
  limit: number,
  remaining: number | null,
): string {
  if (limit < 0 || remaining === null) {
    return t("usage.unlimited", { defaultValue: "Unlimited with fair-use controls" });
  }
  return t("usage.remaining", {
    defaultValue: "{{count}} remaining",
    count: remaining,
  });
}

function formatTokenCount(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value)
}

function tokenBudgetText(
  t: (key: string, options?: Record<string, unknown>) => string,
  remaining: number | null,
): string {
  if (remaining === null) {
    return t("usage.tokenBudgetNotSet", { defaultValue: "No additional token cap configured" })
  }
  return t("usage.tokenRemaining", {
    defaultValue: "{{count}} tokens protected by the workspace cap",
    count: formatTokenCount(remaining),
  })
}

export function AccountPage() {
  const { user, logout, setUser } = useAuth()
  const navigate = useNavigate()
  const [activeSection, setActiveSection] = useState("profile")
  const [displayName, setDisplayName] = useState(user?.display_name || "")
  const [currentPw, setCurrentPw] = useState("")
  const [newPw, setNewPw] = useState("")
  const { t } = useTranslation("account")
  const { data: billingSummary } = useQuery({
    queryKey: ["billing-summary"],
    queryFn: getBillingSummary,
    enabled: !!user,
  })
  const { data: organizationEntitlements } = useQuery({
    queryKey: ["organization-entitlements", user?.org_id],
    queryFn: getOrganizationEntitlements,
    enabled: !!user,
  })

  const updateMut = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: (updated) => {
      setUser(updated)
      toast.success(t("profile.updated"))
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes("Display name cannot be empty")) {
        toast.error(t("profile.emptyName"))
      } else if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
        toast.error(t("toast.networkError"))
      } else {
        toast.error(t("profile.updateFailed"))
      }
    },
  })

  const billingPortalMut = useMutation({
    mutationFn: createBillingPortal,
    onSuccess: (result) => {
      window.location.assign(result.url)
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : String(err)
      if (message.includes("409")) {
        navigate("/pricing")
        return
      }
      toast.error(t("billing.manageFailed", { defaultValue: "Unable to open billing management right now." }))
    },
  })

  const handleLogout = () => {
    logout()
    navigate("/login")
  }

  const handleUpdateProfile = () => {
    updateMut.mutate({ display_name: displayName.trim() })
  }

  const handleChangePassword = () => {
    if (!isStrongPassword(newPw)) {
      toast.error(t("security.passwordHint"));
      return;
    }

    updateMut.mutate(
      { current_password: currentPw, new_password: newPw },
      {
        onSuccess: () => {
          toast.success(t("security.changed"));
          setCurrentPw("");
          setNewPw("");
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : String(err);
          toast.error(msg.includes("incorrect") ? t("security.currentIncorrect") : t("security.changeFailed"));
        },
      },
    );
  }

  const initials = (user?.display_name || t("profile.userFallback")).charAt(0).toUpperCase()

  if (!user) return <AccountPageSkeleton />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground">
          {t("description")}
        </p>
      </div>
      <Separator />

      <div className="flex flex-col space-y-8 lg:flex-row lg:space-y-0 lg:space-x-12">
        <aside className="lg:w-1/5">
          <nav className="flex space-x-2 lg:flex-col lg:space-y-1 lg:space-x-0">
            {sidebarNavItems.map((item) => {
              const Icon = item.icon
              const active = activeSection === item.href
              return (
                <Link
                  key={item.href}
                  to="/account"
                  onClick={(e) => { e.preventDefault(); setActiveSection(item.href); }}
                  style={{
                    background: active ? "rgba(132, 204, 22, 0.1)" : "transparent",
                    color: active ? "var(--primary)" : "var(--muted-foreground)",
                  }}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    !active && "hover:text-foreground"
                  )}
                >
                  <Icon className="size-4" />
                  {t(item.titleKey)}
                </Link>
              )
            })}
          </nav>
        </aside>

        <div className="flex-1 max-w-3xl space-y-8">
          {activeSection === "profile" && (
            <>
              <section className="space-y-4">
                <div>
                  <h2 className="text-lg font-medium">{t("profile.title")}</h2>
                  <p className="text-sm text-muted-foreground">
                    {t("profile.description")}
                  </p>
                </div>
                <Separator />

                <div className="flex items-center gap-4">
                  <Avatar className="size-16">
                    <AvatarFallback className="text-xl">{initials}</AvatarFallback>
                  </Avatar>
                  <div className="space-y-1">
                    <p className="text-sm font-medium leading-none">{user?.display_name || t("profile.userFallback")}</p>
                    <p className="text-xs text-muted-foreground">{user?.email || ""}</p>
                    <Badge variant="outline" className="mt-1">
                      <ShieldIcon className="mr-1 size-3" />
                      {user?.role || "user"}
                    </Badge>
                    <Badge variant="secondary" className="mt-1">
                      <CreditCardIcon className="mr-1 size-3" />
                      {getPlanLabel(user?.plan, t)}
                    </Badge>
                  </div>
                </div>

                {user?.plan === "starter" && (
                  <div className="flex items-center justify-between rounded-md p-4" style={{ background: "rgba(132, 204, 22, 0.06)", border: "1px solid rgba(132, 204, 22, 0.2)" }}>
                    <div>
                      <p className="text-sm font-medium">{t("upgrade.title")}</p>
                      <p className="text-xs text-muted-foreground">
                        {t("upgrade.description")}
                      </p>
                    </div>
                    <Link to="/pricing">
                      <Button size="sm">{t("upgrade.viewPlans")}</Button>
                    </Link>
                  </div>
                )}

                {billingSummary?.data && (
                  <Card className="border-[rgba(132,204,22,0.2)] bg-gradient-to-br from-[rgba(132,204,22,0.04)] to-transparent">
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium">{t("usage.title", { defaultValue: "Usage this month" })}</p>
                          <p className="text-xs text-muted-foreground">
                            {t("usage.window", {
                              defaultValue: "Window starts {{date}}",
                              date: new Date(billingSummary.data.trial_window_start).toLocaleDateString(),
                            })}
                          </p>
                        </div>
                        <Badge variant="outline">
                          {getPlanLabel(billingSummary.data.plan, t)}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3 pt-0">
                      {[
                        {
                          label: t("usage.workflow", { defaultValue: "AI drafting workflows" }),
                          used: billingSummary.data.monthly_workflow_used,
                          limit: billingSummary.data.monthly_workflow_limit,
                          remaining: billingSummary.data.monthly_workflow_remaining,
                        },
                        {
                          label: t("usage.assistant", { defaultValue: "Assistant messages" }),
                          used: billingSummary.data.monthly_assistant_used,
                          limit: billingSummary.data.monthly_assistant_limit,
                          remaining: billingSummary.data.monthly_assistant_remaining,
                        },
                        {
                          label: t("usage.indexing", { defaultValue: "Document indexing jobs" }),
                          used: billingSummary.data.monthly_indexing_used,
                          limit: billingSummary.data.monthly_indexing_limit,
                          remaining: billingSummary.data.monthly_indexing_remaining,
                        },
                      ].map((item) => (
                        <div key={item.label} className="flex items-center justify-between gap-4 rounded-md border border-border/60 px-3 py-2">
                          <div>
                            <p className="text-sm font-medium">{item.label}</p>
                            <p className="text-xs text-muted-foreground">
                              {quotaText(t, item.limit, item.remaining)}
                            </p>
                          </div>
                          <p className="text-sm font-semibold tabular-nums">
                            {item.used}
                            {item.limit > 0 ? ` / ${item.limit}` : ""}
                          </p>
                        </div>
                      ))}
                      <div className="rounded-md border border-border/60 px-3 py-3">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="text-sm font-medium">
                              {t("usage.modelMetering", { defaultValue: "Model token metering" })}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {t("usage.modelMeteringDescription", {
                                defaultValue: "Provider-reported tokens only. Monetary cost appears after a reviewed price catalog is configured.",
                              })}
                            </p>
                          </div>
                          <Badge variant="outline">
                            {t("usage.costUnavailable", { defaultValue: "Cost unavailable" })}
                          </Badge>
                        </div>
                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          {[
                            {
                              label: t("usage.officialModel", { defaultValue: "Platform model capacity" }),
                              value: billingSummary.data.official_model_usage,
                            },
                            {
                              label: t("usage.byokModel", { defaultValue: "Your provider key" }),
                              value: billingSummary.data.byok_model_usage,
                            },
                          ].map(({ label, value }) => (
                            <div key={label} className="rounded-md bg-muted/40 px-3 py-2">
                              <div className="flex items-center justify-between gap-3">
                                <p className="text-xs font-medium">{label}</p>
                                <p className="text-xs font-semibold tabular-nums">
                                  {formatTokenCount(value.total_tokens)}
                                </p>
                              </div>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {t("usage.tokenBreakdown", {
                                  defaultValue: "In {{input}} · Out {{output}}",
                                  input: formatTokenCount(value.input_tokens),
                                  output: formatTokenCount(value.output_tokens),
                                })}
                              </p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {value.reserved_tokens > 0
                                  ? t("usage.tokenReserved", {
                                      defaultValue: "{{count}} held for in-flight work",
                                      count: formatTokenCount(value.reserved_tokens),
                                    })
                                  : tokenBudgetText(t, value.remaining_tokens)}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                      <Link to="/pricing">
                        <Button variant="outline" size="sm">
                          {t("upgrade.viewPlans")}
                        </Button>
                      </Link>
                    </CardContent>
                  </Card>
                )}

                {billingSummary?.data && (
                  <Card>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium">{t("billing.title")}</p>
                          <p className="text-xs text-muted-foreground">{t("billing.description")}</p>
                        </div>
                        <Badge variant={billingSummary.data.status === "active" ? "default" : "secondary"}>
                          {t(`billing.status.${billingSummary.data.status}`, { defaultValue: billingSummary.data.status })}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="flex items-center justify-between gap-4 pt-0">
                      <div className="text-sm text-muted-foreground">
                        <p>{t("billing.plan", { plan: getPlanLabel(billingSummary.data.plan, t) })}</p>
                        <p>{t("billing.customer", { status: billingSummary.data.stripe_customer_id ? t("billing.connected") : t("billing.notConnected") })}</p>
                      </div>
                      {billingSummary.data.is_billing_owner && billingSummary.data.stripe_customer_id ? (
                        <Button
                          size="sm"
                          disabled={billingPortalMut.isPending}
                          onClick={() => billingPortalMut.mutate()}
                        >
                          {billingPortalMut.isPending
                            ? t("billing.opening", { defaultValue: "Opening…" })
                            : t("billing.manage")}
                        </Button>
                      ) : billingSummary.data.is_billing_owner ? (
                        <Link to="/pricing">
                          <Button size="sm">{t("billing.manage")}</Button>
                        </Link>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          {t("billing.ownerOnly")}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                )}

                {organizationEntitlements && (
                  <Card>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="text-sm font-medium">{t("workspace.title")}</p>
                          <p className="text-xs text-muted-foreground">{t("workspace.description")}</p>
                        </div>
                        <Badge variant="outline">
                          {getPlanLabel(organizationEntitlements.plan, t)}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-3 pt-0 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-center gap-3">
                        <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                          <UsersRoundIcon className="size-4" />
                        </span>
                        <div>
                          <p className="text-sm font-medium tabular-nums">
                            {t("workspace.seats", {
                              used: organizationEntitlements.active_member_count,
                              limit: organizationEntitlements.seat_limit,
                            })}
                          </p>
                          {organizationEntitlements.seat_overage_count > 0 ? (
                            <p className="text-xs text-destructive">
                              {t("workspace.overCapacity", {
                                count: organizationEntitlements.seat_overage_count,
                              })}
                            </p>
                          ) : (
                            <p className="text-xs text-muted-foreground">
                              {organizationEntitlements.capacity_enforced
                                ? t("workspace.available", { count: organizationEntitlements.available_seats })
                                : t("workspace.compatibility")}
                            </p>
                          )}
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground sm:max-w-56 sm:text-right">
                        {organizationEntitlements.is_billing_owner
                          ? t("workspace.billingOwner")
                          : t("workspace.member")}
                      </p>
                    </CardContent>
                  </Card>
                )}

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="display-name">{t("profile.displayName")}</Label>
                    <Input
                      id="display-name"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder={t("profile.displayNamePlaceholder")}
                    />
                    <p className="text-xs text-muted-foreground">
                      {t("profile.displayNameHelp")}
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">{t("profile.email")}</Label>
                    <div className="flex items-center gap-2">
                      <Input id="email" value={user?.email || ""} disabled />
                      <Badge variant="secondary" className="shrink-0">
                        <MailIcon className="mr-1 size-3" />
                        {t("profile.verified")}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {t("profile.emailHelp")}
                    </p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button
                    onClick={handleUpdateProfile}
                    disabled={
                      displayName === user?.display_name ||
                      !displayName.trim() ||
                      updateMut.isPending
                    }
                  >
                    {updateMut.isPending && <Spinner data-icon="inline-start" />}
                    {t("profile.updateProfile")}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setDisplayName(user?.display_name || "")}
                    disabled={displayName === user?.display_name || updateMut.isPending}
                  >
                    {t("reset")}
                  </Button>
                </div>
              </section>

              <section className="space-y-4">
                <div>
                  <h2 className="text-lg font-medium text-destructive">{t("danger.title")}</h2>
                  <p className="text-sm text-muted-foreground">
                    {t("danger.description")}
                  </p>
                </div>
                <Separator />

                <div className="flex items-center justify-between rounded-md border border-destructive/30 bg-destructive/5 p-4">
                  <div>
                    <p className="text-sm font-medium">{t("danger.signOut")}</p>
                    <p className="text-xs text-muted-foreground">
                      {t("danger.signOutDesc")}
                    </p>
                  </div>
                  <Button variant="destructive" onClick={handleLogout} size="sm" className="gap-2">
                    <LogOutIcon className="size-4" />
                    {t("danger.signOutButton")}
                  </Button>
                </div>
              </section>
            </>
          )}

          {activeSection === "security" && (
            <section className="space-y-4">
              <div>
                <h2 className="text-lg font-medium">{t("security.title")}</h2>
                <p className="text-sm text-muted-foreground">
                  {t("security.description")}
                </p>
              </div>
              <Separator />

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="current-password">{t("security.currentPassword")}</Label>
                  <Input
                    id="current-password"
                    type="password"
                    placeholder={t("security.passwordPlaceholder")}
                    value={currentPw}
                    onChange={(e) => setCurrentPw(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-password">{t("security.newPassword")}</Label>
                  <Input
                    id="new-password"
                    type="password"
                    placeholder={t("security.passwordPlaceholder")}
                    value={newPw}
                    onChange={(e) => setNewPw(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t("security.passwordHint")}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleChangePassword}
                  disabled={!currentPw || !newPw || updateMut.isPending}
                >
                  {updateMut.isPending && <Spinner data-icon="inline-start" />}
                  {t("security.changePassword")}
                </Button>
              </div>
            </section>
          )}

          {activeSection === "notifications" && (
            <section className="space-y-4">
              <div>
                <h2 className="text-lg font-medium">{t("notifications.title")}</h2>
                <p className="text-sm text-muted-foreground">
                  {t("notifications.description")}
                </p>
              </div>
              <Separator />
              <p className="text-sm text-muted-foreground">
                {t("notifications.placeholder")}
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
