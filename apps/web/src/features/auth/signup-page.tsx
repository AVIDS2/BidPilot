import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { EyeIcon, EyeOffIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import {
  InputGroup,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import {
  TurnstileWidget,
  isTurnstileConfigured,
  resetTurnstile,
  type TurnstileWidgetHandle,
} from "@/components/security/turnstile-widget";
import { isStrongPassword } from "@/lib/password";
import { useAuth } from "@/lib/auth";
import { AuthShell } from "./auth-shell";
import { getRegistrationErrorKey } from "./registration-errors";
import { readRegistrationDraft, saveRegistrationDraft } from "./registration-draft";

export function SignupPage() {
  const [searchParams] = useSearchParams();
  const invitationFromUrl = searchParams.get("invitation") || "";
  const savedDraft = readRegistrationDraft();
  const [email, setEmail] = useState(savedDraft?.email ?? "");
  const [displayName, setDisplayName] = useState(savedDraft?.displayName ?? "");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [invitationToken, setInvitationToken] = useState(
    invitationFromUrl || savedDraft?.invitationToken || "",
  );
  const [orgName, setOrgName] = useState(savedDraft?.orgName ?? "");
  const [orgSlug, setOrgSlug] = useState(savedDraft?.orgSlug ?? "");
  const [loading, setLoading] = useState(false);
  const [turnstileWidgetId, setTurnstileWidgetId] = useState<string | null>(null);
  const turnstileRef = useRef<TurnstileWidgetHandle | null>(null);
  const { register } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation("auth");
  const hasInvitation = Boolean(invitationToken);

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

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (password !== confirmPassword) {
      toast.error(t("toast.passwordsMismatch"));
      return;
    }
    if (!isStrongPassword(password)) {
      toast.error(t("toast.passwordTooShort"));
      return;
    }
    if (!hasInvitation && (!orgName || !orgSlug)) {
      toast.error(t("signup.missingOrgFields"));
      return;
    }

    setLoading(true);
    try {
      const verificationToken = await getVerificationToken();
      if (isTurnstileConfigured() && !verificationToken) return;
      await register(
        email,
        displayName,
        password,
        invitationToken || undefined,
        hasInvitation ? undefined : orgName || undefined,
        hasInvitation ? undefined : orgSlug || undefined,
        verificationToken,
      );
      saveRegistrationDraft({ displayName, email, invitationToken, orgName, orgSlug });
      toast.success(t("toast.accountCreated"));
      navigate("/verify-email-prompt", { state: { email } });
    } catch (error: unknown) {
      toast.error(t(getRegistrationErrorKey(error)));
    } finally {
      resetTurnstile(turnstileWidgetId);
      setLoading(false);
    }
  };

  return (
    <AuthShell
      eyebrow={t("signup.title")}
      title={t("signup.title")}
      description={t("signup.subtitle")}
      footer={
        <p className="text-sm text-muted-foreground">
          {t("signup.hasAccount")} {" "}
          <Link className="font-medium text-foreground underline-offset-4 hover:underline" to="/login">
            {t("signup.signIn")}
          </Link>
        </p>
      }
    >
      <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
        <FieldGroup className="gap-4">
          <Field>
            <FieldLabel htmlFor="display-name">{t("signup.displayNameLabel")}</FieldLabel>
            <Input
              id="display-name"
              type="text"
              placeholder={t("signup.displayNamePlaceholder")}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="name"
              required
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="email">{t("signup.emailLabel")}</FieldLabel>
            <Input
              id="email"
              type="email"
              placeholder={t("signup.emailPlaceholder")}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
            <FieldDescription>{t("signup.emailDescription")}</FieldDescription>
          </Field>

          <Field>
            <FieldLabel htmlFor="org-name">{t("signup.orgLabel")}</FieldLabel>
            <FieldDescription>{t("signup.orgDescription")}</FieldDescription>
            {!hasInvitation ? (
              <FieldGroup className="gap-4 pt-1">
                <Field>
                  <FieldLabel htmlFor="org-name">{t("signup.orgNameLabel")}</FieldLabel>
                  <Input
                    id="org-name"
                    type="text"
                    placeholder={t("signup.orgNamePlaceholder")}
                    value={orgName}
                    onChange={(event) => setOrgName(event.target.value)}
                    autoComplete="organization"
                    required
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="org-slug">{t("signup.orgSlugLabel")}</FieldLabel>
                  <Input
                    id="org-slug"
                    type="text"
                    placeholder={t("signup.orgSlugPlaceholder")}
                    value={orgSlug}
                    onChange={(event) => setOrgSlug(event.target.value.replace(/[^a-z0-9-]/g, "").toLowerCase())}
                    autoComplete="off"
                    required
                  />
                  <FieldDescription>{t("signup.orgSlugDescription")}</FieldDescription>
                </Field>
              </FieldGroup>
            ) : (
              <div className="rounded-lg border bg-muted/40 p-3">
                <FieldLabel htmlFor="invitation-token">{t("signup.invitationTokenLabel")}</FieldLabel>
                <Input
                  id="invitation-token"
                  className="mt-2"
                  type="text"
                  placeholder={t("signup.invitationTokenPlaceholder")}
                  value={invitationToken}
                  onChange={(event) => setInvitationToken(event.target.value)}
                  autoComplete="off"
                />
                <FieldDescription className="mt-2">{t("signup.invitationTokenDescription")}</FieldDescription>
              </div>
            )}
          </Field>

          <Separator />

          <FieldGroup className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="password">{t("signup.passwordLabel")}</FieldLabel>
              <InputGroup className="h-9">
                <InputGroupInput
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="new-password"
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
            <Field>
              <FieldLabel htmlFor="confirm-password">{t("signup.confirmPasswordLabel")}</FieldLabel>
              <InputGroup className="h-9">
                <InputGroupInput
                  id="confirm-password"
                  type={showConfirmPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  required
                />
                <InputGroupButton
                  aria-label={showConfirmPassword ? "Hide characters" : "Show characters"}
                  onClick={() => setShowConfirmPassword((visible) => !visible)}
                  size="icon-sm"
                  type="button"
                >
                  {showConfirmPassword ? <EyeOffIcon aria-hidden="true" /> : <EyeIcon aria-hidden="true" />}
                </InputGroupButton>
              </InputGroup>
            </Field>
          </FieldGroup>
          <FieldDescription>{t("signup.passwordHint")}</FieldDescription>
        </FieldGroup>

        <TurnstileWidget
          ref={turnstileRef}
          action="signup"
          onWidgetIdChange={setTurnstileWidgetId}
          className="min-h-16"
        />

        <Button className="w-full" disabled={loading || !email || !displayName || !password} type="submit">
          {loading ? <Spinner data-icon="inline-start" /> : null}
          {t("signup.submit")}
        </Button>

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
