import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { resendVerification } from "@/lib/api";
import { toast } from "sonner";
import { EyeIcon, EyeOffIcon, Loader2Icon, MailIcon } from "lucide-react";
import { TurnstileWidget, isTurnstileConfigured, resetTurnstile } from "@/components/security/turnstile-widget";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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

      <div className="relative z-20 w-full max-w-md">
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
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label
                htmlFor="email"
                className="block text-sm font-medium text-foreground"
              >
                {t("login.emailLabel")}
              </label>
              <Input
                id="email"
                type="email"
                placeholder={t("login.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-10"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-foreground"
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

            <TurnstileWidget
              action="login"
              onTokenChange={handleTurnstileToken}
              onWidgetIdChange={setTurnstileWidgetId}
              className="min-h-[65px]"
            />

            <Button
              type="submit"
              disabled={loading || !email || !password || (isTurnstileConfigured() && !turnstileToken)}
              className="w-full h-10"
            >
              {loading && <Loader2Icon className="animate-spin" />}
              {t("login.submit")}
            </Button>

            {/* 未验证邮箱提示 */}
            {unverifiedEmail && (
              <div className="p-4 rounded-lg text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-400/10 border border-amber-200 dark:border-amber-400/20">
                <div className="flex items-center gap-2 font-medium mb-1">
                  <MailIcon className="size-4" />
                  {t("unverified.title")}
                </div>
                <p className="mb-2 text-amber-600/80 dark:text-amber-400/80">
                  {t("unverified.description")}
                </p>
                <button
                  type="button"
                  onClick={handleResendVerification}
                  disabled={resending || (isTurnstileConfigured() && !turnstileToken)}
                  className="text-xs font-medium text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 transition-colors duration-300 underline underline-offset-2"
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
              className="text-foreground hover:text-primary transition-colors duration-300 font-medium"
            >
              {t("login.signUp")}
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
