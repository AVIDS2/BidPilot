"use client"

import { useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { resendVerification } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import { MailCheckIcon, ArrowLeftIcon } from "lucide-react"
import { toast } from "sonner"

export function VerifyEmailPromptPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const email = (location.state as { email?: string } | null)?.email || ""
  const [resending, setResending] = useState(false)
  const [resent, setResent] = useState(false)
  const { t } = useTranslation("auth")

  const handleResend = async () => {
    if (!email) return
    setResending(true)
    try {
      await resendVerification("", email)
      setResent(true)
      toast.success(t("verifyEmail.resentToast"))
    } catch {
      toast.error(t("verifyEmail.resendFailed"))
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <Card>
          <CardHeader className="text-center">
            <div className="flex justify-center mb-2">
              <div className="rounded-full bg-primary/10 p-3">
                <MailCheckIcon className="size-8 text-primary" />
              </div>
            </div>
            <CardTitle className="text-xl">{t("verifyEmail.promptTitle")}</CardTitle>
            <CardDescription>
              {t("verifyEmail.promptDesc", { email: email || t("verifyEmail.promptDescFallback") })}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <p className="text-sm text-muted-foreground text-center">
              {t("verifyEmail.promptBody")}
            </p>
            {email && !resent && (
              <Button
                variant="outline"
                onClick={handleResend}
                disabled={resending}
                className="w-full"
              >
                {resending && <Spinner data-icon="inline-start" />}
                {t("verifyEmail.resend")}
              </Button>
            )}
            {resent && (
              <p className="text-sm text-center text-green-600 font-medium">
                {t("verifyEmail.resent")}
              </p>
            )}
            <Button
              variant="ghost"
              onClick={() => navigate("/login")}
              className="w-full"
            >
              <ArrowLeftIcon className="size-4 mr-2" />
              {t("verifyEmail.backToLogin")}
            </Button>
          </CardContent>
        </Card>
        <p className="text-center text-xs text-muted-foreground">
          {t("verifyEmail.helpText")}
        </p>
      </div>
    </div>
  )
}
