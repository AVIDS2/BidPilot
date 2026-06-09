import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Link } from "react-router-dom";
import {
  FileSearch,
  PenTool,
  ShieldCheck,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import { useTranslation } from "react-i18next";

function HeroSection() {
  const { t } = useTranslation("landing");
  return (
    <section className="gradient-hero relative mx-auto flex w-full max-w-6xl flex-col items-start gap-8 px-6 pt-32 pb-24 lg:flex-row lg:items-center lg:gap-16">
      {/* Subtle decorative dot grid */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "radial-gradient(circle, oklch(0.45 0.18 255) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />
      <div className="relative flex flex-1 flex-col items-start gap-6">
        <Badge variant="secondary" className="px-3 py-1 text-xs font-medium tracking-wide">
          {t("socialProof.label")}
        </Badge>
        <h1 className="text-4xl font-bold leading-tight tracking-tight text-foreground sm:text-5xl lg:text-6xl">
          {t("hero.title")}
        </h1>
        <p className="max-w-lg text-lg leading-relaxed text-muted-foreground">
          {t("hero.description")}
        </p>
        <div className="flex items-center gap-3 pt-2">
          <Link to="/signup">
            <Button
              size="lg"
              className="transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5"
            >
              {t("hero.getStarted")}
              <ArrowRight className="ml-1 size-4" />
            </Button>
          </Link>
          <Link to="/pricing">
            <Button
              variant="outline"
              size="lg"
              className="transition-all duration-200 hover:shadow-md hover:-translate-y-0.5"
            >
              {t("hero.viewPricing")}
            </Button>
          </Link>
        </div>
      </div>
      {/* Product screenshot placeholder */}
      <div className="animate-fade-in flex-1">
        <div className="relative aspect-[4/3] w-full rounded-2xl border border-border bg-card shadow-lg">
          <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-primary/5 via-transparent to-accent/5" />
        </div>
      </div>
    </section>
  );
}

function SocialProofSection() {
  const { t } = useTranslation("landing");
  const logos = ["Contour Design", "Harbor Group", "Northway Systems", "Atria Capital", "Vantage Partners"];
  return (
    <section className="border-y border-border bg-muted/30 py-14">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-8 px-6">
        <p className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          {t("socialProof.label")}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-4">
          {logos.map((name) => (
            <span
              key={name}
              className="text-sm font-semibold tracking-wider text-muted-foreground/50 uppercase transition-colors hover:text-muted-foreground/80"
            >
              {name}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

const STEPS = [
  { key: "upload", icon: FileSearch, num: 1 },
  { key: "generate", icon: PenTool, num: 2 },
  { key: "review", icon: ShieldCheck, num: 3 },
] as const;

function HowItWorksSection() {
  const { t } = useTranslation("landing");
  return (
    <section className="mx-auto max-w-6xl px-6 py-24">
      <div className="max-w-2xl">
        <h2 className="text-3xl font-bold leading-tight tracking-tight text-foreground">
          {t("howItWorks.heading")}
        </h2>
        <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
          {t("howItWorks.subheading")}
        </p>
      </div>
      <div className="mt-14 space-y-0">
        {STEPS.map((step) => (
          <div
            key={step.key}
            className="animate-fade-in relative flex gap-6 border-l border-border pl-8 pb-12 last:pb-0"
          >
            <span className="absolute -left-3.5 top-0 flex size-7 items-center justify-center rounded-full border border-border bg-background text-xs font-semibold text-foreground shadow-xs">
              {step.num}
            </span>
            <div className="pt-0.5">
              <div className="mb-2 flex items-center gap-2.5">
                <step.icon className="size-5 text-primary" />
                <h3 className="text-base font-semibold text-foreground">
                  {t(`howItWorks.steps.${step.key}.title`)}
                </h3>
              </div>
              <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
                {t(`howItWorks.steps.${step.key}.description`)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function FeaturesSection() {
  const { t } = useTranslation("landing");
  const features = [
    {
      key: "extraction",
      className: "col-span-full lg:col-span-2",
    },
    { key: "drafts", className: "lg:col-span-1" },
    { key: "audit", className: "lg:col-span-1" },
  ] as const;

  return (
    <section className="gradient-subtle mx-auto max-w-6xl px-6 py-24">
      <div className="max-w-2xl">
        <h2 className="text-3xl font-bold leading-tight tracking-tight text-foreground">
          {t("features.heading")}
        </h2>
        <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
          {t("features.subheading")}
        </p>
      </div>
      <div className="mt-14 grid gap-6 lg:grid-cols-3">
        {features.map((f) => (
          <div
            key={f.key}
            className={`card-elevated gradient-card flex flex-col justify-between rounded-2xl border border-border p-7 ${f.className}`}
          >
            <div>
              <h3 className="text-lg font-semibold text-foreground">
                {t(`features.${f.key}.title`)}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t(`features.${f.key}.description`)}
              </p>
            </div>
            <div className="mt-8 flex items-center gap-1.5 text-sm font-medium text-primary transition-colors hover:text-primary/80">
              {t(`features.${f.key}.learnMore`)}
              <ArrowRight className="size-3.5" />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function PricingSection() {
  const { t } = useTranslation("landing");
  const tiers = ["starter", "team", "enterprise"] as const;
  return (
    <section className="mx-auto max-w-6xl px-6 py-24">
      <div className="max-w-2xl">
        <h2 className="text-3xl font-bold leading-tight tracking-tight text-foreground">
          {t("pricing.heading")}
        </h2>
        <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
          {t("pricing.subheading")}
        </p>
      </div>
      <div className="mt-14 grid gap-6 lg:grid-cols-3">
        {tiers.map((tier) => {
          const highlighted = tier === "team";
          return (
            <div
              key={tier}
              className={`card-elevated flex flex-col rounded-2xl border p-7 transition-all duration-200 ${
                highlighted
                  ? "border-primary/50 shadow-md ring-1 ring-primary/20"
                  : "border-border"
              }`}
            >
              <Badge
                variant={highlighted ? "default" : "secondary"}
                className="w-fit"
              >
                {t(`pricing.tiers.${tier}.label`)}
              </Badge>
              <p className="mt-5 text-4xl font-bold tracking-tight text-foreground">
                {t(`pricing.tiers.${tier}.price`)}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {t(`pricing.tiers.${tier}.sub`)}
              </p>
              <ul className="mt-8 flex-1 space-y-3">
                {(
                  t(`pricing.tiers.${tier}.features`, {
                    returnObjects: true,
                  }) as string[]
                ).map((feat) => (
                  <li
                    key={feat}
                    className="flex items-start gap-2.5 text-sm leading-relaxed text-muted-foreground"
                  >
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
                    {feat}
                  </li>
                ))}
              </ul>
              <Link to="/signup" className="mt-8">
                <Button
                  variant={highlighted ? "default" : "outline"}
                  className="w-full transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5"
                >
                  {t(`pricing.tiers.${tier}.cta`)}
                </Button>
              </Link>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function FinalCtaSection() {
  const { t } = useTranslation("landing");
  return (
    <section className="border-t border-border py-24">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-6 text-center">
        <h2 className="text-3xl font-bold leading-tight tracking-tight text-foreground">
          {t("finalCta.heading")}
        </h2>
        <p className="max-w-md text-lg leading-relaxed text-muted-foreground">
          {t("finalCta.subheading")}
        </p>
        <Link to="/signup">
          <Button
            size="lg"
            className="transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5"
          >
            {t("finalCta.cta")}
            <ArrowRight className="ml-1 size-4" />
          </Button>
        </Link>
      </div>
    </section>
  );
}

export function LandingPage() {
  return (
    <div className="flex min-h-svh flex-col">
      <HeroSection />
      <SocialProofSection />
      <HowItWorksSection />
      <FeaturesSection />
      <PricingSection />
      <FinalCtaSection />
    </div>
  );
}
