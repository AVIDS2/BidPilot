import { useRef, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { requestPasswordReset } from "@/lib/api"
import { toast } from "sonner"
import { Loader2Icon, MailIcon } from "lucide-react"
import { TurnstileWidget, isTurnstileConfigured, resetTurnstile, type TurnstileWidgetHandle } from "@/components/security/turnstile-widget"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { BrandLogo } from "@/components/brand"

const FilmFrameAnnotations = () => (
  <div className="absolute inset-0 pointer-events-none z-10">
    <span className="absolute top-6 left-6 text-[10px] text-foreground/20 font-mono">BidPilot v1.0</span>
    <span className="absolute top-6 right-6 text-[10px] text-foreground/20 font-mono">[16:9]</span>
    <span className="absolute bottom-6 left-6 text-[10px] text-foreground/20 font-mono">OVERSCAN: 1920 x 1080</span>
    <span className="absolute bottom-6 right-6 text-[10px] text-foreground/20 font-mono">100%</span>
  </div>
)

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null)
  const [turnstileWidgetId, setTurnstileWidgetId] = useState<string | null>(null)
  const turnstileRef = useRef<TurnstileWidgetHandle | null>(null)
  const navigate = useNavigate()
  const { t } = useTranslation("auth")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const verificationToken = isTurnstileConfigured()
        ? await turnstileRef.current?.execute()
        : null
      if (isTurnstileConfigured() && !verificationToken) {
        toast.error(t("turnstile.required"))
        return
      }
      await requestPasswordReset(email, verificationToken)
      setSent(true)
    } catch {
      toast.error(t("forgotPassword.error"))
    } finally {
      resetTurnstile(turnstileWidgetId)
      setTurnstileToken(null)
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-background px-6">
        <FilmFrameAnnotations />
        <div className="relative z-20 w-full max-w-md text-center">
          <div className="p-8 rounded-xl bg-card border border-border shadow-sm">
            <MailIcon className="mx-auto size-8 mb-4 text-primary" />
            <h1 className="text-xl font-bold text-foreground mb-2">{t("forgotPassword.checkEmail")}</h1>
            <p className="text-sm mb-6 text-muted-foreground">
              {t("forgotPassword.emailSent", { email })}
            </p>
            <Button
              variant="outline"
              onClick={() => navigate("/login")}
              className="w-full h-10"
            >
              {t("forgotPassword.backToLogin")}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-background px-6">
      <FilmFrameAnnotations />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(132,204,22,0.03)"/><circle cx="75" cy="75" r="1" fill="rgba(132,204,22,0.03)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>')`,
        }}
      />
      <div className="relative z-20 w-full max-w-md">
        <div className="text-center mb-10">
          <Link to="/" className="inline-flex transition-colors duration-300 hover:text-primary">
            <BrandLogo markClassName="size-10" textClassName="text-3xl" />
          </Link>
          <p className="mt-3 text-sm text-muted-foreground">{t("forgotPassword.title")}</p>
        </div>
        <div className="p-8 rounded-xl bg-card border border-border shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-medium text-foreground">
                {t("forgotPassword.emailLabel")}
              </label>
              <Input
                id="email"
                type="email"
                placeholder={t("forgotPassword.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-10"
              />
            </div>
            <TurnstileWidget
              ref={turnstileRef}
              action="password_reset"
              onTokenChange={setTurnstileToken}
              onWidgetIdChange={setTurnstileWidgetId}
              className="min-h-[65px]"
            />
            <Button
              type="submit"
              disabled={loading || !email}
              className="w-full h-10"
            >
              {loading && <Loader2Icon className="animate-spin" />}
              {t("forgotPassword.submit")}
            </Button>
          </form>
          <p className="mt-6 text-center text-xs text-muted-foreground">
            {t("forgotPassword.rememberPassword")}{" "}
            <Link to="/login" className="text-foreground hover:text-primary transition-colors duration-300 font-medium">
              {t("forgotPassword.signIn")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
