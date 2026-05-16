import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Link } from "react-router-dom";
import { FileTextIcon, SparklesIcon, ShieldCheckIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

const FEATURE_KEYS = [
  {
    icon: <SparklesIcon className="size-6 text-primary" />,
    key: "extraction",
  },
  {
    icon: <FileTextIcon className="size-6 text-primary" />,
    key: "drafts",
  },
  {
    icon: <ShieldCheckIcon className="size-6 text-primary" />,
    key: "audit",
  },
] as const;

export function LandingPage() {
  const { t } = useTranslation("landing");

  return (
    <div className="flex min-h-svh flex-col">
      {/* Hero */}
      <div className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-20 text-center">
        <Badge variant="secondary" className="text-sm">
          {t("badge")}
        </Badge>
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
          {t("hero.title")}
        </h1>
        <p className="max-w-xl text-lg text-muted-foreground">
          {t("hero.description")}
        </p>
        <div className="flex gap-3">
          <Link to="/signup">
            <Button size="lg">{t("hero.getStarted")}</Button>
          </Link>
          <Link to="/pricing">
            <Button variant="outline" size="lg">{t("hero.viewPricing")}</Button>
          </Link>
        </div>
      </div>

      {/* Features */}
      <div className="mx-auto grid max-w-5xl gap-6 px-6 pb-20 sm:grid-cols-3">
        {FEATURE_KEYS.map((f) => (
          <Card key={f.key}>
            <CardHeader>
              {f.icon}
              <CardTitle className="mt-2">
                {t(`features.${f.key}.title`)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                {t(`features.${f.key}.description`)}
              </CardDescription>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
