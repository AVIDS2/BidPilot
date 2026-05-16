import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Outlet, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ProjectListPage } from "./features/projects/project-list-page";
import { ProjectDetailPage } from "./features/projects/project-detail-page";
import { AccountPage } from "./features/account/account-page";
import { PricingPage } from "./features/pricing/pricing-page";
import { LandingPage } from "./features/landing/landing-page";
import { UserManagementPage } from "./features/admin/user-management-page";
import { ForgotPasswordPage } from "./features/auth/forgot-password-page";
import { ResetPasswordPage } from "./features/auth/reset-password-page";
import { VerifyEmailPromptPage } from "./features/auth/verify-email-prompt-page";
import { VerifyEmailPage } from "./features/auth/verify-email-page";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { AppSidebar } from "@/components/app-sidebar";
import { SiteHeader } from "@/components/site-header";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { LoginForm } from "@/components/login-form";
import { SignupForm } from "@/components/signup-form";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ErrorBoundary } from "@/components/error-boundary";
import { FileTextIcon, CreditCardIcon, UsersIcon } from "lucide-react";

const queryClient = new QueryClient();

function LoginPage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-md flex-col gap-6">
        <a href="#" className="flex items-center gap-2 self-center font-medium">
          <div className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <FileTextIcon className="size-4" />
          </div>
          DocPilot
        </a>
        <LoginForm />
      </div>
    </div>
  );
}

function SignupPage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-3xl flex-col gap-6">
        <a href="#" className="flex items-center gap-2 self-center font-medium">
          <div className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <FileTextIcon className="size-4" />
          </div>
          DocPilot
        </a>
        <SignupForm />
      </div>
    </div>
  );
}

function AppLayout() {
  const { user, isAuthenticated } = useAuth();
  const { t } = useTranslation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const isAdmin = user?.role === "admin";

  const navItems = [
    { title: t("nav.projects"), url: "/projects", icon: <FileTextIcon /> },
    { title: t("nav.pricing"), url: "/pricing", icon: <CreditCardIcon /> },
    { title: t("nav.users"), url: "/admin/users", icon: <UsersIcon /> },
  ];

  const teams = [
    { name: "DocPilot", logo: <FileTextIcon className="size-3" />, plan: t("app.tagline") },
  ];

  const visibleNavItems = navItems.filter(
    (item) => item.title !== t("nav.users") || isAdmin
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
      <AppSidebar
        navItems={visibleNavItems}
        teams={teams}
        user={sidebarUser}
      />
      <SidebarInset>
        <SiteHeader />
        <div className="flex flex-1 flex-col">
          <div className="@container/main flex flex-1 flex-col gap-2">
            <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
              <Outlet />
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <BrowserRouter>
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/pricing" element={<PricingPage />} />
                <Route element={<AppLayout />}>
                  <Route path="/projects" element={<ProjectListPage />} />
                  <Route path="/projects/:id" element={<ProjectDetailPage />} />
                  <Route path="/account" element={<AccountPage />} />
                  <Route path="/admin/users" element={<UserManagementPage />} />
                </Route>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/signup" element={<SignupPage />} />
                <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                <Route path="/reset-password" element={<ResetPasswordPage />} />
                <Route path="/verify-email-prompt" element={<VerifyEmailPromptPage />} />
                <Route path="/verify-email" element={<VerifyEmailPage />} />
              </Routes>
            </ErrorBoundary>
          </BrowserRouter>
          <Toaster />
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
