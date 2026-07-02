import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { EyeIcon, EyeOffIcon, Loader2Icon } from "lucide-react";
import { TurnstileWidget, isTurnstileConfigured, resetTurnstile, type TurnstileWidgetHandle } from "@/components/security/turnstile-widget";
import { isStrongPassword } from "@/lib/password";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand";

export function SignupPage() {
  const [searchParams] = useSearchParams();
  const invToken = searchParams.get("invitation") || "";

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [invitationToken, setInvitationToken] = useState(invToken);
  const createOrg = !invitationToken;
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [loading, setLoading] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileWidgetId, setTurnstileWidgetId] = useState<string | null>(null);
  const turnstileRef = useRef<TurnstileWidgetHandle | null>(null);
  const { register } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation("auth");

  const hasInvitation = !!invitationToken;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      toast.error(t("toast.passwordsMismatch"));
      return;
    }
    if (!isStrongPassword(password)) {
      toast.error(t("toast.passwordTooShort"));
      return;
    }
    if (createOrg && !invitationToken) {
      if (!orgName || !orgSlug) {
        toast.error(t("signup.missingOrgFields"));
        return;
      }
    }
    setLoading(true);
    try {
      const verificationToken = isTurnstileConfigured()
        ? await turnstileRef.current?.execute()
        : null;
      if (isTurnstileConfigured() && !verificationToken) {
        toast.error(t("turnstile.required"));
        return;
      }
      await register(
        email,
        displayName,
        password,
        invitationToken || undefined,
        createOrg ? orgName || undefined : undefined,
        createOrg ? orgSlug || undefined : undefined,
        verificationToken,
      );
      toast.success(t("toast.accountCreated"));
      navigate("/verify-email-prompt", { state: { email } });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("Email already registered")) {
        toast.error(t("toast.emailExists"));
      } else if (
        msg.includes("Failed to fetch") ||
        msg.includes("NetworkError")
      ) {
        toast.error(t("toast.registrationNetworkError"));
      } else {
        toast.error(t("toast.registrationGenericError"));
      }
    } finally {
      resetTurnstile(turnstileWidgetId);
      setTurnstileToken(null);
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-background px-6 py-12">
      {/* 影视画框标注 */}
      <div className="absolute inset-0 pointer-events-none z-10">
        <span className="absolute top-6 left-6 text-[10px] text-foreground/20 font-mono">
          BidPilot v1.0
        </span>
        <span className="absolute top-6 right-6 text-[10px] text-foreground/20 font-mono">
          [16:9]
        </span>
        <span className="absolute bottom-6 left-6 text-[10px] text-foreground/20 font-mono">
          OVERSCAN: 1920 x 1080
        </span>
        <span className="absolute bottom-6 right-6 text-[10px] text-foreground/20 font-mono">
          100%
        </span>
      </div>

      {/* 背景纹理 */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(132,204,22,0.03)"/><circle cx="75" cy="75" r="1" fill="rgba(132,204,22,0.03)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>')`,
        }}
      />

      <div className="relative z-20 w-full max-w-lg">
        {/* Logo */}
        <div className="text-center mb-10">
          <Link
            to="/"
            className="inline-flex transition-colors duration-300 hover:text-primary"
          >
            <BrandLogo markClassName="size-10" textClassName="text-3xl" />
          </Link>
          <p className="mt-3 text-sm text-muted-foreground">
            AI-Powered Bid Execution
          </p>
        </div>

        {/* 表单卡片 */}
        <div className="p-8 rounded-xl bg-card border border-border shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* 显示名称 */}
            <div className="space-y-2">
              <label
                htmlFor="display-name"
                className="block text-sm font-medium text-foreground"
              >
                {t("signup.displayNameLabel")}
              </label>
              <Input
                id="display-name"
                type="text"
                placeholder={t("signup.displayNamePlaceholder")}
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                className="h-10"
              />
            </div>

            {/* 邮箱 */}
            <div className="space-y-2">
              <label
                htmlFor="email"
                className="block text-sm font-medium text-foreground"
              >
                {t("signup.emailLabel")}
              </label>
              <Input
                id="email"
                type="email"
                placeholder={t("signup.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-10"
              />
              <p className="text-xs text-muted-foreground">
                {t("signup.emailDescription")}
              </p>
            </div>

            {/* 组织区域 */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-foreground">
                {t("signup.orgLabel")}
              </label>
              <p className="text-xs text-muted-foreground">
                {t("signup.orgDescription")}
              </p>

              {!hasInvitation && (
                <div className="space-y-4 mt-3">
                  <div className="space-y-2">
                    <label
                      htmlFor="org-name"
                      className="block text-xs font-medium text-muted-foreground"
                    >
                      {t("signup.orgNameLabel")}
                    </label>
                    <Input
                      id="org-name"
                      type="text"
                      placeholder={t("signup.orgNamePlaceholder")}
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      required={createOrg}
                      className="h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <label
                      htmlFor="org-slug"
                      className="block text-xs font-medium text-muted-foreground"
                    >
                      {t("signup.orgSlugLabel")}
                    </label>
                    <Input
                      id="org-slug"
                      type="text"
                      placeholder={t("signup.orgSlugPlaceholder")}
                      value={orgSlug}
                      onChange={(e) =>
                        setOrgSlug(
                          e.target.value
                            .replace(/[^a-z0-9-]/g, "")
                            .toLowerCase()
                        )
                      }
                      required={createOrg}
                      className="h-10"
                    />
                    <p className="text-xs text-muted-foreground">
                      {t("signup.orgSlugDescription")}
                    </p>
                  </div>
                </div>
              )}

              {hasInvitation && (
                <div className="p-4 mt-3 rounded-lg bg-muted border border-border space-y-2">
                  <label
                    htmlFor="invitation-token"
                    className="block text-xs font-medium text-muted-foreground"
                  >
                    {t("signup.invitationTokenLabel")}
                  </label>
                  <Input
                    id="invitation-token"
                    type="text"
                    placeholder={t("signup.invitationTokenPlaceholder")}
                    value={invitationToken}
                    onChange={(e) => setInvitationToken(e.target.value)}
                    className="h-10"
                  />
                  <p className="text-xs text-muted-foreground">
                    {t("signup.invitationTokenDescription")}
                  </p>
                </div>
              )}
            </div>

            {/* 密码 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-foreground"
                >
                  {t("signup.passwordLabel")}
                </label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="h-10 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? (
                      <EyeOffIcon className="size-4" />
                    ) : (
                      <EyeIcon className="size-4" />
                    )}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <label
                  htmlFor="confirm-password"
                  className="block text-sm font-medium text-foreground"
                >
                  {t("signup.confirmPasswordLabel")}
                </label>
                <div className="relative">
                  <Input
                    id="confirm-password"
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    className="h-10 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    tabIndex={-1}
                  >
                    {showConfirmPassword ? (
                      <EyeOffIcon className="size-4" />
                    ) : (
                      <EyeIcon className="size-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
            <p className="text-xs text-muted-foreground -mt-2">
              {t("signup.passwordHint")}
            </p>

            <TurnstileWidget
              ref={turnstileRef}
              action="signup"
              onTokenChange={setTurnstileToken}
              onWidgetIdChange={setTurnstileWidgetId}
              className="min-h-[65px]"
            />

            {/* 提交按钮 */}
            <Button
              type="submit"
              disabled={loading || !email || !displayName || !password}
              className="w-full h-10"
            >
              {loading && <Loader2Icon className="animate-spin" />}
              {t("signup.submit")}
            </Button>
          </form>
        </div>

        {/* 底部链接 */}
        <div className="mt-6 text-center">
          <p className="text-sm text-muted-foreground">
            {t("signup.hasAccount")}{" "}
            <Link
              to="/login"
              className="text-foreground hover:text-primary transition-colors duration-300 font-medium"
            >
              {t("signup.signIn")}
            </Link>
          </p>
        </div>

        {/* 条款 */}
        <p className="mt-6 text-center text-xs text-muted-foreground/60">
          {t("login.termsText")}{" "}
          <a
            href="#"
            className="text-muted-foreground hover:text-primary transition-colors duration-300"
          >
            {t("login.termsOfService")}
          </a>{" "}
          {t("login.and")}{" "}
          <a
            href="#"
            className="text-muted-foreground hover:text-primary transition-colors duration-300"
          >
            {t("login.privacyPolicy")}
          </a>
          .
        </p>
      </div>
    </div>
  );
}
