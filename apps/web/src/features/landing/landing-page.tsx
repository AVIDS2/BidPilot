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
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useRef, useState, useEffect, useCallback, type MouseEvent } from "react";
import { Card3D, GlowEffect, ScrollReveal } from "./interactions";
import { useParallax } from "@/hooks/use-parallax";
import { ScrollProgress } from "@/components/ui/scroll-progress";
import { AnimatedCounter } from "@/components/ui/animated-counter";

/* ============================================================
   StatCounter — scroll-triggered number animation
   ============================================================ */

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
      <span
        className="text-2xl font-bold tracking-tight sm:text-3xl"
        style={{ color: "var(--landing-text-primary)" }}
      >
        {current.toLocaleString()}
        {suffix}
      </span>
      <span
        className="text-xs font-medium"
        style={{ color: "oklch(0.65 0.01 250)" }}
      >
        {label}
      </span>
    </div>
  );
}

/* ============================================================
   HeroSection — Serif title, dark canvas, product mockup
   ============================================================ */

function ProductMockup() {
  return (
    <div
      className="flex size-full flex-col overflow-hidden rounded-xl"
      style={{
        background: "var(--landing-surface-1)",
        border: "1px solid oklch(1 0 0 / 8%)",
      }}
    >
      {/* Title bar */}
      <div
        className="flex h-9 items-center gap-1.5 px-3"
        style={{
          borderBottom: "1px solid oklch(1 0 0 / 6%)",
          background: "var(--landing-surface-2)",
        }}
      >
        <span className="size-2.5 rounded-full" style={{ background: "#ff5f57" }} />
        <span className="size-2.5 rounded-full" style={{ background: "#febc2e" }} />
        <span className="size-2.5 rounded-full" style={{ background: "#28c840" }} />
        <span
          className="ml-3 text-[11px] font-medium"
          style={{ color: "oklch(0.55 0.01 250)" }}
        >
          DocPilot — BidPilot RFP Response
        </span>
      </div>
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar icons */}
        <div
          className="hidden w-12 shrink-0 flex-col items-center gap-3 py-3 sm:flex"
          style={{
            borderRight: "1px solid oklch(1 0 0 / 6%)",
            background: "oklch(0.20 0.008 250)",
          }}
        >
          <div
            className="flex size-7 items-center justify-center rounded-lg"
            style={{ background: "oklch(0.68 0.17 264 / 0.12)" }}
          >
            <FolderOpen className="size-3.5" style={{ color: "var(--landing-accent)" }} />
          </div>
          <div className="flex size-7 items-center justify-center rounded-lg">
            <FileText className="size-3.5" style={{ color: "oklch(0.50 0.01 250)" }} />
          </div>
          <div className="flex size-7 items-center justify-center rounded-lg">
            <BotMessageSquare className="size-3.5" style={{ color: "oklch(0.50 0.01 250)" }} />
          </div>
          <div className="flex size-7 items-center justify-center rounded-lg">
            <BarChart3 className="size-3.5" style={{ color: "oklch(0.50 0.01 250)" }} />
          </div>
        </div>
        {/* Document list */}
        <div
          className="hidden w-40 shrink-0 flex-col py-2 lg:flex"
          style={{ borderRight: "1px solid oklch(1 0 0 / 6%)" }}
        >
          <div
            className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: "oklch(0.50 0.01 250)" }}
          >
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
              className="mx-1.5 flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[11px]"
              style={{
                background: doc.active ? "oklch(0.68 0.17 264 / 0.1)" : "transparent",
                color: doc.active ? "var(--landing-accent)" : "oklch(0.50 0.01 250)",
                fontWeight: doc.active ? 500 : 400,
              }}
            >
              <FileText className="size-3 shrink-0" />
              <span className="truncate">{doc.name}</span>
            </div>
          ))}
        </div>
        {/* Editor area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <div
            className="flex h-8 items-center gap-2 px-3"
            style={{ borderBottom: "1px solid oklch(1 0 0 / 6%)" }}
          >
            <span
              className="rounded px-1.5 py-0.5 text-[9px] font-semibold"
              style={{
                background: "oklch(0.68 0.17 264 / 0.12)",
                color: "var(--landing-accent)",
              }}
            >
              AI Draft
            </span>
            <div className="h-3 w-px" style={{ background: "oklch(1 0 0 / 10%)" }} />
            <div className="flex gap-1">
              {["B", "I", "U"].map((l) => (
                <span
                  key={l}
                  className="flex size-5 items-center justify-center rounded text-[10px] font-bold"
                  style={{ color: "oklch(0.50 0.01 250)" }}
                >
                  {l}
                </span>
              ))}
            </div>
          </div>
          <div className="flex-1 space-y-3 overflow-hidden p-4">
            <div className="space-y-1">
              <div className="h-2.5 w-3/4 rounded" style={{ background: "oklch(1 0 0 / 0.08)" }} />
              <div className="h-2.5 w-full rounded" style={{ background: "oklch(1 0 0 / 0.06)" }} />
              <div className="h-2.5 w-5/6 rounded" style={{ background: "oklch(1 0 0 / 0.06)" }} />
            </div>
            <div className="space-y-1">
              <div className="h-2 w-1/2 rounded" style={{ background: "oklch(0.68 0.17 264 / 0.2)" }} />
              <div className="h-2.5 w-full rounded" style={{ background: "oklch(1 0 0 / 0.06)" }} />
              <div className="h-2.5 w-4/5 rounded" style={{ background: "oklch(1 0 0 / 0.06)" }} />
              <div className="h-2.5 w-2/3 rounded" style={{ background: "oklch(1 0 0 / 0.04)" }} />
            </div>
            <div className="space-y-1">
              <div className="h-2 w-2/5 rounded" style={{ background: "oklch(0.68 0.17 264 / 0.2)" }} />
              <div className="h-2.5 w-full rounded" style={{ background: "oklch(1 0 0 / 0.06)" }} />
              <div className="h-2.5 w-3/4 rounded" style={{ background: "oklch(1 0 0 / 0.06)" }} />
            </div>
            <div className="flex items-center gap-1">
              <div className="h-4 w-px animate-pulse" style={{ background: "var(--landing-accent)" }} />
              <span className="text-[9px]" style={{ color: "oklch(0.68 0.17 264 / 0.6)" }}>
                AI writing...
              </span>
            </div>
          </div>
        </div>
        {/* AI Assistant panel */}
        <div
          className="hidden w-44 shrink-0 flex-col xl:flex"
          style={{
            borderLeft: "1px solid oklch(1 0 0 / 6%)",
            background: "oklch(0.14 0.008 250)",
          }}
        >
          <div
            className="flex items-center gap-1.5 px-3 py-2"
            style={{ borderBottom: "1px solid oklch(1 0 0 / 6%)" }}
          >
            <Sparkles className="size-3" style={{ color: "var(--landing-accent)" }} />
            <span className="text-[11px] font-semibold" style={{ color: "var(--landing-text-primary)" }}>
              AI Assistant
            </span>
          </div>
          <div className="flex-1 space-y-2.5 p-3">
            <div
              className="rounded-lg p-2"
              style={{ background: "oklch(0.68 0.17 264 / 0.06)" }}
            >
              <p className="text-[10px] leading-relaxed" style={{ color: "oklch(0.55 0.01 250)" }}>
                Draft generated from 3 evidence sources. Confidence: 94%
              </p>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="size-3" style={{ color: "#34d399" }} />
                <span className="text-[10px]" style={{ color: "oklch(0.55 0.01 250)" }}>
                  Section 2.1 completed
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="size-3 animate-spin rounded-full"
                  style={{
                    border: "1px solid var(--landing-accent)",
                    borderTopColor: "transparent",
                  }}
                />
                <span className="text-[10px]" style={{ color: "oklch(0.55 0.01 250)" }}>
                  Analyzing Section 3.2
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="size-3 rounded-full"
                  style={{ border: "1px solid oklch(1 0 0 / 15%)" }}
                />
                <span className="text-[10px]" style={{ color: "oklch(0.40 0.01 250)" }}>
                  Section 4 pending
                </span>
              </div>
            </div>
            <div
              className="mt-2 rounded-lg p-2"
              style={{
                border: "1px solid oklch(1 0 0 / 8%)",
                background: "var(--landing-surface-2)",
              }}
            >
              <p className="text-[9px] font-medium" style={{ color: "oklch(0.55 0.01 250)" }}>
                Evidence Used
              </p>
              <div className="mt-1 space-y-1">
                {["Contract Section 5.2", "Past Performance DB", "Compliance Guide"].map(
                  (src) => (
                    <div
                      key={src}
                      className="flex items-center gap-1 text-[9px]"
                      style={{ color: "oklch(0.65 0.01 250)" }}
                    >
                      <div
                        className="size-1 rounded-full"
                        style={{ background: "oklch(0.68 0.17 264 / 0.5)" }}
                      />
                      {src}
                    </div>
                  ),
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* Status bar */}
      <div
        className="flex h-6 items-center justify-between px-3"
        style={{
          borderTop: "1px solid oklch(1 0 0 / 6%)",
          background: "oklch(0.14 0.008 250)",
        }}
      >
        <span className="text-[9px]" style={{ color: "oklch(0.45 0.01 250)" }}>
          3 sections complete
        </span>
        <span className="text-[9px]" style={{ color: "oklch(0.45 0.01 250)" }}>
          Last saved 2 min ago
        </span>
      </div>
    </div>
  );
}

function HeroSection() {
  const { t } = useTranslation("landing");
  const cardRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [isHovering, setIsHovering] = useState(false);
  const glowParallax = useParallax({ speed: 0.12 });

  const handleMouseMove = useCallback((e: MouseEvent<HTMLDivElement>) => {
    const el = cardRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setTilt({
      x: (y - 0.5) * -12,
      y: (x - 0.5) * 12,
    });
  }, []);

  const handleMouseEnter = useCallback(() => setIsHovering(true), []);
  const handleMouseLeave = useCallback(() => {
    setIsHovering(false);
    setTilt({ x: 0, y: 0 });
  }, []);

  return (
    <section
      className="gradient-hero relative mx-auto flex w-full max-w-5xl flex-col items-center gap-10 px-6 pt-32 pb-20 text-center"
      style={{ background: "var(--landing-canvas)" }}
    >
      {/* Dot grid pattern */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          opacity: 0.04,
          backgroundImage:
            "radial-gradient(circle, oklch(0.45 0.18 255) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />
      {/* Gradient orb: top-right (lavender blue) */}
      <div
        ref={glowParallax.ref as React.RefObject<HTMLDivElement>}
        className="landing-hero-orb-1 pointer-events-none absolute -top-40 -right-40 size-[600px] rounded-full blur-[120px]"
        style={{
          background:
            "radial-gradient(circle, oklch(0.42 0.16 264 / 0.30) 0%, oklch(0.35 0.12 270 / 0.10) 50%, transparent 70%)",
          ...glowParallax.style,
        }}
      />
      {/* Gradient orb: bottom-left (warm teal) */}
      <div
        className="landing-hero-orb-2 pointer-events-none absolute -bottom-48 -left-40 size-[500px] rounded-full blur-[120px]"
        style={{
          background:
            "radial-gradient(circle, oklch(0.55 0.12 190 / 0.20) 0%, oklch(0.45 0.10 200 / 0.06) 50%, transparent 70%)",
        }}
      />
      {/* Top glow line */}
      <div
        className="landing-hero-glow-pulse pointer-events-none absolute top-0 left-1/2 h-px w-[600px] -translate-x-1/2"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, oklch(0.68 0.17 264 / 0.4) 50%, transparent 100%)",
        }}
      />
      {/* Bottom hairline */}
      <div
        className="pointer-events-none absolute bottom-0 left-0 h-px w-full"
        style={{
          background:
            "linear-gradient(90deg, transparent, var(--landing-hairline), transparent)",
        }}
      />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center gap-6">
        <Badge
          variant="secondary"
          className="px-3 py-1 text-xs font-medium tracking-wide"
        >
          {t("socialProof.label")}
        </Badge>
        <h1
          className="max-w-3xl text-5xl font-semibold leading-[1.1] tracking-tight sm:text-6xl lg:text-7xl"
          style={{
            fontFamily: "var(--font-heading)",
            color: "var(--landing-text-primary)",
            letterSpacing: "-0.03em",
          }}
        >
          {t("hero.title")}
        </h1>
        <p
          className="max-w-xl text-lg leading-relaxed"
          style={{ color: "var(--landing-text-secondary)" }}
        >
          {t("hero.description")}
        </p>
        <div className="flex items-center gap-3 pt-2">
          <Link to="/signup">
            <Button
              size="lg"
              className="h-11 rounded-full px-6 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
              style={{
                background: "var(--landing-warm)",
                color: "#fff",
              }}
            >
              {t("hero.getStarted")}
              <ArrowRight className="ml-1 size-4" />
            </Button>
          </Link>
          <Link to="/pricing">
            <Button
              variant="outline"
              size="lg"
              className="h-11 rounded-full px-6 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
              style={{
                borderColor: "var(--landing-hairline)",
                color: "var(--landing-text-secondary)",
              }}
            >
              {t("hero.viewPricing")}
            </Button>
          </Link>
        </div>
        <div
          className="mt-4 flex items-center gap-8 pt-6"
          style={{ borderTop: "1px solid var(--landing-hairline)" }}
        >
          <StatCounter value={12000} suffix="+" label="Documents processed" delay={300} />
          <div className="h-8 w-px" style={{ background: "var(--landing-hairline)" }} />
          <StatCounter value={85} suffix="%" label="Time saved" delay={500} />
          <div className="h-8 w-px" style={{ background: "var(--landing-hairline)" }} />
          <StatCounter value={97} suffix="%" label="Accuracy rate" delay={700} />
        </div>
      </div>

      {/* Product mockup */}
      <div className="animate-fade-in relative z-10 w-full max-w-4xl">
        <div
          className="landing-hero-glow-pulse-slow pointer-events-none absolute -top-20 left-1/2 h-[400px] w-[700px] -translate-x-1/2 rounded-full blur-[100px]"
          style={{
            background:
              "radial-gradient(ellipse, oklch(0.68 0.17 264 / 0.12) 0%, oklch(0.55 0.15 270 / 0.04) 50%, transparent 70%)",
          }}
        />
        <div className="relative" style={{ perspective: "1200px" }}>
          <div
            ref={cardRef}
            onMouseMove={handleMouseMove}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            className="relative aspect-[16/10] w-full cursor-default overflow-hidden rounded-2xl"
            style={{
              transform: isHovering
                ? `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`
                : "rotateX(0deg) rotateY(0deg)",
              transition: isHovering
                ? "transform 0.1s ease-out"
                : "transform 0.5s ease-out",
              transformStyle: "preserve-3d",
              border: "1px solid oklch(1 0 0 / 8%)",
              boxShadow: isHovering
                ? `0 25px 50px -12px oklch(0 0 0 / 0.3), 0 0 0 1px oklch(0.68 0.17 264 / 0.1), 0 0 60px -15px oklch(0.68 0.17 264 / 0.12)`
                : `0 10px 15px -3px oklch(0 0 0 / 0.2), 0 4px 6px -4px oklch(0 0 0 / 0.15)`,
              transitionProperty: "transform, box-shadow",
            }}
          >
            {/* Top edge glow */}
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-px"
              style={{
                background: isHovering
                  ? "linear-gradient(90deg, transparent, oklch(0.68 0.17 264 / 0.3), transparent)"
                  : "linear-gradient(90deg, transparent, oklch(0.68 0.17 264 / 0.1), transparent)",
                transition: "background 0.3s ease",
              }}
            />
            <ProductMockup />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ============================================================
   SocialProofSection — Refined logos with SVG marks
   ============================================================ */

const LOGOS = [
  { name: "Contour Design", letter: "C" },
  { name: "Harbor Group", letter: "H" },
  { name: "Northway Systems", letter: "N" },
  { name: "Atria Capital", letter: "A" },
  { name: "Vantage Partners", letter: "V" },
];

function SocialProofSection() {
  const { t } = useTranslation("landing");
  return (
    <section
      className="py-14"
      style={{ background: "var(--landing-canvas)" }}
    >
      <ScrollReveal animation="fade-up" duration={500}>
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-8 px-6">
          <p
            className="text-sm font-medium tracking-wide uppercase"
            style={{ color: "oklch(0.50 0.01 250)" }}
          >
            {t("socialProof.label")}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6">
            {LOGOS.map((logo, i) => (
              <ScrollReveal key={logo.name} animation="fade-up" delay={i * 80} duration={400}>
                <div className="group flex items-center gap-3 transition-opacity hover:opacity-100" style={{ opacity: 0.5 }}>
                  <div
                    className="flex size-8 items-center justify-center rounded-lg text-xs font-bold transition-colors"
                    style={{
                      background: "oklch(1 0 0 / 0.06)",
                      color: "oklch(0.60 0.01 250)",
                      border: "1px solid oklch(1 0 0 / 0.08)",
                    }}
                  >
                    {logo.letter}
                  </div>
                  <span
                    className="text-sm font-semibold tracking-wide"
                    style={{ color: "oklch(0.60 0.01 250)" }}
                  >
                    {logo.name}
                  </span>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </ScrollReveal>
    </section>
  );
}

/* ============================================================
   HowItWorksSection — Timeline with connecting line
   ============================================================ */

const STEPS = [
  { key: "upload", icon: FileSearch, num: 1 },
  { key: "generate", icon: PenTool, num: 2 },
  { key: "review", icon: ShieldCheck, num: 3 },
] as const;

function HowItWorksSection() {
  const { t } = useTranslation("landing");
  return (
    <section className="mx-auto max-w-5xl px-6 py-24">
      <ScrollReveal animation="fade-up" duration={500}>
        <div className="max-w-2xl">
          <h2
            className="text-3xl font-bold leading-tight tracking-tight"
            style={{
              fontFamily: "var(--font-heading)",
              color: "var(--foreground)",
            }}
          >
            {t("howItWorks.heading")}
          </h2>
          <p className="mt-4 text-lg leading-relaxed" style={{ color: "var(--muted-foreground)" }}>
            {t("howItWorks.subheading")}
          </p>
        </div>
      </ScrollReveal>
      <div className="mt-14 space-y-0">
        {STEPS.map((step, i) => (
          <ScrollReveal key={step.key} animation="fade-left" delay={i * 120} duration={500}>
            <div
              className="relative flex gap-6 pl-8 pb-12 last:pb-0"
              style={{ borderLeft: "1px solid var(--border)" }}
            >
              {/* Step number */}
              <span
                className="absolute -left-3.5 top-0 flex size-7 items-center justify-center rounded-full text-xs font-semibold shadow-xs"
                style={{
                  border: "1px solid var(--border)",
                  background: "var(--background)",
                  color: "var(--foreground)",
                }}
              >
                {step.num}
              </span>
              <div className="pt-0.5">
                <div className="mb-2 flex items-center gap-2.5">
                  <step.icon className="size-5" style={{ color: "var(--primary)" }} />
                  <h3 className="text-base font-semibold" style={{ color: "var(--foreground)" }}>
                    {t(`howItWorks.steps.${step.key}.title`)}
                  </h3>
                </div>
                <p className="max-w-md text-sm leading-relaxed" style={{ color: "var(--muted-foreground)" }}>
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

/* ============================================================
   StatsSection — Scroll-animated counters
   ============================================================ */

function StatsSection() {
  return (
    <section
      className="py-16"
      style={{
        borderTop: "1px solid var(--border)",
        borderBottom: "1px solid var(--border)",
        background: "var(--muted)",
      }}
    >
      <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 px-6 lg:grid-cols-4">
        {[
          { value: 50, suffix: "%", label: "Time Saved" },
          { value: 10, suffix: "x", label: "Faster Drafting" },
          { value: 99, suffix: "%", label: "Compliance Rate" },
          { value: 500, suffix: "+", label: "Proposals Delivered" },
        ].map((stat, i) => (
          <ScrollReveal key={stat.label} animation="fade-up" delay={i * 150} duration={600}>
            <div className="flex flex-col items-center gap-2 text-center">
              <span
                className="text-4xl font-bold tracking-tight"
                style={{ color: "var(--foreground)" }}
              >
                <AnimatedCounter
                  target={stat.value}
                  suffix={stat.suffix}
                  duration={2000}
                />
              </span>
              <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                {stat.label}
              </span>
            </div>
          </ScrollReveal>
        ))}
      </div>
    </section>
  );
}

/* ============================================================
   FeaturesSection — Dark cards with accent glow (Linear style)
   ============================================================ */

const FEATURE_ICONS = [FileSearch, PenTool, ShieldCheck];

function FeaturesSection() {
  const { t } = useTranslation("landing");
  const features = [
    { key: "extraction", className: "col-span-full lg:col-span-2" },
    { key: "drafts", className: "lg:col-span-1" },
    { key: "audit", className: "lg:col-span-1" },
  ] as const;

  return (
    <section
      className="mx-auto max-w-5xl px-6 py-24"
      style={{ background: "var(--landing-canvas)" }}
    >
      <ScrollReveal animation="fade-up" duration={500}>
        <div className="max-w-2xl">
          <h2
            className="text-3xl font-bold leading-tight tracking-tight"
            style={{
              fontFamily: "var(--font-heading)",
              color: "var(--landing-text-primary)",
            }}
          >
            {t("features.heading")}
          </h2>
          <p
            className="mt-4 text-lg leading-relaxed"
            style={{ color: "var(--landing-text-secondary)" }}
          >
            {t("features.subheading")}
          </p>
        </div>
      </ScrollReveal>
      <div className="mt-14 grid gap-6 lg:grid-cols-3">
        {features.map((f, i) => {
          const Icon = FEATURE_ICONS[i];
          return (
            <ScrollReveal key={f.key} animation="fade-up" delay={i * 120}>
              <Card3D maxTilt={6}>
                <GlowEffect
                  radius={250}
                  opacity={0.08}
                  color="oklch(0.68 0.17 264)"
                >
                  <div
                    className={`landing-card flex flex-col justify-between rounded-2xl p-7 transition-all duration-300 ${f.className}`}
                  >
                    <div>
                      <div
                        className="mb-4 flex size-10 items-center justify-center rounded-xl"
                        style={{
                          background: "oklch(0.68 0.17 264 / 0.1)",
                          border: "1px solid oklch(0.68 0.17 264 / 0.15)",
                        }}
                      >
                        <Icon className="size-5" style={{ color: "var(--landing-accent)" }} />
                      </div>
                      <h3
                        className="text-lg font-semibold"
                        style={{ color: "var(--landing-text-primary)" }}
                      >
                        {t(`features.${f.key}.title`)}
                      </h3>
                      <p
                        className="mt-3 text-sm leading-relaxed"
                        style={{ color: "var(--landing-text-secondary)" }}
                      >
                        {t(`features.${f.key}.description`)}
                      </p>
                    </div>
                    <div
                      className="mt-8 flex items-center gap-1.5 text-sm font-medium transition-colors"
                      style={{ color: "var(--landing-accent)" }}
                    >
                      {t(`features.${f.key}.learnMore`)}
                      <ArrowRight className="size-3.5" />
                    </div>
                  </div>
                </GlowEffect>
              </Card3D>
            </ScrollReveal>
          );
        })}
      </div>
    </section>
  );
}

/* ============================================================
   PricingSection — Linear-style dark pricing cards
   ============================================================ */

function PricingSection() {
  const { t } = useTranslation("landing");
  const tiers = ["starter", "team", "enterprise"] as const;
  return (
    <section
      className="mx-auto max-w-5xl px-6 py-24"
      style={{
        background: "var(--landing-canvas)",
        borderTop: "1px solid var(--landing-hairline)",
      }}
    >
      <ScrollReveal animation="fade-up" duration={500}>
        <div className="max-w-2xl">
          <h2
            className="text-3xl font-bold leading-tight tracking-tight"
            style={{
              fontFamily: "var(--font-heading)",
              color: "var(--landing-text-primary)",
            }}
          >
            {t("pricing.heading")}
          </h2>
          <p
            className="mt-4 text-lg leading-relaxed"
            style={{ color: "var(--landing-text-secondary)" }}
          >
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
                className={`flex flex-col rounded-2xl p-7 transition-all duration-300 ${
                  highlighted ? "landing-card-highlight" : "landing-card"
                }`}
                style={{
                  background: highlighted
                    ? "linear-gradient(145deg, oklch(0.68 0.17 264 / 0.06), var(--landing-surface-1))"
                    : undefined,
                }}
              >
                <Badge variant={highlighted ? "default" : "secondary"} className="w-fit">
                  {t(`pricing.tiers.${tier}.label`)}
                </Badge>
                <p
                  className="mt-5 text-4xl font-bold tracking-tight"
                  style={{ color: "var(--landing-text-primary)" }}
                >
                  {t(`pricing.tiers.${tier}.price`)}
                </p>
                <p
                  className="mt-2 text-sm leading-relaxed"
                  style={{ color: "var(--landing-text-secondary)" }}
                >
                  {t(`pricing.tiers.${tier}.sub`)}
                </p>
                <ul className="mt-8 flex-1 space-y-3">
                  {(
                    t(`pricing.tiers.${tier}.features`, { returnObjects: true }) as string[]
                  ).map((feat) => (
                    <li
                      key={feat}
                      className="flex items-start gap-2.5 text-sm leading-relaxed"
                      style={{ color: "var(--landing-text-secondary)" }}
                    >
                      <CheckCircle2
                        className="mt-0.5 size-4 shrink-0"
                        style={{ color: "var(--landing-accent)" }}
                      />
                      {feat}
                    </li>
                  ))}
                </ul>
                <Link to="/signup" className="mt-8">
                  <Button
                    variant={highlighted ? "default" : "outline"}
                    className="w-full transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
                    style={
                      highlighted
                        ? {
                            background: "var(--landing-warm)",
                            color: "#fff",
                            borderColor: "transparent",
                          }
                        : {
                            borderColor: "var(--landing-hairline)",
                            color: "var(--landing-text-secondary)",
                          }
                    }
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

/* ============================================================
   FinalCtaSection — Vercel-inspired gradient + coral CTA
   ============================================================ */

function FinalCtaSection() {
  const { t } = useTranslation("landing");
  return (
    <section
      className="relative overflow-hidden py-24"
      style={{
        background: "linear-gradient(180deg, #010102, #06081a)",
        borderTop: "1px solid var(--landing-hairline)",
      }}
    >
      {/* Gradient orbs */}
      <div
        className="landing-cta-orb-1 pointer-events-none absolute -top-32 left-1/4 size-[500px] rounded-full blur-[140px]"
        style={{
          background:
            "radial-gradient(circle, oklch(0.68 0.17 264 / 0.15), transparent 60%)",
        }}
      />
      <div
        className="landing-cta-orb-2 pointer-events-none absolute -bottom-32 right-1/4 size-[400px] rounded-full blur-[140px]"
        style={{
          background:
            "radial-gradient(circle, oklch(0.55 0.12 190 / 0.10), transparent 60%)",
        }}
      />
      <ScrollReveal animation="scale" duration={600}>
        <div className="relative z-10 mx-auto flex max-w-5xl flex-col items-center gap-6 px-6 text-center">
          <h2
            className="max-w-2xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl"
            style={{
              fontFamily: "var(--font-heading)",
              color: "var(--landing-text-primary)",
              letterSpacing: "-0.03em",
            }}
          >
            {t("finalCta.heading")}
          </h2>
          <p
            className="max-w-md text-lg leading-relaxed"
            style={{ color: "var(--landing-text-secondary)" }}
          >
            {t("finalCta.subheading")}
          </p>
          <Link to="/signup">
            <Button
              size="lg"
              className="h-12 rounded-full px-8 text-base transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
              style={{
                background: "var(--landing-warm)",
                color: "#fff",
              }}
            >
              {t("finalCta.cta")}
              <ArrowRight className="ml-1.5 size-4" />
            </Button>
          </Link>
        </div>
      </ScrollReveal>
    </section>
  );
}

/* ============================================================
   LandingPage — Main export
   ============================================================ */

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
