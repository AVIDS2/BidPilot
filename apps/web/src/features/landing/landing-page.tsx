import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, FileText, PenTool, ShieldCheck } from "lucide-react";
import { CinematicHero } from "@/components/hero/CinematicHero";
import BlurText from "@/components/BlurText";
import AnimatedContent from "@/components/AnimatedContent";
import StarBorder from "@/components/StarBorder";
import GlareHover from "@/components/GlareHover";
import DecryptedText from "@/components/DecryptedText";

// Hero区域 - 使用CinematicHero + BlurText逐字动画
function HeroSection() {
  const { t } = useTranslation("landing");

  return (
    <CinematicHero variant="mixed">
      {/* 区域标签 - DecryptedText解密效果 */}
      <DecryptedText
        text={t("hero.label")}
        speed={60}
        maxIterations={6}
        animateOn="view"
        className="text-sm font-medium tracking-widest uppercase"
        parentClassName="inline-block"
        style={{ color: "var(--landing-accent)" }}
      />

      {/* 标题 - BlurText逐词blur入场 */}
      <BlurText
        text={t("hero.title")}
        delay={150}
        animateBy="words"
        direction="bottom"
        threshold={0}
        stepDuration={0.6}
        className="mt-7 max-w-[12ch] text-[clamp(3.15rem,16vw,5.25rem)] font-medium leading-[0.9] tracking-[-0.055em] text-white sm:mt-8 sm:max-w-[10ch] md:text-8xl md:leading-[0.85]"
      />

      {/* 副标题 */}
      <p className="mt-6 max-w-[20rem] text-lg leading-relaxed text-white/80 sm:max-w-2xl sm:text-xl md:text-2xl">
        {t("hero.description")}
      </p>

      {/* CTA 按钮 - StarBorder包裹主CTA */}
      <div className="mt-10 grid w-full max-w-[22rem] grid-cols-2 gap-3 sm:mt-12 sm:flex sm:max-w-none sm:gap-6">
        <StarBorder
          as="a"
          color="rgba(132, 204, 22, 0.8)"
          speed="5s"
          thickness={1}
          className="inline-flex min-h-24 w-full sm:min-h-0"
          href="/signup"
        >
          <span className="flex w-full items-center justify-between gap-3 px-6 py-5 text-xl font-medium leading-tight sm:justify-start sm:px-8 sm:py-4 sm:text-lg">
            {t("hero.getStarted")}
            <span className="text-sm">→</span>
          </span>
        </StarBorder>
        <Link
          to="/pricing"
          className="inline-flex min-h-24 items-center justify-center gap-3 px-5 py-5 text-center text-xl font-medium leading-tight text-white transition-all duration-300 hover:border-white/20 sm:min-h-0 sm:px-8 sm:py-4 sm:text-lg"
          style={{
            border: "1px solid var(--landing-hairline)",
          }}
        >
          {t("hero.viewPricing")}
        </Link>
      </div>

      {/* 滚动提示 */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
        <div className="flex flex-col items-center gap-2 text-white/30">
          <span className="text-xs tracking-widest uppercase">{t("hero.scrollHint")}</span>
          <div className="w-px h-8 animate-pulse" style={{ background: "var(--landing-accent)" }} />
        </div>
      </div>
    </CinematicHero>
  );
}

// 社会证明区域
function SocialProofSection() {
  const { t } = useTranslation("landing");
  const logos = t("socialProof.logos", { returnObjects: true }) as string[];

  return (
    <section
      className="py-16"
      style={{
        background: "var(--landing-canvas)",
        borderTop: "1px solid var(--landing-hairline)",
        borderBottom: "1px solid var(--landing-hairline)",
      }}
    >
      <div className="max-w-7xl mx-auto px-8">
        <AnimatedContent distance={30} duration={0.6}>
          <p className="text-sm font-medium tracking-widest uppercase text-center mb-8" style={{ color: "var(--landing-text-tertiary)" }}>
            {t("socialProof.label")}
          </p>
        </AnimatedContent>
        <div className="flex flex-wrap items-center justify-center gap-x-16 gap-y-6">
          {logos.map((name, index) => (
            <AnimatedContent key={name} delay={index * 0.08} distance={20} duration={0.5}>
              <span
                className="text-sm font-medium tracking-wider uppercase transition-colors duration-300 hover:text-white"
                style={{ color: "var(--landing-text-tertiary)" }}
              >
                {name}
              </span>
            </AnimatedContent>
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
    <section className="py-32" style={{ background: "var(--landing-canvas)" }}>
      <div className="max-w-7xl mx-auto px-8">
        <AnimatedContent distance={40} duration={0.8}>
          <h2
            className="text-4xl md:text-5xl font-medium leading-tight tracking-tight mb-4"
            style={{ color: "var(--landing-text-primary)" }}
          >
            {t("howItWorks.heading")}
          </h2>
          <p className="text-xl max-w-2xl mb-16" style={{ color: "var(--landing-text-secondary)" }}>
            {t("howItWorks.subheading")}
          </p>
        </AnimatedContent>

        <div className="relative">
          {/* 时间线连接线 */}
          <div
            className="absolute left-[19px] top-0 bottom-0 w-px"
            style={{ background: "var(--landing-border-inner)" }}
          />

          {steps.map((step, index) => (
            <AnimatedContent key={step.key} delay={index * 0.15} distance={60} direction="horizontal" duration={0.7}>
              <div className="relative flex gap-8 pb-16 last:pb-0">
                {/* 步骤编号 */}
                <div
                  className="relative z-10 flex items-center justify-center w-10 h-10 text-sm font-medium"
                  style={{
                    background: "var(--landing-surface-1)",
                    border: "1px solid var(--landing-border-inner)",
                    color: "var(--landing-accent)",
                  }}
                >
                  {step.num}
                </div>

                {/* 内容 */}
                <div className="flex-1 pt-2">
                  <div className="flex items-center gap-3 mb-3">
                    <step.icon className="w-5 h-5" style={{ color: "var(--landing-accent)" }} />
                    <h3 className="text-xl font-medium" style={{ color: "var(--landing-text-primary)" }}>
                      {t(`howItWorks.steps.${step.key}.title`)}
                    </h3>
                  </div>
                  <p className="text-base leading-relaxed max-w-lg" style={{ color: "var(--landing-text-secondary)" }}>
                    {t(`howItWorks.steps.${step.key}.description`)}
                  </p>
                </div>
              </div>
            </AnimatedContent>
          ))}
        </div>
      </div>
    </section>
  );
}

// Features 区域 - 使用GlareHover
function FeaturesSection() {
  const { t } = useTranslation("landing");
  const features = [
    { key: "extraction", icon: FileText },
    { key: "drafts", icon: PenTool },
    { key: "audit", icon: ShieldCheck },
  ];

  return (
    <section className="py-32" style={{ background: "var(--landing-canvas)" }}>
      <div className="max-w-7xl mx-auto px-8">
        <AnimatedContent distance={40} duration={0.8}>
          <h2
            className="text-4xl md:text-5xl font-medium leading-tight tracking-tight mb-4"
            style={{ color: "var(--landing-text-primary)" }}
          >
            {t("features.heading")}
          </h2>
          <p className="text-xl max-w-2xl mb-16" style={{ color: "var(--landing-text-secondary)" }}>
            {t("features.subheading")}
          </p>
        </AnimatedContent>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <AnimatedContent key={feature.key} delay={index * 0.12} distance={50} duration={0.7}>
              <GlareHover
                width="100%"
                height="auto"
                background="var(--landing-surface-1)"
                borderRadius="0px"
                borderColor="var(--landing-hairline)"
                glareColor="132, 204, 22"
                glareOpacity={0.15}
                glareSize={300}
                transitionDuration={700}
                className="!h-full"
              >
                <div className="p-8 h-full">
                  {/* 图标 */}
                  <div
                    className="w-12 h-12 flex items-center justify-center mb-6"
                    style={{
                      background: "rgba(132, 204, 22, 0.1)",
                      border: "1px solid var(--landing-border-inner)",
                    }}
                  >
                    <feature.icon className="w-6 h-6" style={{ color: "var(--landing-accent)" }} />
                  </div>

                  {/* 标题 */}
                  <h3 className="text-xl font-medium mb-3" style={{ color: "var(--landing-text-primary)" }}>
                    {t(`features.${feature.key}.title`)}
                  </h3>

                  {/* 描述 */}
                  <p className="text-base leading-relaxed mb-6" style={{ color: "var(--landing-text-secondary)" }}>
                    {t(`features.${feature.key}.description`)}
                  </p>

                  {/* Learn more */}
                  <span
                    className="inline-flex items-center gap-2 text-sm font-medium transition-colors duration-300 group-hover:text-white"
                    style={{ color: "var(--landing-accent)" }}
                  >
                    {t(`features.${feature.key}.learnMore`)}
                    <ArrowRight className="w-4 h-4" />
                  </span>
                </div>
              </GlareHover>
            </AnimatedContent>
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
    <section className="py-32" style={{ background: "var(--landing-canvas)" }}>
      <div className="max-w-7xl mx-auto px-8">
        <AnimatedContent distance={40} duration={0.8}>
          <h2
            className="text-4xl md:text-5xl font-medium leading-tight tracking-tight mb-4"
            style={{ color: "var(--landing-text-primary)" }}
          >
            {t("pricing.heading")}
          </h2>
          <p className="text-xl max-w-2xl mb-16" style={{ color: "var(--landing-text-secondary)" }}>
            {t("pricing.subheading")}
          </p>
        </AnimatedContent>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {tiers.map((tier, index) => {
            const highlighted = tier === "team";
            return (
              <AnimatedContent key={tier} delay={index * 0.12} distance={50} duration={0.7}>
                <div
                  className="p-8 transition-all duration-300 hover:-translate-y-1 h-full"
                  style={{
                    background: "var(--landing-surface-1)",
                    border: highlighted
                      ? "1px solid var(--landing-border-inner)"
                      : "1px solid var(--landing-hairline)",
                  }}
                >
                  {/* 标签 */}
                  <span
                    className="inline-block px-3 py-1 text-xs font-medium tracking-widest uppercase mb-6"
                    style={{
                      background: highlighted ? "rgba(132, 204, 22, 0.1)" : "var(--landing-hairline)",
                      color: highlighted ? "var(--landing-accent)" : "var(--landing-text-secondary)",
                      border: highlighted
                        ? "1px solid var(--landing-border-inner)"
                        : "1px solid var(--landing-hairline)",
                    }}
                  >
                    {t(`pricing.tiers.${tier}.label`)}
                  </span>

                  {/* 价格 */}
                  <p className="text-5xl font-medium tracking-tight mb-2" style={{ color: "var(--landing-text-primary)" }}>
                    {t(`pricing.tiers.${tier}.price`)}
                  </p>

                  {/* 描述 */}
                  <p className="text-sm mb-8" style={{ color: "var(--landing-text-tertiary)" }}>
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
                          style={{ color: "var(--landing-accent)" }}
                        >
                          ✓
                        </span>
                        <span className="text-sm" style={{ color: "var(--landing-text-secondary)" }}>
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
                      background: highlighted ? "var(--landing-accent)" : "transparent",
                      color: highlighted ? "var(--landing-canvas)" : "var(--landing-text-primary)",
                      border: highlighted ? "none" : "1px solid var(--landing-hairline)",
                    }}
                  >
                    {t(`pricing.tiers.${tier}.cta`)}
                  </Link>
                </div>
              </AnimatedContent>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// Final CTA 区域 - StarBorder
function FinalCtaSection() {
  const { t } = useTranslation("landing");

  return (
    <section className="py-32" style={{ background: "var(--landing-canvas)" }}>
      <div className="max-w-7xl mx-auto px-8 text-center">
        <AnimatedContent distance={40} duration={0.8}>
          <h2
            className="text-4xl md:text-6xl font-medium leading-tight tracking-tight mb-6"
            style={{ color: "var(--landing-text-primary)" }}
          >
            {t("finalCta.heading")}
          </h2>
          <p className="text-xl max-w-2xl mx-auto mb-12" style={{ color: "var(--landing-text-secondary)" }}>
            {t("finalCta.subheading")}
          </p>
        </AnimatedContent>
        <AnimatedContent delay={0.2} distance={30} duration={0.6}>
          <StarBorder
            as="a"
            color="rgba(132, 204, 22, 0.8)"
            speed="5s"
            thickness={1}
            className="inline-block"
            href="/signup"
          >
            <span className="flex items-center gap-3 text-lg font-medium px-10 py-5">
              {t("finalCta.cta")}
              <span className="text-sm">→</span>
            </span>
          </StarBorder>
        </AnimatedContent>
      </div>
    </section>
  );
}

// 导出落地页
export function LandingPage() {
  return (
    <div className="landing-page-shell min-h-screen" style={{ background: "var(--landing-canvas)" }}>
      <HeroSection />
      <SocialProofSection />
      <HowItWorksSection />
      <FeaturesSection />
      <PricingSection />
      <FinalCtaSection />
    </div>
  );
}
