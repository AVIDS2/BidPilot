import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { requestPasswordReset } from "@/lib/api"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "sonner"
import { MailIcon } from "lucide-react"

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const navigate = useNavigate()
  const { t } = useTranslation("auth")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await requestPasswordReset(email)
      setSent(true)
    } catch {
      toast.error(t("forgotPassword.error"))
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
        <div className="flex w-full max-w-md flex-col gap-6">
          <div className="flex flex-col items-center gap-2 text-center">
            <MailIcon className="size-8 text-primary" />
            <h1 className="text-xl font-bold">{t("forgotPassword.checkEmail")}</h1>
            <p className="text-sm text-muted-foreground">
              {t("forgotPassword.emailSent", { email })}
            </p>
          </div>
          <Button variant="outline" onClick={() => navigate("/login")}>
            {t("forgotPassword.backToLogin")}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-md flex-col gap-6">
        <form onSubmit={handleSubmit}>
          <FieldGroup>
            <div className="flex flex-col items-center gap-2 text-center">
              <h1 className="text-xl font-bold">{t("forgotPassword.title")}</h1>
              <FieldDescription>
                {t("forgotPassword.description")}
              </FieldDescription>
            </div>
            <Field>
              <FieldLabel htmlFor="email">{t("forgotPassword.emailLabel")}</FieldLabel>
              <Input
                id="email"
                type="email"
                placeholder={t("forgotPassword.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </Field>
            <Field>
              <Button type="submit" disabled={loading || !email}>
                {loading && <Spinner data-icon="inline-start" />}
                {t("forgotPassword.submit")}
              </Button>
            </Field>
            <FieldDescription className="text-center">
              {t("forgotPassword.rememberPassword")}{" "}<a href="/login">{t("forgotPassword.signIn")}</a>
            </FieldDescription>
          </FieldGroup>
        </form>
      </div>
    </div>
  )
}
