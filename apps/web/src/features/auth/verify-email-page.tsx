"use client"

import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { verifyEmail } from "@/lib/api"
import { CheckCircleIcon, XCircleIcon, ArrowLeftIcon } from "lucide-react"

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get("token") || ""
  const [verifying, setVerifying] = useState(false)
  const [result, setResult] = useState<"success" | "error" | null>(null)
  const [errorMsg, setErrorMsg] = useState("")
  const { t } = useTranslation("auth")

  // Auto-verify if token is present - using useEffect instead of calling in render
  useEffect(() => {
    if (!token || result !== null || verifying) return

    const handleVerify = async () => {
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

    handleVerify()
  }, [token, result, verifying, t])

  return (
    <div className="h-screen flex items-center justify-center bg-background px-6">
      <div className="absolute inset-0 pointer-events-none z-10">
        <span className="absolute top-6 left-6 text-[10px] text-foreground/20 font-mono">DocPilot v1.0</span>
        <span className="absolute top-6 right-6 text-[10px] text-foreground/20 font-mono">[16:9]</span>
        <span className="absolute bottom-6 left-6 text-[10px] text-foreground/20 font-mono">OVERSCAN: 1920 x 1080</span>
        <span className="absolute bottom-6 right-6 text-[10px] text-foreground/20 font-mono">100%</span>
      </div>
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(132,204,22,0.03)"/><circle cx="75" cy="75" r="1" fill="rgba(132,204,22,0.03)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>')`,
        }}
      />
      <div className="relative z-20 w-full max-w-md">
        <div className="text-center mb-10">
          <Link to="/" className="text-3xl font-medium tracking-[-0.04em] text-foreground hover:text-primary transition-colors duration-300">
            DocPilot
          </Link>
        </div>
        <div className="p-8 rounded-xl bg-card border border-border shadow-sm">
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <div className={`rounded-full p-3 ${result === "success" ? "bg-green-900/30" : result === "error" ? "bg-red-900/30" : ""}`} style={result === null ? { background: "rgba(132, 204, 22, 0.1)" } : undefined}>
                {result === "success" ? (
                  <CheckCircleIcon className="size-8" style={{ color: "var(--landing-accent)" }} />
                ) : result === "error" ? (
                  <XCircleIcon className="size-8" style={{ color: "var(--destructive)" }} />
                ) : (
                  <svg className="animate-spin size-8" viewBox="0 0 24 24" fill="none" style={{ color: "var(--landing-accent)" }}>
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                )}
              </div>
            </div>
            <h2 className="text-xl font-bold text-foreground mb-2">
              {result === "success"
                ? t("verifyEmail.verifiedTitle")
                : result === "error"
                ? t("verifyEmail.failedTitle")
                : t("verifyEmail.verifying")}
            </h2>
            <p className="text-sm mb-6 text-muted-foreground">
              {result === "success"
                ? t("verifyEmail.verifiedDesc")
                : result === "error"
                ? errorMsg
                : t("verifyEmail.verifyingDesc")}
            </p>
            {result === "success" && (
              <button
                onClick={() => navigate("/login")}
                className="w-full py-3.5 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:scale-[0.98]"
              >
                {t("verifyEmail.continueToLogin")}
              </button>
            )}
            {result === "error" && (
              <div className="space-y-3">
                <button
                  onClick={() => navigate("/verify-email-prompt")}
                  className="w-full py-3 text-sm font-medium transition-all duration-300 hover:scale-[0.98] border border-border text-muted-foreground"
                >
                  {t("verifyEmail.failedResend")}
                </button>
                <button
                  onClick={() => navigate("/login")}
                  className="w-full py-3 text-sm font-medium inline-flex items-center justify-center gap-2 transition-colors duration-300 text-muted-foreground/70"
                >
                  <ArrowLeftIcon className="size-4" />
                  {t("verifyEmail.failedBack")}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
