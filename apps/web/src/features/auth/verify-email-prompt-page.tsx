"use client"

import { useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { resendVerification } from "@/lib/api"
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
    <div className="h-screen flex items-center justify-center bg-[#0a0a0a] px-6">
      <div className="absolute inset-0 pointer-events-none z-10">
        <span className="absolute top-6 left-6 text-[10px] text-white/30 font-mono">DocPilot v1.0</span>
        <span className="absolute top-6 right-6 text-[10px] text-white/30 font-mono">[16:9]</span>
        <span className="absolute bottom-6 left-6 text-[10px] text-white/30 font-mono">OVERSCAN: 1920 x 1080</span>
        <span className="absolute bottom-6 right-6 text-[10px] text-white/30 font-mono">100%</span>
      </div>
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(132,204,22,0.03)"/><circle cx="75" cy="75" r="1" fill="rgba(132,204,22,0.03)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>')`,
        }}
      />
      <div className="relative z-20 w-full max-w-md">
        <div className="text-center mb-10">
          <Link to="/" className="text-3xl font-medium tracking-[-0.04em] text-white hover:text-[#84cc16] transition-colors duration-300">
            DocPilot
          </Link>
          <p className="mt-3 text-sm" style={{ color: "#737373" }}>{t("verifyEmail.promptTitle")}</p>
        </div>
        <div className="p-8" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <div className="rounded-full p-3" style={{ background: "rgba(132, 204, 22, 0.1)" }}>
                <MailCheckIcon className="size-8" style={{ color: "#84cc16" }} />
              </div>
            </div>
            <h2 className="text-xl font-bold text-white mb-2">{t("verifyEmail.promptTitle")}</h2>
            <p className="text-sm mb-4" style={{ color: "#a3a3a3" }}>
              {t("verifyEmail.promptDesc", { email: email || t("verifyEmail.promptDescFallback") })}
            </p>
            <p className="text-sm mb-6" style={{ color: "#737373" }}>{t("verifyEmail.promptBody")}</p>
            {email && !resent && (
              <button
                onClick={handleResend}
                disabled={resending}
                className="w-full py-3 text-sm font-medium transition-all duration-300 hover:scale-[0.98] mb-3"
                style={{ border: "1px solid rgba(163, 163, 163, 0.1)", color: "#a3a3a3" }}
              >
                {resending ? (
                  <span className="inline-flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    {t("verifyEmail.resend")}
                  </span>
                ) : (
                  t("verifyEmail.resend")
                )}
              </button>
            )}
            {resent && (
              <p className="text-sm mb-3 font-medium" style={{ color: "#84cc16" }}>{t("verifyEmail.resent")}</p>
            )}
            <button
              onClick={() => navigate("/login")}
              className="w-full py-3 text-sm font-medium transition-all duration-300 hover:scale-[0.98] inline-flex items-center justify-center gap-2"
              style={{ color: "#737373" }}
            >
              <ArrowLeftIcon className="size-4" />
              {t("verifyEmail.backToLogin")}
            </button>
          </div>
          <p className="text-center text-xs mt-6" style={{ color: "#525252" }}>
            {t("verifyEmail.helpText")}
          </p>
        </div>
      </div>
    </div>
  )
}
