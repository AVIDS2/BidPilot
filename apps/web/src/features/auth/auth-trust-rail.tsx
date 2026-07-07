import { Badge } from "@/components/ui/badge";
import { Building2Icon, FingerprintIcon, KeyRoundIcon, ShieldCheckIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

const TRUST_ITEMS = [
  { key: "audit", icon: ShieldCheckIcon },
  { key: "sso", icon: KeyRoundIcon },
  { key: "isolation", icon: FingerprintIcon },
] as const;

const ROLE_TAGS = ["proposal", "presales", "delivery", "compliance"] as const;

export function AuthTrustRail() {
  const { t } = useTranslation("auth");

  return (
    <aside className="hidden lg:flex lg:flex-col lg:justify-between rounded-3xl border border-border bg-card/70 p-8 shadow-xl shadow-black/10">
      <div>
        <Badge variant="outline" className="mb-6 border-primary/30 bg-primary/10 text-primary">
          {t("trust.badge")}
        </Badge>
        <h2 className="max-w-sm text-3xl font-semibold tracking-tight text-foreground">
          {t("trust.title")}
        </h2>
        <p className="mt-4 max-w-sm text-sm leading-6 text-muted-foreground">
          {t("trust.description")}
        </p>
      </div>

      <div className="my-8 space-y-3">
        {TRUST_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.key} className="flex gap-3 rounded-2xl border border-border/70 bg-background/45 p-4">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon className="size-5" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">{t(`trust.items.${item.key}.title`)}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{t(`trust.items.${item.key}.description`)}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="rounded-2xl border border-border/70 bg-muted/25 p-4">
        <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
          <Building2Icon className="size-4" />
          {t("trust.rolesLabel")}
        </div>
        <div className="flex flex-wrap gap-2">
          {ROLE_TAGS.map((role) => (
            <span key={role} className="rounded-full border border-border bg-background px-3 py-1 text-xs text-muted-foreground">
              {t(`trust.roles.${role}`)}
            </span>
          ))}
        </div>
      </div>
    </aside>
  );
}
