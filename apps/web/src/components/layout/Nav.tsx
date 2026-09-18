import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MenuIcon } from "lucide-react";

import { BrandLogo } from "@/components/brand";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export function Nav() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { isAuthenticated } = useAuth();
  const { t } = useTranslation("common");

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80">
      <div className="mx-auto flex h-14 w-full max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" aria-label="BidPilot home" className="shrink-0">
          <BrandLogo markClassName="size-7" textClassName="text-lg" />
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label={t("nav.navigation")}>
          <Link className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" to="/">
            {t("nav.home")}
          </Link>
          <Link className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" to="/pricing">
            {t("nav.pricing")}
          </Link>
          <Link className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" to="/docs">
            {t("nav.docs")}
          </Link>
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          {isAuthenticated ? (
            <Link className={buttonVariants()} to="/dashboard">{t("nav.enterPlatform")}</Link>
          ) : (
            <>
              <Link className={buttonVariants({ variant: "ghost" })} to="/login">{t("nav.login")}</Link>
              <Link className={buttonVariants()} to="/signup">{t("nav.signup")}</Link>
            </>
          )}
        </div>

        <div className="md:hidden">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger render={<Button aria-label={t("nav.navigation")} size="icon-sm" variant="ghost" />}>
              <MenuIcon aria-hidden="true" />
            </SheetTrigger>
            <SheetContent className="w-[min(22rem,calc(100vw-1rem))]" side="right">
              <SheetHeader>
                <SheetTitle>{t("nav.navigation")}</SheetTitle>
                <SheetDescription>{t("app.tagline")}</SheetDescription>
              </SheetHeader>
              <nav className="flex flex-col gap-1 px-4" aria-label={t("nav.navigation")}>
                <Link className="rounded-md px-3 py-2.5 text-sm font-medium hover:bg-muted" onClick={() => setMobileOpen(false)} to="/">
                  {t("nav.home")}
                </Link>
                <Link className="rounded-md px-3 py-2.5 text-sm font-medium hover:bg-muted" onClick={() => setMobileOpen(false)} to="/pricing">
                  {t("nav.pricing")}
                </Link>
                <Link className="rounded-md px-3 py-2.5 text-sm font-medium hover:bg-muted" onClick={() => setMobileOpen(false)} to="/docs">
                  {t("nav.docs")}
                </Link>
              </nav>
              <SheetFooter>
                {isAuthenticated ? (
                  <Link className={cn(buttonVariants(), "w-full")} to="/dashboard">{t("nav.enterPlatform")}</Link>
                ) : (
                  <div className="grid gap-2">
                    <Link className={cn(buttonVariants({ variant: "outline" }), "w-full")} to="/login">{t("nav.login")}</Link>
                    <Link className={cn(buttonVariants(), "w-full")} to="/signup">{t("nav.signup")}</Link>
                  </div>
                )}
              </SheetFooter>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
