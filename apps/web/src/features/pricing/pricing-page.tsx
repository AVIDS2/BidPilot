import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { CheckIcon, ArrowLeftIcon, FileTextIcon } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Link, useNavigate } from "react-router-dom";
import { createCheckout } from "@/lib/api";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { useMemo } from "react";

interface PricingTier {
  name: string;
  price: string;
  period: string;
  description: string;
  recommended?: boolean;
  features: string[];
  cta: string;
}

function TierCard({ tier, current, onUpgrade, t }: { tier: PricingTier; current: boolean; onUpgrade: (plan: string) => void; t: (key: string) => string }) {
  return (
    <Card
      className={`flex flex-col${tier.recommended ? " border-primary shadow-lg" : ""}${current ? " ring-2 ring-primary" : ""}`}
    >
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-xl">{tier.name}</CardTitle>
          {tier.recommended && !current && <Badge>{t("badges.recommended")}</Badge>}
          {current && <Badge variant="secondary">{t("badges.currentPlan")}</Badge>}
        </div>
        <CardDescription>{tier.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <div className="mb-4">
          <span className="text-3xl font-bold">{tier.price}</span>
          {tier.period && (
            <span className="text-muted-foreground">{tier.period}</span>
          )}
        </div>
        <Separator className="mb-4" />
        <ul className="space-y-2 text-sm">
          {tier.features.map((feature) => (
            <li key={feature} className="flex items-center gap-2">
              <CheckIcon className="size-4 text-primary shrink-0" />
              {feature}
            </li>
          ))}
        </ul>
      </CardContent>
      <CardFooter>
        <Button
          className="w-full"
          variant={current ? "secondary" : tier.recommended ? "default" : "outline"}
          disabled={current}
          onClick={() => onUpgrade(tier.name.toLowerCase())}
        >
          {current ? t("button.currentPlan") : tier.cta}
        </Button>
      </CardFooter>
    </Card>
  );
}

export function PricingPage() {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const currentPlan = user?.plan?.toLowerCase() ?? "";
  const { t } = useTranslation("pricing");

  const TIERS: PricingTier[] = useMemo(() => [
    {
      name: t("tiers.starter.name"),
      price: t("tiers.starter.price"),
      period: t("tiers.starter.period"),
      description: t("tiers.starter.description"),
      features: t("tiers.starter.features", { returnObjects: true }) as unknown as string[],
      cta: t("tiers.starter.cta"),
    },
    {
      name: t("tiers.professional.name"),
      price: t("tiers.professional.price"),
      period: t("tiers.professional.period"),
      description: t("tiers.professional.description"),
      recommended: true,
      features: t("tiers.professional.features", { returnObjects: true }) as unknown as string[],
      cta: t("tiers.professional.cta"),
    },
    {
      name: t("tiers.enterprise.name"),
      price: t("tiers.enterprise.price"),
      period: t("tiers.enterprise.period"),
      description: t("tiers.enterprise.description"),
      features: t("tiers.enterprise.features", { returnObjects: true }) as unknown as string[],
      cta: t("tiers.enterprise.cta"),
    },
  ], [t]);

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
    <div className="mx-auto max-w-5xl py-8">
      <div className="flex items-center justify-between mb-8">
        <Link
          to={isAuthenticated ? "/projects" : "/"}
          className="inline-flex items-center gap-1 rounded-lg px-2.5 h-7 text-[0.8rem] font-medium hover:bg-muted hover:text-foreground transition-colors"
        >
          <ArrowLeftIcon className="size-3.5" />
          {isAuthenticated ? t("back.projects") : t("back.home")}
        </Link>
        <Link to="/" className="flex items-center gap-2 font-medium">
          <div className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <FileTextIcon className="size-4" />
          </div>
          DocPilot
        </Link>
        <div className="w-20" />
      </div>
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="mt-2 text-muted-foreground">
          {t("description")}
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        {TIERS.map((tier) => (
          <TierCard key={tier.name} tier={tier} current={tier.name.toLowerCase() === currentPlan} onUpgrade={handleUpgrade} t={t} />
        ))}
      </div>
    </div>
  );
}
