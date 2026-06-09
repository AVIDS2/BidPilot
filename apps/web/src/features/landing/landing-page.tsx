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
   CinematicHero — 电影级Hero区域（老师风格）
   ============================================================ */

function AnimatedText({ text, className, style }: { text: string; className?: string; style?: React.CSSProperties }) {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.5 }
    );

    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <h1 ref={ref} className={className} style={style}>
      {text.split("").map((char, index) => (
        <span
          key={index}
          className="anim-char"
          style={{ "--i": index } as React.CSSProperties}
        >
          {char === " " ? " " : char}
        </span>
      ))}
      {isVisible && <span className="animate-in" />}
    </h1>
  );
}

function CinematicHero() {
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
      className="relative mx-auto flex min-h-[100dvh] w-full max-w-7xl flex-col items-center justify-center gap-12 px-6 py-24 text-center"
      style={{ background: "#0a0a0a" }}
    >
      {/* 网格背景 */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          opacity: 0.03,
          backgroundImage:
            "radial-gradient(circle, rgba(132, 204, 22, 0.3) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />

      {/* 青柠绿渐变光晕 - 右上 */}
      <div
        ref={glowParallax.ref as React.RefObject<HTMLDivElement>}
        className="landing-hero-orb-1 pointer-events-none absolute -top-40 -right-40 size-[600px] rounded-full blur-[120px]"
        style={{
          background:
            "radial-gradient(circle, rgba(132, 204, 22, 0.25) 0%, rgba(132, 204, 22, 0.08) 50%, transparent 70%)",
          ...glowParallax.style,
        }}
      />

      {/* 青柠绿渐变光晕 - 左下 */}
      <div
        className="landing-hero-orb-2 pointer-events-none absolute -bottom-48 -left-40 size-[500px] rounded-full blur-[120px]"
        style={{
          background:
            "radial-gradient(circle, rgba(163, 230, 53, 0.15) 0%, rgba(132, 204, 22, 0.05) 50%, transparent 70%)",
        }}
      />

      {/* 顶部青柠绿光线 */}
      <div
        className="landing-hero-glow-pulse pointer-events-none absolute top-0 left-1/2 h-px w-[600px] -translate-x-1/2"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(132, 204, 22, 0.4) 50%, transparent 100%)",
        }}
      />

      {/* 底部分隔线 */}
      <div
        className="pointer-events-none absolute bottom-0 left-0 h-px w-full"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(163, 163, 163, 0.1), transparent)",
        }}
      />

      {/* 影视风格标注 - 左上 */}
      <div className="pointer-events-none absolute top-8 left-8 flex items-center gap-2">
        <div className="size-2 rounded-full bg-[#84cc16]" />
        <span className="text-[10px] font-medium tracking-widest text-[#737373] uppercase">
          DocPilot v1.0
        </span>
      </div>

      {/* 影视风格标注 - 右上 */}
      <div className="pointer-events-none absolute top-8 right-8 flex items-center gap-2">
        <span className="text-[10px] font-medium tracking-widest text-[#737373] uppercase">
          16:9 OVERSCAN
        </span>
        <div className="size-2 rounded-full bg-[#84cc16]" />
      </div>

      {/* 内容 */}
      <div className="relative z-10 flex flex-col items-center gap-8">
        <Badge
          variant="secondary"
          className="rounded-full px-4 py-1.5 text-xs font-medium tracking-wide"
          style={{
            background: "rgba(132, 204, 22, 0.1)",
            color: "#84cc16",
            border: "1px solid rgba(132, 204, 22, 0.2)",
          }}
        >
          {t("socialProof.label")}
        </Badge>

        <AnimatedText
          text={t("hero.title")}
          className="max-w-4xl text-5xl font-semibold leading-[1.1] tracking-tight sm:text-6xl lg:text-7xl"
          style={{
            fontFamily: "var(--font-heading)",
            color: "#ffffff",
            letterSpacing: "-0.03em",
          }}
        />

        <p
          className="max-w-2xl text-lg leading-relaxed"
          style={{ color: "#a3a3a3" }}
        >
          {t("hero.description")}
        </p>

        <div className="flex items-center gap-4 pt-4">
          <Link to="/signup">
            <Button
              size="lg"
              className="h-12 rounded-full px-8 text-base font-medium transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg"
              style={{
                background: "#84cc16",
                color: "#0a0a0a",
                boxShadow: "0 0 30px rgba(132, 204, 22, 0.3)",
              }}
            >
              {t("hero.getStarted")}
              <ArrowRight className="ml-2 size-4" />
            </Button>
          </Link>
          <Link to="/pricing">
            <Button
              variant="outline"
              size="lg"
              className="h-12 rounded-full px-8 text-base font-medium transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
              style={{
                borderColor: "rgba(163, 163, 163, 0.2)",
                color: "#a3a3a3",
                background: "transparent",
              }}
            >
              {t("hero.viewPricing")}
            </Button>
          </Link>
        </div>

        {/* 统计数据 */}
        <div
          className="mt-8 flex items-center gap-8 pt-8"
          style={{ borderTop: "1px solid rgba(163, 163, 163, 0.1)" }}
        >
          <StatCounter value={12000} suffix="+" label="Documents processed" delay={300} />
          <div className="h-8 w-px" style={{ background: "rgba(163, 163, 163, 0.1)" }} />
          <StatCounter value={85} suffix="%" label="Time saved" delay={500} />
          <div className="h-8 w-px" style={{ background: "rgba(163, 163, 163, 0.1)" }} />
          <StatCounter value={97} suffix="%" label="Accuracy rate" delay={700} />
        </div>
      </div>

      {/* 产品界面模拟 */}
      <div className="animate-fade-in relative z-10 w-full max-w-5xl">
        <div
          className="landing-hero-glow-pulse-slow pointer-events-none absolute -top-20 left-1/2 h-[400px] w-[700px] -translate-x-1/2 rounded-full blur-[100px]"
          style={{
            background:
              "radial-gradient(ellipse, rgba(132, 204, 22, 0.12) 0%, rgba(132, 204, 22, 0.04) 50%, transparent 70%)",
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
              border: "1px solid rgba(163, 163, 163, 0.1)",
              boxShadow: isHovering
                ? `0 25px 50px -12px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(132, 204, 22, 0.1), 0 0 60px -15px rgba(132, 204, 22, 0.12)`
                : `0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -4px rgba(0, 0, 0, 0.15)`,
              transitionProperty: "transform, box-shadow",
            }}
          >
            {/* 顶部青柠绿光线 */}
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-px"
              style={{
                background: isHovering
                  ? "linear-gradient(90deg, transparent, rgba(132, 204, 22, 0.3), transparent)"
                  : "linear-gradient(90deg, transparent, rgba(132, 204, 22, 0.1), transparent)",
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

function ProductMockup() {
  return (
    <div
      className="flex size-full flex-col overflow-hidden rounded-xl"
      style={{
        background: "#171717",
        border: "1px solid rgba(163, 163, 163, 0.1)",
      }}
    >
      {/* 标题栏 */}
      <div
        className="flex h-9 items-center gap-1.5 px-3"
        style={{
          borderBottom: "1px solid rgba(163, 163, 163, 0.1)",
          background: "#262626",
        }}
      >
        <span className="size-2.5 rounded-full" style={{ background: "#ff5f57" }} />
        <span className="size-2.5 rounded-full" style={{ background: "#febc2e" }} />
        <span className="size-2.5 rounded-full" style={{ background: "#28c840" }} />
        <span
          className="ml-3 text-[11px] font-medium"
          style={{ color: "#737373" }}
        >
          DocPilot — BidPilot RFP Response
        </span>
      </div>
      <div className="flex flex-1 overflow-hidden">
        {/* 侧边栏图标 */}
        <div
          className="hidden w-12 shrink-0 flex-col items-center gap-3 py-3 sm:flex"
          style={{
            borderRight: "1px solid rgba(163, 163, 163, 0.1)",
            background: "#0a0a0a",
          }}
        >
          <div
            className="flex size-7 items-center justify-center rounded-lg"
            style={{ background: "rgba(132, 204, 22, 0.12)" }}
          >
            <FolderOpen className="size-3.5" style={{ color: "#84cc16" }} />
          </div>
          <div className="flex size-7 items-center justify-center rounded-lg">
            <FileText className="size-3.5" style={{ color: "#737373" }} />
          </div>
          <div className="flex size-7 items-center justify-center rounded-lg">
            <BotMessageSquare className="size-3.5" style={{ color: "#737373" }} />
          </div>
          <div className="flex size-7 items-center justify-center rounded-lg">
            <BarChart3 className="size-3.5" style={{ color: "#737373" }} />
          </div>
        </div>
        {/* 文档列表 */}
        <div
          className="hidden w-40 shrink-0 flex-col py-2 lg:flex"
          style={{ borderRight: "1px solid rgba(163, 163, 163, 0.1)" }}
        >
          <div
            className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: "#737373" }}
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
                background: doc.active ? "rgba(132, 204, 22, 0.1)" : "transparent",
                color: doc.active ? "#84cc16" : "#737373",
                fontWeight: doc.active ? 500 : 400,
              }}
            >
              <FileText className="size-3 shrink-0" />
              <span className="truncate">{doc.name}</span>
            </div>
          ))}
        </div>
        {/* 编辑器区域 */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <div
            className="flex h-8 items-center gap-2 px-3"
            style={{ borderBottom: "1px solid rgba(163, 163, 163, 0.1)" }}
          >
            <span
              className="rounded px-1.5 py-0.5 text-[9px] font-semibold"
              style={{
                background: "rgba(132, 204, 22, 0.12)",
                color: "#84cc16",
              }}
            >
              AI Draft
            </span>
            <div className="h-3 w-px" style={{ background: "rgba(163, 163, 163, 0.1)" }} />
            <div className="flex gap-1">
              {["B", "I", "U"].map((l) => (
                <span
                  key={l}
                  className="flex size-5 items-center justify-center rounded text-[10px] font-bold"
                  style={{ color: "#737373" }}
                >
                  {l}
                </span>
              ))}
            </div>
          </div>
          <div className="flex-1 space-y-3 overflow-hidden p-4">
            <div className="space-y-1">
              <div className="h-2.5 w-3/4 rounded" style={{ background: "rgba(255, 255, 255, 0.08)" }} />
              <div className="h-2.5 w-full rounded" style={{ background: "rgba(255, 255, 255, 0.06)" }} />
              <div className="h-2.5 w-5/6 rounded" style={{ background: "rgba(255, 255, 255, 0.06)" }} />
            </div>
            <div className="space-y-1">
              <div className="h-2 w-1/2 rounded" style={{ background: "rgba(132, 204, 22, 0.2)" }} />
              <div className="h-2.5 w-full rounded" style={{ background: "rgba(255, 255, 255, 0.06)" }} />
              <div className="h-2.5 w-4/5 rounded" style={{ background: "rgba(255, 255, 255, 0.06)" }} />
              <div className="h-2.5 w-2/3 rounded" style={{ background: "rgba(255, 255, 255, 0.04)" }} />
            </div>
            <div className="space-y-1">
              <div className="h-2 w-2/5 rounded" style={{ background: "rgba(132, 204, 22, 0.2)" }} />
              <div className="h-2.5 w-full rounded" style={{ background: "rgba(255, 255, 255, 0.06)" }} />
              <div className="h-2.5 w-3/4 rounded" style={{ background: "rgba(255, 255, 255, 0.06)" }} />
            </div>
            <div className="flex items-center gap-1">
              <div className="h-4 w-px animate-pulse" style={{ background: "#84cc16" }} />
              <span className="text-[9px]" style={{ color: "rgba(132, 204, 22, 0.6)" }}>
                AI writing...
              </span>
            </div>
          </div>
        </div>
        {/* AI助手面板 */}
        <div
          className="hidden w-44 shrink-0 flex-col xl:flex"
          style={{
            borderLeft: "1px solid rgba(163, 163, 163, 0.1)",
            background: "#0a0a0a",
          }}
        >
          <div
            className="flex items-center gap-1.5 px-3 py-2"
            style={{ borderBottom: "1px solid rgba(163, 163, 163, 0.1)" }}
          >
            <Sparkles className="size-3" style={{ color: "#84cc16" }} />
            <span className="text-[11px] font-semibold" style={{ color: "#ffffff" }}>
              AI Assistant
            </span>
          </div>
          <div className="flex-1 space-y-2.5 p-3">
            <div
              className="rounded-lg p-2"
              style={{ background: "rgba(132, 204, 22, 0.06)" }}
            >
              <p className="text-[10px] leading-relaxed" style={{ color: "#a3a3a3" }}>
                Draft generated from 3 evidence sources. Confidence: 94%
              </p>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="size-3" style={{ color: "#84cc16" }} />
                <span className="text-[10px]" style={{ color: "#a3a3a3" }}>
                  Section 2.1 completed
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="size-3 animate-spin rounded-full"
                  style={{
                    border: "1px solid #84cc16",
                    borderTopColor: "transparent",
                  }}
                />
                <span className="text-[10px]" style={{ color: "#a3a3a3" }}>
                  Analyzing Section 3.2
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="size-3 rounded-full"
                  style={{ border: "1px solid rgba(163, 163, 163, 0.15)" }}
                />
                <span className="text-[10px]" style={{ color: "#737373" }}>
                  Section 4 pending
                </span>
              </div>
            </div>
            <div
              className="mt-2 rounded-lg p-2"
              style={{
                border: "1px solid rgba(163, 163, 163, 0.1)",
                background: "#262626",
              }}
            >
              <p className="text-[9px] font-medium" style={{ color: "#a3a3a3" }}>
                Evidence Used
              </p>
              <div className="mt-1 space-y-1">
                {["Contract Section 5.2", "Past Performance DB", "Compliance Guide"].map(
                  (src) => (
                    <div
                      key={src}
                      className="flex items-center gap-1 text-[9px]"
                      style={{ color: "#a3a3a3" }}
                    >
                      <div
                        className="size-1 rounded-full"
                        style={{ background: "rgba(132, 204, 22, 0.5)" }}
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
      {/* 状态栏 */}
      <div
        className="flex h-6 items-center justify-between px-3"
        style={{
          borderTop: "1px solid rgba(163, 163, 163, 0.1)",
          background: "#0a0a0a",
        }}
      >
        <span className="text-[9px]" style={{ color: "#737373" }}>
          3 sections complete
        </span>
        <span className="text-[9px]" style={{ color: "#737373" }}>
          Last saved 2 min ago
        </span>
      </div>
    </div>
  );
}

/* ============================================================
   StatCounter — 数字动画计数器
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
        style={{ color: "#ffffff" }}
      >
        {current.toLocaleString()}
        {suffix}
      </span>
      <span
        className="text-xs font-medium"
        style={{ color: "#737373" }}
      >
        {label}
      </span>
    </div>
  );
}

/* ============================================================
   SocialProofSection — 简洁Logo展示（老师风格）
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
      className="py-20"
      style={{ background: "#0a0a0a" }}
    >
      <ScrollReveal animation="fade-up" duration={600}>
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-10 px-6">
          <p
            className="text-sm font-medium tracking-wide uppercase"
            style={{ color: "#737373" }}
          >
            {t("socialProof.label")}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-16 gap-y-8">
            {LOGOS.map((logo, i) => (
              <ScrollReveal key={logo.name} animation="fade-up" delay={i * 100} duration={500}>
                <div className="group flex items-center gap-3 transition-opacity hover:opacity-100" style={{ opacity: 0.4 }}>
                  <div
                    className="flex size-8 items-center justify-center rounded-lg text-xs font-bold transition-colors"
                    style={{
                      background: "rgba(255, 255, 255, 0.06)",
                      color: "#a3a3a3",
                      border: "1px solid rgba(163, 163, 163, 0.1)",
                    }}
                  >
                    {logo.letter}
                  </div>
                  <span
                    className="text-sm font-semibold tracking-wide"
                    style={{ color: "#a3a3a3" }}
                  >
                    {logo.name}
                  </span>
                </div>
              </ScrollReveal>
            ))}
          </div>
          {/* 青柠绿分隔线 */}
          <div
            className="h-px w-full max-w-md"
            style={{
              background: "linear-gradient(90deg, transparent, rgba(132, 204, 22, 0.3), transparent)",
            }}
          />
        </div>
      </ScrollReveal>
    </section>
  );
}

/* ============================================================
   HowItWorksSection — 时间线设计（老师风格）
   ============================================================ */

const STEPS = [
  { key: "upload", icon: FileSearch, num: 1 },
  { key: "generate", icon: PenTool, num: 2 },
  { key: "review", icon: ShieldCheck, num: 3 },
] as const;

function HowItWorksSection() {
  const { t } = useTranslation("landing");
  return (
    <section className="mx-auto max-w-6xl px-6 py-32">
      <ScrollReveal animation="fade-up" duration={600}>
        <div className="max-w-2xl">
          <h2
            className="text-4xl font-bold leading-tight tracking-tight"
            style={{
              fontFamily: "var(--font-heading)",
              color: "#ffffff",
            }}
          >
            {t("howItWorks.heading")}
          </h2>
          <p className="mt-6 text-lg leading-relaxed" style={{ color: "#a3a3a3" }}>
            {t("howItWorks.subheading")}
          </p>
        </div>
      </ScrollReveal>
      <div className="mt-20 space-y-0">
        {STEPS.map((step, i) => (
          <ScrollReveal key={step.key} animation="fade-left" delay={i * 150} duration={600}>
            <div
              className="relative flex gap-8 pl-12 pb-16 last:pb-0"
              style={{ borderLeft: "1px solid rgba(132, 204, 22, 0.2)" }}
            >
              {/* 步骤编号 - 青柠绿 */}
              <span
                className="absolute -left-4 top-0 flex size-8 items-center justify-center rounded-full text-xs font-semibold shadow-xs"
                style={{
                  border: "2px solid #84cc16",
                  background: "#0a0a0a",
                  color: "#84cc16",
                }}
              >
                {step.num}
              </span>
              <div className="pt-1">
                <div className="mb-3 flex items-center gap-3">
                  <step.icon className="size-6" style={{ color: "#84cc16" }} />
                  <h3 className="text-xl font-semibold" style={{ color: "#ffffff" }}>
                    {t(`howItWorks.steps.${step.key}.title`)}
                  </h3>
                </div>
                <p className="max-w-lg text-base leading-relaxed" style={{ color: "#a3a3a3" }}>
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
   StatsSection — 统计数据展示
   ============================================================ */

function StatsSection() {
  return (
    <section
      className="py-24"
      style={{
        borderTop: "1px solid rgba(163, 163, 163, 0.1)",
        borderBottom: "1px solid rgba(163, 163, 163, 0.1)",
        background: "#171717",
      }}
    >
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-12 px-6 lg:grid-cols-4">
        {[
          { value: 50, suffix: "%", label: "Time Saved" },
          { value: 10, suffix: "x", label: "Faster Drafting" },
          { value: 99, suffix: "%", label: "Compliance Rate" },
          { value: 500, suffix: "+", label: "Proposals Delivered" },
        ].map((stat, i) => (
          <ScrollReveal key={stat.label} animation="fade-up" delay={i * 150} duration={600}>
            <div className="flex flex-col items-center gap-3 text-center">
              <span
                className="text-4xl font-bold tracking-tight"
                style={{ color: "#84cc16" }}
              >
                <AnimatedCounter
                  target={stat.value}
                  suffix={stat.suffix}
                  duration={2000}
                />
              </span>
              <span className="text-sm" style={{ color: "#a3a3a3" }}>
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
   FeaturesSection — 深灰卡片 + 青柠绿图标（老师风格）
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
      className="mx-auto max-w-6xl px-6 py-32"
      style={{ background: "#0a0a0a" }}
    >
      <ScrollReveal animation="fade-up" duration={600}>
        <div className="max-w-2xl">
          <h2
            className="text-4xl font-bold leading-tight tracking-tight"
            style={{
              fontFamily: "var(--font-heading)",
              color: "#ffffff",
            }}
          >
            {t("features.heading")}
          </h2>
          <p
            className="mt-6 text-lg leading-relaxed"
            style={{ color: "#a3a3a3" }}
          >
            {t("features.subheading")}
          </p>
        </div>
      </ScrollReveal>
      <div className="mt-20 grid gap-8 lg:grid-cols-3">
        {features.map((f, i) => {
          const Icon = FEATURE_ICONS[i];
          return (
            <ScrollReveal key={f.key} animation="fade-up" delay={i * 150}>
              <Card3D maxTilt={6}>
                <GlowEffect
                  radius={250}
                  opacity={0.08}
                  color="rgba(132, 204, 22, 0.15)"
                >
                  <div
                    className={`landing-card flex flex-col justify-between rounded-2xl p-8 transition-all duration-300 ${f.className}`}
                  >
                    <div>
                      <div
                        className="mb-6 flex size-12 items-center justify-center rounded-xl"
                        style={{
                          background: "rgba(132, 204, 22, 0.1)",
                          border: "1px solid rgba(132, 204, 22, 0.2)",
                        }}
                      >
                        <Icon className="size-6" style={{ color: "#84cc16" }} />
                      </div>
                      <h3
                        className="text-xl font-semibold"
                        style={{ color: "#ffffff" }}
                      >
                        {t(`features.${f.key}.title`)}
                      </h3>
                      <p
                        className="mt-4 text-base leading-relaxed"
                        style={{ color: "#a3a3a3" }}
                      >
                        {t(`features.${f.key}.description`)}
                      </p>
                    </div>
                    <div
                      className="mt-8 flex items-center gap-2 text-sm font-medium transition-colors"
                      style={{ color: "#84cc16" }}
                    >
                      {t(`features.${f.key}.learnMore`)}
                      <ArrowRight className="size-4" />
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
   PricingSection — 深灰卡片 + 青柠绿高亮（老师风格）
   ============================================================ */

function PricingSection() {
  const { t } = useTranslation("landing");
  const tiers = ["starter", "team", "enterprise"] as const;
  return (
    <section
      className="mx-auto max-w-6xl px-6 py-32"
      style={{
        background: "#0a0a0a",
        borderTop: "1px solid rgba(163, 163, 163, 0.1)",
      }}
    >
      <ScrollReveal animation="fade-up" duration={600}>
        <div className="max-w-2xl">
          <h2
            className="text-4xl font-bold leading-tight tracking-tight"
            style={{
              fontFamily: "var(--font-heading)",
              color: "#ffffff",
            }}
          >
            {t("pricing.heading")}
          </h2>
          <p
            className="mt-6 text-lg leading-relaxed"
            style={{ color: "#a3a3a3" }}
          >
            {t("pricing.subheading")}
          </p>
        </div>
      </ScrollReveal>
      <div className="mt-20 grid gap-8 lg:grid-cols-3">
        {tiers.map((tier, i) => {
          const highlighted = tier === "team";
          return (
            <ScrollReveal key={tier} animation="fade-up" delay={i * 150} duration={600}>
              <div
                className={`flex flex-col rounded-2xl p-8 transition-all duration-300 ${
                  highlighted ? "landing-card-highlight" : "landing-card"
                }`}
                style={{
                  background: highlighted
                    ? "linear-gradient(145deg, rgba(132, 204, 22, 0.06), #171717)"
                    : undefined,
                }}
              >
                <Badge
                  variant={highlighted ? "default" : "secondary"}
                  className="w-fit rounded-full px-3 py-1"
                  style={{
                    background: highlighted ? "rgba(132, 204, 22, 0.15)" : "rgba(255, 255, 255, 0.06)",
                    color: highlighted ? "#84cc16" : "#a3a3a3",
                    border: highlighted ? "1px solid rgba(132, 204, 22, 0.3)" : "1px solid rgba(163, 163, 163, 0.1)",
                  }}
                >
                  {t(`pricing.tiers.${tier}.label`)}
                </Badge>
                <p
                  className="mt-6 text-4xl font-bold tracking-tight"
                  style={{ color: "#ffffff" }}
                >
                  {t(`pricing.tiers.${tier}.price`)}
                </p>
                <p
                  className="mt-3 text-sm leading-relaxed"
                  style={{ color: "#a3a3a3" }}
                >
                  {t(`pricing.tiers.${tier}.sub`)}
                </p>
                <ul className="mt-10 flex-1 space-y-4">
                  {(
                    t(`pricing.tiers.${tier}.features`, { returnObjects: true }) as string[]
                  ).map((feat) => (
                    <li
                      key={feat}
                      className="flex items-start gap-3 text-sm leading-relaxed"
                      style={{ color: "#a3a3a3" }}
                    >
                      <CheckCircle2
                        className="mt-0.5 size-4 shrink-0"
                        style={{ color: "#84cc16" }}
                      />
                      {feat}
                    </li>
                  ))}
                </ul>
                <Link to="/signup" className="mt-10">
                  <Button
                    variant={highlighted ? "default" : "outline"}
                    className="w-full rounded-full transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg"
                    style={
                      highlighted
                        ? {
                            background: "#84cc16",
                            color: "#0a0a0a",
                            borderColor: "transparent",
                            boxShadow: "0 0 30px rgba(132, 204, 22, 0.3)",
                          }
                        : {
                            borderColor: "rgba(163, 163, 163, 0.2)",
                            color: "#a3a3a3",
                            background: "transparent",
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
   FinalCtaSection — 青柠绿渐变背景（老师风格）
   ============================================================ */

function FinalCtaSection() {
  const { t } = useTranslation("landing");
  return (
    <section
      className="relative overflow-hidden py-32"
      style={{
        background: "linear-gradient(180deg, #0a0a0a, #171717)",
        borderTop: "1px solid rgba(163, 163, 163, 0.1)",
      }}
    >
      {/* 青柠绿渐变光晕 */}
      <div
        className="landing-cta-orb-1 pointer-events-none absolute -top-32 left-1/4 size-[500px] rounded-full blur-[140px]"
        style={{
          background:
            "radial-gradient(circle, rgba(132, 204, 22, 0.2), transparent 60%)",
        }}
      />
      <div
        className="landing-cta-orb-2 pointer-events-none absolute -bottom-32 right-1/4 size-[400px] rounded-full blur-[140px]"
        style={{
          background:
            "radial-gradient(circle, rgba(163, 230, 53, 0.15), transparent 60%)",
        }}
      />
      <ScrollReveal animation="scale" duration={700}>
        <div className="relative z-10 mx-auto flex max-w-6xl flex-col items-center gap-8 px-6 text-center">
          <h2
            className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl"
            style={{
              fontFamily: "var(--font-heading)",
              color: "#ffffff",
              letterSpacing: "-0.03em",
            }}
          >
            {t("finalCta.heading")}
          </h2>
          <p
            className="max-w-xl text-lg leading-relaxed"
            style={{ color: "#a3a3a3" }}
          >
            {t("finalCta.subheading")}
          </p>
          <Link to="/signup">
            <Button
              size="lg"
              className="h-14 rounded-full px-10 text-base font-medium transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg"
              style={{
                background: "#84cc16",
                color: "#0a0a0a",
                boxShadow: "0 0 40px rgba(132, 204, 22, 0.4)",
              }}
            >
              {t("finalCta.cta")}
              <ArrowRight className="ml-2 size-5" />
            </Button>
          </Link>
        </div>
      </ScrollReveal>
    </section>
  );
}

/* ============================================================
   LandingPage — 主导出
   ============================================================ */

export function LandingPage() {
  return (
    <div className="flex min-h-svh flex-col">
      <ScrollProgress />
      <CinematicHero />
      <SocialProofSection />
      <HowItWorksSection />
      <StatsSection />
      <FeaturesSection />
      <PricingSection />
      <FinalCtaSection />
    </div>
  );
}
