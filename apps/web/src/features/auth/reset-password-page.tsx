import { useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { confirmPasswordReset } from "@/lib/api"
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
      <div className="h-screen flex items-center justify-center bg-background px-6">
        <div className="absolute inset-0 pointer-events-none z-10">
          <span className="absolute top-6 left-6 text-[10px] text-white/30 font-mono">DocPilot v1.0</span>
          <span className="absolute top-6 right-6 text-[10px] text-white/30 font-mono">[16:9]</span>
          <span className="absolute bottom-6 left-6 text-[10px] text-white/30 font-mono">OVERSCAN: 1920 x 1080</span>
          <span className="absolute bottom-6 right-6 text-[10px] text-white/30 font-mono">100%</span>
        </div>
        <div className="relative z-20 w-full max-w-md text-center">
          <div className="p-8" style={{ background: "var(--landing-surface-1)", border: "1px solid var(--landing-hairline)" }}>
            <h1 className="text-xl font-bold text-white mb-2">{t("resetPassword.invalidTitle")}</h1>
            <p className="text-sm mb-6" style={{ color: "var(--landing-text-secondary)" }}>{t("resetPassword.invalidDesc")}</p>
            <button
              onClick={() => navigate("/forgot-password")}
              className="w-full py-3 text-sm font-medium transition-all duration-300 hover:scale-[0.98]"
              style={{ border: "1px solid var(--landing-hairline)", color: "var(--landing-text-secondary)" }}
            >
              {t("resetPassword.requestNew")}
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (done) {
    return (
      <div className="h-screen flex items-center justify-center bg-background px-6">
        <div className="absolute inset-0 pointer-events-none z-10">
          <span className="absolute top-6 left-6 text-[10px] text-white/30 font-mono">DocPilot v1.0</span>
          <span className="absolute top-6 right-6 text-[10px] text-white/30 font-mono">[16:9]</span>
          <span className="absolute bottom-6 left-6 text-[10px] text-white/30 font-mono">OVERSCAN: 1920 x 1080</span>
          <span className="absolute bottom-6 right-6 text-[10px] text-white/30 font-mono">100%</span>
        </div>
        <div className="relative z-20 w-full max-w-md text-center">
          <div className="p-8" style={{ background: "var(--landing-surface-1)", border: "1px solid var(--landing-hairline)" }}>
            <KeyIcon className="mx-auto size-8 mb-4" style={{ color: "var(--landing-accent)" }} />
            <h1 className="text-xl font-bold text-white mb-2">{t("resetPassword.successTitle")}</h1>
            <p className="text-sm mb-6" style={{ color: "var(--landing-text-secondary)" }}>{t("resetPassword.successDesc")}</p>
            <button
              onClick={() => navigate("/login")}
              className="w-full py-3.5 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:scale-[0.98]"
            >
              {t("resetPassword.signIn")}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex items-center justify-center bg-background px-6">
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
          <Link to="/" className="text-3xl font-medium tracking-[-0.04em] text-white hover:text-primary transition-colors duration-300">
            DocPilot
          </Link>
          <p className="mt-3 text-sm" style={{ color: "var(--landing-text-tertiary)" }}>{t("resetPassword.title")}</p>
        </div>
        <div className="p-8" style={{ background: "var(--landing-surface-1)", border: "1px solid var(--landing-hairline)" }}>
          <form onSubmit={handleSubmit} className="space-y-6">
            <p className="text-sm text-center" style={{ color: "var(--landing-text-secondary)" }}>{t("resetPassword.description")}</p>
            <div>
              <label htmlFor="new-password" className="block text-sm font-medium mb-2" style={{ color: "var(--landing-text-secondary)" }}>
                {t("resetPassword.newPasswordLabel")}
              </label>
              <input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
              />
              <p className="text-xs mt-1" style={{ color: "var(--landing-text-tertiary)" }}>{t("resetPassword.passwordHint")}</p>
            </div>
            <div>
              <label htmlFor="confirm-password" className="block text-sm font-medium mb-2" style={{ color: "var(--landing-text-secondary)" }}>
                {t("resetPassword.confirmPasswordLabel")}
              </label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="w-full px-4 py-3 text-sm text-white bg-muted border border-border outline-none focus:border-primary transition-colors duration-300"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !newPassword || !confirmPassword}
              className="w-full py-3.5 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {t("resetPassword.submit")}
                </span>
              ) : (
                t("resetPassword.submit")
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
