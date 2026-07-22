import type { PageContext } from "@/lib/ai-assistant-store";

/**
 * Derive the server-bound Assistant context from the active product route.
 * Global surfaces deliberately clear project context unless it is explicit.
 */
export function assistantContextForLocation(pathname: string, search = ""): PageContext {
  const projectMatch = pathname.match(/^\/projects\/([^/]+)/);
  const projectId = projectMatch?.[1] ?? (
    pathname === "/agent" ? new URLSearchParams(search).get("project") ?? undefined : undefined
  );

  return projectId ? { page: pathname, projectId } : { page: pathname };
}
