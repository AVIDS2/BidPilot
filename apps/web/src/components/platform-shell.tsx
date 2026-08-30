import { lazy, Suspense, useEffect, type CSSProperties } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ActivityIcon,
  BotIcon,
  BookOpenCheckIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  MailIcon,
  SettingsIcon,
  UserPlusIcon,
  UsersIcon,
} from "lucide-react";

import { AppSidebar } from "@/components/app-sidebar";
import { SiteHeader } from "@/components/site-header";
import bidpilotLogo from "@/assets/bidpilot-logo.svg";
import { CommandPalette } from "@/features/agent/components/CommandPalette";
import { FloatingAssistant } from "@/features/agent/components/FloatingAssistant";
import { InlineSuggestionBar } from "@/features/agent/components/InlineSuggestion";
import { AgentWakeResume } from "@/features/agent/components/AgentWakeResume";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AIAssistantProvider, useAIAssistant } from "@/features/agent/state/agent-store";
import { useAuth } from "@/lib/auth";
import { ErrorBoundary } from "@/components/error-boundary";
import { useAIAssistantHotkeys } from "@/hooks/use-ai-assistant-hotkeys";
import { cn } from "@/lib/utils";
import { assistantContextForLocation } from "@/features/agent/runtime/assistant-route-context";
import { loadWithChunkRecovery } from "@/app-route-loaders";

const AIAssistantPanel = lazy(() =>
  loadWithChunkRecovery(
    () => import("@/features/agent/components/AIAssistantPanel"),
    "assistant-panel",
  ).then(({ AIAssistantPanel }) => ({
    default: AIAssistantPanel,
  })),
);

export function PlatformShell() {
  return (
    <AIAssistantProvider>
      <TooltipProvider>
        <AgentWakeResume />
        <PlatformShellContent />
      </TooltipProvider>
    </AIAssistantProvider>
  );
}

function PlatformShellContent() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const { state, toggle, dispatch } = useAIAssistant();
  useAIAssistantHotkeys();
  const location = useLocation();

  useEffect(() => {
    dispatch({
      type: "SET_CONTEXT",
      context: assistantContextForLocation(location.pathname, location.search),
    });
  }, [dispatch, location.pathname, location.search]);

  const isAdmin = user?.role === "admin";
  const navGroups = [
    {
      title: t("nav.workbench", { defaultValue: "工作区" }),
      items: [
        { title: t("nav.dashboard"), url: "/dashboard", icon: <LayoutDashboardIcon /> },
        { title: t("nav.agent", { defaultValue: "智能体" }), url: "/agent", icon: <BotIcon /> },
        { title: t("nav.projects"), url: "/projects", icon: <FileTextIcon /> },
      ],
    },
    {
      title: t("nav.execution", { defaultValue: "执行" }),
      items: [
        { title: t("nav.knowledge", { defaultValue: "知识资产" }), url: "/knowledge", icon: <BookOpenCheckIcon /> },
        { title: t("nav.runs", { defaultValue: "运行" }), url: "/runs", icon: <ActivityIcon /> },
      ],
    },
    {
      title: t("nav.administration", { defaultValue: "管理" }),
      items: [
        { title: t("nav.settings"), url: "/settings/providers", icon: <SettingsIcon /> },
        { title: t("nav.teams"), url: "/admin/teams", icon: <UserPlusIcon /> },
        { title: t("nav.invitations"), url: "/admin/invitations", icon: <MailIcon /> },
        { title: t("nav.users"), url: "/admin/users", icon: <UsersIcon /> },
      ],
    },
  ];
  const teams = [
    {
      name: "BidPilot",
      logo: <img alt="BidPilot" className="size-5 object-contain" src={bidpilotLogo} />,
      plan: t("app.tagline"),
    },
  ];
  const adminOnlyUrls = ["/admin/users"];
  const visibleNavGroups = navGroups.map((group) => ({
    ...group,
    items: group.items.filter(
      (item) => !adminOnlyUrls.includes(item.url) || isAdmin,
    ),
  })).filter((group) => group.items.length > 0);
  const isAgentWorkspace = location.pathname === "/agent";
  const assistantPanelOpen = !isAgentWorkspace && state.isOpen && state.mode === "panel";
  const sidebarUser = {
    name: user?.display_name || t("user.fallbackName"),
    email: user?.email || "",
    avatar: "",
  };

  return (
    <SidebarProvider
      // Lock the authenticated shell to the viewport. Nested surfaces choose
      // their own scroll (chat: internal; project list: main pane).
      className="h-svh overflow-hidden"
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as CSSProperties
      }
    >
      <CommandPalette
        open={state.isOpen && state.mode === "command"}
        onOpenChange={(open) => {
          if (!open) toggle();
        }}
      />
      <AppSidebar navGroups={visibleNavGroups} teams={teams} user={sidebarUser} />
      <SidebarInset
        className={cn(
          // Bound the shell to the viewport so nested chat surfaces can use
          // internal scroll instead of stretching the whole page.
          "min-h-0 min-w-0 overflow-x-hidden overflow-y-hidden transition-[margin] duration-200 ease-out",
          assistantPanelOpen && "xl:mr-[560px]",
        )}
      >
        <SiteHeader />
        <InlineSuggestionBar />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="@container/main flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <div
              className={cn(
                "flex min-h-0 min-w-0 flex-1 flex-col",
                // Agent workspace fills the main pane edge-to-edge for history + chat.
                isAgentWorkspace
                  ? "overflow-hidden px-0 py-0"
                  : "gap-4 overflow-y-auto px-3 py-4 sm:px-4 md:gap-6 md:py-6 lg:px-6",
              )}
            >
              <ErrorBoundary>
                <Outlet />
              </ErrorBoundary>
            </div>
          </div>
        </div>
      </SidebarInset>
      {!isAgentWorkspace && (
        <Suspense fallback={null}>
          <AIAssistantPanel />
        </Suspense>
      )}
      {!isAgentWorkspace && <FloatingAssistant />}
    </SidebarProvider>
  );
}
