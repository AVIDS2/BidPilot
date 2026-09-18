import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { EyeIcon, EyeOffIcon, MailIcon } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  InputGroup,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  TurnstileWidget,
  isTurnstileConfigured,
  resetTurnstile,
  type TurnstileWidgetHandle,
} from "@/components/security/turnstile-widget";
import { useAuth } from "@/lib/auth";
import { resendVerification } from "@/lib/api";
import { AuthShell } from "./auth-shell";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [unverifiedEmail, setUnverifiedEmail] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const [turnstileWidgetId, setTurnstileWidgetId] = useState<string | null>(null);
  const turnstileRef = useRef<TurnstileWidgetHandle | null>(null);
  const { login, token } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation("auth");

  const getVerificationToken = async () => {
    const verificationToken = isTurnstileConfigured()
      ? await turnstileRef.current?.execute()
      : null;
    if (isTurnstileConfigured() && !verificationToken) {
      toast.error(t("turnstile.required"));
      return null;
    }
    return verificationToken;
  };

  const handleResendVerification = async () => {
    if (!unverifiedEmail) return;
    setResending(true);
    try {
      const verificationToken = await getVerificationToken();
      if (isTurnstileConfigured() && !verificationToken) return;
      await resendVerification(token || "", unverifiedEmail, verificationToken);
      toast.success(t("toast.verificationSent"));
    } catch {
      toast.error(t("toast.verificationResendFailed"));
    } finally {
      resetTurnstile(turnstileWidgetId);
      setResending(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setUnverifiedEmail(null);
    try {
      const verificationToken = await getVerificationToken();
      if (isTurnstileConfigured() && !verificationToken) return;
      await login(email, password, verificationToken);
      toast.success(t("toast.loggedIn"));
      navigate("/dashboard");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes("email_not_verified") || message.includes("not verified")) {
        setUnverifiedEmail(email);
        toast.error(t("toast.emailNotVerified"));
      } else if (message.includes("Invalid credentials")) {
        toast.error(t("toast.invalidCredentials"));
      } else if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
        toast.error(t("toast.networkError"));
      } else {
        toast.error(t("toast.loginFailed"));
      }
    } finally {
      resetTurnstile(turnstileWidgetId);
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title={t("login.title")}
      description="Sign in to continue working with your bid response workspace."
      footer={
        <p className="text-sm text-muted-foreground">
          {t("login.noAccount")} {" "}
          <Link className="font-medium text-foreground underline-offset-4 hover:underline" to="/signup">
            {t("login.signUp")}
          </Link>
        </p>
      }
    >
      <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
        <FieldGroup className="gap-4">
          <Field>
            <FieldLabel htmlFor="email">{t("login.emailLabel")}</FieldLabel>
            <Input
              id="email"
              type="email"
              placeholder={t("login.emailPlaceholder")}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </Field>

          <Field>
            <div className="flex items-center justify-between gap-3">
              <FieldLabel htmlFor="password">{t("login.passwordLabel")}</FieldLabel>
              <Link
                className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                to="/forgot-password"
              >
                {t("login.forgotPassword")}
              </Link>
            </div>
            <InputGroup className="h-9">
              <InputGroupInput
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
              <InputGroupButton
                aria-label={showPassword ? "Hide characters" : "Show characters"}
                onClick={() => setShowPassword((visible) => !visible)}
                size="icon-sm"
                type="button"
              >
                {showPassword ? <EyeOffIcon aria-hidden="true" /> : <EyeIcon aria-hidden="true" />}
              </InputGroupButton>
            </InputGroup>
          </Field>
        </FieldGroup>

        <TurnstileWidget
          ref={turnstileRef}
          action="login"
          onWidgetIdChange={setTurnstileWidgetId}
          className="min-h-16"
        />

        <Button className="w-full" disabled={loading || !email || !password} type="submit">
          {loading ? <Spinner data-icon="inline-start" /> : null}
          {t("login.submit")}
        </Button>

        {unverifiedEmail ? (
          <Alert className="border-amber-500/40 bg-amber-500/5">
            <MailIcon aria-hidden="true" />
            <AlertTitle>{t("unverified.title")}</AlertTitle>
            <AlertDescription>
              <span>{t("unverified.description")}</span>{" "}
              <Button
                className="h-auto px-0 text-xs font-medium"
                disabled={resending}
                onClick={handleResendVerification}
                size="sm"
                type="button"
                variant="link"
              >
                {resending ? <Spinner data-icon="inline-start" /> : null}
                {t("unverified.resend")}
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}

        <p className="text-center text-xs leading-5 text-muted-foreground">
          {t("login.termsText")} {" "}
          <a className="underline-offset-4 hover:underline" href="#terms">
            {t("login.termsOfService")}
          </a>{" "}
          {t("login.and")} {" "}
          <a className="underline-offset-4 hover:underline" href="#privacy">
            {t("login.privacyPolicy")}
          </a>
          .
        </p>
      </form>
    </AuthShell>
  );
}
