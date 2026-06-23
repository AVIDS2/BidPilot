import { useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { confirmPasswordReset } from "@/lib/api"
import { toast } from "sonner"
import { EyeIcon, EyeOffIcon, KeyIcon, Loader2Icon } from "lucide-react"
import { isStrongPassword } from "@/lib/password"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

const FilmFrameAnnotations = () => (
  <div className="absolute inset-0 pointer-events-none z-10">
    <span className="absolute top-6 left-6 text-[10px] text-foreground/20 font-mono">DocPilot v1.0</span>
    <span className="absolute top-6 right-6 text-[10px] text-foreground/20 font-mono">[16:9]</span>
    <span className="absolute bottom-6 left-6 text-[10px] text-foreground/20 font-mono">OVERSCAN: 1920 x 1080</span>
    <span className="absolute bottom-6 right-6 text-[10px] text-foreground/20 font-mono">100%</span>
  </div>
)

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token") || ""
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
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
    if (!isStrongPassword(newPassword)) {
      toast.error(t("resetPassword.passwordHint"))
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
        <FilmFrameAnnotations />
        <div className="relative z-20 w-full max-w-md text-center">
          <div className="p-8 rounded-xl bg-card border border-border shadow-sm">
            <h1 className="text-xl font-bold text-foreground mb-2">{t("resetPassword.invalidTitle")}</h1>
            <p className="text-sm mb-6 text-muted-foreground">{t("resetPassword.invalidDesc")}</p>
            <Button
              variant="outline"
              onClick={() => navigate("/forgot-password")}
              className="w-full h-10"
            >
              {t("resetPassword.requestNew")}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (done) {
    return (
      <div className="h-screen flex items-center justify-center bg-background px-6">
        <FilmFrameAnnotations />
        <div className="relative z-20 w-full max-w-md text-center">
          <div className="p-8 rounded-xl bg-card border border-border shadow-sm">
            <KeyIcon className="mx-auto size-8 mb-4 text-primary" />
            <h1 className="text-xl font-bold text-foreground mb-2">{t("resetPassword.successTitle")}</h1>
            <p className="text-sm mb-6 text-muted-foreground">{t("resetPassword.successDesc")}</p>
            <Button
              onClick={() => navigate("/login")}
              className="w-full h-10"
            >
              {t("resetPassword.signIn")}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex items-center justify-center bg-background px-6">
      <FilmFrameAnnotations />
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
          <p className="mt-3 text-sm text-muted-foreground">{t("resetPassword.title")}</p>
        </div>
        <div className="p-8 rounded-xl bg-card border border-border shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-6">
            <p className="text-sm text-center text-muted-foreground">{t("resetPassword.description")}</p>
            <div className="space-y-2">
              <label htmlFor="new-password" className="block text-sm font-medium text-foreground">
                {t("resetPassword.newPasswordLabel")}
              </label>
              <div className="relative">
                <Input
                  id="new-password"
                  type={showPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  className="h-10 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">{t("resetPassword.passwordHint")}</p>
            </div>
            <div className="space-y-2">
              <label htmlFor="confirm-password" className="block text-sm font-medium text-foreground">
                {t("resetPassword.confirmPasswordLabel")}
              </label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="h-10"
              />
            </div>
            <Button
              type="submit"
              disabled={loading || !newPassword || !confirmPassword}
              className="w-full h-10"
            >
              {loading && <Loader2Icon className="animate-spin" />}
              {t("resetPassword.submit")}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
