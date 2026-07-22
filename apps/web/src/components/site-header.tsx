import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { MoonIcon, SunIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { NotificationBell } from "@/components/notification-bell";

export function SiteHeader() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const { theme, setTheme } = useTheme();

  const title = (() => {
    if (location.pathname === "/dashboard") return t("nav.dashboard");
    if (location.pathname === "/agent") return t("nav.agent", { defaultValue: "智能体" });
    if (location.pathname === "/knowledge") return t("nav.knowledge", { defaultValue: "知识资产" });
    if (location.pathname === "/runs") return t("nav.runs", { defaultValue: "运行" });
    if (location.pathname === "/projects") return t("nav.projects");
    if (location.pathname.startsWith("/projects/")) return t("nav.projects");
    if (location.pathname === "/pricing") return t("nav.pricing", { defaultValue: "定价" });
    if (location.pathname === "/docs") return t("nav.docs", { defaultValue: "文档" });
    if (location.pathname.startsWith("/settings")) return t("nav.settings");
    if (location.pathname === "/admin/users") return t("nav.users");
    if (location.pathname === "/admin/teams") return t("nav.teams");
    if (location.pathname === "/admin/invitations") return t("nav.invitations");
    return t("app.documents");
  })();

  const toggleLang = () => {
    const next = i18n.language === "zh-CN" ? "en" : "zh-CN";
    i18n.changeLanguage(next);
  };

  return (
    <header
      className="flex h-(--header-height) shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)"
      style={{
        borderBottom: "1px solid var(--border)",
        background: "var(--background)",
      }}
    >
      <div className="flex min-w-0 w-full items-center gap-1 px-3 sm:px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground" />
        <Separator
          orientation="vertical"
          className="mx-1 h-4 data-vertical:self-auto sm:mx-2"
        />
        <h1 className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{title}</h1>
        <div className="ml-auto flex shrink-0 items-center gap-1 sm:gap-2">
          <NotificationBell />
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="relative rounded-md p-1.5 transition-colors duration-200"
            style={{ color: "var(--muted-foreground)" }}
          >
            <SunIcon className="size-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <MoonIcon className="absolute left-1 top-1 size-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
          </button>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleLang}
            className="px-2 text-xs text-muted-foreground hover:text-foreground sm:px-3"
          >
            {t("language.switch")}
          </Button>
        </div>
      </div>
    </header>
  )
}
