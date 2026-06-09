import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, FileText, PenTool, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CinematicHero } from "@/components/hero/CinematicHero";

// 完全复刻老师blog的逐字动画组件
function AnimatedTitle({ text, className }: { text: string; className?: string }) {
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!titleRef.current) return;

    const el = titleRef.current;
    const content = el.textContent || '';
    el.innerHTML = content.split('').map((char, i) =>
      `<span class="anim-char" style="--i:${i}">${char === ' ' ? '&nbsp;' : char}</span>`
    ).join('');

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animate-in');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 }
    );

    el.querySelectorAll('.anim-char').forEach(el => {
      observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  return <h1 ref={titleRef} className={className}>{text}</h1>;
}

// 复刻老师的ScrollReveal组件
function ScrollReveal({
  children,
  className = "",
  delay = 0,
  direction = "up"
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  direction?: "up" | "down" | "left" | "right";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (!ref.current) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTimeout(() => setIsVisible(true), delay);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [delay]);

  const getTransform = () => {
    switch (direction) {
      case "up": return "translateY(40px)";
      case "down": return "translateY(-40px)";
      case "left": return "translateX(40px)";
      case "right": return "translateX(-40px)";
      default: return "translateY(40px)";
    }
  };

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "none" : getTransform(),
        filter: isVisible ? "blur(0px)" : "blur(4px)",
        transition: `all 0.8s cubic-bezier(0.32, 0.72, 0, 1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

// Hero区域 - 使用CinematicHero（视频背景 + 粒子 + 网格）
function HeroSection() {
  const { t } = useTranslation("landing");

  return (
    <CinematicHero variant="mixed">
      {/* 区域标签 */}
      <span
        className="text-sm font-medium tracking-widest uppercase"
        style={{ color: "#84cc16" }}
      >
        / AI-Powered Document Execution
      </span>

      {/* 标题 - 使用逐字动画 */}
      <AnimatedTitle
        text={t("hero.title")}
        className="mt-8 text-6xl md:text-8xl font-medium leading-[0.85] tracking-[-0.04em] text-white"
      />

      {/* 副标题 */}
      <p className="mt-6 text-xl md:text-2xl text-white/80 max-w-2xl">
        {t("hero.description")}
      </p>

      {/* CTA 按钮 */}
      <div className="mt-12 flex gap-6">
        <Link
          to="/signup"
          className="inline-flex items-center gap-3 text-lg font-medium px-8 py-4 transition-all duration-300 hover:scale-[0.98]"
          style={{
            background: "#84cc16",
            color: "#0a0a0a",
          }}
        >
          {t("hero.getStarted")}
          <span className="text-sm">→</span>
        </Link>
        <Link
          to="/pricing"
          className="inline-flex items-center gap-3 text-lg font-medium text-white px-8 py-4 transition-all duration-300"
          style={{
            border: "1px solid rgba(163, 163, 163, 0.1)",
          }}
        >
          {t("hero.viewPricing")}
        </Link>
      </div>

      {/* 滚动提示 */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
        <div className="flex flex-col items-center gap-2 text-white/30">
          <span className="text-xs tracking-widest uppercase">Scroll to content</span>
          <div className="w-px h-8 animate-pulse" style={{ background: "#84cc16" }} />
        </div>
      </div>
    </CinematicHero>
  );
}

// 社会证明区域
function SocialProofSection() {
  const { t } = useTranslation("landing");
  const logos = ["Contour Design", "Harbor Group", "Northway Systems", "Atria Capital", "Vantage Partners"];

  return (
    <section
      className="py-16"
      style={{
        background: "#0a0a0a",
        borderTop: "1px solid rgba(163, 163, 163, 0.1)",
        borderBottom: "1px solid rgba(163, 163, 163, 0.1)",
      }}
    >
      <div className="max-w-7xl mx-auto px-8">
        <ScrollReveal>
          <p className="text-sm font-medium tracking-widest uppercase text-center mb-8" style={{ color: "#737373" }}>
            {t("socialProof.label")}
          </p>
        </ScrollReveal>
        <div className="flex flex-wrap items-center justify-center gap-x-16 gap-y-6">
          {logos.map((name, index) => (
            <ScrollReveal key={name} delay={index * 100}>
              <span
                className="text-sm font-medium tracking-wider uppercase transition-colors duration-300 hover:text-white"
                style={{ color: "#525252" }}
              >
                {name}
              </span>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// How It Works 区域
function HowItWorksSection() {
  const { t } = useTranslation("landing");
  const steps = [
    { key: "upload", icon: FileText, num: 1 },
    { key: "generate", icon: PenTool, num: 2 },
    { key: "review", icon: ShieldCheck, num: 3 },
  ];

  return (
    <section className="py-32" style={{ background: "#0a0a0a" }}>
      <div className="max-w-7xl mx-auto px-8">
        <ScrollReveal>
          <h2
            className="text-4xl md:text-5xl font-medium leading-tight tracking-tight mb-4"
            style={{ color: "#ffffff" }}
          >
            {t("howItWorks.heading")}
          </h2>
          <p className="text-xl max-w-2xl mb-16" style={{ color: "#a3a3a3" }}>
            {t("howItWorks.subheading")}
          </p>
        </ScrollReveal>

        <div className="relative">
          {/* 时间线连接线 */}
          <div
            className="absolute left-[19px] top-0 bottom-0 w-px"
            style={{ background: "rgba(132, 204, 22, 0.2)" }}
          />

          {steps.map((step, index) => (
            <ScrollReveal key={step.key} delay={index * 200} direction="left">
              <div className="relative flex gap-8 pb-16 last:pb-0">
                {/* 步骤编号 - 青柠绿 */}
                <div
                  className="relative z-10 flex items-center justify-center w-10 h-10 text-sm font-medium"
                  style={{
                    background: "#171717",
                    border: "1px solid rgba(132, 204, 22, 0.3)",
                    color: "#84cc16",
                  }}
                >
                  {step.num}
                </div>

                {/* 内容 */}
                <div className="flex-1 pt-2">
                  <div className="flex items-center gap-3 mb-3">
                    <step.icon className="w-5 h-5" style={{ color: "#84cc16" }} />
                    <h3 className="text-xl font-medium" style={{ color: "#ffffff" }}>
                      {t(`howItWorks.steps.${step.key}.title`)}
                    </h3>
                  </div>
                  <p className="text-base leading-relaxed max-w-lg" style={{ color: "#a3a3a3" }}>
                    {t(`howItWorks.steps.${step.key}.description`)}
                  </p>
                </div>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// Features 区域
function FeaturesSection() {
  const { t } = useTranslation("landing");
  const features = [
    { key: "extraction", icon: FileText },
    { key: "drafts", icon: PenTool },
    { key: "audit", icon: ShieldCheck },
  ];

  return (
    <section className="py-32" style={{ background: "#0a0a0a" }}>
      <div className="max-w-7xl mx-auto px-8">
        <ScrollReveal>
          <h2
            className="text-4xl md:text-5xl font-medium leading-tight tracking-tight mb-4"
            style={{ color: "#ffffff" }}
          >
            {t("features.heading")}
          </h2>
          <p className="text-xl max-w-2xl mb-16" style={{ color: "#a3a3a3" }}>
            {t("features.subheading")}
          </p>
        </ScrollReveal>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <ScrollReveal key={feature.key} delay={index * 150}>
              <div
                className="group p-8 transition-all duration-300 hover:-translate-y-1"
                style={{
                  background: "#171717",
                  border: "1px solid rgba(163, 163, 163, 0.1)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "rgba(132, 204, 22, 0.3)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "rgba(163, 163, 163, 0.1)";
                }}
              >
                {/* 图标 */}
                <div
                  className="w-12 h-12 flex items-center justify-center mb-6"
                  style={{
                    background: "rgba(132, 204, 22, 0.1)",
                    border: "1px solid rgba(132, 204, 22, 0.2)",
                  }}
                >
                  <feature.icon className="w-6 h-6" style={{ color: "#84cc16" }} />
                </div>

                {/* 标题 */}
                <h3 className="text-xl font-medium mb-3" style={{ color: "#ffffff" }}>
                  {t(`features.${feature.key}.title`)}
                </h3>

                {/* 描述 */}
                <p className="text-base leading-relaxed mb-6" style={{ color: "#a3a3a3" }}>
                  {t(`features.${feature.key}.description`)}
                </p>

                {/* Learn more */}
                <span
                  className="inline-flex items-center gap-2 text-sm font-medium transition-colors duration-300 group-hover:text-white"
                  style={{ color: "#84cc16" }}
                >
                  {t(`features.${feature.key}.learnMore`)}
                  <ArrowRight className="w-4 h-4" />
                </span>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// Pricing 区域
function PricingSection() {
  const { t } = useTranslation("landing");
  const tiers = ["starter", "team", "enterprise"] as const;

  return (
    <section className="py-32" style={{ background: "#0a0a0a" }}>
      <div className="max-w-7xl mx-auto px-8">
        <ScrollReveal>
          <h2
            className="text-4xl md:text-5xl font-medium leading-tight tracking-tight mb-4"
            style={{ color: "#ffffff" }}
          >
            {t("pricing.heading")}
          </h2>
          <p className="text-xl max-w-2xl mb-16" style={{ color: "#a3a3a3" }}>
            {t("pricing.subheading")}
          </p>
        </ScrollReveal>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {tiers.map((tier, index) => {
            const highlighted = tier === "team";
            return (
              <ScrollReveal key={tier} delay={index * 150}>
                <div
                  className="p-8 transition-all duration-300 hover:-translate-y-1"
                  style={{
                    background: "#171717",
                    border: highlighted
                      ? "1px solid rgba(132, 204, 22, 0.4)"
                      : "1px solid rgba(163, 163, 163, 0.1)",
                  }}
                >
                  {/* 标签 */}
                  <span
                    className="inline-block px-3 py-1 text-xs font-medium tracking-widest uppercase mb-6"
                    style={{
                      background: highlighted ? "rgba(132, 204, 22, 0.1)" : "rgba(163, 163, 163, 0.1)",
                      color: highlighted ? "#84cc16" : "#a3a3a3",
                      border: highlighted
                        ? "1px solid rgba(132, 204, 22, 0.2)"
                        : "1px solid rgba(163, 163, 163, 0.1)",
                    }}
                  >
                    {t(`pricing.tiers.${tier}.label`)}
                  </span>

                  {/* 价格 */}
                  <p className="text-5xl font-medium tracking-tight mb-2" style={{ color: "#ffffff" }}>
                    {t(`pricing.tiers.${tier}.price`)}
                  </p>

                  {/* 描述 */}
                  <p className="text-sm mb-8" style={{ color: "#737373" }}>
                    {t(`pricing.tiers.${tier}.sub`)}
                  </p>

                  {/* 功能列表 */}
                  <ul className="space-y-4 mb-8">
                    {(
                      t(`pricing.tiers.${tier}.features`, { returnObjects: true }) as string[]
                    ).map((feat) => (
                      <li key={feat} className="flex items-start gap-3">
                        <span
                          className="mt-1 w-4 h-4 flex items-center justify-center text-xs"
                          style={{ color: "#84cc16" }}
                        >
                          ✓
                        </span>
                        <span className="text-sm" style={{ color: "#a3a3a3" }}>
                          {feat}
                        </span>
                      </li>
                    ))}
                  </ul>

                  {/* CTA */}
                  <Link
                    to="/signup"
                    className="block w-full text-center py-4 text-sm font-medium transition-all duration-300 hover:scale-[0.98]"
                    style={{
                      background: highlighted ? "#84cc16" : "transparent",
                      color: highlighted ? "#0a0a0a" : "#ffffff",
                      border: highlighted ? "none" : "1px solid rgba(163, 163, 163, 0.1)",
                    }}
                  >
                    {t(`pricing.tiers.${tier}.cta`)}
                  </Link>
                </div>
              </ScrollReveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// Final CTA 区域
function FinalCtaSection() {
  const { t } = useTranslation("landing");

  return (
    <section className="py-32" style={{ background: "#0a0a0a" }}>
      <div className="max-w-7xl mx-auto px-8 text-center">
        <ScrollReveal>
          <h2
            className="text-4xl md:text-6xl font-medium leading-tight tracking-tight mb-6"
            style={{ color: "#ffffff" }}
          >
            {t("finalCta.heading")}
          </h2>
          <p className="text-xl max-w-2xl mx-auto mb-12" style={{ color: "#a3a3a3" }}>
            {t("finalCta.subheading")}
          </p>
          <Link
            to="/signup"
            className="inline-flex items-center gap-3 text-lg font-medium px-10 py-5 transition-all duration-300 hover:scale-[0.98]"
            style={{
              background: "#84cc16",
              color: "#0a0a0a",
            }}
          >
            {t("finalCta.cta")}
            <span className="text-sm">→</span>
          </Link>
        </ScrollReveal>
      </div>
    </section>
  );
}

// 导出落地页
export function LandingPage() {
  return (
    <div className="min-h-screen" style={{ background: "#0a0a0a" }}>
      <HeroSection />
      <SocialProofSection />
      <HowItWorksSection />
      <FeaturesSection />
      <PricingSection />
      <FinalCtaSection />
    </div>
  );
}
