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
const AgentWorkspacePage = lazy(() => import("./features/agent/agent-workspace-page").then(({ AgentWorkspacePage }) => ({ default: AgentWorkspacePage })));
const AccountPageV2 = lazy(() => import("@/features/workbench-v2/account-page-v2").then(({ AccountPageV2 }) => ({ default: AccountPageV2 })));
const ProviderSettingsPageV2 = lazy(() => import("@/features/workbench-v2/provider-settings-page-v2").then(({ ProviderSettingsPageV2 }) => ({ default: ProviderSettingsPageV2 })));
const WebhookSettingsPageV2 = lazy(() => import("@/features/workbench-v2/webhook-settings-page-v2").then(({ WebhookSettingsPageV2 }) => ({ default: WebhookSettingsPageV2 })));
const UserManagementPageV2 = lazy(() => import("@/features/workbench-v2/administration-detail-pages-v2").then(({ UserManagementPageV2 }) => ({ default: UserManagementPageV2 })));
const TeamManagementPageV2 = lazy(() => import("@/features/workbench-v2/administration-detail-pages-v2").then(({ TeamManagementPageV2 }) => ({ default: TeamManagementPageV2 })));
const InvitationManagementPageV2 = lazy(() => import("@/features/workbench-v2/administration-detail-pages-v2").then(({ InvitationManagementPageV2 }) => ({ default: InvitationManagementPageV2 })));
const PlatformShell = lazy(() => import("@/components/platform-shell").then(({ PlatformShell }) => ({ default: PlatformShell })));
const WorkbenchV2Layout = lazy(() => import("@/features/workbench-v2/workbench-v2-layout").then(({ WorkbenchV2Layout }) => ({ default: WorkbenchV2Layout })));
const BidProjectsPageV2 = lazy(() => import("@/features/workbench-v2/bid-projects-page-v2").then(({ BidProjectsPageV2 }) => ({ default: BidProjectsPageV2 })));
const ProjectWorkspacePageV2 = lazy(() => import("@/features/workbench-v2/project-workspace-page-v2").then(({ ProjectWorkspacePageV2 }) => ({ default: ProjectWorkspacePageV2 })));
const RadarPageV2 = lazy(() => import("@/features/workbench-v2/radar-page-v2").then(({ RadarPageV2 }) => ({ default: RadarPageV2 })));
const InboxPageV2 = lazy(() => import("@/features/workbench-v2/workbench-v2-data-pages").then(({ InboxPageV2 }) => ({ default: InboxPageV2 })));
const DashboardPageV2 = lazy(() => import("@/features/workbench-v2/workbench-v2-data-pages").then(({ DashboardPageV2 }) => ({ default: DashboardPageV2 })));
const MyWorkPageV2 = lazy(() => import("@/features/workbench-v2/workbench-v2-data-pages").then(({ MyWorkPageV2 }) => ({ default: MyWorkPageV2 })));
const RunsPageV2 = lazy(() => import("@/features/workbench-v2/workbench-v2-data-pages").then(({ RunsPageV2 }) => ({ default: RunsPageV2 })));
const KnowledgePageV2 = lazy(() => import("@/features/workbench-v2/workbench-v2-data-pages").then(({ KnowledgePageV2 }) => ({ default: KnowledgePageV2 })));
const DeliverablesPageV2 = lazy(() => import("@/features/workbench-v2/workbench-v2-operations-pages").then(({ DeliverablesPageV2 }) => ({ default: DeliverablesPageV2 })));
const ReviewsPageV2 = lazy(() => import("@/features/workbench-v2/workbench-v2-operations-pages").then(({ ReviewsPageV2 }) => ({ default: ReviewsPageV2 })));
const MembersPageV2 = lazy(() => import("@/features/workbench-v2/workbench-v2-operations-pages").then(({ MembersPageV2 }) => ({ default: MembersPageV2 })));
const AdministrationPageV2 = lazy(() => import("@/features/workbench-v2/workbench-v2-operations-pages").then(({ AdministrationPageV2 }) => ({ default: AdministrationPageV2 })));

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

  return <WorkbenchV2Layout />;
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
        <Route path="/dashboard" element={<DashboardPageV2 />} />
        <Route path="/inbox" element={<InboxPageV2 />} />
        <Route path="/my-work" element={<MyWorkPageV2 />} />
        <Route path="/runs" element={<RunsPageV2 />} />
        <Route path="/knowledge" element={<KnowledgePageV2 />} />
        <Route path="/radar" element={<RadarPageV2 />} />
        <Route path="/projects" element={<BidProjectsPageV2 />} />
        <Route path="/projects/:id" element={<ProjectWorkspacePageV2 />} />
        <Route path="/reviews" element={<ReviewsPageV2 />} />
        <Route path="/deliverables" element={<DeliverablesPageV2 />} />
        <Route path="/members" element={<MembersPageV2 />} />
        <Route path="/administration" element={<AdministrationPageV2 />} />
        <Route path="/account" element={<AccountPageV2 />} />
        <Route path="/admin/users" element={<UserManagementPageV2 />} />
        <Route path="/admin/teams" element={<TeamManagementPageV2 />} />
        <Route path="/admin/invitations" element={<InvitationManagementPageV2 />} />
        <Route path="/settings/providers" element={<ProviderSettingsPageV2 />} />
        <Route path="/settings/webhooks" element={<WebhookSettingsPageV2 />} />
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
