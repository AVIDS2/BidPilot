"use client"

import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth"
import { resendVerification } from "@/lib/api"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { GalleryVerticalEndIcon, MailIcon } from "lucide-react"
import { toast } from "sonner"

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [unverifiedEmail, setUnverifiedEmail] = useState<string | null>(null)
  const [resending, setResending] = useState(false)
  const { login, token } = useAuth()
  const navigate = useNavigate()
  const { t } = useTranslation("auth")

  const handleResendVerification = async () => {
    if (!unverifiedEmail) return
    setResending(true)
    try {
      await resendVerification(token || "", unverifiedEmail)
      toast.success(t("toast.verificationSent"))
    } catch {
      toast.error(t("toast.verificationResendFailed"))
    } finally {
      setResending(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setUnverifiedEmail(null)
    try {
      await login(email, password)
      toast.success(t("toast.loggedIn"))
      navigate("/projects")
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes("email_not_verified") || msg.includes("not verified")) {
        setUnverifiedEmail(email)
        toast.error(t("toast.emailNotVerified"))
      } else if (msg.includes("Invalid credentials")) {
        toast.error(t("toast.invalidCredentials"))
      } else if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
        toast.error(t("toast.networkError"))
      } else if (msg.includes("API 4")) {
        toast.error(t("toast.authFailed"))
      } else {
        toast.error(t("toast.loginFailed"))
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <form onSubmit={handleSubmit}>
        <FieldGroup>
          <div className="flex flex-col items-center gap-2 text-center">
            <a
              href="#"
              className="flex flex-col items-center gap-2 font-medium"
            >
              <div className="flex size-8 items-center justify-center rounded-md">
                <GalleryVerticalEndIcon className="size-6" />
              </div>
              <span className="sr-only">DocPilot</span>
            </a>
            <h1 className="text-xl font-bold">{t("login.title")}</h1>
            <FieldDescription>
              {t("login.noAccount")}{" "}<a href="/signup">{t("login.signUp")}</a>
            </FieldDescription>
          </div>
          <Field>
            <FieldLabel htmlFor="email">{t("login.emailLabel")}</FieldLabel>
            <Input
              id="email"
              type="email"
              placeholder={t("login.emailPlaceholder")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="password">{t("login.passwordLabel")}</FieldLabel>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <FieldDescription className="text-right">
              <a href="/forgot-password" className="text-primary hover:underline">{t("login.forgotPassword")}</a>
            </FieldDescription>
          </Field>
          <Field>
            <Button type="submit" disabled={loading || !email || !password}>
              {loading && <Spinner data-icon="inline-start" />}
              {t("login.submit")}
            </Button>
          </Field>
          {unverifiedEmail && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <div className="flex items-center gap-2 font-medium mb-1">
                <MailIcon className="size-4" />
                {t("unverified.title")}
              </div>
              <p className="mb-2">{t("unverified.description")}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleResendVerification}
                disabled={resending}
              >
                {resending && <Spinner data-icon="inline-start" />}
                {t("unverified.resend")}
              </Button>
            </div>
          )}
        </FieldGroup>
      </form>
      <FieldDescription className="px-6 text-center">
        {t("login.termsText")}{" "}<a href="#">{t("login.termsOfService")}</a>{" "}
        {t("login.and")}{" "}<a href="#">{t("login.privacyPolicy")}</a>.
      </FieldDescription>
    </div>
  )
}
