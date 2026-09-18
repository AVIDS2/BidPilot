import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRightIcon,
  CheckIcon,
  FileCheck2Icon,
  FileSearch2Icon,
  GitBranchIcon,
  MessagesSquareIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from "lucide-react";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { BrandLogo } from "@/components/brand";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type IconType = typeof FileSearch2Icon;

function Section({
  id,
  eyebrow,
  title,
  description,
  children,
  className = "",
}: {
  id?: string;
  eyebrow?: string;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`border-b py-20 sm:py-24 ${className}`}>
      <div className="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl">
          {eyebrow ? <p className="text-sm font-medium text-primary">{eyebrow}</p> : null}
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2>
          {description ? <p className="mt-4 text-base leading-7 text-muted-foreground">{description}</p> : null}
        </div>
        <div className="mt-10">{children}</div>
      </div>
    </section>
  );
}

function HeroSection() {
  const { t } = useTranslation("landing");
  const { isAuthenticated } = useAuth();
  const ctaPath = isAuthenticated ? "/dashboard" : "/signup";

  return (
    <section className="border-b">
      <div className="mx-auto grid w-full max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:gap-16 lg:px-8 lg:py-28">
        <div className="max-w-2xl">
          <Badge variant="outline" className="gap-1.5">
            <SparklesIcon aria-hidden="true" data-icon="inline-start" />
            {t("hero.label")}
          </Badge>
          <h1 className="mt-6 text-4xl font-semibold tracking-tight sm:text-5xl lg:text-6xl">
            {t("hero.title")}
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-muted-foreground">
            {t("hero.description")}
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link className={buttonVariants({ size: "lg" })} to={ctaPath}>
              {t("hero.getStarted")}
              <ArrowRightIcon data-icon="inline-end" />
            </Link>
            <Link className={buttonVariants({ size: "lg", variant: "outline" })} to="/pricing">
              {t("hero.viewPricing")}
            </Link>
          </div>
          <p className="mt-5 text-xs text-muted-foreground">{t("hero.noCreditCard")}</p>
        </div>

        <div className="relative min-w-0">
          <div className="overflow-hidden rounded-xl border bg-card shadow-lg">
            <div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-3">
              <span className="size-2 rounded-full bg-primary" />
              <span className="text-xs font-medium text-muted-foreground">{t("hero.previewLabel")}</span>
            </div>
            <img
              src="/marketing/projects.png"
              alt={t("hero.previewAlt")}
              className="block aspect-[16/10] w-full object-cover object-top"
            />
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheckIcon aria-hidden="true" />
              {t("hero.previewTrust")}
            </span>
            <span>{t("hero.previewStatus")}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function ProofSection() {
  const { t } = useTranslation("landing");
  const stats = t("socialProof.stats", { returnObjects: true }) as Array<{ value: string; label: string }>;

  return (
    <section className="border-b bg-muted/30">
      <div className="mx-auto grid w-full max-w-7xl grid-cols-2 divide-x divide-y px-4 sm:grid-cols-4 sm:divide-y-0 sm:px-6 lg:px-8">
        {stats.map((stat) => (
          <div key={stat.label} className="flex min-h-28 flex-col justify-center px-4 py-6 first:pl-0 sm:px-6">
            <strong className="text-2xl font-semibold tracking-tight sm:text-3xl">{stat.value}</strong>
            <span className="mt-1 text-xs text-muted-foreground sm:text-sm">{stat.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function WorkflowSection() {
  const { t } = useTranslation("landing");
  const steps: Array<{ key: "upload" | "generate" | "review"; icon: IconType; number: string }> = [
    { key: "upload", icon: FileSearch2Icon, number: "01" },
    { key: "generate", icon: SparklesIcon, number: "02" },
    { key: "review", icon: FileCheck2Icon, number: "03" },
  ];

  return (
    <Section
      id="workflow"
      eyebrow={t("howItWorks.eyebrow")}
      title={t("howItWorks.heading")}
      description={t("howItWorks.subheading")}
    >
      <div className="grid gap-4 md:grid-cols-3">
        {steps.map(({ key, icon: Icon, number }) => (
          <Card key={key} className="relative overflow-hidden">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon aria-hidden="true" />
                </div>
                <span className="font-mono text-xs text-muted-foreground">{number}</span>
              </div>
              <CardTitle className="mt-5">{t(`howItWorks.steps.${key}.title`)}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-6 text-muted-foreground">{t(`howItWorks.steps.${key}.description`)}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </Section>
  );
}

function CapabilitiesSection() {
  const { t } = useTranslation("landing");
  const capabilities: Array<{ key: "extraction" | "drafts" | "audit"; icon: IconType; image: string }> = [
    { key: "extraction", icon: FileSearch2Icon, image: "/marketing/projects.png" },
    { key: "drafts", icon: MessagesSquareIcon, image: "/marketing/agent-run.png" },
    { key: "audit", icon: ShieldCheckIcon, image: "/marketing/knowledge.png" },
  ];

  return (
    <Section
      id="capabilities"
      eyebrow={t("features.eyebrow")}
      title={t("features.heading")}
      description={t("features.subheading")}
      className="bg-muted/20"
    >
      <div className="grid gap-6 lg:grid-cols-3">
        {capabilities.map(({ key, icon: Icon, image }) => (
          <Card key={key} className="overflow-hidden">
            <div className="border-b bg-muted/30 p-2">
              <img
                src={image}
                alt={t(`features.${key}.title`)}
                className="aspect-[16/9] w-full rounded-lg border object-cover object-top"
              />
            </div>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Icon aria-hidden="true" className="text-primary" />
                <CardTitle className="text-lg">{t(`features.${key}.title`)}</CardTitle>
              </div>
              <CardDescription className="leading-6">{t(`features.${key}.description`)}</CardDescription>
            </CardHeader>
            <CardFooter>
              <Link className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline" to="/signup">
                {t(`features.${key}.learnMore`)}
                <ArrowRightIcon aria-hidden="true" />
              </Link>
            </CardFooter>
          </Card>
        ))}
      </div>
    </Section>
  );
}

function PricingSection() {
  const { t } = useTranslation("landing");
  const tiers = ["starter", "team", "enterprise"] as const;

  return (
    <Section id="pricing" eyebrow={t("pricing.eyebrow")} title={t("pricing.heading")} description={t("pricing.subheading")}>
      <div className="grid items-stretch gap-4 lg:grid-cols-3">
        {tiers.map((tier) => {
          const recommended = tier === "team";
          const features = t(`pricing.tiers.${tier}.features`, { returnObjects: true }) as string[];
          return (
            <Card key={tier} className={recommended ? "border-primary shadow-md" : undefined}>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <CardTitle>{t(`pricing.tiers.${tier}.label`)}</CardTitle>
                  {recommended ? <Badge>{t("pricing.recommended")}</Badge> : null}
                </div>
                <CardDescription className="min-h-12 leading-6">{t(`pricing.tiers.${tier}.sub`)}</CardDescription>
                <p className="pt-3 text-3xl font-semibold tracking-tight">{t(`pricing.tiers.${tier}.price`)}</p>
              </CardHeader>
              <CardContent className="flex-1">
                <Separator className="mb-5" />
                <ul className="grid gap-3 text-sm text-muted-foreground">
                  {features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2">
                      <CheckIcon aria-hidden="true" className="mt-0.5 shrink-0 text-primary" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
              <CardFooter>
                {tier === "enterprise" ? (
                  <a className={cn(buttonVariants({ variant: "outline" }), "w-full")} href="mailto:sales@bidpilot.ai">
                    {t(`pricing.tiers.${tier}.cta`)}
                  </a>
                ) : (
                  <Link className={cn(buttonVariants({ variant: recommended ? "default" : "outline" }), "w-full")} to="/signup">
                    {t(`pricing.tiers.${tier}.cta`)}
                  </Link>
                )}
              </CardFooter>
            </Card>
          );
        })}
      </div>
    </Section>
  );
}

function FaqSection() {
  const { t } = useTranslation("landing");
  const items = useMemo(
    () => t("faq.items", { returnObjects: true }) as Array<{ question: string; answer: string }>,
    [t],
  );

  return (
    <Section id="faq" eyebrow={t("faq.eyebrow")} title={t("faq.heading")}>
      <Accordion className="max-w-3xl" defaultValue={items[0] ? ["faq-0"] : undefined}>
        {items.map((item, index) => (
          <AccordionItem key={item.question} value={`faq-${index}`}>
            <AccordionTrigger>{item.question}</AccordionTrigger>
            <AccordionContent>
              <p className="leading-6 text-muted-foreground">{item.answer}</p>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </Section>
  );
}

function FinalCtaSection() {
  const { t } = useTranslation("landing");
  return (
    <section className="border-b">
      <div className="mx-auto flex w-full max-w-7xl flex-col items-start gap-6 px-4 py-20 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t("finalCta.heading")}</h2>
          <p className="mt-3 text-base text-muted-foreground">{t("finalCta.subheading")}</p>
        </div>
        <Link className={buttonVariants({ size: "lg" })} to="/signup">
          {t("finalCta.cta")}
          <ArrowRightIcon data-icon="inline-end" />
        </Link>
      </div>
    </section>
  );
}

function LandingFooter() {
  const { t } = useTranslation("common");
  return (
    <footer>
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <BrandLogo markClassName="size-6" textClassName="text-base" />
        <div className="flex flex-wrap items-center gap-4">
          <Link className="hover:text-foreground" to="/docs">{t("nav.docs")}</Link>
          <Link className="hover:text-foreground" to="/pricing">{t("nav.pricing")}</Link>
          <a className="inline-flex items-center gap-1.5 hover:text-foreground" href="https://github.com/AVIDS2/BidPilot" rel="noreferrer" target="_blank">
            <GitBranchIcon aria-hidden="true" />
            GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}

export function LandingPage() {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <HeroSection />
      <ProofSection />
      <WorkflowSection />
      <CapabilitiesSection />
      <PricingSection />
      <FaqSection />
      <FinalCtaSection />
      <LandingFooter />
    </div>
  );
}
