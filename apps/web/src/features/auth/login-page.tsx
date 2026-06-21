import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { resendVerification } from "@/lib/api";
import { toast } from "sonner";
import { MailIcon } from "lucide-react";
import { TurnstileWidget, isTurnstileConfigured, resetTurnstile } from "@/components/security/turnstile-widget";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [unverifiedEmail, setUnverifiedEmail] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileWidgetId, setTurnstileWidgetId] = useState<string | null>(null);
  const { login, token } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation("auth");

  const handleResendVerification = async () => {
    if (!unverifiedEmail) return;
    if (isTurnstileConfigured() && !turnstileToken) {
      toast.error(t("turnstile.required"));
      return;
    }
    setResending(true);
    try {
      await resendVerification(token || "", unverifiedEmail, turnstileToken);
      toast.success(t("toast.verificationSent"));
    } catch {
      toast.error(t("toast.verificationResendFailed"));
    } finally {
      resetTurnstile(turnstileWidgetId);
      setTurnstileToken(null);
      setResending(false);
    }
  };

  const handleTurnstileToken = useCallback((value: string | null) => {
    setTurnstileToken(value);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isTurnstileConfigured() && !turnstileToken) {
      toast.error(t("turnstile.required"));
      return;
    }
    setLoading(true);
    setUnverifiedEmail(null);
    try {
      await login(email, password, turnstileToken);
      toast.success(t("toast.loggedIn"));
      navigate("/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("email_not_verified") || msg.includes("not verified")) {
        setUnverifiedEmail(email);
        toast.error(t("toast.emailNotVerified"));
      } else if (msg.includes("Invalid credentials")) {
        toast.error(t("toast.invalidCredentials"));
      } else if (
        msg.includes("Failed to fetch") ||
        msg.includes("NetworkError")
      ) {
        toast.error(t("toast.networkError"));
      } else {
        toast.error(t("toast.loginFailed"));
      }
    } finally {
      resetTurnstile(turnstileWidgetId);
      setTurnstileToken(null);
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex items-center justify-center bg-background px-6">
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

      <div className="relative z-20 w-full max-w-md">
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
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-muted-foreground mb-2"
              >
                {t("login.emailLabel")}
              </label>
              <input
                id="email"
                type="email"
                placeholder={t("login.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-muted-foreground"
                >
                  {t("login.passwordLabel")}
                </label>
                <Link
                  to="/forgot-password"
                  className="text-xs text-muted-foreground hover:text-primary transition-colors duration-300"
                >
                  {t("login.forgotPassword")}
                </Link>
              </div>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
              />
            </div>

            <TurnstileWidget
              action="login"
              onTokenChange={handleTurnstileToken}
              onWidgetIdChange={setTurnstileWidgetId}
              className="min-h-[65px]"
            />

            <button
              type="submit"
              disabled={loading || !email || !password || (isTurnstileConfigured() && !turnstileToken)}
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
                  {t("login.submit")}
                </span>
              ) : (
                t("login.submit")
              )}
            </button>

            {/* 未验证邮箱提示 */}
            {unverifiedEmail && (
              <div className="p-3 text-sm text-amber-400 bg-amber-400/10 border border-amber-400/20">
                <div className="flex items-center gap-2 font-medium mb-1">
                  <MailIcon className="size-4" />
                  {t("unverified.title")}
                </div>
                <p className="mb-2 text-amber-400/80">
                  {t("unverified.description")}
                </p>
                <button
                  type="button"
                  onClick={handleResendVerification}
                  disabled={resending || (isTurnstileConfigured() && !turnstileToken)}
                  className="text-xs font-medium text-amber-400 hover:text-amber-300 transition-colors duration-300 underline underline-offset-2"
                >
                  {resending ? "发送中..." : t("unverified.resend")}
                </button>
              </div>
            )}
          </form>
        </div>

        {/* 底部链接 */}
        <div className="mt-6 text-center">
          <p className="text-sm text-muted-foreground">
            {t("login.noAccount")}{" "}
            <Link
              to="/signup"
              className="text-muted-foreground hover:text-primary transition-colors duration-300"
            >
              {t("login.signUp")}
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
