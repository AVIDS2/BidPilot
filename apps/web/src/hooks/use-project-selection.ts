'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo } from 'react';
import type { ProjectRead } from '@/lib/bidpilot-api';

/** Keep project-scoped work surfaces aligned with the URL and each other. */
export function useProjectSelection(projects?: ProjectRead[]) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedProjectId = searchParams.get('project_id') || searchParams.get('project') || '';
  const availableProjectIds = useMemo(
    () => new Set((projects ?? []).map((project) => project.id)),
    [projects]
  );
  const projectId = useMemo(() => {
    if (requestedProjectId && availableProjectIds.has(requestedProjectId)) {
      return requestedProjectId;
    }
    return projects?.[0]?.id ?? '';
  }, [availableProjectIds, projects, requestedProjectId]);

  const updateUrl = useCallback(
    (nextProjectId: string) => {
      const nextParams = new URLSearchParams(searchParams.toString());
      nextParams.delete('project');
      if (nextProjectId) nextParams.set('project_id', nextProjectId);
      else nextParams.delete('project_id');
      const query = nextParams.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams]
  );

  useEffect(() => {
    if (!projects?.length || !requestedProjectId || availableProjectIds.has(requestedProjectId)) {
      return;
    }
    updateUrl(projectId);
  }, [availableProjectIds, projectId, projects, requestedProjectId, updateUrl]);

  const hasExplicitSelection = Boolean(
    requestedProjectId && availableProjectIds.has(requestedProjectId)
  );

  return { projectId, onChange: updateUrl, hasExplicitSelection };
}
