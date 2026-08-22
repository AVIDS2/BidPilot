import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Building2Icon,
  CreditCardIcon,
  KeyRoundIcon,
  LogOutIcon,
  ShieldCheckIcon,
  UserRoundIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  createBillingPortal,
  getBillingSummary,
  getOrganizationEntitlements,
  getNotificationPreferences,
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

function quotaLabel(value: number | null) {
  return value === null ? "不限" : String(value);
}

export function AccountPage() {
  const { user, logout, setUser } = useAuth();
  const navigate = useNavigate();
  const [section, setSection] = useState<AccountSection>("profile");
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const billingQuery = useQuery({ queryKey: ["billing-summary"], queryFn: getBillingSummary, enabled: Boolean(user) });
  const entitlementsQuery = useQuery({ queryKey: ["organization-entitlements"], queryFn: getOrganizationEntitlements, enabled: Boolean(user) });
  const notificationPreferencesQuery = useQuery({ queryKey: ["notification-preferences"], queryFn: getNotificationPreferences, enabled: Boolean(user) });

  useEffect(() => {
    setDisplayName(user?.display_name ?? "");
  }, [user?.display_name]);

  const updateProfileMutation = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: (updated) => {
      setUser(updated);
      toast.success("个人资料已更新。");
    },
    onError: (error) => toast.error(errorText(error, "个人资料未能更新。")),
  });
  const passwordMutation = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast.success("密码已更新。");
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
    onSuccess: () => toast.success("通知偏好已保存。"),
    onError: (error) => toast.error(errorText(error, "通知偏好未能保存。")),
  });

  if (!user) return null;

  const billing = billingQuery.data?.data;
  const entitlements = entitlementsQuery.data;
  const saveProfile = () => {
    const normalized = displayName.trim();
    if (!normalized) return toast.error("显示名称不能为空。");
    updateProfileMutation.mutate({ display_name: normalized });
  };
  const savePassword = () => {
    if (!currentPassword || !newPassword || !confirmPassword) return toast.error("请完整填写密码信息。");
    if (newPassword !== confirmPassword) return toast.error("两次输入的新密码不一致。");
    if (!isStrongPassword(newPassword)) return toast.error("新密码至少 8 位，且包含大写字母、小写字母和数字。");
    passwordMutation.mutate({ current_password: currentPassword, new_password: newPassword });
  };
  const updatePreference = (field: keyof NotificationPreferencesRead, value: boolean) => {
    notificationPreferencesMutation.mutate({ [field]: value });
  };
  const notificationPreferences = notificationPreferencesQuery.data;

  return (
    <section className="wb-settings-page wb-account-settings" aria-labelledby="account-title">
      <SettingsNavigation />
      <main className="wb-settings-main">
      <div className="wb-settings-content">
      <header className="wb-settings-content-head">
        <div>
          <p className="wb-eyebrow">Account & preferences</p>
          <h1 id="account-title">账户与个性化</h1>
          <p>管理个人身份和登录安全。团队协作、权限、模板与模型连接由组织设置统一负责。</p>
        </div>
      </header>

      <Tabs className="wb-account-tabs" onValueChange={(value) => setSection(value as AccountSection)} value={section}>
        <TabsList aria-label="账户设置分区">
          <TabsTrigger value="profile">个人资料</TabsTrigger>
          <TabsTrigger value="notifications">通知</TabsTrigger>
          <TabsTrigger value="security">安全</TabsTrigger>
          <TabsTrigger value="organization">组织与用量</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="wb-account-content">
        {section === "profile" ? <div className="space-y-10">
          <section className="wb-settings-section" aria-labelledby="profile-section-title">
            <div className="mb-6"><h2 className="text-sm font-medium" id="profile-section-title">个人资料</h2><p className="mt-1 text-sm text-muted-foreground">显示名称用于工作区协作、审阅记录和项目活动。</p></div>
            <div className="mb-7 flex items-center gap-3"><span className="grid size-10 place-items-center rounded-lg bg-muted text-sm font-medium">{initials(user.display_name || user.email)}</span><div className="min-w-0"><p className="truncate text-sm font-medium">{user.display_name || "BidPilot 用户"}</p><p className="truncate text-xs text-muted-foreground">{user.email}</p></div><Badge className="ml-auto" variant="outline"><ShieldCheckIcon aria-hidden="true" />{displayWorkbenchValue(user.role)}</Badge></div>
            <FieldGroup className="max-w-lg"><Field><FieldLabel htmlFor="account-display-name">显示名称</FieldLabel><Input id="account-display-name" onChange={(event) => setDisplayName(event.target.value)} value={displayName} /></Field><Field><FieldLabel htmlFor="account-email">邮箱</FieldLabel><Input disabled id="account-email" value={user.email} /><p className="text-xs text-muted-foreground">邮箱由登录身份管理，不能在此页修改。</p></Field></FieldGroup>
            <div className="mt-6 flex items-center gap-2"><Button disabled={updateProfileMutation.isPending || !displayName.trim() || displayName.trim() === user.display_name} onClick={saveProfile} size="sm">保存修改</Button><Button onClick={() => setDisplayName(user.display_name)} size="sm" variant="ghost">撤销</Button></div>
          </section>
          <section className="wb-settings-section" aria-labelledby="memory-section-title">
            <div className="flex items-start gap-3"><div className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted"><UserRoundIcon aria-hidden="true" className="size-4" /></div><div><div className="flex flex-wrap items-center gap-2"><h2 className="text-sm font-medium" id="memory-section-title">个人 Agent 记忆</h2><Badge variant="outline">即将上线</Badge></div><p className="mt-1 max-w-xl text-sm leading-6 text-muted-foreground">个人偏好、常用术语和工作习惯需要由服务端按组织范围持久化并允许随时清除。该能力尚未开放，因此这里不提供无效开关；当前项目资料和已确认的共享知识仍会按权限正常使用。</p></div></div>
          </section>
          <section className="wb-settings-section" aria-labelledby="signout-section-title"><h2 className="text-sm font-medium" id="signout-section-title">当前会话</h2><p className="mt-1 text-sm text-muted-foreground">退出后会从此浏览器移除访问令牌，不影响已经开始的后台处理。</p><Button className="mt-4" onClick={() => { logout(); navigate("/login"); }} size="sm" variant="outline"><LogOutIcon aria-hidden="true" data-icon="inline-start" />退出登录</Button></section>
        </div> : null}

        {section === "security" ? <section className="wb-settings-section" aria-labelledby="security-section-title"><div className="mb-6"><h2 className="text-sm font-medium" id="security-section-title">修改密码</h2><p className="mt-1 text-sm text-muted-foreground">更新后新密码将用于下一次登录，不会终止已经开始的后台任务。</p></div><FieldGroup className="max-w-lg"><Field><FieldLabel htmlFor="account-current-password">当前密码</FieldLabel><Input autoComplete="current-password" id="account-current-password" onChange={(event) => setCurrentPassword(event.target.value)} type="password" value={currentPassword} /></Field><Field><FieldLabel htmlFor="account-new-password">新密码</FieldLabel><Input autoComplete="new-password" id="account-new-password" onChange={(event) => setNewPassword(event.target.value)} type="password" value={newPassword} /><p className="text-xs text-muted-foreground">至少 8 位，包含大写字母、小写字母和数字。</p></Field><Field><FieldLabel htmlFor="account-confirm-password">确认新密码</FieldLabel><Input autoComplete="new-password" id="account-confirm-password" onChange={(event) => setConfirmPassword(event.target.value)} type="password" value={confirmPassword} /></Field></FieldGroup><Button className="mt-6" disabled={passwordMutation.isPending} onClick={savePassword} size="sm"><KeyRoundIcon aria-hidden="true" data-icon="inline-start" />更新密码</Button></section> : null}

        {section === "notifications" ? <section className="wb-settings-section" aria-labelledby="notification-section-title"><div className="mb-6"><h2 className="text-sm font-medium" id="notification-section-title">通知偏好</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">只控制提醒渠道；审核决定、审批状态和项目记录仍会完整保存。邮件服务仅在工作区配置 Resend 或 SMTP 后才会实际发送。</p></div>{notificationPreferencesQuery.isLoading || !notificationPreferences ? <p className="wb-list-loading">正在读取通知偏好…</p> : <div className="max-w-2xl divide-y divide-border rounded-lg border"><PreferenceRow checked={notificationPreferences.in_app_enabled} description="关闭后不再接收站内铃铛提醒。" disabled={notificationPreferencesMutation.isPending} label="站内通知" onCheckedChange={(checked) => updatePreference("in_app_enabled", checked)} /><PreferenceRow checked={notificationPreferences.email_enabled} description="关闭后不再发送已启用类别的邮件提醒。" disabled={notificationPreferencesMutation.isPending} label="邮件通知" onCheckedChange={(checked) => updatePreference("email_enabled", checked)} /><PreferenceRow checked={notificationPreferences.review_updates} description="章节审核、退回修改和需要复核的项目更新。" disabled={notificationPreferencesMutation.isPending} label="审核与交付" onCheckedChange={(checked) => updatePreference("review_updates", checked)} /><PreferenceRow checked={notificationPreferences.agent_updates} description="Agent 后台任务完成、审批或需要恢复时提醒。" disabled={notificationPreferencesMutation.isPending} label="Agent 与工作流" onCheckedChange={(checked) => updatePreference("agent_updates", checked)} /><PreferenceRow checked={notificationPreferences.radar_updates} description="招标雷达命中订阅条件时提醒。" disabled={notificationPreferencesMutation.isPending} label="招标雷达" onCheckedChange={(checked) => updatePreference("radar_updates", checked)} /><PreferenceRow checked={notificationPreferences.material_updates} description="资料解析完成、失败或需要手动处理时提醒。" disabled={notificationPreferencesMutation.isPending} label="资料处理" onCheckedChange={(checked) => updatePreference("material_updates", checked)} /></div>}</section> : null}

        {section === "organization" ? <div className="space-y-10">
          <section className="wb-settings-section" aria-labelledby="organization-section-title"><div className="mb-6 flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-sm font-medium" id="organization-section-title">当前工作区</h2><p className="mt-1 text-sm text-muted-foreground">套餐和资源额度属于整个团队，个人不能在这里修改成员、权限或集成。</p></div>{user.role === "admin" ? <Button onClick={() => navigate("/administration")} size="sm" variant="outline"><Building2Icon aria-hidden="true" data-icon="inline-start" />组织设置</Button> : null}</div>
            {billingQuery.isLoading || entitlementsQuery.isLoading ? <p className="wb-list-loading">正在读取组织用量…</p> : null}
            {billing ? <div className="wb-account-usage-grid"><UsageMeter label="起草工作流" limit={billing.monthly_workflow_limit} used={billing.monthly_workflow_used} /><UsageMeter label="Agent 消息" limit={billing.monthly_assistant_limit} used={billing.monthly_assistant_used} /><UsageMeter label="文档索引" limit={billing.monthly_indexing_limit} used={billing.monthly_indexing_used} /><div className="wb-account-plan"><p>当前套餐</p><strong>{displayWorkbenchValue(billing.plan)}</strong><small>{displayWorkbenchValue(billing.status)}</small>{billing.is_billing_owner ? <Button disabled={billingPortalMutation.isPending} onClick={() => billingPortalMutation.mutate()} size="sm" variant="outline"><CreditCardIcon aria-hidden="true" data-icon="inline-start" />管理套餐</Button> : null}</div></div> : null}
            {entitlements ? <dl className="wb-account-organization-facts"><div><dt>成员席位</dt><dd>{entitlements.active_member_count} / {entitlements.seat_limit}</dd></div><div><dt>项目上限</dt><dd>{entitlements.project_limit}</dd></div><div><dt>订阅状态</dt><dd>{displayWorkbenchValue(entitlements.subscription_status)}</dd></div></dl> : null}
            {!billingQuery.isLoading && !billing ? <Empty className="border-dashed py-10"><EmptyHeader><EmptyMedia variant="icon"><CreditCardIcon aria-hidden="true" /></EmptyMedia><EmptyTitle>暂时无法读取组织用量</EmptyTitle><EmptyDescription>请稍后重试，或联系工作区管理员确认套餐状态。</EmptyDescription></EmptyHeader></Empty> : null}
          </section>
        </div> : null}
      </div>
      </div>
      </main>
    </section>
  );
}

function UsageMeter({ label, limit, used }: { label: string; limit: number; used: number }) {
  const percentage = quotaPercentage(used, limit);
  return <div className="wb-account-usage-meter"><Progress value={percentage}><ProgressLabel>{label}</ProgressLabel><ProgressValue>{() => limit > 0 ? `${used} / ${limit}` : quotaLabel(null)}</ProgressValue></Progress><p>{limit > 0 ? `已使用 ${percentage}%` : "当前套餐不设此项上限"}</p></div>;
}

function PreferenceRow({ checked, description, disabled, label, onCheckedChange }: { checked: boolean; description: string; disabled: boolean; label: string; onCheckedChange: (checked: boolean) => void }) {
  return <label className="flex items-center justify-between gap-6 px-4 py-4"><span><strong className="text-sm font-medium">{label}</strong><small className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</small></span><Switch checked={checked} disabled={disabled} onCheckedChange={onCheckedChange} /></label>;
}
