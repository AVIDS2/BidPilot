import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BellIcon,
  Building2Icon,
  CreditCardIcon,
  KeyRoundIcon,
  LogOutIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  UserRoundIcon,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Avatar, AvatarBadge, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  createBillingPortal,
  getBillingSummary,
  getNotificationPreferences,
  getOrganizationEntitlements,
  updateCurrentUser,
  updateNotificationPreferences,
  type NotificationPreferencesRead,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isStrongPassword } from "@/lib/password";

import { displayWorkbenchValue } from "./workbench-labels";
import { SettingsNavigation } from "./settings-navigation";

type AccountSection = "profile" | "notifications" | "security" | "organization";

function initials(value: string) {
  return value.trim().slice(0, 2).toUpperCase() || "BP";
}

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function quotaPercentage(used: number, limit: number) {
  if (limit <= 0) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

function AccountUsageSkeleton() {
  return (
    <div className="grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-2">
      {Array.from({ length: 4 }).map((_, index) => (
        <div className="flex min-h-28 flex-col justify-center gap-3 bg-card px-4 py-4" key={index}>
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-1.5 w-full" />
          <Skeleton className="h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

function AccountQueryEmpty({
  icon: Icon,
  title,
  description,
  onRetry,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  onRetry: () => void;
}) {
  return (
    <Empty className="border-dashed py-10">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon aria-hidden="true" />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      <ButtonWithRefresh onClick={onRetry} />
    </Empty>
  );
}

export function AccountPage() {
  const { user, logout, setUser } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [section, setSection] = useState<AccountSection>("profile");
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const billingQuery = useQuery({
    queryKey: ["billing-summary", user?.id],
    queryFn: getBillingSummary,
    enabled: Boolean(user),
  });
  const entitlementsQuery = useQuery({
    queryKey: ["organization-entitlements", user?.org_id],
    queryFn: getOrganizationEntitlements,
    enabled: Boolean(user),
  });
  const notificationPreferencesQuery = useQuery({
    queryKey: ["notification-preferences", user?.id],
    queryFn: getNotificationPreferences,
    enabled: Boolean(user),
  });

  useEffect(() => {
    setDisplayName(user?.display_name ?? "");
  }, [user?.display_name]);

  const updateProfileMutation = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: (updated) => {
      setUser(updated);
      toast.success("个人资料已更新。 ");
    },
    onError: (error) => toast.error(errorText(error, "个人资料未能更新。")),
  });
  const passwordMutation = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast.success("密码已更新。 ");
    },
    onError: (error) => toast.error(errorText(error, "密码未能更新。")),
  });
  const billingPortalMutation = useMutation({
    mutationFn: createBillingPortal,
    onSuccess: (result) => window.location.assign(result.url),
    onError: () => toast.error("暂时无法打开套餐管理。"),
  });
  const notificationPreferencesMutation = useMutation({
    mutationFn: updateNotificationPreferences,
    onSuccess: (updated) => {
      queryClient.setQueryData(
        ["notification-preferences", user?.id],
        updated,
      );
      toast.success("通知偏好已保存。 ");
    },
    onError: (error) => toast.error(errorText(error, "通知偏好未能保存。")),
  });

  if (!user) return null;

  const billing = billingQuery.data?.data;
  const entitlements = entitlementsQuery.data;
  const notificationPreferences = notificationPreferencesQuery.data;
  const saveProfile = () => {
    const normalized = displayName.trim();
    if (!normalized) return toast.error("显示名称不能为空。 ");
    updateProfileMutation.mutate({ display_name: normalized });
  };
  const savePassword = () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      return toast.error("请完整填写密码信息。 ");
    }
    if (newPassword !== confirmPassword) {
      return toast.error("两次输入的新密码不一致。 ");
    }
    if (!isStrongPassword(newPassword)) {
      return toast.error("新密码至少 8 位，且包含大写字母、小写字母和数字。 ");
    }
    passwordMutation.mutate({ current_password: currentPassword, new_password: newPassword });
  };
  const updatePreference = (field: keyof NotificationPreferencesRead, value: boolean) => {
    notificationPreferencesMutation.mutate({ [field]: value });
  };

  return (
    <section className="wb-settings-page wb-account-settings" aria-labelledby="account-title" data-testid="account-page">
      <SettingsNavigation />
      <main className="wb-settings-main">
        <div className="wb-settings-content">
          <header className="wb-settings-content-head">
            <div>
              <p className="wb-eyebrow">Personal settings</p>
              <h1 id="account-title">账户与个性化</h1>
              <p>管理个人身份和登录安全。团队协作、权限、模板与模型连接由组织设置统一负责。</p>
            </div>
          </header>

          <Tabs
            className="wb-account-tabs"
            onValueChange={(value) => setSection(value as AccountSection)}
            value={section}
          >
            <TabsList aria-label="账户设置分区" variant="line">
              <TabsTrigger value="profile">个人资料</TabsTrigger>
              <TabsTrigger value="notifications">通知</TabsTrigger>
              <TabsTrigger value="security">安全</TabsTrigger>
              <TabsTrigger value="organization">组织与用量</TabsTrigger>
            </TabsList>

            <TabsContent className="wb-account-tab-content" value="profile">
              <div className="flex flex-col gap-4">
                <Card data-testid="account-profile-card" size="sm">
                  <CardHeader className="border-b">
                    <div>
                      <CardTitle>个人资料</CardTitle>
                      <CardDescription>显示名称用于工作区协作、审阅记录和项目活动。</CardDescription>
                    </div>
                    <CardAction>
                      <Badge variant="outline">
                        <ShieldCheckIcon aria-hidden="true" data-icon="inline-start" />
                        {displayWorkbenchValue(user.role)}
                      </Badge>
                    </CardAction>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-6">
                    <div className="flex flex-wrap items-center gap-3">
                      <Avatar size="lg">
                        <AvatarFallback>{initials(user.display_name || user.email)}</AvatarFallback>
                        <AvatarBadge aria-label="已验证身份">
                          <ShieldCheckIcon aria-hidden="true" />
                        </AvatarBadge>
                      </Avatar>
                      <div className="grid min-w-0 gap-1">
                        <p className="truncate text-sm font-medium">{user.display_name || "BidPilot 用户"}</p>
                        <p className="truncate text-xs text-muted-foreground">{user.email}</p>
                        <Badge className="mt-1 w-fit" variant="secondary">
                          <CreditCardIcon aria-hidden="true" data-icon="inline-start" />
                          {displayWorkbenchValue(user.plan)}
                        </Badge>
                      </div>
                    </div>
                    <Separator />
                    <FieldGroup className="wb-account-form">
                      <Field>
                        <FieldLabel htmlFor="account-display-name">显示名称</FieldLabel>
                        <Input
                          id="account-display-name"
                          onChange={(event) => setDisplayName(event.target.value)}
                          value={displayName}
                        />
                        <FieldDescription>这个名称会显示在工作区活动和审阅记录中。</FieldDescription>
                      </Field>
                      <Field>
                        <FieldLabel htmlFor="account-email">邮箱</FieldLabel>
                        <Input disabled id="account-email" value={user.email} />
                        <FieldDescription>邮箱由登录身份管理，不能在此页修改。</FieldDescription>
                      </Field>
                    </FieldGroup>
                  </CardContent>
                  <CardFooter className="justify-end gap-2">
                    <Button onClick={() => setDisplayName(user.display_name)} size="sm" variant="ghost">
                      撤销
                    </Button>
                    <Button
                      disabled={updateProfileMutation.isPending || !displayName.trim() || displayName.trim() === user.display_name}
                      onClick={saveProfile}
                      size="sm"
                    >
                      {updateProfileMutation.isPending ? <Spinner data-icon="inline-start" /> : null}
                      保存修改
                    </Button>
                  </CardFooter>
                </Card>

                <Card className="border-dashed" size="sm">
                  <CardHeader>
                    <div className="flex items-start gap-3">
                      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
                        <UserRoundIcon aria-hidden="true" />
                      </span>
                      <div>
                        <CardTitle>个人 Agent 记忆</CardTitle>
                        <CardDescription>个人偏好、常用术语和工作习惯将由服务端按组织范围管理。</CardDescription>
                      </div>
                    </div>
                    <CardAction>
                      <Badge variant="outline">即将上线</Badge>
                    </CardAction>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs leading-5 text-muted-foreground">当前不提供无效开关；项目资料和已确认的共享知识仍会按权限正常使用。</p>
                  </CardContent>
                </Card>

                <Card className="border-destructive/20" size="sm">
                  <CardHeader>
                    <CardTitle>当前会话</CardTitle>
                    <CardDescription>退出后会从此浏览器移除访问令牌，不影响已经开始的后台处理。</CardDescription>
                  </CardHeader>
                  <CardFooter>
                    <Button
                      onClick={() => {
                        logout();
                        navigate("/login");
                      }}
                      size="sm"
                      variant="outline"
                    >
                      <LogOutIcon aria-hidden="true" data-icon="inline-start" />
                      退出登录
                    </Button>
                  </CardFooter>
                </Card>
              </div>
            </TabsContent>

            <TabsContent className="wb-account-tab-content" value="security">
              <Card size="sm">
                <CardHeader className="border-b">
                  <div>
                    <CardTitle>修改密码</CardTitle>
                    <CardDescription>更新后新密码将用于下一次登录，不会终止已经开始的后台任务。</CardDescription>
                  </div>
                  <CardAction>
                    <Badge variant="outline">
                      <KeyRoundIcon aria-hidden="true" data-icon="inline-start" />
                      登录安全
                    </Badge>
                  </CardAction>
                </CardHeader>
                <CardContent>
                  <FieldGroup className="wb-account-form">
                    <Field>
                      <FieldLabel htmlFor="account-current-password">当前密码</FieldLabel>
                      <Input
                        autoComplete="current-password"
                        id="account-current-password"
                        onChange={(event) => setCurrentPassword(event.target.value)}
                        type="password"
                        value={currentPassword}
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="account-new-password">新密码</FieldLabel>
                      <Input
                        autoComplete="new-password"
                        id="account-new-password"
                        onChange={(event) => setNewPassword(event.target.value)}
                        type="password"
                        value={newPassword}
                      />
                      <FieldDescription>至少 8 位，包含大写字母、小写字母和数字。</FieldDescription>
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="account-confirm-password">确认新密码</FieldLabel>
                      <Input
                        autoComplete="new-password"
                        id="account-confirm-password"
                        onChange={(event) => setConfirmPassword(event.target.value)}
                        type="password"
                        value={confirmPassword}
                      />
                    </Field>
                  </FieldGroup>
                </CardContent>
                <CardFooter className="justify-end">
                  <Button disabled={passwordMutation.isPending} onClick={savePassword} size="sm">
                    {passwordMutation.isPending ? <Spinner data-icon="inline-start" /> : <KeyRoundIcon aria-hidden="true" data-icon="inline-start" />}
                    更新密码
                  </Button>
                </CardFooter>
              </Card>
            </TabsContent>

            <TabsContent className="wb-account-tab-content" value="notifications">
              <Card size="sm">
                <CardHeader className="border-b">
                  <div>
                    <CardTitle>通知偏好</CardTitle>
                    <CardDescription>只控制提醒渠道；审核决定、审批状态和项目记录仍会完整保存。</CardDescription>
                  </div>
                  <CardAction>
                    <Badge variant="outline">
                      <BellIcon aria-hidden="true" data-icon="inline-start" />
                      提醒渠道
                    </Badge>
                  </CardAction>
                </CardHeader>
                <CardContent className="p-0">
                  {notificationPreferencesQuery.isPending ? (
                    <div className="flex flex-col gap-3 p-4" role="status" aria-label="正在读取通知偏好">
                      {Array.from({ length: 4 }).map((_, index) => (
                        <div className="flex items-center justify-between gap-5 border-b py-3 last:border-0" key={index}>
                          <div className="grid min-w-0 flex-1 gap-2">
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-3 w-64 max-w-full" />
                          </div>
                          <Skeleton className="h-5 w-8 rounded-full" />
                        </div>
                      ))}
                    </div>
                  ) : notificationPreferencesQuery.isError ? (
                    <AccountQueryEmpty
                      description="通知设置暂时无法读取，稍后可以重新加载。"
                      icon={BellIcon}
                      onRetry={() => void notificationPreferencesQuery.refetch()}
                      title="通知设置暂时不可用"
                    />
                  ) : notificationPreferences ? (
                    <div className="divide-y">
                      <PreferenceRow checked={notificationPreferences.in_app_enabled} description="关闭后不再接收站内铃铛提醒。" disabled={notificationPreferencesMutation.isPending} label="站内通知" name="in_app_enabled" onCheckedChange={(checked) => updatePreference("in_app_enabled", checked)} />
                      <PreferenceRow checked={notificationPreferences.email_enabled} description="关闭后不再发送已启用类别的邮件提醒。" disabled={notificationPreferencesMutation.isPending} label="邮件通知" name="email_enabled" onCheckedChange={(checked) => updatePreference("email_enabled", checked)} />
                      <PreferenceRow checked={notificationPreferences.review_updates} description="章节审核、退回修改和需要复核的项目更新。" disabled={notificationPreferencesMutation.isPending} label="审核与交付" name="review_updates" onCheckedChange={(checked) => updatePreference("review_updates", checked)} />
                      <PreferenceRow checked={notificationPreferences.agent_updates} description="Agent 后台任务完成、审批或需要恢复时提醒。" disabled={notificationPreferencesMutation.isPending} label="Agent 与工作流" name="agent_updates" onCheckedChange={(checked) => updatePreference("agent_updates", checked)} />
                      <PreferenceRow checked={notificationPreferences.radar_updates} description="招标雷达命中订阅条件时提醒。" disabled={notificationPreferencesMutation.isPending} label="招标雷达" name="radar_updates" onCheckedChange={(checked) => updatePreference("radar_updates", checked)} />
                      <PreferenceRow checked={notificationPreferences.material_updates} description="资料解析完成、失败或需要手动处理时提醒。" disabled={notificationPreferencesMutation.isPending} label="资料处理" name="material_updates" onCheckedChange={(checked) => updatePreference("material_updates", checked)} />
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent className="wb-account-tab-content" value="organization">
              <Card size="sm">
                <CardHeader className="border-b">
                  <div>
                    <CardTitle>当前工作区</CardTitle>
                    <CardDescription>套餐和资源额度属于整个团队，成员不能在这里修改组织权限或集成。</CardDescription>
                  </div>
                  {user.role === "admin" ? (
                    <CardAction>
                      <Button onClick={() => navigate("/administration")} size="sm" variant="outline">
                        <Building2Icon aria-hidden="true" data-icon="inline-start" />
                        组织设置
                      </Button>
                    </CardAction>
                  ) : null}
                </CardHeader>
                <CardContent className="flex flex-col gap-6">
                  {billingQuery.isPending || entitlementsQuery.isPending ? <AccountUsageSkeleton /> : null}
                  {!billingQuery.isPending && billingQuery.isError ? (
                    <AccountQueryEmpty
                      description="套餐和额度暂时无法读取，稍后可以重新加载。"
                      icon={CreditCardIcon}
                      onRetry={() => {
                        void billingQuery.refetch();
                        void entitlementsQuery.refetch();
                      }}
                      title="组织用量暂时不可用"
                    />
                  ) : null}
                  {!billingQuery.isPending && !billingQuery.isError && billing ? (
                    <>
                      <div className="wb-account-usage-grid">
                        <UsageMeter label="起草工作流" limit={billing.monthly_workflow_limit} used={billing.monthly_workflow_used} />
                        <UsageMeter label="Agent 消息" limit={billing.monthly_assistant_limit} used={billing.monthly_assistant_used} />
                        <UsageMeter label="文档索引" limit={billing.monthly_indexing_limit} used={billing.monthly_indexing_used} />
                        <div className="wb-account-plan">
                          <div className="flex items-center justify-between gap-3">
                            <span>当前套餐</span>
                            <Badge variant="secondary">{displayWorkbenchValue(billing.plan)}</Badge>
                          </div>
                          <strong>{displayWorkbenchValue(billing.status)}</strong>
                          {billing.is_billing_owner ? (
                            <Button
                              className="w-fit"
                              disabled={billingPortalMutation.isPending}
                              onClick={() => billingPortalMutation.mutate()}
                              size="sm"
                              variant="outline"
                            >
                              {billingPortalMutation.isPending ? <Spinner data-icon="inline-start" /> : <CreditCardIcon aria-hidden="true" data-icon="inline-start" />}
                              管理套餐
                            </Button>
                          ) : null}
                        </div>
                      </div>
                      {entitlements ? (
                        <dl className="wb-account-organization-facts">
                          <div><dt>成员席位</dt><dd>{entitlements.active_member_count} / {entitlements.seat_limit}</dd></div>
                          <div><dt>项目上限</dt><dd>{entitlements.project_limit}</dd></div>
                          <div><dt>订阅状态</dt><dd>{displayWorkbenchValue(entitlements.subscription_status)}</dd></div>
                        </dl>
                      ) : null}
                    </>
                  ) : null}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </section>
  );
}

function ButtonWithRefresh({ onClick }: { onClick: () => void }) {
  return (
    <Button onClick={onClick} size="sm" variant="outline">
      <RefreshCwIcon aria-hidden="true" data-icon="inline-start" />
      重新读取
    </Button>
  );
}

function UsageMeter({ label, limit, used }: { label: string; limit: number; used: number }) {
  const percentage = quotaPercentage(used, limit);
  return (
    <div className="wb-account-usage-meter">
      <div className="flex items-center justify-between gap-3">
        <span>{label}</span>
        <strong>{limit > 0 ? `${used} / ${limit}` : "不限"}</strong>
      </div>
      <Progress aria-label={label} value={percentage} />
      <p>{limit > 0 ? `已使用 ${percentage}%` : "当前套餐不设此项上限"}</p>
    </div>
  );
}

function PreferenceRow({
  checked,
  description,
  disabled,
  label,
  name,
  onCheckedChange,
}: {
  checked: boolean;
  description: string;
  disabled: boolean;
  label: string;
  name: string;
  onCheckedChange: (checked: boolean) => void;
}) {
  const descriptionId = `${name}-description`;
  return (
    <Field className="wb-account-preference-row" data-disabled={disabled || undefined} orientation="horizontal">
      <FieldContent>
        <FieldLabel htmlFor={name}>{label}</FieldLabel>
        <FieldDescription id={descriptionId}>{description}</FieldDescription>
      </FieldContent>
      <Switch
        aria-describedby={descriptionId}
        checked={checked}
        disabled={disabled}
        id={name}
        onCheckedChange={onCheckedChange}
      />
    </Field>
  );
}
