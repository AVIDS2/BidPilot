import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { requestPasswordReset } from "@/lib/api"
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
      <div className="h-screen flex items-center justify-center bg-[#0a0a0a] px-6">
        <div className="absolute inset-0 pointer-events-none z-10">
          <span className="absolute top-6 left-6 text-[10px] text-white/30 font-mono">DocPilot v1.0</span>
          <span className="absolute top-6 right-6 text-[10px] text-white/30 font-mono">[16:9]</span>
          <span className="absolute bottom-6 left-6 text-[10px] text-white/30 font-mono">OVERSCAN: 1920 x 1080</span>
          <span className="absolute bottom-6 right-6 text-[10px] text-white/30 font-mono">100%</span>
        </div>
        <div className="relative z-20 w-full max-w-md text-center">
          <div className="p-8" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
            <MailIcon className="mx-auto size-8 mb-4" style={{ color: "#84cc16" }} />
            <h1 className="text-xl font-bold text-white mb-2">{t("forgotPassword.checkEmail")}</h1>
            <p className="text-sm mb-6" style={{ color: "#a3a3a3" }}>
              {t("forgotPassword.emailSent", { email })}
            </p>
            <button
              onClick={() => navigate("/login")}
              className="w-full py-3 text-sm font-medium transition-all duration-300 hover:scale-[0.98]"
              style={{ border: "1px solid rgba(163, 163, 163, 0.1)", color: "#a3a3a3" }}
            >
              {t("forgotPassword.backToLogin")}
            </button>
          </div>
        </div>
      </div>
    )
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
          <p className="mt-3 text-sm" style={{ color: "#737373" }}>{t("forgotPassword.title")}</p>
        </div>
        <div className="p-8" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-2" style={{ color: "#a3a3a3" }}>
                {t("forgotPassword.emailLabel")}
              </label>
              <input
                id="email"
                type="email"
                placeholder={t("forgotPassword.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-3 text-sm text-white bg-[#262626] border border-[rgba(163,163,163,0.1)] outline-none focus:border-[#84cc16] transition-colors duration-300"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !email}
              className="w-full py-3.5 text-sm font-medium bg-[#84cc16] text-[#0a0a0a] hover:bg-[#65a30d] transition-all duration-300 hover:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {t("forgotPassword.submit")}
                </span>
              ) : (
                t("forgotPassword.submit")
              )}
            </button>
          </form>
          <p className="mt-6 text-center text-xs" style={{ color: "#737373" }}>
            {t("forgotPassword.rememberPassword")}{" "}
            <a href="/login" className="text-[#a3a3a3] hover:text-[#84cc16] transition-colors duration-300">
              {t("forgotPassword.signIn")}
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
