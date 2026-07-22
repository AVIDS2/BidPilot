import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import {
  BookOpenCheckIcon,
  CheckIcon,
  FileTextIcon,
  GitBranchIcon,
  LoaderCircleIcon,
  NetworkIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  SparklesIcon,
  XIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  approveMemory,
  getMemoryEvidenceMap,
  getMemoryCompilation,
  listProjectMemory,
  reviewMemoryGraphItem,
  startMemoryCompilation,
  startMemoryGraphExtraction,
  type MemoryGraphProposalRead,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type GraphNode = Node<{ label: ReactNode }>;

interface KnowledgeTabProps {
  projectId: string;
  canApprove: boolean;
}

const COMPILATION_IN_PROGRESS = new Set(["queued", "running"]);

function locatorSummary(locator: Record<string, unknown> | null) {
  if (!locator) return null;

  const parts: string[] = [];
  if (typeof locator.page === "number" || typeof locator.page === "string") {
    parts.push(`p. ${locator.page}`);
  }
  if (typeof locator.section === "string") {
    parts.push(`§ ${locator.section}`);
  }
  if (typeof locator.chunk_index === "number") {
    parts.push(`#${locator.chunk_index + 1}`);
  }
  if (Array.isArray(locator.heading_path) && locator.heading_path.length > 0) {
    parts.push(locator.heading_path.filter((item): item is string => typeof item === "string").join(" / "));
  }
  return parts.filter(Boolean).join(" · ") || null;
}

function formatRecordDate(value: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(date);
}

export function KnowledgeTab({ projectId, canApprove }: KnowledgeTabProps) {
  const { t } = useTranslation("projects");
  const queryClient = useQueryClient();
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null);
  const [compilationRunId, setCompilationRunId] = useState<string | null>(null);

  const memoryQuery = useQuery({
    queryKey: ["project-memory", projectId, canApprove ? "with-proposals" : "active"],
    queryFn: () => listProjectMemory(projectId, canApprove),
    staleTime: 15_000,
  });
  const compilationQuery = useQuery({
    queryKey: ["memory-compilation", compilationRunId],
    queryFn: () => getMemoryCompilation(compilationRunId!),
    enabled: !!compilationRunId,
    refetchInterval: (query) =>
      COMPILATION_IN_PROGRESS.has(query.state.data?.status ?? "queued") ? 2_500 : false,
  });
  const evidenceMapQuery = useQuery({
    queryKey: ["memory-evidence-map", projectId],
    queryFn: () => getMemoryEvidenceMap(projectId),
    staleTime: 15_000,
  });

  const records = useMemo(
    () =>
      [...(memoryQuery.data ?? [])].sort((left, right) => {
        if (left.status === right.status) return (right.updated_at ?? "").localeCompare(left.updated_at ?? "");
        return left.status === "proposed" ? -1 : 1;
      }),
    [memoryQuery.data],
  );
  const selectedRecord = records.find((record) => record.id === selectedRecordId) ?? records[0] ?? null;
  const activeCount = records.filter((record) => record.status === "active").length;
  const proposalCount = records.filter((record) => record.status === "proposed").length;

  useEffect(() => {
    setSelectedRecordId((current) => {
      if (current && records.some((record) => record.id === current)) return current;
      return records[0]?.id ?? null;
    });
  }, [records]);

  useEffect(() => {
    if (compilationQuery.data?.status !== "succeeded") return;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["project-memory", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["memory-evidence-map", projectId] }),
    ]);
  }, [compilationQuery.data?.status, projectId, queryClient]);

  const compileMutation = useMutation({
    mutationFn: () => startMemoryCompilation({ project_id: projectId }),
    onSuccess: (run) => {
      setCompilationRunId(run.id);
      toast.success(t("knowledge.compilationQueued"));
    },
    onError: () => toast.error(t("knowledge.compilationFailed")),
  });
  const approveMutation = useMutation({
    mutationFn: approveMemory,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project-memory", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["memory-evidence-map", projectId] }),
      ]);
      toast.success(t("knowledge.approved"));
    },
    onError: () => toast.error(t("knowledge.approveFailed")),
  });
  const graphExtractionMutation = useMutation({
    mutationFn: (memoryRecordId: string) =>
      startMemoryGraphExtraction({ project_id: projectId, memory_record_id: memoryRecordId }),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: ["runtime-runs"] });
      toast.success(run.reused ? t("knowledge.graphExtractionAlreadyQueued") : t("knowledge.graphExtractionQueued"));
    },
    onError: () => toast.error(t("knowledge.graphExtractionFailed")),
  });
  const graphReviewMutation = useMutation({
    mutationFn: ({
      memoryId,
      itemId,
      decision,
    }: {
      memoryId: string;
      itemId: string;
      decision: "accepted" | "rejected";
    }) => reviewMemoryGraphItem(memoryId, { item_id: itemId, decision }),
    onSuccess: async (_result, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["project-memory", projectId] });
      toast.success(
        variables.decision === "accepted"
          ? t("knowledge.graphReviewAccepted")
          : t("knowledge.graphReviewRejected"),
      );
    },
    onError: () => toast.error(t("knowledge.graphReviewFailed")),
  });

  const graph = useMemo(() => {
    const map = evidenceMapQuery.data;
    const memoryNodes = (map?.nodes ?? []).filter((node) => node.node_type === "memory");
    const sourceNodes = (map?.nodes ?? []).filter((node) => node.node_type === "source");
    const nodes: GraphNode[] = [
      ...memoryNodes.map((node, index) => ({
        id: node.id,
        position: { x: 24, y: index * 112 },
        data: {
          label: (
            <div className="w-52">
              <div className="flex items-center gap-2">
                <BookOpenCheckIcon className="size-3.5 shrink-0 text-primary" />
                <span className="truncate text-xs font-semibold">{node.label}</span>
              </div>
              {node.memory_kind && (
                <p className="mt-1 text-[11px] text-muted-foreground">
                  {t(`knowledge.kinds.${node.memory_kind}`, { defaultValue: node.memory_kind })}
                </p>
              )}
            </div>
          ),
        },
        className: "rounded-xl border border-border bg-card p-2 shadow-sm",
      })),
      ...sourceNodes.map((node, index) => ({
        id: node.id,
        position: { x: 360, y: index * 112 },
        data: {
          label: (
            <div className="w-48">
              <div className="flex items-center gap-2">
                <FileTextIcon className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate text-xs font-medium">{node.label}</span>
              </div>
              {node.source_type && (
                <p className="mt-1 truncate text-[11px] text-muted-foreground">
                  {t(`knowledge.citationTypes.${node.source_type}`, { defaultValue: node.source_type })}
                </p>
              )}
            </div>
          ),
        },
        className: "rounded-xl border border-border bg-muted/35 p-2 shadow-none",
      })),
    ];
    const edges: Edge[] = (map?.edges ?? []).map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
    }));
    return { nodes, edges, truncated: map?.truncated ?? false };
  }, [evidenceMapQuery.data, t]);

  const compilation = compilationQuery.data;
  const compilationIsRunning = compilation ? COMPILATION_IN_PROGRESS.has(compilation.status) : false;
  const compilationCreated = compilation?.result_json?.proposals_created;

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <Card>
        <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2 text-lg">
              <BookOpenCheckIcon className="size-5 text-primary" />
              {t("knowledge.title")}
            </CardTitle>
            <CardDescription className="mt-1 max-w-3xl">{t("knowledge.description")}</CardDescription>
          </div>
          {canApprove && (
            <Button
              onClick={() => compileMutation.mutate()}
              disabled={compileMutation.isPending || compilationIsRunning}
            >
              {compileMutation.isPending || compilationIsRunning ? (
                <LoaderCircleIcon data-icon="inline-start" className="animate-spin" />
              ) : (
                <SparklesIcon data-icon="inline-start" />
              )}
              {t("knowledge.compile")}
            </Button>
          )}
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{t("knowledge.activeCount", { count: activeCount })}</Badge>
          {canApprove && <Badge variant="outline">{t("knowledge.proposalCount", { count: proposalCount })}</Badge>}
          <span className="text-xs text-muted-foreground">{t("knowledge.scopeHint")}</span>
        </CardContent>
      </Card>

      {compilation && (
        <Card className={cn(compilation.status === "failed" && "border-destructive/40")}>
          <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              {compilationIsRunning ? (
                <LoaderCircleIcon className="size-4 shrink-0 animate-spin text-primary" />
              ) : compilation.status === "succeeded" ? (
                <CheckIcon className="size-4 shrink-0 text-primary" />
              ) : (
                <RefreshCwIcon className="size-4 shrink-0 text-muted-foreground" />
              )}
              <div className="min-w-0">
                <p className="text-sm font-medium">{t(`knowledge.compilationStates.${compilation.status}`, { defaultValue: compilation.status })}</p>
                <p className="text-xs text-muted-foreground">
                  {compilation.status === "succeeded" && typeof compilationCreated === "number"
                    ? t("knowledge.compilationFinished", { count: compilationCreated })
                    : t("knowledge.compilationProgress", { count: compilation.input_source_count })}
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={() => void compilationQuery.refetch()}>
              <RefreshCwIcon data-icon="inline-start" />
              {t("knowledge.refresh")}
            </Button>
          </CardContent>
        </Card>
      )}

      {memoryQuery.isLoading && (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.9fr)]">
          <Skeleton className="h-[430px]" />
          <Skeleton className="h-[430px]" />
        </div>
      )}

      {memoryQuery.isError && (
        <Card>
          <CardContent className="py-8">
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><RefreshCwIcon /></EmptyMedia>
                <EmptyTitle>{t("knowledge.loadFailed")}</EmptyTitle>
                <EmptyDescription>{t("knowledge.loadFailedDescription")}</EmptyDescription>
              </EmptyHeader>
              <Button variant="outline" onClick={() => void memoryQuery.refetch()}>{t("knowledge.refresh")}</Button>
            </Empty>
          </CardContent>
        </Card>
      )}

      {!memoryQuery.isLoading && !memoryQuery.isError && records.length === 0 && (
        <Card>
          <CardContent className="py-8">
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><GitBranchIcon /></EmptyMedia>
                <EmptyTitle>{t("knowledge.emptyTitle")}</EmptyTitle>
                <EmptyDescription>
                  {canApprove ? t("knowledge.emptyManagerDescription") : t("knowledge.emptyDescription")}
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          </CardContent>
        </Card>
      )}

      {!memoryQuery.isLoading && !memoryQuery.isError && records.length > 0 && (
        <>
          <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.9fr)]">
            <Card className="min-w-0">
              <CardHeader>
                <CardTitle className="text-base">{t("knowledge.ledgerTitle")}</CardTitle>
                <CardDescription>{t("knowledge.ledgerDescription")}</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[360px]">
                  <div className="flex flex-col gap-2 pr-4">
                    {records.map((record) => {
                      const isSelected = record.id === selectedRecord?.id;
                      const isProposed = record.status === "proposed";
                      return (
                        <div
                          key={record.id}
                          className={cn(
                            "flex min-w-0 items-start gap-3 rounded-xl border p-3 transition-colors",
                            isSelected ? "border-primary/40 bg-primary/5" : "border-border hover:bg-muted/40",
                          )}
                        >
                          <button
                            type="button"
                            className="min-w-0 flex-1 text-left"
                            onClick={() => setSelectedRecordId(record.id)}
                            aria-pressed={isSelected}
                            aria-label={t("knowledge.selectRecord", { title: record.title })}
                          >
                            <div className="flex min-w-0 flex-wrap items-center gap-2">
                              <span className="truncate text-sm font-medium">{record.title}</span>
                              <Badge variant={isProposed ? "outline" : "secondary"}>
                                {t(`knowledge.statuses.${record.status}`, { defaultValue: record.status })}
                              </Badge>
                              <Badge variant="outline">{t(`knowledge.kinds.${record.kind}`, { defaultValue: record.kind })}</Badge>
                            </div>
                            <p className="mt-1 line-clamp-2 text-sm leading-5 text-muted-foreground">{record.body_markdown}</p>
                            <p className="mt-2 text-xs text-muted-foreground">
                              {t("knowledge.sourceCount", { count: record.citations.length })}
                              {formatRecordDate(record.updated_at) ? ` · ${formatRecordDate(record.updated_at)}` : ""}
                            </p>
                          </button>
                          {isProposed && canApprove && !record.graph_proposal && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={approveMutation.isPending}
                              onClick={() => approveMutation.mutate(record.id)}
                              aria-label={t("knowledge.approveRecord", { title: record.title })}
                            >
                              <ShieldCheckIcon data-icon="inline-start" />
                              {t("knowledge.approve")}
                            </Button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            <Card className="min-w-0">
              <CardHeader>
                <CardTitle className="text-base">{t("knowledge.traceTitle")}</CardTitle>
                <CardDescription>{selectedRecord?.title ?? t("knowledge.traceEmpty")}</CardDescription>
              </CardHeader>
              <CardContent>
                {selectedRecord && (
                  <div className="flex flex-col gap-4">
                    <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">{selectedRecord.body_markdown}</p>
                    {selectedRecord.graph_proposal && (
                      <GraphProposalReview
                        proposal={selectedRecord.graph_proposal}
                        canReview={canApprove && selectedRecord.status === "proposed"}
                        pendingItemId={graphReviewMutation.isPending ? graphReviewMutation.variables?.itemId ?? null : null}
                        isFinalizing={approveMutation.isPending}
                        onReview={(itemId, decision) =>
                          graphReviewMutation.mutate({
                            memoryId: selectedRecord.id,
                            itemId,
                            decision,
                          })
                        }
                        onFinalize={() => approveMutation.mutate(selectedRecord.id)}
                      />
                    )}
                    {canApprove && selectedRecord.status === "active" && selectedRecord.citations.length > 0 && (
                      <div className="flex flex-col gap-3 rounded-xl border bg-muted/20 p-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <p className="text-sm font-medium">{t("knowledge.graphExtractionTitle")}</p>
                          <p className="mt-1 text-xs leading-5 text-muted-foreground">
                            {t("knowledge.graphExtractionHint")}
                          </p>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          className="shrink-0"
                          disabled={graphExtractionMutation.isPending}
                          onClick={() => graphExtractionMutation.mutate(selectedRecord.id)}
                        >
                          {graphExtractionMutation.isPending ? (
                            <LoaderCircleIcon data-icon="inline-start" className="animate-spin" />
                          ) : (
                            <NetworkIcon data-icon="inline-start" />
                          )}
                          {t("knowledge.extractGraph")}
                        </Button>
                      </div>
                    )}
                    <div className="flex flex-col gap-2">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {t("knowledge.sources")}
                      </p>
                      {selectedRecord.citations.map((citation) => (
                        <div key={`${citation.source_type}-${citation.source_id}`} className="rounded-lg border bg-muted/25 p-3">
                          <p className="text-sm font-medium">{citation.label}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {t(`knowledge.citationTypes.${citation.source_type}`, { defaultValue: citation.source_type })}
                            {locatorSummary(citation.locator_json) ? ` · ${locatorSummary(citation.locator_json)}` : ""}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="min-w-0">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <NetworkIcon className="size-4 text-primary" />
                {t("knowledge.mapTitle")}
              </CardTitle>
              <CardDescription>{t("knowledge.mapDescription")}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[360px] overflow-hidden rounded-xl border bg-muted/15" data-testid="bid-wiki-provenance-map">
                {evidenceMapQuery.isLoading ? (
                  <Skeleton className="h-full w-full" />
                ) : evidenceMapQuery.isError ? (
                  <Empty className="h-full">
                    <EmptyHeader>
                      <EmptyMedia variant="icon"><RefreshCwIcon /></EmptyMedia>
                      <EmptyTitle>{t("knowledge.mapLoadFailed")}</EmptyTitle>
                      <EmptyDescription>{t("knowledge.mapLoadFailedDescription")}</EmptyDescription>
                    </EmptyHeader>
                    <Button variant="outline" size="sm" onClick={() => void evidenceMapQuery.refetch()}>
                      {t("knowledge.refresh")}
                    </Button>
                  </Empty>
                ) : graph.nodes.length === 0 ? (
                  <Empty className="h-full">
                    <EmptyHeader>
                      <EmptyMedia variant="icon"><NetworkIcon /></EmptyMedia>
                      <EmptyTitle>{t("knowledge.mapEmptyTitle")}</EmptyTitle>
                      <EmptyDescription>{t("knowledge.mapEmptyDescription")}</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                ) : (
                  <ReactFlow
                    nodes={graph.nodes}
                    edges={graph.edges}
                    fitView
                    fitViewOptions={{ padding: 0.2 }}
                    nodesDraggable={false}
                    nodesConnectable={false}
                    elementsSelectable
                    proOptions={{ hideAttribution: true }}
                  >
                    <Background gap={22} size={1} color="color-mix(in oklch, var(--border) 70%, transparent)" />
                    <Controls showInteractive={false} />
                  </ReactFlow>
                )}
              </div>
              {graph.truncated && <p className="mt-2 text-xs text-muted-foreground">{t("knowledge.mapTruncated")}</p>}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function GraphProposalReview({
  proposal,
  canReview,
  pendingItemId,
  isFinalizing,
  onReview,
  onFinalize,
}: {
  proposal: MemoryGraphProposalRead;
  canReview: boolean;
  pendingItemId: string | null;
  isFinalizing: boolean;
  onReview: (itemId: string, decision: "accepted" | "rejected") => void;
  onFinalize: () => void;
}) {
  const { t } = useTranslation("projects");
  const items = [...proposal.entities, ...proposal.relations];
  const pendingCount = items.filter((item) => item.review_status === "pending").length;
  const acceptedCount = items.filter((item) => item.review_status === "accepted").length;
  const rejectedCount = items.filter((item) => item.review_status === "rejected").length;

  const reviewBadge = (status: "pending" | "accepted" | "rejected") => (
    <Badge
      variant="outline"
      className={cn(
        "shrink-0",
        status === "accepted" && "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        status === "rejected" && "border-destructive/40 bg-destructive/10 text-destructive",
      )}
    >
      {t(`knowledge.graphReviewStatuses.${status}`)}
    </Badge>
  );

  const reviewActions = (itemId: string, status: "pending" | "accepted" | "rejected", label: string) => {
    if (!canReview || status !== "pending") return null;
    const isPending = pendingItemId === itemId;
    return (
      <div className="mt-2 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={pendingItemId !== null}
          onClick={() => onReview(itemId, "accepted")}
          aria-label={t("knowledge.acceptGraphItem", { label })}
        >
          {isPending ? <LoaderCircleIcon data-icon="inline-start" className="animate-spin" /> : <CheckIcon data-icon="inline-start" />}
          {t("knowledge.acceptGraphItemShort")}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={pendingItemId !== null}
          onClick={() => onReview(itemId, "rejected")}
          aria-label={t("knowledge.rejectGraphItem", { label })}
        >
          <XIcon data-icon="inline-start" />
          {t("knowledge.rejectGraphItemShort")}
        </Button>
      </div>
    );
  };

  return (
    <section className="rounded-xl border bg-muted/15 p-3" data-testid="memory-graph-proposal-review">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <NetworkIcon className="size-4 shrink-0 text-primary" />
        <h3 className="mr-auto text-sm font-semibold">{t("knowledge.graphProposalTitle")}</h3>
        {acceptedCount > 0 && <Badge variant="secondary">{t("knowledge.graphReviewAcceptedCount", { count: acceptedCount })}</Badge>}
        {rejectedCount > 0 && <Badge variant="outline">{t("knowledge.graphReviewRejectedCount", { count: rejectedCount })}</Badge>}
        {pendingCount > 0 && <Badge variant="outline">{t("knowledge.graphReviewPendingCount", { count: pendingCount })}</Badge>}
      </div>
      {canReview && <p className="mt-2 text-xs leading-5 text-muted-foreground">{t("knowledge.graphReviewHint")}</p>}
      {canReview && pendingCount === 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 p-2.5">
          <p className="min-w-0 flex-1 text-xs leading-5 text-muted-foreground">{t("knowledge.graphReviewCompleteHint")}</p>
          <Button size="sm" disabled={isFinalizing || pendingItemId !== null} onClick={onFinalize}>
            {isFinalizing ? <LoaderCircleIcon data-icon="inline-start" className="animate-spin" /> : <ShieldCheckIcon data-icon="inline-start" />}
            {t("knowledge.completeGraphReview")}
          </Button>
        </div>
      )}
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div className="min-w-0 rounded-lg border bg-background/70 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("knowledge.graphProposalEntities")}
          </p>
          <div className="mt-2 flex flex-col gap-2">
            {proposal.entities.map((entity) => (
              <div key={entity.item_id} className="rounded-md border bg-muted/20 p-2">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="truncate text-sm font-medium">{entity.canonical_name}</span>
                  <Badge variant="outline">
                    {t(`knowledge.graphEntityTypes.${entity.entity_type}`, { defaultValue: entity.entity_type })}
                  </Badge>
                  {reviewBadge(entity.review_status)}
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {t("knowledge.graphProposalSources")}: {entity.evidence_labels.join(" · ")}
                </p>
                {entity.review_note && <p className="mt-1 text-xs leading-5 text-muted-foreground">{entity.review_note}</p>}
                {reviewActions(entity.item_id, entity.review_status, entity.canonical_name)}
              </div>
            ))}
          </div>
        </div>
        <div className="min-w-0 rounded-lg border bg-background/70 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("knowledge.graphProposalRelations")}
          </p>
          {proposal.relations.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">{t("knowledge.graphProposalNoRelations")}</p>
          ) : (
            <div className="mt-2 flex flex-col gap-2">
              {proposal.relations.map((relation) => {
                return (
                  <div
                    key={relation.item_id}
                    className="rounded-md border bg-muted/20 p-2"
                  >
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <p className="text-sm font-medium leading-5">
                        {relation.subject}
                        <span className="px-1.5 text-muted-foreground">{t(`knowledge.graphPredicates.${relation.predicate}`, { defaultValue: relation.predicate })}</span>
                        {relation.object}
                      </p>
                      {reviewBadge(relation.review_status)}
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {t("knowledge.graphProposalSources")}: {relation.evidence_labels.join(" · ")}
                    </p>
                    {relation.review_note && <p className="mt-1 text-xs leading-5 text-muted-foreground">{relation.review_note}</p>}
                    {reviewActions(
                      relation.item_id,
                      relation.review_status,
                      `${relation.subject} ${t(`knowledge.graphPredicates.${relation.predicate}`, { defaultValue: relation.predicate })} ${relation.object}`,
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
