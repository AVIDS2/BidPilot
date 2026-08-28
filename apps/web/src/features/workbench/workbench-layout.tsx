import {
  ActivityIcon,
  BellIcon,
  BotIcon,
  ChevronDownIcon,
  ChevronsUpDownIcon,
  CommandIcon,
  FolderKanbanIcon,
  InboxIcon,
  LayoutDashboardIcon,
  LanguagesIcon,
  LibraryBigIcon,
  LogOutIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  PlusIcon,
  SearchIcon,
  RadarIcon,
} from "lucide-react";
import {
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  Suspense,
  useEffect,
  useMemo,
  useState,
} from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "@/lib/i18n";
import bidpilotLogo from "@/assets/bidpilot-logo.svg";

import { AgentWakeResume } from "@/features/agent/components/AgentWakeResume";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { AIAssistantProvider } from "@/features/agent/state/agent-store";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { prefetchRoute } from "@/app-route-loaders";

import "./workbench.css";

const SIDEBAR_MIN_WIDTH = 212;
const SIDEBAR_MAX_WIDTH = 360;
const SIDEBAR_DEFAULT_WIDTH = 252;
const SIDEBAR_STORAGE_KEY = "bidpilot.workbench.sidebar-width.v2";
const SIDEBAR_COLLAPSED_STORAGE_KEY = "bidpilot.workbench.sidebar-collapsed.v2";

type WorkbenchNavItem = {
  label: string;
  to: string;
  icon: typeof InboxIcon;
  count?: number;
};

type WorkbenchNavGroup = {
  label?: string;
  items: WorkbenchNavItem[];
};

function clampSidebarWidth(value: number) {
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, value));
}

function getSavedSidebarWidth() {
  const stored = Number(window.localStorage.getItem(SIDEBAR_STORAGE_KEY));
  return Number.isFinite(stored) && stored > 0
    ? clampSidebarWidth(stored)
    : SIDEBAR_DEFAULT_WIDTH;
}

function getInitials(name?: string) {
  const normalized = name?.trim();
  if (!normalized) return "BP";

  const words = normalized.split(/\s+/).filter(Boolean);
  return words.length > 1
    ? words.slice(0, 2).map((word) => word[0]).join("").toUpperCase()
    : normalized.slice(0, 2).toUpperCase();
}

function isPathActive(pathname: string, to: string) {
  if (to === "/dashboard") return pathname === to;
  return pathname === to || pathname.startsWith(`${to}/`);
}

function workbenchPageLabel(pathname: string) {
  if (pathname.startsWith("/projects/")) return "nav.bidProject";
  if (pathname.startsWith("/projects")) return "nav.bidProjects";
  if (pathname.startsWith("/knowledge")) return "nav.knowledge";
  if (pathname.startsWith("/radar")) return "nav.radar";
  if (pathname.startsWith("/runs")) return "nav.runs";
  if (pathname.startsWith("/reviews")) return "nav.reviews";
  if (pathname.startsWith("/deliverables")) return "nav.deliverables";
  if (pathname.startsWith("/members")) return "nav.responseTeam";
  if (pathname.startsWith("/administration") || pathname.startsWith("/admin")) return "nav.administration";
  if (pathname.startsWith("/account")) return "nav.account";
  if (pathname.startsWith("/settings")) return "nav.settings";
  if (pathname.startsWith("/my-work")) return "nav.myWork";
  if (pathname.startsWith("/agent")) return "nav.agent";
  return "nav.dashboard";
}

function WorkbenchRouteLoading() {
  return (
    <div className="flex min-h-full items-start justify-center px-6 py-10 sm:px-10" role="status" aria-label="正在加载页面">
      <div className="flex w-full max-w-5xl flex-col gap-5">
        <div className="flex items-center justify-between gap-4">
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-4 w-72 max-w-full" />
          </div>
          <Skeleton className="h-8 w-24" />
        </div>
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-[min(48dvh,28rem)] w-full" />
      </div>
    </div>
  );
}

export function WorkbenchLayout() {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarWidth, setSidebarWidth] = useState(getSavedSidebarWidth);
  const [isResizing, setIsResizing] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === "true");

  const navGroups = useMemo<WorkbenchNavGroup[]>(() => [
    {
      items: [
        { label: "nav.dashboard", to: "/dashboard", icon: LayoutDashboardIcon },
        { label: "nav.myWork", to: "/my-work", icon: ActivityIcon },
      ],
    },
    {
      label: "nav.workspace",
      items: [
        { label: "nav.bidProjects", to: "/projects", icon: FolderKanbanIcon },
        { label: "nav.radar", to: "/radar", icon: RadarIcon },
        { label: "nav.knowledge", to: "/knowledge", icon: LibraryBigIcon },
        { label: "nav.agent", to: "/agent", icon: BotIcon },
      ],
    },
  ], []);

  const visibleGroups = useMemo(
    () => navGroups,
    [navGroups],
  );

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(sidebarWidth));
  }, [sidebarWidth]);
  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  const finishResize = () => {
    setIsResizing(false);
  };

  const handleResizeStart = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setIsResizing(true);
  };

  const handleResizeMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!isResizing) return;
    setSidebarWidth(clampSidebarWidth(event.clientX));
  };

  const openNewProject = () => {
    if (location.pathname !== "/projects") {
      navigate("/projects");
      window.setTimeout(() => {
        window.dispatchEvent(new Event("bidpilot:new-project"));
      }, 0);
      return;
    }

    window.dispatchEvent(new Event("bidpilot:new-project"));
  };

  const userName = user?.display_name || "BidPilot user";
  const pageLabel = workbenchPageLabel(location.pathname);

  return (
    <AIAssistantProvider>
      <TooltipProvider>
        <AgentWakeResume />
        <div
          className={cn("workbench", isResizing && "is-resizing", sidebarCollapsed && "is-sidebar-collapsed")}
          style={{ "--wb-sidebar-width": `${sidebarCollapsed ? 64 : sidebarWidth}px` } as CSSProperties}
        >
          <aside className="wb-sidebar" aria-label="BidPilot workspace navigation">
            <div className="wb-workspace-row">
              <Button className="wb-workspace-switcher" size="sm" type="button" variant="ghost" aria-label="切换工作区">
                <img alt="BidPilot" className="wb-workspace-mark" src={bidpilotLogo} />
                <span className="wb-workspace-name">{user?.org_slug || "BidPilot workspace"}</span>
                <ChevronDownIcon aria-hidden="true" />
              </Button>
              <div className="wb-workspace-actions">
                <Tooltip><TooltipTrigger render={<Button aria-label="搜索工作区" className="wb-icon-button" size="icon-sm" type="button" variant="ghost" />}><SearchIcon aria-hidden="true" /></TooltipTrigger><TooltipContent>搜索工作区</TooltipContent></Tooltip>
                <Tooltip><TooltipTrigger render={<Button aria-label="新建投标项目" className="wb-icon-button wb-icon-button--raised" onClick={openNewProject} size="icon-sm" type="button" variant="ghost" />}><PlusIcon aria-hidden="true" /></TooltipTrigger><TooltipContent>新建投标项目</TooltipContent></Tooltip>
                <Tooltip><TooltipTrigger render={<Button aria-label={sidebarCollapsed ? "展开侧栏" : "收起侧栏"} aria-pressed={sidebarCollapsed} className="wb-icon-button wb-sidebar-toggle" data-state={sidebarCollapsed ? "collapsed" : "expanded"} onClick={() => setSidebarCollapsed((value) => !value)} size="icon-sm" type="button" variant="ghost" />}>
                  {sidebarCollapsed ? <PanelLeftOpenIcon aria-hidden="true" /> : <PanelLeftCloseIcon aria-hidden="true" />}
                </TooltipTrigger><TooltipContent>{sidebarCollapsed ? "展开侧栏" : "收起侧栏"}</TooltipContent></Tooltip>
              </div>
            </div>

            <nav className="wb-navigation">
              {visibleGroups.map((group) => (
                <section className="wb-nav-group" key={group.label || "priority"}>
                  {group.label && (
                    <p className="wb-nav-group-label">
                      {t(group.label)}
                      <ChevronDownIcon aria-hidden="true" />
                    </p>
                  )}
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const active = isPathActive(location.pathname, item.to);
                    return (
                      <NavLink
                        className={cn("wb-nav-link", active && "is-active")}
                        key={`${group.label}-${item.label}`}
                        onFocus={() => prefetchRoute(item.to)}
                        onMouseEnter={() => prefetchRoute(item.to)}
                        onPointerDown={() => prefetchRoute(item.to)}
                        to={item.to}
                      >
                        <Icon aria-hidden="true" />
                        <span>{t(item.label)}</span>
                        {item.count ? <small>{item.count}</small> : null}
                      </NavLink>
                    );
                  })}
                </section>
              ))}

            </nav>

            <div className="wb-sidebar-spacer" />

            <DropdownMenu>
              <DropdownMenuTrigger
                render={<Button aria-label="打开账户菜单" className="wb-user-menu" size="sm" type="button" variant="ghost" />}
              >
                <span className="wb-user-avatar">{getInitials(userName)}</span>
                <span className="wb-user-copy">
                  <strong>{userName}</strong>
                  <small>{user?.role === "admin" ? "Administrator" : "Team member"}</small>
                </span>
                <ChevronsUpDownIcon aria-hidden="true" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="wb-menu-content">
                <div className="wb-menu-label">{user?.email}</div>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate("/account")}>账户与个性化</DropdownMenuItem>
                {user?.role === "admin" ? <DropdownMenuItem onClick={() => navigate("/administration")}>组织设置</DropdownMenuItem> : null}
                {user?.role === "admin" ? <DropdownMenuItem onClick={() => navigate("/settings/providers")}>集成、模型与 Webhook</DropdownMenuItem> : null}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => {
                    logout();
                    navigate("/");
                  }}
                >
                  <LogOutIcon aria-hidden="true" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </aside>

          <div
            aria-label="调整侧栏宽度"
            aria-orientation="vertical"
            className="wb-sidebar-resize-handle"
            onKeyDown={(event) => {
              if (event.key === "ArrowLeft") setSidebarWidth((width) => clampSidebarWidth(width - 12));
              if (event.key === "ArrowRight") setSidebarWidth((width) => clampSidebarWidth(width + 12));
            }}
            onPointerCancel={finishResize}
            onPointerDown={handleResizeStart}
            onPointerMove={handleResizeMove}
            onPointerUp={finishResize}
            role="separator"
            tabIndex={0}
          />

          <main className="wb-main">
            <section className="wb-canvas" aria-label="BidPilot 工作区">
              <header className="wb-topbar">
                <div className="wb-breadcrumb">
                  <span>/</span>
                  <b>{t(pageLabel)}</b>
                </div>
                <div className="wb-topbar-actions">
                  <Tooltip><TooltipTrigger render={<Button aria-label="切换语言" onClick={() => i18n.changeLanguage(i18n.language === "zh-CN" ? "en" : "zh-CN")} size="icon-sm" type="button" variant="ghost" />}><LanguagesIcon aria-hidden="true" /></TooltipTrigger><TooltipContent>切换语言</TooltipContent></Tooltip>
                  <Tooltip><TooltipTrigger render={<Button aria-label="查看需要处理的事项" onClick={() => navigate("/my-work")} size="icon-sm" type="button" variant="ghost" />}><BellIcon aria-hidden="true" /></TooltipTrigger><TooltipContent>需要处理的事项</TooltipContent></Tooltip>
                  <Tooltip><TooltipTrigger render={<Button aria-label="打开 Agent" onClick={() => navigate("/agent")} size="icon-sm" type="button" variant="ghost" />}><CommandIcon aria-hidden="true" /></TooltipTrigger><TooltipContent>打开 Agent</TooltipContent></Tooltip>
                </div>
              </header>
              <div className="wb-route-surface">
                <Suspense fallback={<WorkbenchRouteLoading />}>
                  <Outlet />
                </Suspense>
              </div>
            </section>
          </main>
        </div>
      </TooltipProvider>
    </AIAssistantProvider>
  );
}
