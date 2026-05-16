import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "sonner"
import { CheckIcon, FileTextIcon } from "lucide-react"

export function SignupForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const [email, setEmail] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()
  const { t } = useTranslation("auth")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirmPassword) {
      toast.error(t("toast.passwordsMismatch"))
      return
    }
    if (password.length < 8) {
      toast.error(t("toast.passwordTooShort"))
      return
    }
    setLoading(true)
    try {
      await register(email, displayName, password)
      toast.success(t("toast.accountCreated"))
      navigate("/verify-email-prompt", { state: { email } })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes("Email already registered")) {
        toast.error(t("toast.emailExists"))
      } else if (msg.includes("API 4")) {
        toast.error(t("toast.registrationFailed"))
      } else if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
        toast.error(t("toast.registrationNetworkError"))
      } else {
        toast.error(t("toast.registrationGenericError"))
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card className="overflow-hidden p-0">
        <CardContent className="grid p-0 md:grid-cols-2">
          <form onSubmit={handleSubmit} className="p-6 md:p-8">
            <FieldGroup>
              <div className="flex flex-col items-center gap-2 text-center">
                <h1 className="text-2xl font-bold">{t("signup.title")}</h1>
                <p className="text-sm text-balance text-muted-foreground">
                  {t("signup.subtitle")}
                </p>
              </div>
              <Field>
                <FieldLabel htmlFor="display-name">{t("signup.displayNameLabel")}</FieldLabel>
                <Input
                  id="display-name"
                  placeholder={t("signup.displayNamePlaceholder")}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
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
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
                <FieldDescription>
                  {t("signup.emailDescription")}
                </FieldDescription>
              </Field>
              <Field>
                <Field className="grid grid-cols-2 gap-4">
                  <Field>
                    <FieldLabel htmlFor="password">{t("signup.passwordLabel")}</FieldLabel>
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="confirm-password">
                      {t("signup.confirmPasswordLabel")}
                    </FieldLabel>
                    <Input
                      id="confirm-password"
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                    />
                  </Field>
                </Field>
                <FieldDescription>
                  {t("signup.passwordHint")}
                </FieldDescription>
              </Field>
              <Field>
                <Button type="submit" disabled={loading || !email || !displayName || !password}>
                  {loading && <Spinner data-icon="inline-start" />}
                  {t("signup.submit")}
                </Button>
              </Field>
              <FieldDescription className="text-center">
                {t("signup.hasAccount")}{" "}<a href="/login">{t("signup.signIn")}</a>
              </FieldDescription>
            </FieldGroup>
          </form>
          <div className="relative hidden bg-gradient-to-br from-primary/90 to-primary md:flex md:flex-col md:items-center md:justify-center md:gap-4 md:p-8">
            <div className="flex size-12 items-center justify-center rounded-lg bg-primary-foreground/20">
              <FileTextIcon className="size-6 text-primary-foreground" />
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-xl font-bold text-primary-foreground">DocPilot</h3>
              <p className="text-sm text-primary-foreground/80">
                {t("signup.productDesc")}
              </p>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-primary-foreground/70 text-xs">
              <div className="flex items-center gap-1.5">
                <CheckIcon className="size-3.5" />
                {t("signup.featureEvidence")}
              </div>
              <div className="flex items-center gap-1.5">
                <CheckIcon className="size-3.5" />
                {t("signup.featureReview")}
              </div>
              <div className="flex items-center gap-1.5">
                <CheckIcon className="size-3.5" />
                {t("signup.featureAudit")}
              </div>
              <div className="flex items-center gap-1.5">
                <CheckIcon className="size-3.5" />
                {t("signup.featureExport")}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      <FieldDescription className="px-6 text-center">
        {t("login.termsText")}{" "}<a href="#">{t("login.termsOfService")}</a>{" "}
        {t("login.and")}{" "}<a href="#">{t("login.privacyPolicy")}</a>.
      </FieldDescription>
    </div>
  )
}
