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
import { UserIcon, ShieldIcon, BellIcon, KeyIcon, LogOutIcon, MailIcon, CreditCardIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { updateCurrentUser, updateSubscription } from "@/lib/api"
import { toast } from "sonner"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const PLAN_LABELS: Record<string, string> = {
  starter: "Starter (Free)",
  professional: "Professional",
  enterprise: "Enterprise",
};

const sidebarNavItems = [
  { title: "Profile", href: "profile", icon: UserIcon },
  { title: "Security", href: "security", icon: KeyIcon },
  { title: "Notifications", href: "notifications", icon: BellIcon },
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

export function AccountPage() {
  const { user, logout, setUser } = useAuth()
  const navigate = useNavigate()
  const [activeSection, setActiveSection] = useState("profile")
  const [displayName, setDisplayName] = useState(user?.display_name || "")
  const [currentPw, setCurrentPw] = useState("")
  const [newPw, setNewPw] = useState("")

  const updateMut = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: (updated) => {
      setUser(updated)
      toast.success("Profile updated")
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes("Display name cannot be empty")) {
        toast.error("Display name cannot be empty")
      } else if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
        toast.error("Cannot connect to server")
      } else {
        toast.error("Update failed. Please try again.")
      }
    },
  })

  const handleLogout = () => {
    logout()
    navigate("/login")
  }

  const handleUpdateProfile = () => {
    updateMut.mutate({ display_name: displayName.trim() })
  }

  const initials = (user?.display_name || "U").charAt(0).toUpperCase()

  if (!user) return <AccountPageSkeleton />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account settings and preferences.
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
                  className={cn(
                    "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                  )}
                >
                  <Icon className="size-4" />
                  {item.title}
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
                  <h2 className="text-lg font-medium">Profile</h2>
                  <p className="text-sm text-muted-foreground">
                    This is how others will see you on the platform.
                  </p>
                </div>
                <Separator />

                <div className="flex items-center gap-4">
                  <Avatar className="size-16">
                    <AvatarFallback className="text-xl">{initials}</AvatarFallback>
                  </Avatar>
                  <div className="space-y-1">
                    <p className="text-sm font-medium leading-none">{user?.display_name || "User"}</p>
                    <p className="text-xs text-muted-foreground">{user?.email || ""}</p>
                    <Badge variant="outline" className="mt-1">
                      <ShieldIcon className="mr-1 size-3" />
                      {user?.role || "user"}
                    </Badge>
                    <Badge variant="secondary" className="mt-1">
                      <CreditCardIcon className="mr-1 size-3" />
                      {PLAN_LABELS[user?.plan ?? "starter"] ?? "Starter (Free)"}
                    </Badge>
                  </div>
                </div>

                {user?.plan === "starter" && (
                  <div className="flex items-center justify-between rounded-md border border-primary/30 bg-primary/5 p-4">
                    <div>
                      <p className="text-sm font-medium">Upgrade to Professional</p>
                      <p className="text-xs text-muted-foreground">
                        Unlimited projects, all scenario packages, and priority support.
                      </p>
                    </div>
                    <Link to="/pricing">
                      <Button size="sm">View Plans</Button>
                    </Link>
                  </div>
                )}

                {user?.role === "admin" && (
                  <div className="rounded-md border bg-muted/30 p-4 space-y-3">
                    <div>
                      <p className="text-sm font-medium">Admin: Change Plan</p>
                      <p className="text-xs text-muted-foreground">
                        Manually update your subscription plan.
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <Select
                        value={user?.plan ?? "starter"}
                        onValueChange={(newPlan) => {
                          if (user && newPlan) {
                            updateSubscription({ user_id: user.id ?? "", plan: newPlan })
                              .then(() => {
                                toast.success(`Plan updated to ${newPlan}`);
                                window.location.reload();
                              })
                              .catch(() => toast.error("Failed to update plan"));
                          }
                        }}
                      >
                        <SelectTrigger className="w-48">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="starter">Starter</SelectItem>
                          <SelectItem value="professional">Professional</SelectItem>
                          <SelectItem value="enterprise">Enterprise</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="display-name">Display Name</Label>
                    <Input
                      id="display-name"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="Your name"
                    />
                    <p className="text-xs text-muted-foreground">
                      This is your public display name.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <div className="flex items-center gap-2">
                      <Input id="email" value={user?.email || ""} disabled />
                      <Badge variant="secondary" className="shrink-0">
                        <MailIcon className="mr-1 size-3" />
                        Verified
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Your primary email address.
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
                    Update Profile
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setDisplayName(user?.display_name || "")}
                    disabled={displayName === user?.display_name || updateMut.isPending}
                  >
                    Reset
                  </Button>
                </div>
              </section>

              <section className="space-y-4">
                <div>
                  <h2 className="text-lg font-medium text-destructive">Danger Zone</h2>
                  <p className="text-sm text-muted-foreground">
                    Irreversible actions for your account.
                  </p>
                </div>
                <Separator />

                <div className="flex items-center justify-between rounded-md border border-destructive/30 bg-destructive/5 p-4">
                  <div>
                    <p className="text-sm font-medium">Sign Out</p>
                    <p className="text-xs text-muted-foreground">
                      Sign out of your account on this device.
                    </p>
                  </div>
                  <Button variant="destructive" onClick={handleLogout} size="sm" className="gap-2">
                    <LogOutIcon className="size-4" />
                    Sign Out
                  </Button>
                </div>
              </section>
            </>
          )}

          {activeSection === "security" && (
            <section className="space-y-4">
              <div>
                <h2 className="text-lg font-medium">Security</h2>
                <p className="text-sm text-muted-foreground">
                  Manage your password and authentication settings.
                </p>
              </div>
              <Separator />

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="current-password">Current Password</Label>
                  <Input
                    id="current-password"
                    type="password"
                    placeholder="••••••••"
                    value={currentPw}
                    onChange={(e) => setCurrentPw(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-password">New Password</Label>
                  <Input
                    id="new-password"
                    type="password"
                    placeholder="••••••••"
                    value={newPw}
                    onChange={(e) => setNewPw(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    At least 8 characters with uppercase, lowercase, and a digit.
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={() => {
                    updateMut.mutate(
                      { current_password: currentPw, new_password: newPw },
                      {
                        onSuccess: () => {
                          toast.success("Password changed successfully");
                          setCurrentPw("");
                          setNewPw("");
                        },
                        onError: (err: unknown) => {
                          const msg = err instanceof Error ? err.message : String(err);
                          toast.error(msg.includes("incorrect") ? "Current password is incorrect" : "Failed to change password");
                        },
                      },
                    );
                  }}
                  disabled={!currentPw || !newPw || updateMut.isPending}
                >
                  {updateMut.isPending && <Spinner data-icon="inline-start" />}
                  Change Password
                </Button>
              </div>
            </section>
          )}

          {activeSection === "notifications" && (
            <section className="space-y-4">
              <div>
                <h2 className="text-lg font-medium">Notifications</h2>
                <p className="text-sm text-muted-foreground">
                  Configure how you receive notifications.
                </p>
              </div>
              <Separator />
              <p className="text-sm text-muted-foreground">
                Notification settings will be available in a future release.
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
