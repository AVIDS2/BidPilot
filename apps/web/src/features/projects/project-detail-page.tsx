import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardAction, CardFooter } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import {
  getProject, listBundles, createDeliverable, reingestBundle, listDeliverables,
  listDeliverableSections, listExecutionRuns, retryExecutionRun, listEvidence,
  getRuntimeSummary, listSectionVersions, listRequirements, createRequirement,
  updateRequirement, listReviewThreads, listReviewComments, createReviewComment,
  submitReviewDecision, listAuditEvents, listKnowledgeChunks, draftSection, redraftSection,
  type BundleRead, type DeliverableRead, type DeliverableSectionRead,
  type ExecutionRunRead, type EvidenceRead, type RuntimeSummary,
  type SectionVersionRead, type RequirementItemRead, type ReviewThreadRead,
  type ReviewCommentRead, type AuditEventRead, type KnowledgeChunkRead,
} from "@/lib/api";
import { BotIcon, MoreHorizontalIcon, RefreshCwIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { canViewGovernance } from "@/lib/permissions";

// Tab components
import { BundlesTab } from "./tabs/bundles-tab";
import { DeliverablesTab } from "./tabs/deliverables-tab";
import { RequirementsTab } from "./tabs/requirements-tab";
import { DraftingTab } from "./tabs/drafting-tab";
import { AgentTab } from "./tabs/agent-tab";
import { EvidenceTab } from "./tabs/evidence-tab";
import { SearchTab } from "./tabs/search-tab";
import { RunsTab } from "./tabs/runs-tab";
import { ReviewTab } from "./tabs/review-tab";
import { AuditTab } from "./tabs/audit-tab";
import { ExportTab } from "./tabs/export-tab";
import { OpsTab } from "./tabs/ops-tab";

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const showGovernance = canViewGovernance(user);
  const { t } = useTranslation(["projects", "common"]);

  // Shared state
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [selectedDeliverableId, setSelectedDeliverableId] = useState<string | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{ title: string; description: string; onConfirm: () => void } | null>(null);

  const showConfirm = (action: { title: string; description: string; onConfirm: () => void }) => {
    setConfirmAction(action);
    setConfirmDialogOpen(true);
  };

  // Data queries
  const { data: project } = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id!), enabled: !!id, staleTime: 60_000 });
  const { data: bundles } = useQuery<BundleRead[]>({ queryKey: ["bundles", id], queryFn: () => listBundles(id!), enabled: !!id, staleTime: 30_000 });
  const { data: deliverables } = useQuery<DeliverableRead[]>({ queryKey: ["deliverables", id], queryFn: () => listDeliverables(id!), enabled: !!id, staleTime: 30_000 });
  const { data: runs } = useQuery<ExecutionRunRead[]>({ queryKey: ["runs", id], queryFn: () => listExecutionRuns(id!), enabled: !!id, staleTime: 15_000 });
  const { data: evidence } = useQuery<EvidenceRead[]>({ queryKey: ["evidence", id], queryFn: () => listEvidence(id!), enabled: !!id, staleTime: 30_000 });
  const { data: ops } = useQuery<RuntimeSummary>({ queryKey: ["ops"], queryFn: getRuntimeSummary, enabled: showGovernance, staleTime: 15_000 });
  const { data: reviewThreads } = useQuery<ReviewThreadRead[]>({ queryKey: ["review-threads", selectedSectionId], queryFn: () => listReviewThreads(selectedSectionId!), enabled: !!selectedSectionId, staleTime: 15_000 });
  const { data: reviewComments } = useQuery<ReviewCommentRead[]>({ queryKey: ["review-comments", selectedThreadId], queryFn: () => listReviewComments(selectedThreadId!), enabled: !!selectedThreadId, staleTime: 15_000 });
  const { data: auditEvents } = useQuery<AuditEventRead[]>({ queryKey: ["audit-events", id], queryFn: () => listAuditEvents(id!), enabled: !!id && showGovernance, staleTime: 30_000 });
  const { data: knowledgeChunks } = useQuery<KnowledgeChunkRead[]>({ queryKey: ["knowledge-chunks", id], queryFn: () => listKnowledgeChunks(id!), enabled: !!id, staleTime: 30_000 });
  const { data: sectionVersions } = useQuery<SectionVersionRead[]>({ queryKey: ["versions", selectedSectionId], queryFn: () => listSectionVersions(selectedSectionId!), enabled: !!selectedSectionId, staleTime: 15_000 });
  const { data: sections } = useQuery<DeliverableSectionRead[]>({ queryKey: ["sections", selectedDeliverableId], queryFn: () => listDeliverableSections(selectedDeliverableId!), enabled: !!selectedDeliverableId, staleTime: 30_000 });
  const { data: requirements } = useQuery<RequirementItemRead[]>({ queryKey: ["requirements", id], queryFn: () => listRequirements(id!), enabled: !!id, staleTime: 30_000 });

  // Mutations
  const reingestMut = useMutation({ mutationFn: reingestBundle, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["bundles", id] }); toast.success(t("bundles.reingestStarted")); }, onError: () => toast.error(t("bundles.reingestFailed")) });
  const createDeliverableMut = useMutation({ mutationFn: createDeliverable, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["deliverables", id] }); toast.success(t("deliverables.created")); }, onError: () => toast.error(t("deliverables.createFailed")) });
  const draftMut = useMutation({ mutationFn: draftSection, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["runs", id] }); toast.success(t("drafting.draftRequested")); }, onError: () => toast.error(t("drafting.draftFailed")) });
  const redraftMut = useMutation({ mutationFn: redraftSection, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["runs", id] }); queryClient.invalidateQueries({ queryKey: ["versions", selectedSectionId] }); toast.success(t("drafting.redraftRequested")); }, onError: () => toast.error(t("drafting.redraftFailed")) });
  const createReqMut = useMutation({ mutationFn: createRequirement, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["requirements", id] }); toast.success(t("requirements.added")); }, onError: () => toast.error(t("requirements.addFailed")) });
  const updateReqMut = useMutation({ mutationFn: ({ id: rid, data }: { id: string; data: Parameters<typeof updateRequirement>[1] }) => updateRequirement(rid, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["requirements", id] }); toast.success(t("requirements.updated")); }, onError: () => toast.error(t("requirements.updateFailed")) });
  const retryMut = useMutation({ mutationFn: retryExecutionRun, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["runs", id] }); toast.success(t("runs.retryStarted")); }, onError: () => toast.error(t("runs.retryFailed")) });
  const addCommentMut = useMutation({ mutationFn: createReviewComment, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["review-comments", selectedThreadId] }); toast.success(t("review.commentAdded")); }, onError: () => toast.error(t("review.commentFailed")) });
  const submitDecisionMut = useMutation({ mutationFn: submitReviewDecision, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["review-threads", selectedSectionId] }); toast.success(t("review.decisionSubmitted")); }, onError: () => toast.error(t("review.decisionFailed")) });

  if (!project) return <div className="flex flex-col gap-6"><Skeleton className="h-8 w-48" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem><BreadcrumbLink render={<Link to="/projects" />}>{t("detail.projects")}</BreadcrumbLink></BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem><BreadcrumbPage>{project.name}</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <p className="text-muted-foreground">
            {project.scenario_package} &middot; <Badge>{t(`statusValues.${project.status}`, { defaultValue: project.status })}</Badge>
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" size="icon" aria-label={t("detail.projectActions")} />}>
            <MoreHorizontalIcon />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{t("detail.projectActions")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => showConfirm({ title: t("detail.reingestAllTitle"), description: t("detail.reingestAllDesc"), onConfirm: () => bundles?.filter((b) => b.ingest_status !== "ingested").forEach((b) => reingestMut.mutate(b.id)) })}>
              <RefreshCwIcon className="mr-2 size-4" />{t("detail.reingestAll")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
        <Card className="@container/card"><CardHeader><CardDescription>{t("summary.bundles")}</CardDescription><CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">{bundles?.length ?? 0}</CardTitle><CardAction><Badge variant="outline">{t("summary.ingested", { count: bundles?.filter((b) => b.ingest_status === "ingested").length ?? 0 })}</Badge></CardAction></CardHeader><CardFooter className="text-sm text-muted-foreground">{t("summary.bundlesDesc")}</CardFooter></Card>
        <Card className="@container/card"><CardHeader><CardDescription>{t("summary.deliverables")}</CardDescription><CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">{deliverables?.length ?? 0}</CardTitle><CardAction><Badge variant="outline">{t("summary.sections", { count: sections?.length ?? 0 })}</Badge></CardAction></CardHeader><CardFooter className="text-sm text-muted-foreground">{t("summary.deliverablesDesc")}</CardFooter></Card>
        <Card className="@container/card"><CardHeader><CardDescription>{t("summary.evidence")}</CardDescription><CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">{evidence?.length ?? 0}</CardTitle><CardAction><Badge variant="outline">{t("summary.confirmed", { count: requirements?.filter((r) => r.status === "confirmed").length ?? 0 })}</Badge></CardAction></CardHeader><CardFooter className="text-sm text-muted-foreground">{t("summary.evidenceDesc")}</CardFooter></Card>
        <Card className="@container/card"><CardHeader><CardDescription>{t("summary.runs")}</CardDescription><CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">{runs?.length ?? 0}</CardTitle><CardAction><Badge variant={runs?.some((r) => r.status === "failed") ? "destructive" : "outline"}>{t("summary.succeeded", { count: runs?.filter((r) => r.status === "succeeded").length ?? 0 })}</Badge></CardAction></CardHeader><CardFooter className="text-sm text-muted-foreground">{t("summary.runsDesc")}</CardFooter></Card>
      </div>

      {/* Workflow Hint Banner */}
      <Card className="border-[rgba(132,204,22,0.2)] bg-gradient-to-r from-[rgba(132,204,22,0.04)] to-transparent">
        <CardContent className="flex flex-wrap items-center gap-2 py-3 text-xs">
          <span className="font-medium text-muted-foreground">{t("detail.workflow")}</span>
          <Badge variant={bundles?.length ? "default" : "outline"} className="font-normal">{t("detail.wfBundles", { count: bundles?.length ?? 0 })}</Badge>
          <span className="text-muted-foreground">&rarr;</span>
          <Badge variant={deliverables?.length ? "default" : "outline"} className="font-normal">{t("detail.wfDeliverables", { count: deliverables?.length ?? 0 })}</Badge>
          <span className="text-muted-foreground">&rarr;</span>
          <Badge variant={requirements?.length ? "default" : "outline"} className="font-normal">{t("detail.wfRequirements", { count: requirements?.length ?? 0 })}</Badge>
          <span className="text-muted-foreground">&rarr;</span>
          <Badge variant={runs?.length ? "default" : "outline"} className="font-normal">{t("detail.wfDrafting", { count: runs?.length ?? 0 })}</Badge>
          <span className="text-muted-foreground">&rarr;</span>
          <Badge variant={sections?.some((s) => s.status === "approved") ? "default" : "outline"} className="font-normal">{t("detail.wfReview", { count: sections?.filter((s) => s.status === "approved").length ?? 0 })}</Badge>
          <span className="text-muted-foreground">&rarr;</span>
          <Badge variant={deliverables?.some((d) => d.export_status === "exported") ? "default" : "outline"} className="font-normal">{t("detail.wfExport")}</Badge>
        </CardContent>
      </Card>

      <Tabs defaultValue="bundles">
        <ScrollArea className="w-full">
          <TabsList className="w-max min-w-full justify-start">
            <TabsTrigger value="bundles">{t("tabs.bundles")}</TabsTrigger>
            <TabsTrigger value="deliverables">{t("tabs.deliverables")}</TabsTrigger>
            <TabsTrigger value="requirements">{t("tabs.requirements")}</TabsTrigger>
            <TabsTrigger value="drafting">{t("tabs.drafting")}</TabsTrigger>
            <TabsTrigger value="agent"><span className="flex items-center gap-1.5"><BotIcon className="size-3.5" />{t("tabs.agent")}</span></TabsTrigger>
            <TabsTrigger value="evidence">{t("tabs.evidence")}</TabsTrigger>
            <TabsTrigger value="search">{t("tabs.search")}</TabsTrigger>
            <TabsTrigger value="runs">{t("tabs.runs")}</TabsTrigger>
            <TabsTrigger value="review">{t("tabs.review")}</TabsTrigger>
            {showGovernance && <TabsTrigger value="audit">{t("tabs.audit")}</TabsTrigger>}
            <TabsTrigger value="export">{t("tabs.export")}</TabsTrigger>
            {showGovernance && <TabsTrigger value="ops">{t("tabs.system")}</TabsTrigger>}
          </TabsList>
        </ScrollArea>

        <TabsContent value="bundles">
          <BundlesTab projectId={id!} bundles={bundles ?? []} onReingest={(bid) => reingestMut.mutate(bid)} onConfirm={showConfirm} />
        </TabsContent>
        <TabsContent value="deliverables">
          <DeliverablesTab projectId={id!} deliverables={deliverables ?? []} sections={sections} selectedSectionId={selectedSectionId} onSelectSection={setSelectedSectionId} onCreateDeliverable={(title) => createDeliverableMut.mutate({ project_id: id!, type: "proposal", title })} />
        </TabsContent>
        <TabsContent value="requirements">
          <RequirementsTab requirements={requirements ?? []} onCreateRequirement={(data) => createReqMut.mutate({ project_id: id!, ...data })} onUpdateRequirement={(rid, data) => updateReqMut.mutate({ id: rid, data })} />
        </TabsContent>
        <TabsContent value="drafting">
          <DraftingTab projectId={id!} sectionVersions={sectionVersions} sections={sections} selectedSectionId={selectedSectionId} evidence={evidence} onDraft={(sk) => draftMut.mutate({ project_id: id!, section_key: sk })} onRedraft={(sk) => redraftMut.mutate({ project_id: id!, section_key: sk, review_feedback: "Revise based on review" })} draftPending={draftMut.isPending} redraftPending={redraftMut.isPending} />
        </TabsContent>
        <TabsContent value="agent">
          <AgentTab runs={runs ?? []} />
        </TabsContent>
        <TabsContent value="evidence">
          <EvidenceTab evidence={evidence ?? []} knowledgeChunks={knowledgeChunks ?? []} />
        </TabsContent>
        <TabsContent value="search">
          <SearchTab projectId={id!} />
        </TabsContent>
        <TabsContent value="runs">
          <RunsTab runs={runs ?? []} onRetry={(rid) => retryMut.mutate(rid)} retrying={retryMut.isPending} onConfirm={showConfirm} t={(k, o) => t(k, o as Record<string, unknown>)} />
        </TabsContent>
        <TabsContent value="review">
          <ReviewTab sections={sections} reviewThreads={reviewThreads} reviewComments={reviewComments} selectedSectionId={selectedSectionId} selectedThreadId={selectedThreadId} onSelectSection={setSelectedSectionId} onSelectThread={setSelectedThreadId} onAddComment={(tid, body) => addCommentMut.mutate({ thread_id: tid, body })} onSubmitDecision={(sid, dec, cmt) => submitDecisionMut.mutate({ section_id: sid, decision: dec as "approved" | "rejected", comment: cmt })} addCommentPending={addCommentMut.isPending} submitDecisionPending={submitDecisionMut.isPending} />
        </TabsContent>
        {showGovernance && <TabsContent value="audit"><AuditTab auditEvents={auditEvents ?? []} /></TabsContent>}
        <TabsContent value="export"><ExportTab deliverables={deliverables ?? []} /></TabsContent>
        {showGovernance && <TabsContent value="ops"><OpsTab runs={runs ?? []} ops={ops} /></TabsContent>}
      </Tabs>

      <AlertDialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmAction?.title}</AlertDialogTitle>
            <AlertDialogDescription>{confirmAction?.description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("confirm.cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={() => { confirmAction?.onConfirm(); setConfirmDialogOpen(false); }}>
              {t("common:actions.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
