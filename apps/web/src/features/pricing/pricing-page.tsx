import { Badge } from "@/components/ui/badge";
import { ArrowLeftIcon, CheckIcon, FileTextIcon, HelpCircleIcon, QuoteIcon, ShieldCheckIcon } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Link, useNavigate } from "react-router-dom";
import { createCheckout } from "@/lib/api";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { useMemo } from "react";
import AnimatedContent from "@/components/AnimatedContent";

interface PricingTier {
  name: string;
  price: string;
  period: string;
  description: string;
  recommended?: boolean;
  features: string[];
  cta: string;
}

interface ComparisonRow {
  feature: string;
  starter: string;
  professional: string;
  enterprise: string;
}

interface Testimonial {
  quote: string;
  author: string;
  role: string;
}

interface FaqItem {
  question: string;
  answer: string;
}

function TierCard({
  tier,
  current,
  onUpgrade,
  t,
  inPlatform,
}: {
  tier: PricingTier;
  current: boolean;
  onUpgrade: (plan: string) => void;
  t: (key: string) => string;
  inPlatform: boolean;
}) {
  const highlighted = tier.recommended && !current;

  return (
    <div
      className="relative flex flex-col p-8 transition-all duration-300 hover:-translate-y-1"
      style={{
        background: inPlatform ? "var(--card)" : "var(--landing-surface-1)",
        border: highlighted
          ? `1px solid ${inPlatform ? "var(--primary)" : "var(--landing-border-inner)"}`
          : current
            ? `1px solid ${inPlatform ? "var(--primary)" : "rgba(132, 204, 22, 0.6)"}`
            : `1px solid ${inPlatform ? "var(--border)" : "var(--landing-hairline)"}`,
      }}
    >
      {/* 推荐标签 */}
      {highlighted && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <Badge
            className="px-3 py-0.5 text-[0.7rem] font-medium uppercase tracking-wider border-0"
            style={{
              background: inPlatform ? "var(--primary)" : "var(--landing-accent)",
              color: inPlatform ? "var(--primary-foreground)" : "var(--landing-canvas)",
            }}
          >
            {t("badges.recommended")}
          </Badge>
        </div>
      )}

      {/* 当前方案标签 */}
      {current && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <Badge
            className="px-3 py-0.5 text-[0.7rem] font-medium uppercase tracking-wider border-0"
            style={{
              background: inPlatform ? "var(--muted)" : "var(--landing-surface-2)",
              color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-secondary)",
            }}
          >
            {t("badges.currentPlan")}
          </Badge>
        </div>
      )}

      {/* 标题和描述 */}
      <div className={highlighted || current ? "pt-4" : ""}>
        <h3 className="text-lg font-semibold" style={{ color: inPlatform ? "var(--foreground)" : "white" }}>
          {tier.name}
        </h3>
        <p className="mt-1 text-sm" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-tertiary)" }}>
          {tier.description}
        </p>
      </div>

      {/* 价格 */}
      <div className="mt-6">
        <span className="text-4xl font-bold tracking-tight" style={{ color: inPlatform ? "var(--foreground)" : "white" }}>
          {tier.price}
        </span>
        {tier.period && (
          <span className="text-sm ml-1.5" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-tertiary)" }}>
            {tier.period}
          </span>
        )}
      </div>

      {/* 分割线 */}
      <div
        className="my-6"
        style={{ borderTop: `1px solid ${inPlatform ? "var(--border)" : "var(--landing-hairline)"}` }}
      />

      {/* 功能列表 */}
      <ul className="space-y-4 flex-1">
        {tier.features.map((feat) => (
          <li key={feat} className="flex items-start gap-3">
            <CheckIcon
              className="mt-1 size-4 shrink-0"
              style={{ color: inPlatform ? "var(--primary)" : "var(--landing-accent)" }}
            />
            <span className="text-sm" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-secondary)" }}>
              {feat}
            </span>
          </li>
        ))}
      </ul>

      {/* 按钮 */}
      <Link
        to={current ? "#" : tier.name.toLowerCase() === "starter" ? "/login" : "/signup"}
        className="block w-full text-center py-4 text-sm font-medium transition-all duration-300 hover:scale-[0.98] mt-8"
        style={{
          background: highlighted ? (inPlatform ? "var(--primary)" : "var(--landing-accent)") : "transparent",
          color: highlighted
            ? (inPlatform ? "var(--primary-foreground)" : "var(--landing-canvas)")
            : current
              ? (inPlatform ? "var(--muted-foreground)" : "var(--landing-text-tertiary)")
              : (inPlatform ? "var(--foreground)" : "var(--landing-text-primary)"),
          border: highlighted
            ? "none"
            : current
              ? `1px solid ${inPlatform ? "var(--border)" : "var(--landing-hairline)"}`
              : `1px solid ${inPlatform ? "var(--border)" : "var(--landing-hairline)"}`,
          cursor: current ? "default" : "pointer",
          opacity: current ? 0.6 : 1,
        }}
        onClick={(e) => {
          if (current) {
            e.preventDefault();
            return;
          }
          e.preventDefault();
          onUpgrade(tier.name.toLowerCase());
        }}
      >
        {current ? t("button.currentPlan") : tier.cta}
      </Link>
    </div>
  );
}

export function PricingPage() {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const currentPlan = user?.plan?.toLowerCase() ?? "";
  const { t } = useTranslation("pricing");
  const inPlatform = isAuthenticated;

  const TIERS: PricingTier[] = useMemo(
    () => [
      {
        name: t("tiers.starter.name"),
        price: t("tiers.starter.price"),
        period: t("tiers.starter.period"),
        description: t("tiers.starter.description"),
        features: t("tiers.starter.features", {
          returnObjects: true,
        }) as unknown as string[],
        cta: t("tiers.starter.cta"),
      },
      {
        name: t("tiers.professional.name"),
        price: t("tiers.professional.price"),
        period: t("tiers.professional.period"),
        description: t("tiers.professional.description"),
        recommended: true,
        features: t("tiers.professional.features", {
          returnObjects: true,
        }) as unknown as string[],
        cta: t("tiers.professional.cta"),
      },
      {
        name: t("tiers.enterprise.name"),
        price: t("tiers.enterprise.price"),
        period: t("tiers.enterprise.period"),
        description: t("tiers.enterprise.description"),
        features: t("tiers.enterprise.features", {
          returnObjects: true,
        }) as unknown as string[],
        cta: t("tiers.enterprise.cta"),
      },
    ],
    [t],
  );

  const comparisonRows = useMemo(
    () => t("comparison.rows", { returnObjects: true }) as unknown as ComparisonRow[],
    [t],
  );

  const testimonials = useMemo(
    () => t("testimonials.items", { returnObjects: true }) as unknown as Testimonial[],
    [t],
  );

  const faqItems = useMemo(
    () => t("faq.items", { returnObjects: true }) as unknown as FaqItem[],
    [t],
  );

  const checkoutMut = useMutation({
    mutationFn: createCheckout,
    onSuccess: (data) => {
      window.location.href = data.url;
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("501") || msg.includes("not configured")) {
        toast.error(t("toast.notAvailable"));
      } else {
        toast.error(t("toast.checkoutFailed"));
      }
    },
  });

  const handleUpgrade = (plan: string) => {
    if (plan === currentPlan) return;
    if (plan === "starter") {
      navigate("/login");
      return;
    }
    if (!isAuthenticated) {
      navigate("/login");
      return;
    }
    checkoutMut.mutate(plan);
  };

  return (
    <div
      className={inPlatform ? "" : "min-h-screen"}
      style={{
        background: inPlatform ? "var(--background)" : "var(--landing-canvas)",
        color: inPlatform ? "var(--foreground)" : "var(--landing-text-primary)",
      }}
    >
      <div className={`mx-auto ${inPlatform ? "max-w-6xl py-2 px-0" : "max-w-5xl py-12 px-6"}`}>
        {/* 顶部导航 */}
        {!inPlatform && <div className="flex items-center justify-between mb-16">
          <Link
            to={isAuthenticated ? "/projects" : "/"}
            className="inline-flex items-center gap-1.5 text-sm transition-colors hover:text-white"
            style={{ color: "var(--landing-text-tertiary)" }}
          >
            <ArrowLeftIcon className="size-4" />
            {isAuthenticated ? t("back.projects") : t("back.home")}
          </Link>
          <Link
            to="/"
            className="flex items-center gap-2 font-semibold text-sm text-white"
          >
            <div
              className="flex size-6 items-center justify-center rounded-md"
              style={{ background: "var(--landing-accent)", color: "var(--landing-canvas)" }}
            >
              <FileTextIcon className="size-4" />
            </div>
            BidPilot
          </Link>
          <div className="w-20" />
        </div>}

        {/* 标题区域 */}
        <div className={`${inPlatform ? "mb-8 max-w-2xl" : "text-center mb-16 max-w-xl mx-auto"}`}>
          <span
            className="text-sm font-medium tracking-widest uppercase"
            style={{ color: inPlatform ? "var(--primary)" : "var(--landing-accent)" }}
          >
            {inPlatform ? t("title") : "/ Pricing"}
          </span>
          <h1 className="mt-4 text-4xl font-bold tracking-tight" style={{ color: inPlatform ? "var(--foreground)" : "white" }}>
            {t("title")}
          </h1>
          <p
            className="mt-3 leading-relaxed max-w-[65ch] mx-auto"
            style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-tertiary)" }}
          >
            {t("description")}
          </p>
          {inPlatform && (
            <p className="mt-4 text-sm text-muted-foreground">
              {t("inPlatformNote", { defaultValue: "Your current plan and usage are shown in Settings." })}
            </p>
          )}
        </div>

        {/* 定价卡片 */}
        <div className="grid gap-8 md:grid-cols-3 items-stretch">
          {TIERS.map((tier) => (
            <TierCard
              key={tier.name}
              tier={tier}
              current={tier.name.toLowerCase() === currentPlan}
              onUpgrade={handleUpgrade}
              t={t}
              inPlatform={inPlatform}
            />
          ))}
        </div>

        <AnimatedContent distance={24} duration={0.55} className="mt-16">
          <section
            className="overflow-hidden rounded-3xl border"
            style={{
              background: inPlatform ? "var(--card)" : "var(--landing-surface-1)",
              borderColor: inPlatform ? "var(--border)" : "var(--landing-hairline)",
            }}
          >
            <div className="flex flex-col gap-3 border-b p-6 md:flex-row md:items-center md:justify-between" style={{ borderColor: inPlatform ? "var(--border)" : "var(--landing-hairline)" }}>
              <div>
                <div className="flex items-center gap-2 text-sm font-medium" style={{ color: inPlatform ? "var(--primary)" : "var(--landing-accent)" }}>
                  <ShieldCheckIcon className="size-4" />
                  {t("comparison.label")}
                </div>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight" style={{ color: inPlatform ? "var(--foreground)" : "white" }}>
                  {t("comparison.title")}
                </h2>
              </div>
              <p className="max-w-md text-sm leading-6" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-tertiary)" }}>
                {t("comparison.description")}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-sm">
                <thead>
                  <tr style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-tertiary)" }}>
                    <th className="w-[34%] px-6 py-4 text-left font-medium">{t("comparison.columns.feature")}</th>
                    <th className="px-6 py-4 text-left font-medium">{t("tiers.starter.name")}</th>
                    <th className="px-6 py-4 text-left font-medium">{t("tiers.professional.name")}</th>
                    <th className="px-6 py-4 text-left font-medium">{t("tiers.enterprise.name")}</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonRows.map((row) => (
                    <tr key={row.feature} className="border-t" style={{ borderColor: inPlatform ? "var(--border)" : "var(--landing-hairline)" }}>
                      <td className="px-6 py-4 font-medium" style={{ color: inPlatform ? "var(--foreground)" : "white" }}>{row.feature}</td>
                      <td className="px-6 py-4" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-secondary)" }}>{row.starter}</td>
                      <td className="px-6 py-4" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-secondary)" }}>{row.professional}</td>
                      <td className="px-6 py-4" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-secondary)" }}>{row.enterprise}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </AnimatedContent>

        <section className="mt-12 grid gap-6 md:grid-cols-3">
          {testimonials.map((item, index) => (
            <AnimatedContent key={item.author} delay={index * 0.06} distance={24} duration={0.5}>
              <article
                className="h-full rounded-3xl border p-6"
                style={{
                  background: inPlatform ? "var(--card)" : "var(--landing-surface-1)",
                  borderColor: inPlatform ? "var(--border)" : "var(--landing-hairline)",
                }}
              >
                <QuoteIcon className="size-5" style={{ color: inPlatform ? "var(--primary)" : "var(--landing-accent)" }} />
                <p className="mt-4 text-sm leading-6" style={{ color: inPlatform ? "var(--foreground)" : "var(--landing-text-primary)" }}>
                  {item.quote}
                </p>
                <div className="mt-6">
                  <p className="text-sm font-semibold" style={{ color: inPlatform ? "var(--foreground)" : "white" }}>{item.author}</p>
                  <p className="text-xs" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-tertiary)" }}>{item.role}</p>
                </div>
              </article>
            </AnimatedContent>
          ))}
        </section>

        <AnimatedContent distance={24} duration={0.55} className="mt-12 pb-16">
          <section
            className="rounded-3xl border p-6 md:p-8"
            style={{
              background: inPlatform ? "var(--card)" : "var(--landing-surface-1)",
              borderColor: inPlatform ? "var(--border)" : "var(--landing-hairline)",
            }}
          >
            <div className="mb-6 flex items-center gap-2">
              <HelpCircleIcon className="size-5" style={{ color: inPlatform ? "var(--primary)" : "var(--landing-accent)" }} />
              <h2 className="text-2xl font-semibold tracking-tight" style={{ color: inPlatform ? "var(--foreground)" : "white" }}>
                {t("faq.title")}
              </h2>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {faqItems.map((item) => (
                <div key={item.question} className="rounded-2xl border p-4" style={{ borderColor: inPlatform ? "var(--border)" : "var(--landing-hairline)" }}>
                  <h3 className="text-sm font-semibold" style={{ color: inPlatform ? "var(--foreground)" : "white" }}>{item.question}</h3>
                  <p className="mt-2 text-sm leading-6" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--landing-text-tertiary)" }}>{item.answer}</p>
                </div>
              ))}
            </div>
          </section>
        </AnimatedContent>
      </div>
    </div>
  );
}
