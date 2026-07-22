import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
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
import { motion, AnimatePresence } from "motion/react";
import CountUp from "@/components/CountUp";
import { ProductElectricFrame, ProductGlareCard, ProductShinyText } from "@/components/reactbits-product";
import {
  getProject, listBundles, createDeliverable, reingestBundle, listDeliverables,
  listDeliverableSections, listExecutionRuns, retryExecutionRun, listEvidence,
  getRuntimeSummary, listSectionVersions, listRequirements, createRequirement,
  updateRequirement, bulkAssignRequirements, getReadinessSummary, generateReadinessPack,
  downloadReadinessPack, verifyRequirementEvidenceLink, verifyRequirementClaim,
  listOrganizationMembers, listProjectMembers, addProjectMember, updateProjectMember, removeProjectMember, listReviewThreads, listReviewComments, createReviewComment,
  submitReviewDecision, listAuditEvents, listKnowledgeChunks, draftSection, redraftSection,
  getApiErrorDetail,
  type BundleRead, type DeliverableRead, type DeliverableSectionRead,
  type ExecutionRunRead, type EvidenceRead, type RuntimeSummary,
  type SectionVersionRead, type RequirementItemRead, type ReviewThreadRead,
  type ReviewCommentRead, type AuditEventRead, type KnowledgeChunkRead, type ProjectMemberRead,
} from "@/lib/api";
import { BotIcon, MoreHorizontalIcon, RefreshCwIcon, PackageIcon, PenToolIcon, SearchIcon, MessageSquareIcon, DownloadIcon, CheckCircle2Icon, ShieldCheckIcon } from "lucide-react";
import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { canViewGovernance } from "@/lib/permissions";

function getRequirementConflictIds(error: unknown): string[] {
  const detail = getApiErrorDetail(error);
  if (typeof detail !== "object" || detail === null) return [];
  if (!("code" in detail) || detail.code !== "requirements_changed") return [];
  if (!("requirement_ids" in detail) || !Array.isArray(detail.requirement_ids)) return [];
  return detail.requirement_ids.filter((value): value is string => typeof value === "string");
}

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
import { ProjectAccessTab } from "./tabs/project-access-tab";
import { KnowledgeTab } from "./tabs/knowledge-tab";

// Workflow step configuration
const WORKFLOW_STEPS = [
  { key: "prepare", labelKey: "steps.prepare", icon: PackageIcon },
  { key: "generate", labelKey: "steps.generate", icon: PenToolIcon },
  { key: "verify", labelKey: "steps.verify", icon: SearchIcon },
  { key: "review", labelKey: "steps.review", icon: MessageSquareIcon },
  { key: "export", labelKey: "steps.export", icon: DownloadIcon },
] as const;

type WorkflowStep = typeof WORKFLOW_STEPS[number]["key"];

// Tab group definitions
const TAB_GROUPS: Record<WorkflowStep, string[]> = {
  prepare: ["bundles", "deliverables", "requirements", "knowledge"],
  generate: ["drafting", "agent", "evidence", "search"],
  verify: ["runs"],
  review: ["review", "access"],
  export: ["export"],
};

const PROJECT_TABS = new Set([
  "bundles",
  "deliverables",
  "requirements",
  "knowledge",
  "drafting",
  "agent",
  "evidence",
  "search",
  "runs",
  "review",
  "export",
  "access",
  "audit",
  "ops",
]);

function resolveProjectTab(value: string | null) {
  return value && PROJECT_TABS.has(value) ? value : "bundles";
}

function WorkflowStepper({
  currentStep,
  onStepClick,
  progress,
  t,
}: {
  currentStep: WorkflowStep;
  onStepClick: (step: WorkflowStep) => void;
  progress: Record<string, boolean>;
  t: (key: string, opts?: Record<string, unknown>) => string;
}) {
  return (
    <div className="flex items-center gap-1 w-full">
      {WORKFLOW_STEPS.map((step, i) => {
        const isActive = step.key === currentStep;
        const isDone = progress[step.key];
        const Icon = step.icon;

        return (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            <ProductElectricFrame active={isActive} radius={12}>
              <button
                onClick={() => onStepClick(step.key)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200 cursor-pointer whitespace-nowrap ${
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/20"
                    : isDone
                    ? "text-emerald-600 dark:text-emerald-400 hover:bg-muted/50"
                    : "text-muted-foreground hover:bg-muted/50"
                }`}
              >
                <span className="relative flex size-5 items-center justify-center">
                  {isDone && !isActive ? (
                    <CheckCircle2Icon className="size-4" />
                  ) : (
                    <Icon className="size-4" />
                  )}
                </span>
                <span className="hidden sm:inline">{t(step.labelKey)}</span>
              </button>
            </ProductElectricFrame>
            {i < WORKFLOW_STEPS.length - 1 && (
              <div className="flex-1 mx-1">
                <div className={`h-px w-full ${isDone ? "bg-emerald-500/40" : "bg-border"}`} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Animated tab content wrapper
function AnimatedTabContent({ value, children, currentValue }: { value: string; children: React.ReactNode; currentValue: string }) {
  const isActive = value === currentValue;
  return (
    <TabsContent value={value} className="mt-0">
      <AnimatePresence mode="wait">
        {isActive && (
          <motion.div
            key={value}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </TabsContent>
  );
}

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const showGovernance = canViewGovernance(user);
  const { t } = useTranslation(["projects", "common"]);

  // Shared state
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{ title: string; description: string; onConfirm: () => void } | null>(null);
  const [activeTab, setActiveTab] = useState(() => resolveProjectTab(requestedTab));

  useEffect(() => {
    const nextTab = resolveProjectTab(requestedTab);
    setActiveTab((current) => (current === nextTab ? current : nextTab));
  }, [requestedTab]);

  const selectTab = (nextTab: string) => {
    const params = new URLSearchParams(searchParams);
    if (nextTab === "bundles") {
      params.delete("tab");
    } else {
      params.set("tab", nextTab);
    }
    setActiveTab(nextTab);
    setSearchParams(params, { replace: true });
  };

  const showConfirm = (action: { title: string; description: string; onConfirm: () => void }) => {
    setConfirmAction(action);
    setConfirmDialogOpen(true);
  };

  // Data queries
  const { data: project } = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id!), enabled: !!id, staleTime: 60_000 });
  const { data: bundles } = useQuery<BundleRead[]>({ queryKey: ["bundles", id], queryFn: () => listBundles(id!), enabled: !!id, staleTime: 30_000 });
  const { data: deliverables } = useQuery<DeliverableRead[]>({ queryKey: ["deliverables", id], queryFn: () => listDeliverables(id!), enabled: !!id, staleTime: 30_000 });
  const selectedDeliverableId = deliverables?.[0]?.id;
  const { data: runs } = useQuery<ExecutionRunRead[]>({ queryKey: ["runs", id], queryFn: () => listExecutionRuns(id!), enabled: !!id, staleTime: 15_000 });
  const { data: evidence } = useQuery<EvidenceRead[]>({ queryKey: ["evidence", id], queryFn: () => listEvidence(id!), enabled: !!id, staleTime: 30_000 });
  const { data: ops } = useQuery<RuntimeSummary>({ queryKey: ["ops"], queryFn: getRuntimeSummary, enabled: showGovernance, staleTime: 15_000 });
  const { data: reviewThreads } = useQuery<ReviewThreadRead[]>({ queryKey: ["review-threads", selectedSectionId], queryFn: () => listReviewThreads(selectedSectionId!), enabled: !!selectedSectionId, staleTime: 15_000 });
  const { data: reviewComments } = useQuery<ReviewCommentRead[]>({ queryKey: ["review-comments", selectedThreadId], queryFn: () => listReviewComments(selectedThreadId!), enabled: !!selectedThreadId, staleTime: 15_000 });
  const { data: auditEvents } = useQuery<AuditEventRead[]>({ queryKey: ["audit-events", id], queryFn: () => listAuditEvents(id!), enabled: !!id && showGovernance, staleTime: 30_000 });
  const { data: knowledgeChunks } = useQuery<KnowledgeChunkRead[]>({ queryKey: ["knowledge-chunks", id], queryFn: () => listKnowledgeChunks(id!), enabled: !!id, staleTime: 30_000 });
  const { data: sectionVersions } = useQuery<SectionVersionRead[]>({ queryKey: ["versions", selectedSectionId], queryFn: () => listSectionVersions(selectedSectionId!), enabled: !!selectedSectionId, staleTime: 15_000 });
  const { data: sections } = useQuery<DeliverableSectionRead[]>({ queryKey: ["sections", selectedDeliverableId], queryFn: () => listDeliverableSections(selectedDeliverableId!), enabled: !!selectedDeliverableId, staleTime: 30_000 });
  const { data: requirements, isLoading: requirementsLoading, isError: requirementsError } = useQuery<RequirementItemRead[]>({ queryKey: ["requirements", id], queryFn: () => listRequirements(id!), enabled: !!id, staleTime: 30_000 });
  const { data: readiness, isLoading: readinessLoading, isError: readinessError } = useQuery({ queryKey: ["readiness", id], queryFn: () => getReadinessSummary(id!), enabled: !!id, staleTime: 15_000 });
  const { data: organizationMembers } = useQuery({ queryKey: ["organization-members"], queryFn: listOrganizationMembers, enabled: !!id, staleTime: 60_000 });
  const { data: projectMembers } = useQuery<ProjectMemberRead[]>({ queryKey: ["project-members", id], queryFn: () => listProjectMembers(id!), enabled: !!id, staleTime: 30_000 });

  const requirementPeople = useMemo(() => {
    const people = new Map<string, {
      id: string;
      displayName: string;
      role?: "owner" | "manager" | "contributor" | "reviewer" | "viewer" | "admin";
    }>();
    projectMembers?.forEach((member) => {
      people.set(member.user_id, {
        id: member.user_id,
        displayName: member.display_name || member.user_id,
        role: member.role,
      });
    });
    if (user && !people.has(user.id)) {
      people.set(user.id, {
        id: user.id,
        displayName: user.display_name || user.email,
        role: user.role === "admin" ? "admin" : undefined,
      });
    }
    return Array.from(people.values()).sort((left, right) => left.displayName.localeCompare(right.displayName));
  }, [projectMembers, user]);

  const canManageProjectMembers = user?.role === "admin"
    || projectMembers?.some((member) => member.user_id === user?.id && member.role === "owner")
    || false;
  const canApproveProjectMemory = user?.role === "admin"
    || projectMembers?.some(
      (member) => member.user_id === user?.id && (member.role === "owner" || member.role === "manager"),
    )
    || false;

  // Mutations
  const reingestMut = useMutation({ mutationFn: reingestBundle, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["bundles", id] }); toast.success(t("bundles.reingestStarted")); }, onError: () => toast.error(t("bundles.reingestFailed")) });
  const createDeliverableMut = useMutation({ mutationFn: createDeliverable, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["deliverables", id] }); toast.success(t("deliverables.created")); }, onError: () => toast.error(t("deliverables.createFailed")) });
  const draftMut = useMutation({ mutationFn: draftSection, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["runs", id] }); toast.success(t("drafting.draftRequested")); }, onError: () => toast.error(t("drafting.draftFailed")) });
  const redraftMut = useMutation({ mutationFn: redraftSection, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["runs", id] }); queryClient.invalidateQueries({ queryKey: ["versions", selectedSectionId] }); toast.success(t("drafting.redraftRequested")); }, onError: () => toast.error(t("drafting.redraftFailed")) });
  const invalidateLedger = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["requirements", id] }),
      queryClient.invalidateQueries({ queryKey: ["readiness", id] }),
      queryClient.invalidateQueries({ queryKey: ["requirement-detail", id] }),
    ]);
  };
  const createReqMut = useMutation({ mutationFn: createRequirement, onSuccess: async () => { await invalidateLedger(); toast.success(t("requirements.added")); }, onError: () => toast.error(t("requirements.addFailed")) });
  const updateReqMut = useMutation({ mutationFn: ({ id: rid, data }: { id: string; data: Parameters<typeof updateRequirement>[1] }) => updateRequirement(rid, data), onSuccess: async () => { await invalidateLedger(); toast.success(t("requirements.updated")); }, onError: async () => { await invalidateLedger(); toast.error(t("requirements.updateFailed")); } });
  const bulkAssignReqMut = useMutation({
    mutationFn: bulkAssignRequirements,
    onSuccess: async () => {
      await invalidateLedger();
      toast.success(t("requirements.ledger.assignmentUpdated"));
    },
    onError: async (error) => {
      await invalidateLedger();
      const conflictIds = getRequirementConflictIds(error);
      if (conflictIds.length > 0) {
        const conflictNames = conflictIds
          .map((requirementId) => requirements?.find((item) => item.id === requirementId)?.requirement_text ?? requirementId)
          .slice(0, 3)
          .join(", ");
        toast.error(t("requirements.ledger.assignmentConflict", { items: conflictNames }));
        return;
      }
      toast.error(t("requirements.ledger.assignmentFailed"));
    },
  });
  const verifyEvidenceMut = useMutation({
    mutationFn: ({ requirementId, linkId }: { requirementId: string; linkId: string }) => (
      verifyRequirementEvidenceLink(requirementId, linkId)
    ),
    onSuccess: async () => {
      await invalidateLedger();
      toast.success(t("requirements.ledger.evidenceVerified"));
    },
    onError: async () => {
      await invalidateLedger();
      toast.error(t("requirements.ledger.evidenceVerifyFailed"));
    },
  });
  const verifyClaimMut = useMutation({
    mutationFn: ({ requirementId, claimId }: { requirementId: string; claimId: string }) => (
      verifyRequirementClaim(requirementId, claimId)
    ),
    onSuccess: async () => {
      await invalidateLedger();
      toast.success(t("requirements.ledger.claimVerified"));
    },
    onError: async () => {
      await invalidateLedger();
      toast.error(t("requirements.ledger.claimVerifyFailed"));
    },
  });
  const generateReadinessPackMut = useMutation({ mutationFn: () => generateReadinessPack(id!), onSuccess: () => toast.success(t("requirements.ledger.packGenerated")), onError: () => toast.error(t("requirements.ledger.packFailed")) });
  const retryMut = useMutation({ mutationFn: retryExecutionRun, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["runs", id] }); toast.success(t("runs.retryStarted")); }, onError: () => toast.error(t("runs.retryFailed")) });
  const addCommentMut = useMutation({ mutationFn: createReviewComment, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["review-comments", selectedThreadId] }); toast.success(t("review.commentAdded")); }, onError: () => toast.error(t("review.commentFailed")) });
  const submitDecisionMut = useMutation({ mutationFn: submitReviewDecision, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["review-threads", selectedSectionId] }); toast.success(t("review.decisionSubmitted")); }, onError: () => toast.error(t("review.decisionFailed")) });
  const invalidateProjectMembers = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["project-members", id] }),
      queryClient.invalidateQueries({ queryKey: ["requirements", id] }),
      queryClient.invalidateQueries({ queryKey: ["project", id] }),
    ]);
  };
  const addProjectMemberMut = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: ProjectMemberRead["role"] }) => addProjectMember(id!, { user_id: userId, role }),
    onSuccess: async () => { await invalidateProjectMembers(); toast.success(t("access.memberAdded")); },
    onError: () => toast.error(t("access.memberAddFailed")),
  });
  const updateProjectMemberMut = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: ProjectMemberRead["role"] }) => updateProjectMember(id!, userId, { role }),
    onSuccess: async () => { await invalidateProjectMembers(); toast.success(t("access.roleUpdated")); },
    onError: () => toast.error(t("access.roleUpdateFailed")),
  });
  const removeProjectMemberMut = useMutation({
    mutationFn: (userId: string) => removeProjectMember(id!, userId),
    onSuccess: async () => { await invalidateProjectMembers(); toast.success(t("access.memberRemoved")); },
    onError: () => toast.error(t("access.memberRemoveFailed")),
  });

  // Workflow progress calculation
  const workflowProgress = useMemo(() => ({
    prepare: !!(bundles?.length && deliverables?.length && requirements?.length),
    generate: !!(runs?.length || sections?.length),
    verify: !!(runs?.some((r) => r.status === "succeeded")),
    review: !!(sections?.some((s) => s.status === "approved")),
    export: !!(deliverables?.some((d) => d.export_status === "exported")),
  }), [bundles, deliverables, requirements, runs, sections]);

  // Current workflow step based on active tab
  const currentStep = useMemo(() => {
    for (const [step, tabs] of Object.entries(TAB_GROUPS)) {
      if (tabs.includes(activeTab)) return step as WorkflowStep;
    }
    return "prepare" as WorkflowStep;
  }, [activeTab]);

  if (!project) return <div className="flex flex-col gap-6"><Skeleton className="h-8 w-48" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;

  return (
    <div className="flex min-w-0 flex-col gap-6">
      <Breadcrumb className="min-w-0 overflow-hidden">
        <BreadcrumbList>
          <BreadcrumbItem><BreadcrumbLink render={<Link to="/projects" />}>{t("detail.projects")}</BreadcrumbLink></BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem><BreadcrumbPage>{project.name}</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* Header with animated entry */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}
        className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"
      >
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-bold sm:truncate">
            <ProductShinyText text={project.name} />
          </h1>
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
            <DropdownMenuItem onClick={() => showConfirm({ title: t("detail.reingestAllTitle"), description: t("detail.reingestAllDesc"), onConfirm: () => bundles?.filter((b) => ["ready_to_ingest", "failed"].includes(b.ingest_status)).forEach((b) => reingestMut.mutate(b.id)) })}>
              <RefreshCwIcon className="mr-2 size-4" />{t("detail.reingestAll")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </motion.div>

      {/* Summary Cards - staggered animation */}
      <div className="grid grid-cols-1 gap-4 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
        {[
          { label: t("summary.bundles"), value: bundles?.length ?? 0, badge: t("summary.ingested", { count: bundles?.filter((b) => b.ingest_status === "ingested").length ?? 0 }), desc: t("summary.bundlesDesc") },
          { label: t("summary.deliverables"), value: deliverables?.length ?? 0, badge: t("summary.sections", { count: sections?.length ?? 0 }), desc: t("summary.deliverablesDesc") },
          { label: t("summary.evidence"), value: evidence?.length ?? 0, badge: t("summary.confirmed", { count: requirements?.filter((r) => r.status === "confirmed").length ?? 0 }), desc: t("summary.evidenceDesc") },
          { label: t("summary.runs"), value: runs?.length ?? 0, badge: t("summary.succeeded", { count: runs?.filter((r) => r.status === "succeeded").length ?? 0 }), desc: t("summary.runsDesc"), warn: runs?.some((r) => r.status === "failed") },
        ].map((card, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.07, ease: [0.32, 0.72, 0, 1] }}
          >
            <ProductGlareCard>
              <Card className="@container/card h-full w-full">
                <CardHeader>
                  <CardDescription>{card.label}</CardDescription>
                  <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
                    <CountUp to={card.value} duration={1.2} delay={i * 0.08} />
                  </CardTitle>
                  <CardAction>
                    <Badge variant={card.warn ? "destructive" : "outline"}>{card.badge}</Badge>
                  </CardAction>
                </CardHeader>
                <CardFooter className="text-sm text-muted-foreground">{card.desc}</CardFooter>
              </Card>
            </ProductGlareCard>
          </motion.div>
        ))}
      </div>

      {/* Workflow Stepper */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3, ease: [0.32, 0.72, 0, 1] }}
      >
        <Card className="border-primary/10 bg-gradient-to-r from-primary/[0.03] to-transparent">
          <CardContent className="py-4">
            <WorkflowStepper
              currentStep={currentStep}
              onStepClick={(step) => {
                const firstTab = TAB_GROUPS[step][0];
                if (firstTab) selectTab(firstTab);
              }}
              progress={workflowProgress}
              t={t}
            />
          </CardContent>
        </Card>
      </motion.div>

      {/* Tabs - grouped with separators */}
      <Tabs value={activeTab} onValueChange={selectTab} className="min-w-0">
        <ScrollArea className="w-full">
          <TabsList className="w-max min-w-full justify-start">
            {/* Prepare group */}
            <TabsTrigger value="bundles">{t("tabs.bundles")}</TabsTrigger>
            <TabsTrigger value="deliverables">{t("tabs.deliverables")}</TabsTrigger>
            <TabsTrigger value="requirements">{t("tabs.requirements")}</TabsTrigger>
            <TabsTrigger value="knowledge">{t("tabs.knowledge")}</TabsTrigger>
            {/* Separator */}
            <div className="mx-1 self-stretch w-px bg-border" aria-hidden />
            {/* Generate group */}
            <TabsTrigger value="drafting">{t("tabs.drafting")}</TabsTrigger>
            <TabsTrigger value="agent"><span className="flex items-center gap-1.5"><BotIcon className="size-3.5" />{t("tabs.agent")}</span></TabsTrigger>
            <TabsTrigger value="evidence">{t("tabs.evidence")}</TabsTrigger>
            <TabsTrigger value="search">{t("tabs.search")}</TabsTrigger>
            {/* Separator */}
            <div className="mx-1 self-stretch w-px bg-border" aria-hidden />
            {/* Verify group */}
            <TabsTrigger value="runs">{t("tabs.runs")}</TabsTrigger>
            <TabsTrigger value="review">{t("tabs.review")}</TabsTrigger>
            {/* Separator */}
            <div className="mx-1 self-stretch w-px bg-border" aria-hidden />
            {/* Output */}
            <TabsTrigger value="export">{t("tabs.export")}</TabsTrigger>
            {/* Governance */}
            <div className="mx-1 self-stretch w-px bg-border" aria-hidden />
            <TabsTrigger value="access"><span className="flex items-center gap-1.5"><ShieldCheckIcon className="size-3.5" />{t("tabs.access")}</span></TabsTrigger>
            {showGovernance && <TabsTrigger value="audit">{t("tabs.audit")}</TabsTrigger>}
            {showGovernance && <TabsTrigger value="ops">{t("tabs.system")}</TabsTrigger>}
          </TabsList>
        </ScrollArea>

        <AnimatedTabContent value="bundles" currentValue={activeTab}>
          <BundlesTab projectId={id!} bundles={bundles ?? []} onReingest={(bid) => reingestMut.mutate(bid)} onConfirm={showConfirm} />
        </AnimatedTabContent>
        <AnimatedTabContent value="deliverables" currentValue={activeTab}>
          <DeliverablesTab projectId={id!} deliverables={deliverables ?? []} sections={sections} selectedSectionId={selectedSectionId} onSelectSection={setSelectedSectionId} onCreateDeliverable={(title) => createDeliverableMut.mutate({ project_id: id!, type: "proposal", title })} />
        </AnimatedTabContent>
        <AnimatedTabContent value="requirements" currentValue={activeTab}>
          <RequirementsTab
            projectId={id!}
            requirements={requirements ?? []}
            readiness={readiness}
            loading={requirementsLoading}
            loadError={requirementsError}
            readinessLoading={readinessLoading}
            readinessError={readinessError}
            people={requirementPeople}
            currentUserId={user?.id}
            onCreateRequirement={(data) => createReqMut.mutateAsync({ project_id: id!, ...data })}
            onUpdateRequirement={(rid, data) => updateReqMut.mutateAsync({ id: rid, data }).then(() => undefined)}
            onBulkAssign={(data) => {
              const payload: Parameters<typeof bulkAssignRequirements>[0] = {
                requirement_ids: data.requirementIds,
                lock_versions: data.lockVersions,
              };
              if (data.ownerUserId !== undefined) payload.owner_user_id = data.ownerUserId;
              if (data.reviewerUserId !== undefined) payload.reviewer_user_id = data.reviewerUserId;
              return bulkAssignReqMut.mutateAsync(payload).then(() => undefined);
            }}
            onVerifyEvidence={(requirementId, linkId) => (
              verifyEvidenceMut.mutateAsync({ requirementId, linkId }).then(() => undefined)
            )}
            onVerifyClaim={(requirementId, claimId) => (
              verifyClaimMut.mutateAsync({ requirementId, claimId }).then(() => undefined)
            )}
            onGeneratePack={() => generateReadinessPackMut.mutateAsync()}
            onDownloadPack={downloadReadinessPack}
            creating={createReqMut.isPending}
            updating={updateReqMut.isPending}
            bulkAssigning={bulkAssignReqMut.isPending}
            reviewing={verifyEvidenceMut.isPending || verifyClaimMut.isPending}
          />
        </AnimatedTabContent>
        <AnimatedTabContent value="knowledge" currentValue={activeTab}>
          <KnowledgeTab projectId={id!} canApprove={canApproveProjectMemory} />
        </AnimatedTabContent>
        <AnimatedTabContent value="drafting" currentValue={activeTab}>
          <DraftingTab projectId={id!} sectionVersions={sectionVersions} sections={sections} selectedSectionId={selectedSectionId} evidence={evidence} onDraft={(sk) => draftMut.mutate({ project_id: id!, section_key: sk })} onRedraft={(sk) => redraftMut.mutate({ project_id: id!, section_key: sk, review_feedback: "Revise based on review" })} draftPending={draftMut.isPending} redraftPending={redraftMut.isPending} />
        </AnimatedTabContent>
        <AnimatedTabContent value="agent" currentValue={activeTab}>
          <AgentTab runs={runs ?? []} />
        </AnimatedTabContent>
        <AnimatedTabContent value="evidence" currentValue={activeTab}>
          <EvidenceTab evidence={evidence ?? []} knowledgeChunks={knowledgeChunks ?? []} />
        </AnimatedTabContent>
        <AnimatedTabContent value="search" currentValue={activeTab}>
          <SearchTab projectId={id!} />
        </AnimatedTabContent>
        <AnimatedTabContent value="runs" currentValue={activeTab}>
          <RunsTab runs={runs ?? []} onRetry={(rid) => retryMut.mutate(rid)} retrying={retryMut.isPending} onConfirm={showConfirm} t={(k, o) => t(k, o as Record<string, unknown>)} />
        </AnimatedTabContent>
        <AnimatedTabContent value="review" currentValue={activeTab}>
          <ReviewTab sections={sections} sectionVersions={sectionVersions} reviewThreads={reviewThreads} reviewComments={reviewComments} selectedSectionId={selectedSectionId} selectedThreadId={selectedThreadId} onSelectSection={setSelectedSectionId} onSelectThread={setSelectedThreadId} onAddComment={(tid, body) => addCommentMut.mutate({ thread_id: tid, body })} onSubmitDecision={(sid, dec, cmt) => submitDecisionMut.mutate({ section_id: sid, decision: dec as "approved" | "rejected", comment: cmt })} addCommentPending={addCommentMut.isPending} submitDecisionPending={submitDecisionMut.isPending} />
        </AnimatedTabContent>
        <AnimatedTabContent value="export" currentValue={activeTab}>
          <ExportTab deliverables={deliverables ?? []} />
        </AnimatedTabContent>
        <AnimatedTabContent value="access" currentValue={activeTab}>
          <ProjectAccessTab
            projectId={id!}
            members={projectMembers ?? []}
            organizationMembers={organizationMembers ?? []}
            canManageMembers={canManageProjectMembers}
            onAddMember={({ user_id, role }) => addProjectMemberMut.mutateAsync({ userId: user_id, role })}
            onUpdateMember={(userId, role) => updateProjectMemberMut.mutateAsync({ userId, role })}
            onRemoveMember={(userId) => removeProjectMemberMut.mutateAsync(userId)}
            adding={addProjectMemberMut.isPending}
            updating={updateProjectMemberMut.isPending}
            removing={removeProjectMemberMut.isPending}
          />
        </AnimatedTabContent>
        {showGovernance && (
          <AnimatedTabContent value="audit" currentValue={activeTab}>
            <AuditTab auditEvents={auditEvents ?? []} />
          </AnimatedTabContent>
        )}
        {showGovernance && (
          <AnimatedTabContent value="ops" currentValue={activeTab}>
            <OpsTab runs={runs ?? []} ops={ops} />
          </AnimatedTabContent>
        )}
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
