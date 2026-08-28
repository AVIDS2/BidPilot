import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Outlet, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/sonner";
import { Nav } from "@/components/layout/Nav";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ErrorBoundary } from "@/components/error-boundary";
import { ThemeProvider } from "next-themes";
import { Skeleton } from "@/components/ui/skeleton";
import { routeLoaders } from "./app-route-loaders";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
});

const LandingPage = lazy(() => import("./features/landing/landing-page").then(({ LandingPage }) => ({ default: LandingPage })));
const LoginPage = lazy(() => import("./features/auth/login-page").then(({ LoginPage }) => ({ default: LoginPage })));
const SignupPage = lazy(() => import("./features/auth/signup-page").then(({ SignupPage }) => ({ default: SignupPage })));
const ForgotPasswordPage = lazy(() => import("./features/auth/forgot-password-page").then(({ ForgotPasswordPage }) => ({ default: ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import("./features/auth/reset-password-page").then(({ ResetPasswordPage }) => ({ default: ResetPasswordPage })));
const VerifyEmailPromptPage = lazy(() => import("./features/auth/verify-email-prompt-page").then(({ VerifyEmailPromptPage }) => ({ default: VerifyEmailPromptPage })));
const VerifyEmailPage = lazy(() => import("./features/auth/verify-email-page").then(({ VerifyEmailPage }) => ({ default: VerifyEmailPage })));
const PricingPage = lazy(() => import("./features/pricing/pricing-page").then(({ PricingPage }) => ({ default: PricingPage })));
const DocsPage = lazy(() => import("./features/docs/docs-page").then(({ DocsPage }) => ({ default: DocsPage })));
const AgentWorkspacePage = lazy(() => routeLoaders.agent().then(({ AgentWorkspacePage }) => ({ default: AgentWorkspacePage })));
const AccountPage = lazy(() => routeLoaders.account().then(({ AccountPage }) => ({ default: AccountPage })));
const ProviderSettingsPage = lazy(() => routeLoaders.providerSettings().then(({ ProviderSettingsPage }) => ({ default: ProviderSettingsPage })));
const WebhookSettingsPage = lazy(() => routeLoaders.webhookSettings().then(({ WebhookSettingsPage }) => ({ default: WebhookSettingsPage })));
const UserManagementPage = lazy(() => routeLoaders.adminDetails().then(({ UserManagementPage }) => ({ default: UserManagementPage })));
const TeamManagementPage = lazy(() => routeLoaders.adminDetails().then(({ TeamManagementPage }) => ({ default: TeamManagementPage })));
const InvitationManagementPage = lazy(() => routeLoaders.adminDetails().then(({ InvitationManagementPage }) => ({ default: InvitationManagementPage })));
const PlatformShell = lazy(() => import("@/components/platform-shell").then(({ PlatformShell }) => ({ default: PlatformShell })));
const WorkbenchLayout = lazy(() => import("@/features/workbench/workbench-layout").then(({ WorkbenchLayout }) => ({ default: WorkbenchLayout })));
const BidProjectsPage = lazy(() => routeLoaders.bidProjects().then(({ BidProjectsPage }) => ({ default: BidProjectsPage })));
const ProjectWorkspacePage = lazy(() => routeLoaders.projectWorkspace().then(({ ProjectWorkspacePage }) => ({ default: ProjectWorkspacePage })));
const RadarPage = lazy(() => routeLoaders.radar().then(({ RadarPage }) => ({ default: RadarPage })));
const InboxPage = lazy(() => routeLoaders.inbox().then(({ InboxPage }) => ({ default: InboxPage })));
const DashboardPage = lazy(() => routeLoaders.dashboard().then(({ DashboardPage }) => ({ default: DashboardPage })));
const MyWorkPage = lazy(() => routeLoaders.myWork().then(({ MyWorkPage }) => ({ default: MyWorkPage })));
const RunsPage = lazy(() => routeLoaders.runs().then(({ RunsPage }) => ({ default: RunsPage })));
const KnowledgePage = lazy(() => routeLoaders.knowledge().then(({ KnowledgePage }) => ({ default: KnowledgePage })));
const DeliverablesPage = lazy(() => routeLoaders.deliverables().then(({ DeliverablesPage }) => ({ default: DeliverablesPage })));
const ReviewsPage = lazy(() => routeLoaders.reviews().then(({ ReviewsPage }) => ({ default: ReviewsPage })));
const MembersPage = lazy(() => routeLoaders.members().then(({ MembersPage }) => ({ default: MembersPage })));
const AdministrationPage = lazy(() => routeLoaders.administration().then(({ AdministrationPage }) => ({ default: AdministrationPage })));

function RouteLoadingFallback() {
  return (
    <div className="flex min-h-[50dvh] items-center justify-center px-6" role="status" aria-label="正在加载工作区">
      <div className="flex w-full max-w-xl flex-col gap-3">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
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

function PublicLayout() {
  return <div className="dark min-h-[100dvh] overflow-x-hidden bg-background text-foreground"><Nav /><Outlet /></div>;
}

function MarketingOrPlatformLayout() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <PlatformShell /> : <PublicLayout />;
}

// AppLayout - Sidebar navigation for platform pages
function AppLayout() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <WorkbenchLayout />;
}

function AppRoutes() {
  return (
    <Routes>
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
        <Route path="/inbox" element={<InboxPage />} />
        <Route path="/my-work" element={<MyWorkPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/radar" element={<RadarPage />} />
        <Route path="/projects" element={<BidProjectsPage />} />
        <Route path="/projects/:id" element={<ProjectWorkspacePage />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/deliverables" element={<DeliverablesPage />} />
        <Route path="/members" element={<MembersPage />} />
        <Route path="/administration" element={<AdministrationPage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/admin/users" element={<UserManagementPage />} />
        <Route path="/admin/teams" element={<TeamManagementPage />} />
        <Route path="/admin/invitations" element={<InvitationManagementPage />} />
        <Route path="/settings/providers" element={<ProviderSettingsPage />} />
        <Route path="/settings/webhooks" element={<WebhookSettingsPage />} />
        <Route path="/agent" element={<AgentWorkspacePage />} />
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
