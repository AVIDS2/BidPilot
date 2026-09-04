import type { PageContext } from '@/features/agent/state/agent-store';

/**
 * Derive the server-bound Assistant context from the active product route.
 * Global surfaces deliberately clear project context unless it is explicit.
 */
export function assistantContextForLocation(pathname: string, search = ''): PageContext {
  const projectMatch = pathname.match(/^\/projects\/([^/]+)/);
  const agentParams = pathname === '/agent' ? new URLSearchParams(search) : null;
  const projectId =
    projectMatch?.[1] ?? agentParams?.get('project_id') ?? agentParams?.get('project') ?? undefined;

  return projectId ? { page: pathname, projectId } : { page: pathname };
}
