import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Link } from "react-router-dom";
import {
  FileSearch,
  PenTool,
  ShieldCheck,
  ArrowRight,
  CheckCircle2,
  FileText,
  BotMessageSquare,
  BarChart3,
  FolderOpen,
  Sparkles,
  Clock,
  Zap,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useRef, useState, useEffect, useCallback, type MouseEvent } from "react";
import { Card3D, GlowEffect, ScrollReveal, MagneticButton } from "./interactions";
import { useParallax } from "@/hooks/use-parallax";
import { ScrollProgress } from "@/components/ui/scroll-progress";
import { AnimatedCounter as ScrollAnimatedCounter } from "@/components/ui/animated-counter";

/* ---------- useCountUp: number animation hook ---------- */
function useCountUp(target: number, duration = 1600, startDelay = 200) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (hasAnimated.current) return;
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          observer.disconnect();

          const start = performance.now();
          const animate = (now: number) => {
            const elapsed = now - start - startDelay;
            if (elapsed < 0) {
              requestAnimationFrame(animate);
              return;
            }
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setValue(Math.round(eased * target));
            if (progress < 1) requestAnimationFrame(animate);
          };
          requestAnimationFrame(animate);
        }
      },
      { threshold: 0.3 },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [target, duration, startDelay]);

  return { ref, value };
}

/* ---------- StatCounter ---------- */
function StatCounter({
  value,
  suffix,
  label,
  delay,
}: {
  value: number;
  suffix: string;
  label: string;
  delay: number;
}) {
  const { ref, value: current } = useCountUp(value, 1600, delay);
  return (
    <div
      ref={ref}
      className="hero-counter-in flex flex-col items-center gap-1"
      style={{ animationDelay: `${delay}ms` }}
    >
      <span className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
        {current.toLocaleString()}
        {suffix}
      </span>
      <span className="text-xs font-medium text-muted-foreground">
        {label}
      </span>
    </div>
  );
}

/* ---------- ProductMockup: simulated product UI ---------- */
function ProductMockup() {
  return (
    <div className="flex size-full flex-col overflow-hidden rounded-xl bg-card">
      <div className="flex h-9 items-center gap-1.5 border-b border-border px-3">
        <span className="size-2.5 rounded-full bg-red-400/70" />
        <span className="size-2.5 rounded-full bg-yellow-400/70" />
        <span className="size-2.5 rounded-full bg-green-400/70" />
        <span className="ml-3 text-[11px] font-medium text-muted-foreground">
          DocPilot - BidPilot RFP Response
        </span>
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="hidden w-12 shrink-0 flex-col items-center gap-3 border-r border-border bg-muted/40 py-3 sm:flex">
          <div className="flex size-7 items-center justify-center rounded-lg bg-primary/10">
            <FolderOpen className="size-3.5 text-primary" />
          </div>
          <div className="flex size-7 items-center justify-center rounded-lg">
            <FileText className="size-3.5 text-muted-foreground" />
          </div>
          <div className="flex size-7 items-center justify-center rounded-lg">
            <BotMessageSquare className="size-3.5 text-muted-foreground" />
          </div>
          <div className="flex size-7 items-center justify-center rounded-lg">
            <BarChart3 className="size-3.5 text-muted-foreground" />
          </div>
        </div>
        <div className="hidden w-40 shrink-0 flex-col border-r border-border py-2 lg:flex">
          <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Documents
          </div>
          {[
            { name: "RFP-2026-041.pdf", active: true },
            { name: "Technical Spec.docx", active: false },
            { name: "Compliance Matrix", active: false },
            { name: "Past Performance.md", active: false },
          ].map((doc) => (
            <div
              key={doc.name}
              className={`mx-1.5 flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] ${
                doc.active
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted/50"
              }`}
            >
              <FileText className="size-3 shrink-0" />
              <span className="truncate">{doc.name}</span>
            </div>
          ))}
        </div>
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex h-8 items-center gap-2 border-b border-border px-3">
            <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold text-primary">
              AI Draft
            </span>
            <div className="h-3 w-px bg-border" />
            <div className="flex gap-1">
              {["B", "I", "U"].map((l) => (
                <span
                  key={l}
                  className="flex size-5 items-center justify-center rounded text-[10px] font-bold text-muted-foreground"
                >
                  {l}
                </span>
              ))}
            </div>
          </div>
          <div className="flex-1 space-y-3 overflow-hidden p-4">
            <div className="space-y-1">
              <div className="h-2.5 w-3/4 rounded bg-foreground/10" />
              <div className="h-2.5 w-full rounded bg-foreground/8" />
              <div className="h-2.5 w-5/6 rounded bg-foreground/8" />
            </div>
            <div className="space-y-1">
              <div className="h-2 w-1/2 rounded bg-primary/20" />
              <div className="h-2.5 w-full rounded bg-foreground/8" />
              <div className="h-2.5 w-4/5 rounded bg-foreground/8" />
              <div className="h-2.5 w-2/3 rounded bg-foreground/6" />
            </div>
            <div className="space-y-1">
              <div className="h-2 w-2/5 rounded bg-primary/20" />
              <div className="h-2.5 w-full rounded bg-foreground/8" />
              <div className="h-2.5 w-3/4 rounded bg-foreground/8" />
            </div>
            <div className="flex items-center gap-1">
              <div className="h-4 w-px animate-pulse bg-primary" />
              <span className="text-[9px] text-primary/60">AI writing...</span>
            </div>
          </div>
        </div>
        <div className="hidden w-44 shrink-0 flex-col border-l border-border bg-muted/20 xl:flex">
          <div className="flex items-center gap-1.5 border-b border-border px-3 py-2">
            <Sparkles className="size-3 text-primary" />
            <span className="text-[11px] font-semibold text-foreground">
              AI Assistant
            </span>
          </div>
          <div className="flex-1 space-y-2.5 p-3">
            <div className="rounded-lg bg-primary/5 p-2">
              <p className="text-[10px] leading-relaxed text-muted-foreground">
                Draft generated from 3 evidence sources. Confidence: 94%
              </p>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="size-3 text-green-500" />
                <span className="text-[10px] text-muted-foreground">
                  Section 2.1 completed
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="size-3 animate-spin rounded-full border border-primary border-t-transparent" />
                <span className="text-[10px] text-muted-foreground">
                  Analyzing Section 3.2
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="size-3 rounded-full border border-muted-foreground/30" />
                <span className="text-[10px] text-muted-foreground/60">
                  Section 4 pending
                </span>
              </div>
            </div>
            <div className="mt-2 rounded-lg border border-border bg-card p-2">
              <p className="text-[9px] font-medium text-muted-foreground">
                Evidence Used
              </p>
              <div className="mt-1 space-y-1">
                {["Contract Section 5.2", "Past Performance DB", "Compliance Guide"].map(
                  (src) => (
                    <div
                      key={src}
                      className="flex items-center gap-1 text-[9px] text-foreground/70"
                    >
                      <div className="size-1 rounded-full bg-primary/50" />
                      {src}
                    </div>
                  ),
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="flex h-6 items-center justify-between border-t border-border bg-muted/30 px-3">
        <span className="text-[9px] text-muted-foreground">
          3 sections complete
        </span>
        <span className="text-[9px] text-muted-foreground">
          Last saved 2 min ago
        </span>
      </div>
    </div>
  );
}

/* ---------- FloatingElements ---------- */
function FloatingElements() {
  return (
    <>
      <div className="hero-float-1 pointer-events-none absolute -top-6 -right-4 z-10 sm:right-2">
        <div className="flex size-10 items-center justify-center rounded-xl border border-border bg-card/80 shadow-md backdrop-blur-sm">
          <FileText className="size-5 text-primary/70" />
        </div>
      </div>
      <div
        className="hero-float-2 pointer-events-none absolute -top-4 -left-6 z-10 sm:-left-2"
        style={{ animationDelay: "1.5s" }}
      >
        <div className="flex size-9 items-center justify-center rounded-xl border border-primary/20 bg-primary/5 shadow-md backdrop-blur-sm">
          <Sparkles className="size-4 text-primary/80" />
        </div>
      </div>
      <div
        className="hero-float-3 pointer-events-none absolute -bottom-4 -right-2 z-10 sm:right-6"
        style={{ animationDelay: "3s" }}
      >
        <div className="flex size-9 items-center justify-center rounded-xl border border-border bg-card/80 shadow-md backdrop-blur-sm">
          <BarChart3 className="size-4 text-accent/70" />
        </div>
      </div>
      <div
        className="hero-float-1 pointer-events-none absolute bottom-6 -left-8 z-10 sm:-left-4"
        style={{ animationDelay: "2s" }}
      >
        <div className="flex size-8 items-center justify-center rounded-lg border border-border bg-card/80 shadow-md backdrop-blur-sm">
          <Zap className="size-4 text-yellow-500/70" />
        </div>
      </div>
      <div
        className="hero-float-2 pointer-events-none absolute top-1/2 -left-10 z-10 hidden lg:block"
        style={{ animationDelay: "4s" }}
      >
        <div className="flex size-8 items-center justify-center rounded-lg border border-border bg-card/80 shadow-md backdrop-blur-sm">
          <Clock className="size-3.5 text-muted-foreground/60" />
        </div>
      </div>
    </>
  );
}

/* ---------- HeroSection ---------- */
function HeroSection() {
  const { t } = useTranslation("landing");
  const cardRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [isHovering, setIsHovering] = useState(false);
  const glowParallax = useParallax({ speed: 0.12 });
  const floatParallax = useParallax({ speed: 0.06 });

  const handleMouseMove = useCallback((e: MouseEvent<HTMLDivElement>) => {
    const el = cardRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setTilt({
      x: (y - 0.5) * -16,
      y: (x - 0.5) * 16,
    });
  }, []);

  const handleMouseEnter = useCallback(() => setIsHovering(true), []);
  const handleMouseLeave = useCallback(() => {
    setIsHovering(false);
    setTilt({ x: 0, y: 0 });
  }, []);

  return (
    <section className="gradient-hero relative mx-auto flex w-full max-w-6xl flex-col items-start gap-8 px-6 pt-32 pb-24 lg:flex-row lg:items-center lg:gap-16">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "radial-gradient(circle, oklch(0.45 0.18 255) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />
      {/* Glow with parallax */}
      <div
        ref={glowParallax.ref as React.RefObject<HTMLDivElement>}
        className="hero-glow-pulse pointer-events-none absolute -top-24 right-0 size-[500px] rounded-full opacity-40 blur-3xl"
        style={{
          background:
            "radial-gradient(circle, oklch(0.45 0.18 255 / 0.15) 0%, oklch(0.55 0.15 270 / 0.08) 40%, transparent 70%)",
          ...glowParallax.style,
        }}
      />
      <div
        className="hero-glow-pulse pointer-events-none absolute -bottom-32 -left-32 size-[400px] rounded-full opacity-30 blur-3xl"
        style={{
          animationDelay: "3s",
          background:
            "radial-gradient(circle, oklch(0.55 0.15 270 / 0.12) 0%, oklch(0.62 0.12 180 / 0.06) 40%, transparent 70%)",
        }}
      />
      <div className="relative z-10 flex flex-1 flex-col items-start gap-6">
        <Badge
          variant="secondary"
          className="px-3 py-1 text-xs font-medium tracking-wide"
        >
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
        <div className="mt-4 flex items-center gap-8 border-t border-border pt-6">
          <StatCounter value={12000} suffix="+" label="Documents processed" delay={300} />
          <div className="h-8 w-px bg-border" />
          <StatCounter value={85} suffix="%" label="Time saved" delay={500} />
          <div className="h-8 w-px bg-border" />
          <StatCounter value={97} suffix="%" label="Accuracy rate" delay={700} />
        </div>
      </div>
      <div className="animate-fade-in relative z-10 flex-1">
        <div className="relative">
          {/* Floating elements with parallax */}
          <div
            ref={floatParallax.ref as React.RefObject<HTMLDivElement>}
            style={floatParallax.style}
          >
            <FloatingElements />
          </div>
          <div className="relative" style={{ perspective: "1200px" }}>
            <div
              ref={cardRef}
              onMouseMove={handleMouseMove}
              onMouseEnter={handleMouseEnter}
              onMouseLeave={handleMouseLeave}
              className="relative aspect-[4/3] w-full cursor-default overflow-hidden rounded-2xl border border-border bg-card"
              style={{
                transform: isHovering
                  ? `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`
                  : "rotateX(0deg) rotateY(0deg)",
                transition: isHovering
                  ? "transform 0.1s ease-out"
                  : "transform 0.5s ease-out",
                transformStyle: "preserve-3d",
                boxShadow: isHovering
                  ? `0 25px 50px -12px oklch(0 0 0 / 0.15), 0 0 0 1px oklch(0.45 0.18 255 / 0.08), 0 0 40px -10px oklch(0.45 0.18 255 / 0.12)`
                  : `0 10px 15px -3px oklch(0 0 0 / 0.06), 0 4px 6px -4px oklch(0 0 0 / 0.04)`,
                transitionProperty: "transform, box-shadow",
              }}
            >
              <div
                className="pointer-events-none absolute inset-x-0 top-0 h-px"
                style={{
                  background: isHovering
                    ? "linear-gradient(90deg, transparent, oklch(0.45 0.18 255 / 0.3), transparent)"
                    : "linear-gradient(90deg, transparent, oklch(0.45 0.18 255 / 0.1), transparent)",
                  transition: "background 0.3s ease",
                }}
              />
              <ProductMockup />
            </div>
          </div>
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
      <ScrollReveal animation="fade-up" duration={500}>
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-8 px-6">
          <p className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
            {t("socialProof.label")}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-4">
            {logos.map((name, i) => (
              <ScrollReveal key={name} animation="fade-up" delay={i * 80} duration={400}>
                <span className="text-sm font-semibold tracking-wider text-muted-foreground/50 uppercase transition-colors hover:text-muted-foreground/80">
                  {name}
                </span>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </ScrollReveal>
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
      <ScrollReveal animation="fade-up" duration={500}>
        <div className="max-w-2xl">
          <h2 className="text-3xl font-bold leading-tight tracking-tight text-foreground">
            {t("howItWorks.heading")}
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
            {t("howItWorks.subheading")}
          </p>
        </div>
      </ScrollReveal>
      <div className="mt-14 space-y-0">
        {STEPS.map((step, i) => (
          <ScrollReveal key={step.key} animation="fade-left" delay={i * 120} duration={500}>
            <div className="relative flex gap-6 border-l border-border pl-8 pb-12 last:pb-0">
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
          </ScrollReveal>
        ))}
      </div>
    </section>
  );
}

/* ---------- StatsSection: scroll-animated counters ---------- */
function StatsSection() {
  return (
    <section className="border-y border-border bg-muted/30 py-16">
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-8 px-6 lg:grid-cols-4">
        {[
          { value: 50, suffix: "%", label: "Time Saved" },
          { value: 10, suffix: "x", label: "Faster Drafting" },
          { value: 99, suffix: "%", label: "Compliance Rate" },
          { value: 500, suffix: "+", label: "Proposals Delivered" },
        ].map((stat, i) => (
          <ScrollReveal key={stat.label} animation="fade-up" delay={i * 150} duration={600}>
            <div className="flex flex-col items-center gap-2 text-center">
              <span className="text-4xl font-bold tracking-tight text-foreground">
                <ScrollAnimatedCounter
                  target={stat.value}
                  suffix={stat.suffix}
                  duration={2000}
                />
              </span>
              <span className="text-sm text-muted-foreground">
                {stat.label}
              </span>
            </div>
          </ScrollReveal>
        ))}
      </div>
    </section>
  );
}

function FeaturesSection() {
  const { t } = useTranslation("landing");
  const features = [
    { key: "extraction", className: "col-span-full lg:col-span-2" },
    { key: "drafts", className: "lg:col-span-1" },
    { key: "audit", className: "lg:col-span-1" },
  ] as const;

  return (
    <section className="gradient-subtle mx-auto max-w-6xl px-6 py-24">
      <ScrollReveal animation="fade-up" duration={500}>
        <div className="max-w-2xl">
          <h2 className="text-3xl font-bold leading-tight tracking-tight text-foreground">
            {t("features.heading")}
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
            {t("features.subheading")}
          </p>
        </div>
      </ScrollReveal>
      <div className="mt-14 grid gap-6 lg:grid-cols-3">
        {features.map((f, i) => (
          <ScrollReveal key={f.key} animation="fade-up" delay={i * 120}>
            <Card3D maxTilt={6}>
              <GlowEffect radius={250} opacity={0.1}>
                <div
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
              </GlowEffect>
            </Card3D>
          </ScrollReveal>
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
      <ScrollReveal animation="fade-up" duration={500}>
        <div className="max-w-2xl">
          <h2 className="text-3xl font-bold leading-tight tracking-tight text-foreground">
            {t("pricing.heading")}
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
            {t("pricing.subheading")}
          </p>
        </div>
      </ScrollReveal>
      <div className="mt-14 grid gap-6 lg:grid-cols-3">
        {tiers.map((tier, i) => {
          const highlighted = tier === "team";
          return (
            <ScrollReveal key={tier} animation="fade-up" delay={i * 150} duration={500}>
              <div
                className={`card-elevated flex flex-col rounded-2xl border p-7 transition-all duration-200 ${
                  highlighted
                    ? "border-primary/50 shadow-md ring-1 ring-primary/20"
                    : "border-border"
                }`}
              >
                <Badge variant={highlighted ? "default" : "secondary"} className="w-fit">
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
                    t(`pricing.tiers.${tier}.features`, { returnObjects: true }) as string[]
                  ).map((feat) => (
                    <li key={feat} className="flex items-start gap-2.5 text-sm leading-relaxed text-muted-foreground">
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
            </ScrollReveal>
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
      <ScrollReveal animation="scale" duration={600}>
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
      </ScrollReveal>
    </section>
  );
}

export function LandingPage() {
  return (
    <div className="flex min-h-svh flex-col">
      <ScrollProgress />
      <HeroSection />
      <SocialProofSection />
      <HowItWorksSection />
      <StatsSection />
      <FeaturesSection />
      <PricingSection />
      <FinalCtaSection />
    </div>
  );
}
