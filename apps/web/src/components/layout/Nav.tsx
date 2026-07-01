import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { BrandLogo } from "@/components/brand";

export function Nav() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isHidden, setIsHidden] = useState(false);
  const [lastScrollY, setLastScrollY] = useState(0);
  const { isAuthenticated } = useAuth();
  const { t } = useTranslation("common");

  useEffect(() => {
    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      setIsScrolled(currentScrollY > 50);
      setIsHidden(currentScrollY > lastScrollY && currentScrollY > 100);
      setLastScrollY(currentScrollY);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [lastScrollY]);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        isScrolled
          ? "bg-background/80 backdrop-blur-md"
          : "bg-transparent"
      } ${isHidden ? "-translate-y-full" : "translate-y-0"}`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5 sm:px-8 sm:py-6">
        {/* Logo */}
        <Link
          to="/"
          className="min-w-0 text-2xl transition-colors duration-300 hover:text-primary"
        >
          <BrandLogo markClassName="size-7 sm:size-8" textClassName="text-xl sm:text-2xl" />
        </Link>

        {/* Navigation links */}
        <div className="hidden items-center gap-8 md:flex">
          <Link
            to="/"
            className="text-sm text-muted-foreground hover:text-primary transition-colors duration-300"
          >
            {t("nav.home")}
          </Link>
          <Link
            to="/pricing"
            className="text-sm text-muted-foreground hover:text-primary transition-colors duration-300"
          >
            {t("nav.pricing")}
          </Link>
          <Link
            to="/docs"
            className="text-sm text-muted-foreground hover:text-primary transition-colors duration-300"
          >
            {t("nav.docs")}
          </Link>
          {isAuthenticated ? (
            <Link
              to="/dashboard"
              className="inline-flex items-center text-sm font-medium px-5 py-2.5 bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:scale-[0.98]"
            >
              {t("nav.enterPlatform")}
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="text-sm text-muted-foreground hover:text-primary transition-colors duration-300"
              >
                {t("nav.login")}
              </Link>
              <Link
                to="/signup"
                className="inline-flex items-center text-sm font-medium px-5 py-2.5 bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:scale-[0.98]"
              >
                {t("nav.signup")}
              </Link>
            </>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2 md:hidden">
          {isAuthenticated ? (
            <Link
              to="/dashboard"
              className="inline-flex items-center px-3.5 py-2 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:scale-[0.98]"
            >
              {t("nav.enterPlatform")}
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="text-sm text-muted-foreground hover:text-primary transition-colors duration-300"
              >
                {t("nav.login")}
              </Link>
              <Link
                to="/signup"
                className="inline-flex items-center px-3.5 py-2 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:scale-[0.98]"
              >
                {t("nav.signup")}
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
