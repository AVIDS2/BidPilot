import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";

export function SignupPage() {
  const [searchParams] = useSearchParams();
  const invToken = searchParams.get("invitation") || "";

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [invitationToken, setInvitationToken] = useState(invToken);
  const createOrg = !invitationToken;
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [loading, setLoading] = useState(false);
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
    if (password.length < 8) {
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
      await register(
        email,
        displayName,
        password,
        invitationToken || undefined,
        createOrg ? orgName || undefined : undefined,
        createOrg ? orgSlug || undefined : undefined
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
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6 py-12">
      {/* 影视画框标注 */}
      <div className="absolute inset-0 pointer-events-none z-10">
        <span className="absolute top-6 left-6 text-[10px] text-white/30 font-mono">
          DocPilot v1.0
        </span>
        <span className="absolute top-6 right-6 text-[10px] text-white/30 font-mono">
          [16:9]
        </span>
        <span className="absolute bottom-6 left-6 text-[10px] text-white/30 font-mono">
          OVERSCAN: 1920 x 1080
        </span>
        <span className="absolute bottom-6 right-6 text-[10px] text-white/30 font-mono">
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
            className="text-3xl font-medium tracking-[-0.04em] text-white hover:text-primary transition-colors duration-300"
          >
            DocPilot
          </Link>
          <p className="mt-3 text-sm text-muted-foreground">
            AI-Powered Document Execution
          </p>
        </div>

        {/* 表单卡片 */}
        <div
          className="p-8"
          style={{
            background: "var(--landing-surface-1)",
            border: "1px solid var(--landing-hairline)",
          }}
        >
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* 显示名称 */}
            <div>
              <label
                htmlFor="display-name"
                className="block text-sm font-medium text-muted-foreground mb-2"
              >
                {t("signup.displayNameLabel")}
              </label>
              <input
                id="display-name"
                type="text"
                placeholder={t("signup.displayNamePlaceholder")}
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
              />
            </div>

            {/* 邮箱 */}
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-muted-foreground mb-2"
              >
                {t("signup.emailLabel")}
              </label>
              <input
                id="email"
                type="email"
                placeholder={t("signup.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
              />
              <p className="mt-1.5 text-xs text-muted-foreground">
                {t("signup.emailDescription")}
              </p>
            </div>

            {/* 组织区域 */}
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-2">
                {t("signup.orgLabel")}
              </label>
              <p className="mb-3 text-xs text-muted-foreground">
                {t("signup.orgDescription")}
              </p>

              {!hasInvitation && (
                <div className="space-y-4">
                  <div>
                    <label
                      htmlFor="org-name"
                      className="block text-xs font-medium text-muted-foreground mb-1.5"
                    >
                      {t("signup.orgNameLabel")}
                    </label>
                    <input
                      id="org-name"
                      type="text"
                      placeholder={t("signup.orgNamePlaceholder")}
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      required={createOrg}
                      className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="org-slug"
                      className="block text-xs font-medium text-muted-foreground mb-1.5"
                    >
                      {t("signup.orgSlugLabel")}
                    </label>
                    <input
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
                      className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
                    />
                    <p className="mt-1.5 text-xs text-muted-foreground">
                      {t("signup.orgSlugDescription")}
                    </p>
                  </div>
                </div>
              )}

              {hasInvitation && (
                <div className="p-3 bg-muted border border-border">
                  <label
                    htmlFor="invitation-token"
                    className="block text-xs font-medium text-muted-foreground mb-1.5"
                  >
                    {t("signup.invitationTokenLabel")}
                  </label>
                  <input
                    id="invitation-token"
                    type="text"
                    placeholder={t("signup.invitationTokenPlaceholder")}
                    value={invitationToken}
                    onChange={(e) => setInvitationToken(e.target.value)}
                    className="w-full px-4 py-3 text-sm text-white bg-background border border-border outline-none focus:border-primary transition-colors duration-300"
                  />
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    {t("signup.invitationTokenDescription")}
                  </p>
                </div>
              )}
            </div>

            {/* 密码 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-muted-foreground mb-2"
                >
                  {t("signup.passwordLabel")}
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
                />
              </div>
              <div>
                <label
                  htmlFor="confirm-password"
                  className="block text-sm font-medium text-muted-foreground mb-2"
                >
                  {t("signup.confirmPasswordLabel")}
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground -mt-2">
              {t("signup.passwordHint")}
            </p>

            {/* 提交按钮 */}
            <button
              type="submit"
              disabled={loading || !email || !displayName || !password}
              className="w-full py-3.5 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <svg
                    className="animate-spin h-4 w-4"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  {t("signup.submit")}
                </span>
              ) : (
                t("signup.submit")
              )}
            </button>
          </form>
        </div>

        {/* 底部链接 */}
        <div className="mt-6 text-center">
          <p className="text-sm text-muted-foreground">
            {t("signup.hasAccount")}{" "}
            <Link
              to="/login"
              className="text-muted-foreground hover:text-primary transition-colors duration-300"
            >
              {t("signup.signIn")}
            </Link>
          </p>
        </div>

        {/* 条款 */}
        <p className="mt-6 text-center text-xs text-muted-foreground">
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
