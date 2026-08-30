type RouteLoader = () => Promise<unknown>;

const CHUNK_RECOVERY_PARAM = "__docpilot_chunk_recovery";
const CHUNK_RECOVERY_KEY_PREFIX = "docpilot:chunk-recovery:";

/** Identify the browser errors raised when an old HTML/JS shell asks for a removed Vite chunk. */
export function isDynamicImportError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /failed to fetch dynamically imported module|importing a module script failed|loading chunk|chunkloaderror/i.test(message);
}

function chunkRecoveryKey(chunkName: string): string {
  return `${CHUNK_RECOVERY_KEY_PREFIX}${chunkName}:${window.location.pathname}`;
}

function clearChunkRecoveryState(chunkName: string): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(chunkRecoveryKey(chunkName));
    const url = new URL(window.location.href);
    if (url.searchParams.has(CHUNK_RECOVERY_PARAM)) {
      url.searchParams.delete(CHUNK_RECOVERY_PARAM);
      window.history.replaceState({}, "", url);
    }
  } catch {
    // Storage and history are best-effort browser recovery helpers.
  }
}

function reloadForChunkRecovery(chunkName: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    const key = chunkRecoveryKey(chunkName);
    if (sessionStorage.getItem(key)) return false;
    sessionStorage.setItem(key, "1");
    const url = new URL(window.location.href);
    url.searchParams.set(CHUNK_RECOVERY_PARAM, String(Date.now()));
    window.location.replace(url.href);
    return true;
  } catch {
    return false;
  }
}

/** Load a lazy module and recover once when a browser still holds an obsolete build shell. */
export async function loadWithChunkRecovery<T>(
  loader: () => Promise<T>,
  chunkName: string,
): Promise<T> {
  try {
    const module = await loader();
    clearChunkRecoveryState(chunkName);
    return module;
  } catch (error) {
    if (isDynamicImportError(error) && reloadForChunkRecovery(chunkName)) {
      // Navigation will replace the stale document. Throwing as a fallback
      // keeps the boundary finite if the browser refuses the reload.
      throw error;
    }
    throw error;
  }
}

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
