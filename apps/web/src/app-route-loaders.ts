type RouteLoader = () => Promise<unknown>;

export const routeLoaders = {
  agent: () => import("./features/agent/agent-workspace-page"),
  account: () => import("./features/workbench/account-page"),
  administration: () => import("./features/workbench/workbench-operations-pages"),
  adminDetails: () => import("./features/workbench/administration-detail-pages"),
  bidProjects: () => import("./features/workbench/bid-projects-page"),
  deliverables: () => import("./features/workbench/workbench-operations-pages"),
  dashboard: () => import("./features/workbench/workbench-data-pages"),
  inbox: () => import("./features/workbench/workbench-data-pages"),
  knowledge: () => import("./features/workbench/workbench-data-pages"),
  members: () => import("./features/workbench/workbench-operations-pages"),
  myWork: () => import("./features/workbench/workbench-data-pages"),
  projectWorkspace: () => import("./features/workbench/project-workspace-page"),
  radar: () => import("./features/workbench/radar-page"),
  reviews: () => import("./features/workbench/workbench-operations-pages"),
  runs: () => import("./features/workbench/workbench-data-pages"),
  providerSettings: () => import("./features/workbench/provider-settings-page"),
  webhookSettings: () => import("./features/workbench/webhook-settings-page"),
} as const;

const exactRouteLoaders: Record<string, RouteLoader> = {
  "/account": routeLoaders.account,
  "/administration": routeLoaders.administration,
  "/admin/invitations": routeLoaders.adminDetails,
  "/admin/teams": routeLoaders.adminDetails,
  "/admin/users": routeLoaders.adminDetails,
  "/agent": routeLoaders.agent,
  "/deliverables": routeLoaders.deliverables,
  "/dashboard": routeLoaders.dashboard,
  "/inbox": routeLoaders.inbox,
  "/knowledge": routeLoaders.knowledge,
  "/members": routeLoaders.members,
  "/my-work": routeLoaders.myWork,
  "/projects": routeLoaders.bidProjects,
  "/radar": routeLoaders.radar,
  "/reviews": routeLoaders.reviews,
  "/runs": routeLoaders.runs,
  "/settings/providers": routeLoaders.providerSettings,
  "/settings/webhooks": routeLoaders.webhookSettings,
};

function loaderForPathname(pathname: string) {
  if (pathname.startsWith("/projects/")) return routeLoaders.projectWorkspace;
  return exactRouteLoaders[pathname];
}

/** Warm a route's lazy chunk without making navigation wait for the request. */
export function prefetchRoute(pathname: string) {
  const loader = loaderForPathname(pathname);
  if (!loader) return;
  void loader().catch(() => undefined);
}
