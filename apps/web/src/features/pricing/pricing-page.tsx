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

interface PricingTier {
  name: string;
  price: string;
  period: string;
  description: string;
  recommended?: boolean;
  features: string[];
  cta: string;
}

const TIERS: PricingTier[] = [
  {
    name: "Starter",
    price: "Free",
    period: "",
    description: "Try DocPilot on a single RFP response.",
    features: [
      "Up to 3 projects",
      "1 scenario package (BidPilot)",
      "Community support",
      "Basic audit trail",
    ],
    cta: "Get Started",
  },
  {
    name: "Professional",
    price: "$99",
    period: "/month",
    description: "For teams that respond to RFPs regularly.",
    recommended: true,
    features: [
      "Unlimited projects",
      "All scenario packages",
      "Priority support",
      "Full audit and compliance trail",
      "DOCX and PDF export",
      "Team collaboration",
    ],
    cta: "Start Trial",
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For organizations that need control and scale.",
    features: [
      "Custom deployment",
      "SSO and SCIM provisioning",
      "Dedicated support and SLA",
      "Data residency options",
      "Custom scenario packages",
      "API access and integrations",
      "Backup and restore SLA",
    ],
    cta: "Contact Sales",
  },
];

function TierCard({ tier, current, onUpgrade }: { tier: PricingTier; current: boolean; onUpgrade: (plan: string) => void }) {
  return (
    <Card
      className={`flex flex-col${tier.recommended ? " border-primary shadow-lg" : ""}${current ? " ring-2 ring-primary" : ""}`}
    >
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-xl">{tier.name}</CardTitle>
          {tier.recommended && !current && <Badge>Recommended</Badge>}
          {current && <Badge variant="secondary">Current Plan</Badge>}
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
          {current ? "Current Plan" : tier.cta}
        </Button>
      </CardFooter>
    </Card>
  );
}

export function PricingPage() {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const currentPlan = user?.plan?.toLowerCase() ?? "";

  const checkoutMut = useMutation({
    mutationFn: createCheckout,
    onSuccess: (data) => {
      window.location.href = data.url;
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("501") || msg.includes("not configured")) {
        toast.error("Online payments are not yet available. Contact your admin to upgrade.");
      } else {
        toast.error("Could not start checkout. Please try again.");
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
          {isAuthenticated ? "Projects" : "Home"}
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
        <h1 className="text-3xl font-bold tracking-tight">Pricing</h1>
        <p className="mt-2 text-muted-foreground">
          Choose the plan that fits your proposal workflow.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        {TIERS.map((tier) => (
          <TierCard key={tier.name} tier={tier} current={tier.name.toLowerCase() === currentPlan} onUpgrade={handleUpgrade} />
        ))}
      </div>
    </div>
  );
}
