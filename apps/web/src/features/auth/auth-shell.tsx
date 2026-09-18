import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { BrandLogo } from "@/components/brand";
import { FileCheck2Icon, FingerprintIcon, KeyRoundIcon } from "lucide-react";
import { InteractiveGridPattern } from "./interactive-grid";

const TRUST_POINTS = [
  { icon: FileCheck2Icon, key: "audit" },
  { icon: KeyRoundIcon, key: "sso" },
  { icon: FingerprintIcon, key: "isolation" },
] as const;

type AuthShellProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
};

export function AuthShell({ eyebrow, title, description, children, footer }: AuthShellProps) {
  const { t } = useTranslation("auth");
  const resolvedEyebrow = eyebrow ?? t("trust.badge");

  return (
    <main className="min-h-svh bg-background">
      <div className="grid min-h-svh lg:grid-cols-[minmax(0,1fr)_minmax(25rem,38rem)]">
        <section className="relative hidden flex-col justify-between overflow-hidden border-r bg-sidebar p-10 text-sidebar-foreground lg:flex xl:p-14">
          <InteractiveGridPattern
            className="pointer-events-none opacity-70 [mask-image:radial-gradient(ellipse_at_center,black,transparent_72%)]"
            squaresClassName="stroke-sidebar-border/50"
          />

          <Link to="/" aria-label="BidPilot home" className="relative z-10 w-fit">
            <BrandLogo markClassName="size-9" textClassName="text-2xl" />
          </Link>

          <div className="relative z-10 max-w-xl">
            <Badge variant="outline" className="mb-5 border-sidebar-border bg-sidebar-accent/60">
              {resolvedEyebrow}
            </Badge>
            <h1 className="max-w-xl text-4xl font-semibold tracking-tight xl:text-5xl">
              {t("trust.title")}
            </h1>
            <p className="mt-5 max-w-lg text-base leading-7 text-sidebar-foreground/70">
              {t("trust.description")}
            </p>

            <div className="mt-10 grid gap-4">
              {TRUST_POINTS.map(({ icon: Icon, key }) => (
                <div key={key} className="flex items-start gap-3">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-sidebar-border bg-sidebar-accent text-sidebar-foreground">
                    <Icon aria-hidden="true" />
                  </div>
                  <div className="grid gap-1">
                    <p className="text-sm font-medium">{t(`trust.items.${key}.title`)}</p>
                    <p className="max-w-md text-sm leading-6 text-sidebar-foreground/65">
                      {t(`trust.items.${key}.description`)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative z-10 flex items-center gap-3 text-xs text-sidebar-foreground/60">
            <span>BidPilot</span>
            <Separator orientation="vertical" className="h-3 bg-sidebar-border" />
            <span>{t("trust.rolesLabel")}</span>
          </div>
        </section>

        <section className="flex min-h-svh items-center justify-center px-4 py-8 sm:px-8 lg:px-12">
          <div className="w-full max-w-md">
            <div className="mb-8 flex justify-center lg:hidden">
              <Link to="/" aria-label="BidPilot home">
                <BrandLogo markClassName="size-9" textClassName="text-2xl" />
              </Link>
            </div>

            <div className="mb-7">
              <p className="text-sm font-medium text-primary">{resolvedEyebrow}</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight">{title}</h2>
              {description ? <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p> : null}
            </div>

            <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
              <div className="p-6 sm:p-8">{children}</div>
            </div>

            {footer ? <div className="mt-6 text-center">{footer}</div> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
