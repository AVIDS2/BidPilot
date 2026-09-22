'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from '@/components/ui/sheet';
import { ProjectPicker } from '@/components/bidpilot/project-picker';
import { QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { useIsMobile } from '@/hooks/use-mobile';
import { useProjectSelection } from '@/hooks/use-project-selection';
import {
  approveMemory,
  listBundles,
  listDocuments,
  listProjectMemory,
  listProjects,
  searchKnowledge,
  startMemoryCompilation
} from '@/lib/bidpilot-api';
import { KnowledgeCenter } from './knowledge-center';
import { KnowledgeInspector } from './knowledge-inspector';
import { KnowledgeProjectList } from './knowledge-project-list';
import type { InspectorView, WorkspaceView } from './knowledge-types';

export function KnowledgeWorkspace() {
  const client = useQueryClient();
  const isMobile = useIsMobile();
  const [view, setView] = useState<WorkspaceView>('documents');
  const [inspector, setInspector] = useState<InspectorView>('search');
  const [mobileInspectorOpen, setMobileInspectorOpen] = useState(false);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
    staleTime: 30_000,
    refetchOnWindowFocus: true
  });
  const { projectId, onChange: setProjectId } = useProjectSelection(projects.data);
  const bundles = useQuery({
    queryKey: ['knowledge-bundles', projectId],
    queryFn: () => listBundles(projectId),
    enabled: Boolean(projectId),
    refetchInterval: (query) =>
      query.state.data?.some((bundle) =>
        ['queued', 'running', 'indexing'].includes(bundle.ingest_status)
      )
        ? 5_000
        : 30_000,
    refetchOnWindowFocus: true
  });
  const documentQueries = useQueries({
    queries: (bundles.data ?? []).map((bundle) => ({
      queryKey: ['knowledge-documents', bundle.id],
      queryFn: () => listDocuments(bundle.id, 1, 100),
      staleTime: 10_000,
      refetchOnWindowFocus: true
    }))
  });
  const projectMemory = useQuery({
    queryKey: ['project-knowledge', projectId],
    queryFn: () => listProjectMemory(projectId, true, true),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const search = useQuery({
    queryKey: ['knowledge-search', projectId, debouncedSearch],
    queryFn: () => searchKnowledge({ project_id: projectId, query: debouncedSearch, top_k: 10 }),
    enabled: Boolean(projectId && debouncedSearch.length >= 2),
    staleTime: 15_000,
    retry: false
  });
  const compile = useMutation({
    mutationFn: () => startMemoryCompilation({ project_id: projectId }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['project-knowledge', projectId] });
      toast.success('知识建议已开始整理，完成后会出现在项目知识中。');
    },
    onError: () => toast.error('暂时无法整理知识建议，请确认资料已完成处理。')
  });
  const approve = useMutation({
    mutationFn: approveMemory,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['project-knowledge', projectId] });
      toast.success('这条知识已纳入项目知识。');
    },
    onError: () => toast.error('这条知识暂时无法确认，请稍后重试。')
  });

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(searchText.trim()), 280);
    return () => window.clearTimeout(timer);
  }, [searchText]);

  const documents = useMemo(() => {
    const project = projects.data?.find((item) => item.id === projectId);
    if (!project) return [];
    return (bundles.data ?? []).flatMap((bundle, index) =>
      (documentQueries[index]?.data?.items ?? []).map((document) => ({
        ...document,
        bundle,
        project
      }))
    );
  }, [bundles.data, documentQueries, projectId, projects.data]);
  const selectedDocument = documents.find((document) => document.id === documentId) ?? null;
  const indexedCount = documents.filter((document) => document.index_status === 'indexed').length;
  const processingCount = documents.filter((document) =>
    ['pending', 'parsing', 'queued'].includes(document.parse_status)
  ).length;
  const activeMemoryCount =
    projectMemory.data?.filter((item) => item.status === 'active').length ?? 0;
  const proposedMemoryCount =
    projectMemory.data?.filter((item) => item.status === 'proposed').length ?? 0;
  const currentProject = projects.data?.find((project) => project.id === projectId);
  const loadingDocuments = bundles.isPending || documentQueries.some((query) => query.isPending);

  const selectDocument = (nextId: string) => {
    setDocumentId(nextId);
    setInspector('document');
    if (isMobile) setMobileInspectorOpen(true);
  };
  const openInspector = (nextView: InspectorView) => {
    setInspector(nextView);
    setMobileInspectorOpen(true);
  };

  if (projects.isPending) return <QuerySkeleton rows={6} />;
  if (projects.error) return <QueryError message='项目列表暂时无法加载，请稍后重试。' />;
  if (!projects.data?.length || !projectId) return <EmptyProjectState />;

  const center = (
    <KnowledgeCenter
      view={view}
      onViewChange={setView}
      documents={documents}
      memories={projectMemory.data ?? []}
      loadingDocuments={loadingDocuments}
      memoryLoading={projectMemory.isPending}
      memoryError={Boolean(projectMemory.error)}
      selectedDocumentId={documentId}
      onSelectDocument={selectDocument}
      onApproveMemory={(id) => approve.mutate(id)}
      approvingMemoryId={approve.isPending ? (approve.variables ?? null) : null}
      projectId={projectId}
    />
  );
  const inspectorPanel = (
    <KnowledgeInspector
      view={inspector}
      onViewChange={setInspector}
      searchText={searchText}
      onSearchTextChange={setSearchText}
      search={search.data ?? []}
      searching={search.isPending}
      searchError={Boolean(search.error)}
      documents={documents}
      selectedDocument={selectedDocument}
      onSelectDocument={selectDocument}
      project={currentProject}
      documentCount={documents.length}
      indexedCount={indexedCount}
      processingCount={processingCount}
      activeMemoryCount={activeMemoryCount}
      proposedMemoryCount={proposedMemoryCount}
      compiling={compile.isPending}
      onCompile={() => compile.mutate()}
    />
  );

  return (
    <>
      <div className='hidden min-h-[680px] overflow-hidden rounded-lg border bg-background lg:flex'>
        <ResizablePanelGroup orientation='horizontal'>
          <ResizablePanel defaultSize='22%' minSize='18%' maxSize='30%' className='min-w-0'>
            <KnowledgeProjectList
              projects={projects.data}
              projectId={projectId}
              onChange={setProjectId}
            />
          </ResizablePanel>
          <ResizableHandle />
          <ResizablePanel defaultSize='52%' minSize='38%' className='min-w-0'>
            {center}
          </ResizablePanel>
          <ResizableHandle />
          <ResizablePanel defaultSize='26%' minSize='22%' maxSize='38%' className='min-w-0'>
            {inspectorPanel}
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      <div className='flex flex-col gap-3 lg:hidden'>
        <ProjectPicker projects={projects.data} value={projectId} onChange={setProjectId} />
        {center}
        <div className='grid grid-cols-2 gap-2'>
          <Button onClick={() => openInspector('search')} variant='outline'>
            检索知识
          </Button>
          <Button onClick={() => openInspector('status')} variant='outline'>
            索引状态
          </Button>
        </div>
      </div>

      <Sheet open={mobileInspectorOpen} onOpenChange={setMobileInspectorOpen}>
        <SheetContent side='right' className='w-full p-0 sm:max-w-md'>
          <SheetHeader className='border-b'>
            <SheetTitle>知识工作区</SheetTitle>
            <SheetDescription>检索来源、查看资料，或检查当前项目的知识状态。</SheetDescription>
          </SheetHeader>
          {inspectorPanel}
        </SheetContent>
      </Sheet>
    </>
  );
}

function EmptyProjectState() {
  return (
    <div className='flex min-h-[28rem] flex-col items-center justify-center gap-4 rounded-lg border text-center'>
      <Badge variant='outline'>知识工作区</Badge>
      <div>
        <h2 className='font-semibold'>先创建一个项目</h2>
        <p className='text-muted-foreground mt-2 max-w-sm text-sm'>
          知识库会围绕项目资料、可检索内容和已确认事实工作。
        </p>
      </div>
      <Link className='text-primary text-sm underline underline-offset-4' href='/projects'>
        打开项目
      </Link>
    </div>
  );
}
