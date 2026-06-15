import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Outlet, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { DashboardPage } from "./features/dashboard/dashboard-page";
import { ProjectListPage } from "./features/projects/project-list-page";
import { ProjectDetailPage } from "./features/projects/project-detail-page";
import { AccountPage } from "./features/account/account-page";
import { PricingPage } from "./features/pricing/pricing-page";
import { LandingPage } from "./features/landing/landing-page";
import { UserManagementPage } from "./features/admin/user-management-page";
import { TeamManagementPage } from "./features/admin/team-management-page";
import { InvitationManagementPage } from "./features/admin/invitation-management-page";
import { ProviderSettingsPage } from "./features/settings/provider-settings-page";
import { DocsPage } from "./features/docs/docs-page";
import { LoginPage } from "./features/auth/login-page";
import { SignupPage } from "./features/auth/signup-page";
import { ForgotPasswordPage } from "./features/auth/forgot-password-page";
import { ResetPasswordPage } from "./features/auth/reset-password-page";
import { VerifyEmailPromptPage } from "./features/auth/verify-email-prompt-page";
import { VerifyEmailPage } from "./features/auth/verify-email-page";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { AppSidebar } from "@/components/app-sidebar";
import { SiteHeader } from "@/components/site-header";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { Nav } from "@/components/layout/Nav";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ErrorBoundary } from "@/components/error-boundary";
import { ThemeProvider } from "next-themes";
import { FileTextIcon, SettingsIcon, UsersIcon, UserPlusIcon, MailIcon, LayoutDashboardIcon, CreditCardIcon, BookOpenIcon } from "lucide-react";
import { AIAssistantProvider, useAIAssistant } from "@/lib/ai-assistant-store";
import { CommandPalette, AIAssistantPanel, FloatingAssistant, InlineSuggestionBar } from "@/components/ai-assistant";
import { useAIAssistantHotkeys } from "@/hooks/use-ai-assistant-hotkeys";

const queryClient = new QueryClient();

function RootRedirect() {
  const { isAuthenticated } = useAuth();
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }
  return <LandingPage />;
}

// PublicLayout - Nav only on public pages (landing, auth, pricing, docs)
function PublicLayout() {
  return (
    <>
      <Nav />
      <Outlet />
    </>
  );
}

function PlatformShell() {
  const { user, isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const { state, toggle } = useAIAssistant();
  useAIAssistantHotkeys();

  const isAdmin = user?.role === "admin";

  const navItems = [
    { title: t("nav.dashboard"), url: "/dashboard", icon: <LayoutDashboardIcon /> },
    { title: t("nav.projects"), url: "/projects", icon: <FileTextIcon /> },
    { title: t("nav.settings"), url: "/settings/providers", icon: <SettingsIcon /> },
    { title: t("nav.pricing", { defaultValue: "定价" }), url: "/pricing", icon: <CreditCardIcon /> },
    { title: t("nav.docs", { defaultValue: "文档" }), url: "/docs", icon: <BookOpenIcon /> },
    { title: t("nav.teams"), url: "/admin/teams", icon: <UserPlusIcon /> },
    { title: t("nav.invitations"), url: "/admin/invitations", icon: <MailIcon /> },
    { title: t("nav.users"), url: "/admin/users", icon: <UsersIcon /> },
  ];

  const teams = [
    { name: "DocPilot", logo: <FileTextIcon className="size-3" />, plan: t("app.tagline") },
  ];

  const adminOnlyUrls = ["/admin/users", "/admin/teams", "/admin/invitations"];
  const visibleNavItems = navItems.filter(
    (item) => !adminOnlyUrls.includes(item.url) || isAdmin
  );

  const sidebarUser = {
    name: user?.display_name || t("user.fallbackName"),
    email: user?.email || "",
    avatar: "",
  };

  return (
    <SidebarProvider
      style={{
        "--sidebar-width": "calc(var(--spacing) * 72)",
        "--header-height": "calc(var(--spacing) * 12)",
      } as React.CSSProperties}
    >
      <CommandPalette open={state.isOpen && state.mode === "command"} onOpenChange={(open) => { if (!open) toggle(); }} />
      <AppSidebar
        navItems={visibleNavItems}
        teams={teams}
        user={sidebarUser}
      />
      <SidebarInset>
        <SiteHeader />
        <InlineSuggestionBar />
        <div className="flex flex-1 flex-col">
          <div className="@container/main flex flex-1 flex-col gap-2">
            <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
              <ErrorBoundary>
                <Outlet />
              </ErrorBoundary>
            </div>
          </div>
        </div>
      </SidebarInset>
      <AIAssistantPanel />
      <FloatingAssistant />
    </SidebarProvider>
  );
}

// AppLayout - Sidebar navigation for platform pages
function AppLayout() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <PlatformShell />;
}

function MarketingOrPlatformLayout() {
  const { isAuthenticated } = useAuth();

  return isAuthenticated ? <PlatformShell /> : <PublicLayout />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
      <AuthProvider>
      <AIAssistantProvider>
        <TooltipProvider>
          <BrowserRouter>
            <ErrorBoundary>
              <Routes>
                {/* Public pages - Nav navigation */}
                <Route element={<PublicLayout />}>
                  <Route path="/" element={<RootRedirect />} />
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/signup" element={<SignupPage />} />
                  <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                  <Route path="/reset-password" element={<ResetPasswordPage />} />
                  <Route path="/verify-email-prompt" element={<VerifyEmailPromptPage />} />
                  <Route path="/verify-email" element={<VerifyEmailPage />} />
                </Route>

                <Route element={<MarketingOrPlatformLayout />}>
                  <Route path="/pricing" element={<PricingPage />} />
                  <Route path="/docs" element={<DocsPage />} />
                </Route>

                {/* Platform pages - Sidebar navigation */}
                <Route element={<AppLayout />}>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/projects" element={<ProjectListPage />} />
                  <Route path="/projects/:id" element={<ProjectDetailPage />} />
                  <Route path="/account" element={<AccountPage />} />
                  <Route path="/admin/users" element={<UserManagementPage />} />
                  <Route path="/admin/teams" element={<TeamManagementPage />} />
                  <Route path="/admin/invitations" element={<InvitationManagementPage />} />
                  <Route path="/settings/providers" element={<ProviderSettingsPage />} />
                </Route>
              </Routes>
            </ErrorBoundary>
          </BrowserRouter>
          <Toaster />
        </TooltipProvider>
      </AIAssistantProvider>
      </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
