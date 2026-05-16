"use client"

import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { verifyEmail } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import { CheckCircleIcon, XCircleIcon, ArrowLeftIcon } from "lucide-react"

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get("token") || ""
  const [verifying, setVerifying] = useState(false)
  const [result, setResult] = useState<"success" | "error" | null>(null)
  const [errorMsg, setErrorMsg] = useState("")
  const { t } = useTranslation("auth")

  const handleVerify = async () => {
    if (!token) return
    setVerifying(true)
    try {
      await verifyEmail(token)
      setResult("success")
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setResult("error")
      setErrorMsg(msg || t("verifyEmail.failedDefault"))
    } finally {
      setVerifying(false)
    }
  }

  // Auto-verify if token is present
  if (token && result === null && !verifying) {
    handleVerify()
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <Card>
          <CardHeader className="text-center">
            <div className="flex justify-center mb-2">
              <div className={`rounded-full p-3 ${result === "success" ? "bg-green-100" : result === "error" ? "bg-red-100" : "bg-primary/10"}`}>
                {result === "success" ? (
                  <CheckCircleIcon className="size-8 text-green-600" />
                ) : result === "error" ? (
                  <XCircleIcon className="size-8 text-red-600" />
                ) : (
                  <Spinner className="size-8" />
                )}
              </div>
            </div>
            <CardTitle className="text-xl">
              {result === "success"
                ? t("verifyEmail.verifiedTitle")
                : result === "error"
                ? t("verifyEmail.failedTitle")
                : t("verifyEmail.verifying")}
            </CardTitle>
            <CardDescription>
              {result === "success"
                ? t("verifyEmail.verifiedDesc")
                : result === "error"
                ? errorMsg
                : t("verifyEmail.verifyingDesc")}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {result === "success" && (
              <Button onClick={() => navigate("/login")} className="w-full">
                {t("verifyEmail.continueToLogin")}
              </Button>
            )}
            {result === "error" && (
              <>
                <Button variant="outline" onClick={() => navigate("/verify-email-prompt")} className="w-full">
                  {t("verifyEmail.failedResend")}
                </Button>
                <Button variant="ghost" onClick={() => navigate("/login")} className="w-full">
                  <ArrowLeftIcon className="size-4 mr-2" />
                  {t("verifyEmail.failedBack")}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
