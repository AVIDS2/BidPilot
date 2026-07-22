import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Outlet, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/sonner";
import { Nav } from "@/components/layout/Nav";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ErrorBoundary } from "@/components/error-boundary";
import { ThemeProvider } from "next-themes";

const queryClient = new QueryClient();

const LandingPage = lazy(() => import("./features/landing/landing-page").then(({ LandingPage }) => ({ default: LandingPage })));
const LoginPage = lazy(() => import("./features/auth/login-page").then(({ LoginPage }) => ({ default: LoginPage })));
const SignupPage = lazy(() => import("./features/auth/signup-page").then(({ SignupPage }) => ({ default: SignupPage })));
const ForgotPasswordPage = lazy(() => import("./features/auth/forgot-password-page").then(({ ForgotPasswordPage }) => ({ default: ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import("./features/auth/reset-password-page").then(({ ResetPasswordPage }) => ({ default: ResetPasswordPage })));
const VerifyEmailPromptPage = lazy(() => import("./features/auth/verify-email-prompt-page").then(({ VerifyEmailPromptPage }) => ({ default: VerifyEmailPromptPage })));
const VerifyEmailPage = lazy(() => import("./features/auth/verify-email-page").then(({ VerifyEmailPage }) => ({ default: VerifyEmailPage })));
const PricingPage = lazy(() => import("./features/pricing/pricing-page").then(({ PricingPage }) => ({ default: PricingPage })));
const DocsPage = lazy(() => import("./features/docs/docs-page").then(({ DocsPage }) => ({ default: DocsPage })));
const DashboardPage = lazy(() => import("./features/dashboard/dashboard-page").then(({ DashboardPage }) => ({ default: DashboardPage })));
const AgentWorkspacePage = lazy(() => import("./features/agent/agent-workspace-page").then(({ AgentWorkspacePage }) => ({ default: AgentWorkspacePage })));
const RunCenterPage = lazy(() => import("./features/runs/run-center-page").then(({ RunCenterPage }) => ({ default: RunCenterPage })));
const KnowledgePortfolioPage = lazy(() => import("./features/knowledge/knowledge-portfolio-page").then(({ KnowledgePortfolioPage }) => ({ default: KnowledgePortfolioPage })));
const ProjectListPage = lazy(() => import("./features/projects/project-list-page").then(({ ProjectListPage }) => ({ default: ProjectListPage })));
const ProjectDetailPage = lazy(() => import("./features/projects/project-detail-page").then(({ ProjectDetailPage }) => ({ default: ProjectDetailPage })));
const AccountPage = lazy(() => import("./features/account/account-page").then(({ AccountPage }) => ({ default: AccountPage })));
const UserManagementPage = lazy(() => import("./features/admin/user-management-page").then(({ UserManagementPage }) => ({ default: UserManagementPage })));
const TeamManagementPage = lazy(() => import("./features/admin/team-management-page").then(({ TeamManagementPage }) => ({ default: TeamManagementPage })));
const InvitationManagementPage = lazy(() => import("./features/admin/invitation-management-page").then(({ InvitationManagementPage }) => ({ default: InvitationManagementPage })));
const ProviderSettingsPage = lazy(() => import("./features/settings/provider-settings-page").then(({ ProviderSettingsPage }) => ({ default: ProviderSettingsPage })));
const PlatformShell = lazy(() => import("@/components/platform-shell").then(({ PlatformShell }) => ({ default: PlatformShell })));

function RouteLoadingFallback() {
  return (
    <div className="flex min-h-[50dvh] items-center justify-center text-sm text-muted-foreground" role="status">
      Loading workspace...
    </div>
  );
}

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
    <div className="dark min-h-[100dvh] overflow-x-hidden bg-background text-foreground">
      <Nav />
      <Outlet />
    </div>
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

function AppRoutes() {
  return (
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
        <Route path="/agent" element={<AgentWorkspacePage />} />
        <Route path="/runs" element={<RunCenterPage />} />
        <Route path="/knowledge" element={<KnowledgePortfolioPage />} />
        <Route path="/projects" element={<ProjectListPage />} />
        <Route path="/projects/:id" element={<ProjectDetailPage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/admin/users" element={<UserManagementPage />} />
        <Route path="/admin/teams" element={<TeamManagementPage />} />
        <Route path="/admin/invitations" element={<InvitationManagementPage />} />
        <Route path="/settings/providers" element={<ProviderSettingsPage />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
      <AuthProvider>
        <BrowserRouter>
          <ErrorBoundary>
            <Suspense fallback={<RouteLoadingFallback />}>
              <AppRoutes />
            </Suspense>
          </ErrorBoundary>
        </BrowserRouter>
        <Toaster />
      </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
