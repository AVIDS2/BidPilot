import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { confirmPasswordReset } from "@/lib/api"
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
import { KeyIcon } from "lucide-react"

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token") || ""
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const navigate = useNavigate()
  const { t } = useTranslation("auth")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPassword !== confirmPassword) {
      toast.error(t("resetPassword.passwordsMismatch"))
      return
    }
    setLoading(true)
    try {
      await confirmPasswordReset(token, newPassword)
      setDone(true)
      toast.success(t("resetPassword.success"))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(msg.includes("expired") ? t("resetPassword.expired") : t("resetPassword.failed"))
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
        <div className="flex w-full max-w-md flex-col gap-6 text-center">
          <h1 className="text-xl font-bold">{t("resetPassword.invalidTitle")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("resetPassword.invalidDesc")}
          </p>
          <Button variant="outline" onClick={() => navigate("/forgot-password")}>
            {t("resetPassword.requestNew")}
          </Button>
        </div>
      </div>
    )
  }

  if (done) {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
        <div className="flex w-full max-w-md flex-col gap-6 text-center">
          <KeyIcon className="mx-auto size-8 text-primary" />
          <h1 className="text-xl font-bold">{t("resetPassword.successTitle")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("resetPassword.successDesc")}
          </p>
          <Button onClick={() => navigate("/login")}>{t("resetPassword.signIn")}</Button>
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
              <h1 className="text-xl font-bold">{t("resetPassword.title")}</h1>
              <FieldDescription>
                {t("resetPassword.description")}
              </FieldDescription>
            </div>
            <Field>
              <FieldLabel htmlFor="new-password">{t("resetPassword.newPasswordLabel")}</FieldLabel>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
              <FieldDescription>
                {t("resetPassword.passwordHint")}
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="confirm-password">{t("resetPassword.confirmPasswordLabel")}</FieldLabel>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </Field>
            <Field>
              <Button type="submit" disabled={loading || !newPassword || !confirmPassword}>
                {loading && <Spinner data-icon="inline-start" />}
                {t("resetPassword.submit")}
              </Button>
            </Field>
          </FieldGroup>
        </form>
      </div>
    </div>
  )
}
