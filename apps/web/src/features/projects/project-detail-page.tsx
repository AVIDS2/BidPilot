import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardAction, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { FieldGroup, Field, FieldLabel } from "@/components/ui/field";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { canViewGovernance } from "@/lib/permissions";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { PromptInput, PromptInputTextarea, PromptInputActions, PromptInputAction } from "@/components/ui/prompt-input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Source } from "@/components/ui/source";
import { Message, MessageAvatar, MessageContent, MessageActions, MessageAction } from "@/components/ui/message";
import { RuntimeSummaryCards } from "@/features/ops/runtime-summary";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getProject,
  listBundles,
  createBundle,
  reingestBundle,
  listDeliverables,
  createDeliverable,
  listDeliverableSections,
  listDocuments,
  uploadDocument,
  getDocumentDownloadUrl,
  draftSection,
  redraftSection,
  listExecutionRuns,
  retryExecutionRun,
  listEvidence,
  getRuntimeSummary,
  listSectionVersions,
  listRequirements,
  createRequirement,
  updateRequirement,
  listReviewThreads,
  listReviewComments,
  createReviewComment,
  submitReviewDecision,
  listAuditEvents,
  exportDeliverableDocx,
  exportDeliverablePdf,
  searchKnowledge,
  listKnowledgeChunks,
  type BundleRead,
  type DeliverableRead,
  type DeliverableSectionRead,
  type DocumentsPaginatedResponse,
  type ExecutionRunRead,
  type EvidenceRead,
  type RuntimeSummary,
  type SectionVersionRead,
  type RequirementItemRead,
  type ReviewThreadRead,
  type ReviewCommentRead,
  type AuditEventRead,
  type SearchResult,
  type KnowledgeChunkRead,
} from "@/lib/api";
import { ActivityIcon, AlertTriangleIcon, ClipboardCheckIcon, DownloadIcon, FileIcon, LayersIcon, MessageCircleIcon, MoreHorizontalIcon, PackageIcon, RefreshCwIcon, SearchIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const showGovernance = canViewGovernance(user);
  const { t } = useTranslation(["projects", "common"]);
  const [bundleLabel, setBundleLabel] = useState("");
  const [deliverableTitle, setDeliverableTitle] = useState("");
  const [sectionKey, setSectionKey] = useState("");
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [selectedDeliverableId, setSelectedDeliverableId] = useState<string | null>(null);
  const [selectedBundleId, setSelectedBundleId] = useState<string | null>(null);
  const [reqSectionKey, setReqSectionKey] = useState("");
  const [reqText, setReqText] = useState("");
  const [editingReqId, setEditingReqId] = useState<string | null>(null);
  const [editingReqText, setEditingReqText] = useState("");
  const [diffVersionA, setDiffVersionA] = useState<number | null>(null);
  const [diffVersionB, setDiffVersionB] = useState<number | null>(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{ title: string; description: string; onConfirm: () => void } | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [reviewCommentBody, setReviewCommentBody] = useState("");
  const [reviewDecisionComment, setReviewDecisionComment] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const { data: project } = useQuery({
    queryKey: ["project", id],
    queryFn: () => getProject(id!),
    enabled: !!id,
    staleTime: 60 * 1000,
  });

  const { data: bundles } = useQuery<BundleRead[]>({
    queryKey: ["bundles", id],
    queryFn: () => listBundles(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });

  const { data: deliverables } = useQuery<DeliverableRead[]>({
    queryKey: ["deliverables", id],
    queryFn: () => listDeliverables(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });

  const { data: runs } = useQuery<ExecutionRunRead[]>({
    queryKey: ["runs", id],
    queryFn: () => listExecutionRuns(id!),
    enabled: !!id,
    staleTime: 15 * 1000,
  });

  const { data: evidence } = useQuery<EvidenceRead[]>({
    queryKey: ["evidence", id],
    queryFn: () => listEvidence(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });

  const { data: ops } = useQuery<RuntimeSummary>({
    queryKey: ["ops"],
    queryFn: getRuntimeSummary,
    enabled: showGovernance,
    staleTime: 15 * 1000,
  });

  // Review queries - fetch threads for all sections
  const { data: reviewThreads } = useQuery<ReviewThreadRead[]>({
    queryKey: ["review-threads", selectedSectionId],
    queryFn: () => listReviewThreads(selectedSectionId!),
    enabled: !!selectedSectionId,
    staleTime: 15 * 1000,
  });

  const { data: reviewComments } = useQuery<ReviewCommentRead[]>({
    queryKey: ["review-comments", selectedThreadId],
    queryFn: () => listReviewComments(selectedThreadId!),
    enabled: !!selectedThreadId,
    staleTime: 15 * 1000,
  });

  const { data: auditEvents } = useQuery<AuditEventRead[]>({
    queryKey: ["audit-events", id],
    queryFn: () => listAuditEvents(id!),
    enabled: !!id && showGovernance,
    staleTime: 30 * 1000,
  });

  const { data: knowledgeChunks } = useQuery<KnowledgeChunkRead[]>({
    queryKey: ["knowledge-chunks", id],
    queryFn: () => listKnowledgeChunks(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });

  const handleSearch = async () => {
    if (!searchQuery.trim() || !id) return;
    setIsSearching(true);
    try {
      const results = await searchKnowledge({ project_id: id, query: searchQuery.trim() });
      setSearchResults(results);
    } catch {
      toast.error(t("search.failed"));
    } finally {
      setIsSearching(false);
    }
  };

  const addCommentMut = useMutation({
    mutationFn: createReviewComment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-comments", selectedThreadId] });
      setReviewCommentBody("");
      toast.success(t("review.commentAdded"));
    },
    onError: () => {
      toast.error(t("review.commentFailed"));
    },
  });

  const submitDecisionMut = useMutation({
    mutationFn: submitReviewDecision,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-threads", selectedSectionId] });
      setReviewDecisionComment("");
      toast.success(t("review.decisionSubmitted"));
    },
    onError: () => {
      toast.error(t("review.decisionFailed"));
    },
  });

  const { data: sectionVersions } = useQuery<SectionVersionRead[]>({
    queryKey: ["versions", selectedSectionId],
    queryFn: () => listSectionVersions(selectedSectionId!),
    enabled: !!selectedSectionId,
    staleTime: 15 * 1000,
  });

  const { data: sections } = useQuery<DeliverableSectionRead[]>({
    queryKey: ["sections", selectedDeliverableId],
    queryFn: () => listDeliverableSections(selectedDeliverableId!),
    enabled: !!selectedDeliverableId,
    staleTime: 30 * 1000,
  });

  const { data: documents } = useQuery<DocumentsPaginatedResponse>({
    queryKey: ["documents", selectedBundleId],
    queryFn: () => listDocuments(selectedBundleId!),
    enabled: !!selectedBundleId,
    staleTime: 30 * 1000,
  });

  const createBundleMut = useMutation({
    mutationFn: createBundle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bundles", id] });
      toast.success(t("bundles.registered"));
    },
    onError: () => {
      toast.error(t("bundles.registerFailed"));
    },
  });

  const createDeliverableMut = useMutation({
    mutationFn: createDeliverable,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deliverables", id] });
      toast.success(t("deliverables.created"));
    },
    onError: () => {
      toast.error(t("deliverables.createFailed"));
    },
  });

  const draftMut = useMutation({
    mutationFn: draftSection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs", id] });
      toast.success(t("drafting.draftRequested"));
    },
    onError: () => {
      toast.error(t("drafting.draftFailed"));
    },
  });

  const redraftMut = useMutation({
    mutationFn: redraftSection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs", id] });
      queryClient.invalidateQueries({ queryKey: ["versions", selectedSectionId] });
      toast.success(t("drafting.redraftRequested"));
    },
    onError: () => {
      toast.error(t("drafting.redraftFailed"));
    },
  });

  const { data: requirements } = useQuery<RequirementItemRead[]>({
    queryKey: ["requirements", id],
    queryFn: () => listRequirements(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });

  const createReqMut = useMutation({
    mutationFn: createRequirement,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["requirements", id] });
      toast.success(t("requirements.added"));
    },
    onError: () => {
      toast.error(t("requirements.addFailed"));
    },
  });

  const updateReqMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateRequirement>[1] }) => updateRequirement(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["requirements", id] });
      setEditingReqId(null);
      toast.success(t("requirements.updated"));
    },
    onError: () => {
      toast.error(t("requirements.updateFailed"));
    },
  });

  const reingestMut = useMutation({
    mutationFn: reingestBundle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bundles", id] });
      toast.success(t("bundles.reingestStarted"));
    },
    onError: () => {
      toast.error(t("bundles.reingestFailed"));
    },
  });

  const retryMut = useMutation({
    mutationFn: retryExecutionRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs", id] });
      toast.success(t("runs.retryStarted"));
    },
    onError: () => {
      toast.error(t("runs.retryFailed"));
    },
  });

  if (!project) return <div className="flex flex-col gap-6"><Skeleton className="h-8 w-48" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link to="/projects" />}>{t("detail.projects")}</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{project.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <p className="text-muted-foreground">
            {project.scenario_package} &middot; <Badge>{project.status}</Badge>
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" size="icon" aria-label={t("detail.projectActions")} />}>
            <MoreHorizontalIcon />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{t("detail.projectActions")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                setConfirmAction({
                  title: t("detail.reingestAllTitle"),
                  description: t("detail.reingestAllDesc"),
                  onConfirm: () => {
                    bundles?.filter((b) => b.ingest_status !== "ingested").forEach((b) => reingestMut.mutate(b.id));
                  },
                });
                setConfirmDialogOpen(true);
              }}
            >
              <RefreshCwIcon className="mr-2 size-4" />
              {t("detail.reingestAll")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 *:data-[slot=card]:bg-linear-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card *:data-[slot=card]:shadow-xs @xl/main:grid-cols-2 @5xl/main:grid-cols-4 dark:*:data-[slot=card]:bg-card">
        <Card className="@container/card">
          <CardHeader>
            <CardDescription>{t("summary.bundles")}</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {bundles?.length ?? 0}
            </CardTitle>
            <CardAction>
              <Badge variant="outline">
                {t("summary.ingested", { count: bundles?.filter((b) => b.ingest_status === "ingested").length ?? 0 })}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className="text-sm text-muted-foreground">
            {t("summary.bundlesDesc")}
          </CardFooter>
        </Card>
        <Card className="@container/card">
          <CardHeader>
            <CardDescription>{t("summary.deliverables")}</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {deliverables?.length ?? 0}
            </CardTitle>
            <CardAction>
              <Badge variant="outline">
                {t("summary.sections", { count: sections?.length ?? 0 })}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className="text-sm text-muted-foreground">
            {t("summary.deliverablesDesc")}
          </CardFooter>
        </Card>
        <Card className="@container/card">
          <CardHeader>
            <CardDescription>{t("summary.evidence")}</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {evidence?.length ?? 0}
            </CardTitle>
            <CardAction>
              <Badge variant="outline">
                {t("summary.confirmed", { count: requirements?.filter((r) => r.status === "confirmed").length ?? 0 })}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className="text-sm text-muted-foreground">
            {t("summary.evidenceDesc")}
          </CardFooter>
        </Card>
        <Card className="@container/card">
          <CardHeader>
            <CardDescription>{t("summary.runs")}</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {runs?.length ?? 0}
            </CardTitle>
            <CardAction>
              <Badge variant={runs?.some((r) => r.status === "failed") ? "destructive" : "outline"}>
                {t("summary.succeeded", { count: runs?.filter((r) => r.status === "succeeded").length ?? 0 })}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className="text-sm text-muted-foreground">
            {t("summary.runsDesc")}
          </CardFooter>
        </Card>
      </div>

      {/* Workflow Hint Banner */}
      <Card className="border-primary/30 bg-gradient-to-r from-primary/5 to-transparent">
        <CardContent className="flex flex-wrap items-center gap-2 py-3 text-xs">
          <span className="font-medium text-muted-foreground">{t("detail.workflow")}</span>
          <Badge variant={bundles?.length ? "default" : "outline"} className="font-normal">{t("detail.wfBundles", { count: bundles?.length ?? 0 })}</Badge>
          <span className="text-muted-foreground">→</span>
          <Badge variant={deliverables?.length ? "default" : "outline"} className="font-normal">{t("detail.wfDeliverables", { count: deliverables?.length ?? 0 })}</Badge>
          <span className="text-muted-foreground">→</span>
          <Badge variant={requirements?.length ? "default" : "outline"} className="font-normal">{t("detail.wfRequirements", { count: requirements?.length ?? 0 })}</Badge>
          <span className="text-muted-foreground">→</span>
          <Badge variant={runs?.length ? "default" : "outline"} className="font-normal">{t("detail.wfDrafting", { count: runs?.length ?? 0 })}</Badge>
          <span className="text-muted-foreground">→</span>
          <Badge variant={sections?.some((s) => s.status === "approved") ? "default" : "outline"} className="font-normal">{t("detail.wfReview", { count: sections?.filter((s) => s.status === "approved").length ?? 0 })}</Badge>
          <span className="text-muted-foreground">→</span>
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
            <TabsTrigger value="evidence">{t("tabs.evidence")}</TabsTrigger>
            <TabsTrigger value="search">{t("tabs.search")}</TabsTrigger>
            <TabsTrigger value="runs">{t("tabs.runs")}</TabsTrigger>
            <TabsTrigger value="review">{t("tabs.review")}</TabsTrigger>
            {showGovernance && <TabsTrigger value="audit">{t("tabs.audit")}</TabsTrigger>}
            <TabsTrigger value="export">{t("tabs.export")}</TabsTrigger>
            {showGovernance && <TabsTrigger value="ops">{t("tabs.system")}</TabsTrigger>}
          </TabsList>
        </ScrollArea>

        {/* Bundles */}
        <TabsContent value="bundles">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t("bundles.title")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="bundle-label">{t("bundles.label")}</FieldLabel>
                  <Input
                    id="bundle-label"
                    value={bundleLabel}
                    onChange={(e) => setBundleLabel(e.target.value)}
                    placeholder={t("bundles.labelPlaceholder")}
                    className="max-w-xs"
                  />
                </Field>
                <Button
                  size="sm"
                  disabled={!bundleLabel}
                  onClick={() => {
                    createBundleMut.mutate({ project_id: id!, label: bundleLabel, source_type: "upload" });
                    setBundleLabel("");
                  }}
                >
                  {t("bundles.register")}
                </Button>
              </FieldGroup>
              {bundles?.length === 0 && <Empty><EmptyHeader><EmptyMedia variant="icon"><PackageIcon /></EmptyMedia><EmptyTitle>{t("bundles.emptyTitle")}</EmptyTitle><EmptyDescription>{t("bundles.emptyDesc")}</EmptyDescription></EmptyHeader></Empty>}
              <Accordion multiple onValueChange={(v) => setSelectedBundleId(v[v.length - 1] ?? null)}>
                {bundles?.map((b) => (
                  <AccordionItem key={b.id} value={b.id}>
                    <AccordionTrigger className="hover:no-underline">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-medium">{b.label}</span>
                        <Badge variant={b.ingest_status === "ingested" ? "default" : "secondary"}>
                          {b.ingest_status}
                        </Badge>
                        {b.ingest_status !== "ingested" && (
                          <Button size="sm" variant="outline" onClick={(e) => {
                            e.stopPropagation();
                            setConfirmAction({
                              title: t("bundles.reingestTitle"),
                              description: t("bundles.reingestDesc", { label: b.label }),
                              onConfirm: () => {
                                reingestMut.mutate(b.id);
                              },
                            });
                            setConfirmDialogOpen(true);
                          }}>
                            {t("bundles.reingest")}
                          </Button>
                        )}
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="flex flex-col gap-2">
                        <Field>
                          <FieldLabel htmlFor={`file-upload-${b.id}`} className="text-xs">{t("bundles.uploadDocument")}</FieldLabel>
                          <Input
                            id={`file-upload-${b.id}`}
                            type="file"
                            className="cursor-pointer file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1 file:text-xs file:font-medium file:text-primary-foreground hover:file:bg-primary/90"
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) {
                                uploadDocument(b.id, file).then(() => {
                                  toast.success(t("bundles.uploaded", { filename: file.name }));
                                  queryClient.invalidateQueries({ queryKey: ["documents", b.id] });
                                }).catch((err) => {
                                  const msg = err instanceof Error ? err.message : "Upload failed";
                                  toast.error(t("bundles.uploadFailed", { message: msg }));
                                });
                              }
                            }}
                          />
                        </Field>
                        {documents?.items.map((d) => (
                          <div key={d.id} className="flex items-center gap-2 text-xs ml-2">
                            <a
                              href={getDocumentDownloadUrl(d.id)}
                              className="text-primary hover:underline"
                            >
                              {d.original_filename}
                            </a>
                            <Badge variant="outline">{d.parse_status}</Badge>
                          </div>
                        ))}
                        {documents?.items.length === 0 && (
                          <p className="text-xs text-muted-foreground ml-2">{t("bundles.noDocuments")}</p>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Deliverables */}
        <TabsContent value="deliverables">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t("deliverables.title")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="deliverable-title">{t("deliverables.label")}</FieldLabel>
                  <Input
                    id="deliverable-title"
                    value={deliverableTitle}
                    onChange={(e) => setDeliverableTitle(e.target.value)}
                    placeholder={t("deliverables.labelPlaceholder")}
                    className="max-w-xs"
                  />
                </Field>
                <Button
                  size="sm"
                  disabled={!deliverableTitle}
                  onClick={() => {
                    createDeliverableMut.mutate({ project_id: id!, type: "proposal", title: deliverableTitle });
                    setDeliverableTitle("");
                  }}
                >
                  {t("deliverables.add")}
                </Button>
              </FieldGroup>
              {deliverables?.length === 0 && <Empty><EmptyHeader><EmptyMedia variant="icon"><LayersIcon /></EmptyMedia><EmptyTitle>{t("deliverables.emptyTitle")}</EmptyTitle><EmptyDescription>{t("deliverables.emptyDesc")}</EmptyDescription></EmptyHeader></Empty>}
              <Accordion multiple onValueChange={(v) => setSelectedDeliverableId(v[v.length - 1] ?? null)}>
                {deliverables?.map((d) => (
                  <AccordionItem key={d.id} value={d.id}>
                    <AccordionTrigger className="hover:no-underline">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-medium">{d.title}</span>
                        <Badge variant="outline">{d.type}</Badge>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      {sections?.map((s) => (
                        <div
                          role="button"
                          tabIndex={0}
                          aria-pressed={selectedSectionId === s.id}
                          className={cn(
                            "flex items-center gap-2 text-sm cursor-pointer rounded p-1",
                            selectedSectionId === s.id ? "bg-accent" : "hover:bg-accent",
                          )}
                          onClick={() => setSelectedSectionId(s.id === selectedSectionId ? null : s.id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedSectionId(s.id === selectedSectionId ? null : s.id);
                            }
                          }}
                        >
                          <span>{s.title}</span>
                          <Badge variant={s.status === "draft" ? "secondary" : "default"}>{s.status}</Badge>
                        </div>
                      ))}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Requirements */}
        <TabsContent value="requirements">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t("requirements.title")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="req-section-key">{t("requirements.sectionKey")}</FieldLabel>
                  <Input
                    id="req-section-key"
                    value={reqSectionKey}
                    onChange={(e) => setReqSectionKey(e.target.value)}
                    placeholder={t("requirements.sectionKeyPlaceholder")}
                    className="max-w-[140px]"
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="req-text">{t("requirements.requirementText")}</FieldLabel>
                  <Input
                    id="req-text"
                    value={reqText}
                    onChange={(e) => setReqText(e.target.value)}
                    placeholder={t("requirements.requirementTextPlaceholder")}
                    className="flex-1 min-w-[200px]"
                  />
                </Field>
                <Button
                  size="sm"
                  disabled={!reqText || !reqSectionKey}
                  onClick={() => {
                    createReqMut.mutate({ project_id: id!, section_key: reqSectionKey, requirement_text: reqText });
                    setReqText("");
                  }}
                >
                  {t("requirements.add")}
                </Button>
              </FieldGroup>
              {requirements?.length === 0 && <Empty><EmptyHeader><EmptyMedia variant="icon"><ClipboardCheckIcon /></EmptyMedia><EmptyTitle>{t("requirements.emptyTitle")}</EmptyTitle><EmptyDescription>{t("requirements.emptyDesc")}</EmptyDescription></EmptyHeader></Empty>}
              <div className="flex flex-col gap-2">
                {requirements?.map((r) => (
                  <div key={r.id} className="border rounded-md p-3 flex flex-col gap-1">
                    {editingReqId === r.id ? (
                      <div className="flex gap-2">
                        <Input
                          value={editingReqText}
                          onChange={(e) => setEditingReqText(e.target.value)}
                          className="flex-1"
                        />
                        <Button
                          size="sm"
                          onClick={() => updateReqMut.mutate({ id: r.id, data: { requirement_text: editingReqText } })}
                        >
                          {t("requirements.save")}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setEditingReqId(null)}>{t("requirements.cancel")}</Button>
                      </div>
                    ) : (
                      <>
                        <p className="text-sm">{r.requirement_text}</p>
                        <div className="flex gap-2 text-xs text-muted-foreground">
                          <Badge variant="outline">{r.section_key}</Badge>
                          <Badge variant={r.priority === "high" ? "destructive" : r.priority === "normal" ? "secondary" : "default"}>
                            {r.priority}
                          </Badge>
                          <Badge variant={r.status === "confirmed" ? "default" : "secondary"}>{r.status}</Badge>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-5 px-1 text-xs"
                            onClick={() => { setEditingReqId(r.id); setEditingReqText(r.requirement_text); }}
                          >
                            {t("requirements.edit")}
                          </Button>
                          {r.status !== "confirmed" && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-5 px-1 text-xs"
                              onClick={() => updateReqMut.mutate({ id: r.id, data: { status: "confirmed" } })}
                            >
                              {t("requirements.confirm")}
                            </Button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Drafting */}
        <TabsContent value="drafting">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t("drafting.title")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <PromptInput
                value={sectionKey}
                onValueChange={setSectionKey}
                onSubmit={() => {
                  if (sectionKey) draftMut.mutate({ project_id: id!, section_key: sectionKey });
                }}
                isLoading={draftMut.isPending}
                className="max-w-xl"
              >
                <PromptInputTextarea placeholder={t("drafting.placeholder")} />
                <PromptInputActions>
                  <PromptInputAction tooltip={t("drafting.generateDraft")}>
                    <Button
                      size="sm"
                      disabled={!sectionKey || draftMut.isPending}
                      onClick={() => draftMut.mutate({ project_id: id!, section_key: sectionKey })}
                    >
                      {draftMut.isPending && <Spinner data-icon="inline-start" />}
                      {t("drafting.generate")}
                    </Button>
                  </PromptInputAction>
                </PromptInputActions>
              </PromptInput>

              {/* Section Editor */}
              {selectedSectionId && sectionVersions && sectionVersions.length > 0 && (
                <div className="flex flex-col gap-3">
                  <Message>
                    <MessageAvatar src="" alt={t("drafting.aiAssistant")} fallback={t("drafting.aiFallback")} />
                    <div className="flex flex-col gap-3 flex-1">
                      <div className="flex gap-2 text-xs text-muted-foreground">
                        <span>{t("drafting.version", { number: sectionVersions[0].version_number })}</span>
                        <span>{t("drafting.by", { actor: sectionVersions[0].created_by_actor })}</span>
                      </div>
                      <MessageContent markdown className="flex-1">
                        {sectionVersions[0].content_markdown || ""}
                      </MessageContent>
                      <MessageActions>
                        <MessageAction tooltip={t("drafting.redraft")}>
                          <Button
                            size="sm"
                            variant="outline"
                            aria-label={t("drafting.redraft")}
                            disabled={redraftMut.isPending}
                            onClick={() => {
                              const section = sections?.find((s) => s.id === selectedSectionId);
                              if (section) {
                                redraftMut.mutate({ project_id: id!, section_key: section.section_key, review_feedback: "Revise based on review" });
                              }
                            }}
                          >
                            {redraftMut.isPending && <Spinner data-icon="inline-start" />}
                            <RefreshCwIcon className="size-3.5" />
                          </Button>
                        </MessageAction>
                      </MessageActions>

                      {/* Evidence for this section version */}
                      {evidence?.filter((ev) => ev.quote_text).length ? (
                        <div className="flex flex-col gap-2">
                          <p className="text-xs font-medium text-muted-foreground">{t("drafting.evidence")}</p>
                          {evidence
                            ?.filter((ev) => ev.quote_text)
                            .slice(0, 5)
                            .map((ev) => (
                              <Source key={ev.id} href={`#evidence-${ev.id}`}>
                                <p className="text-xs">{ev.quote_text}</p>
                                <span className="text-[10px] text-muted-foreground">
                                  {t("drafting.confidence", { value: ev.confidence?.toFixed(2) ?? t("common:notAvailable") })}
                                </span>
                              </Source>
                            ))}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 rounded-md border border-dashed border-yellow-500/50 bg-yellow-500/5 px-3 py-2">
                          <AlertTriangleIcon className="size-4 text-yellow-600 shrink-0" />
                          <p className="text-xs text-yellow-700 dark:text-yellow-400">{t("drafting.noEvidence")}</p>
                        </div>
                      )}

                      {/* Version diff */}
                      {sectionVersions.length > 1 && (
                        <div className="flex flex-col gap-2">
                          <p className="text-xs font-medium text-muted-foreground">{t("drafting.versionHistory")}</p>
                          <div className="flex gap-2 text-xs">
                            {(() => {
                              const versionItems = sectionVersions.map((v) => ({
                                label: t("drafting.versionLabel", { number: v.version_number }),
                                value: v.version_number.toString(),
                              }));
                              return (
                                <>
                                  <Select items={versionItems} value={diffVersionA?.toString() ?? ""} onValueChange={(v) => setDiffVersionA(v ? Number(v) : null)}>
                                    <SelectTrigger size="sm" className="w-28">
                                      <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                      <SelectGroup>
                                        {versionItems.map((item) => (
                                          <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                                        ))}
                                      </SelectGroup>
                                    </SelectContent>
                                  </Select>
                                  <span className="self-center">{t("drafting.vs")}</span>
                                  <Select items={versionItems} value={diffVersionB?.toString() ?? ""} onValueChange={(v) => setDiffVersionB(v ? Number(v) : null)}>
                                    <SelectTrigger size="sm" className="w-28">
                                      <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                      <SelectGroup>
                                        {versionItems.map((item) => (
                                          <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                                        ))}
                                      </SelectGroup>
                                    </SelectContent>
                                  </Select>
                                </>
                              );
                            })()}
                          </div>
                          {diffVersionA != null && diffVersionB != null && (
                            <ScrollArea className="h-48">
                              <div className="p-2 text-xs font-mono whitespace-pre-wrap">
                                {(() => {
                                  const a = sectionVersions.find((v) => v.version_number === diffVersionA);
                                  const b = sectionVersions.find((v) => v.version_number === diffVersionB);
                                  if (!a || !b) return t("drafting.selectTwo");
                                  const linesA = (a.content_markdown || "").split("\n");
                                  const linesB = (b.content_markdown || "").split("\n");
                                  const maxLen = Math.max(linesA.length, linesB.length);
                                  const diff: string[] = [];
                                  for (let i = 0; i < maxLen; i++) {
                                    const la = linesA[i] ?? "";
                                    const lb = linesB[i] ?? "";
                                    if (la === lb) {
                                      diff.push(`  ${la}`);
                                    } else {
                                      if (la) diff.push(`- ${la}`);
                                      if (lb) diff.push(`+ ${lb}`);
                                    }
                                  }
                                  return diff.join("\n") || t("drafting.noDifferences");
                                })()}
                              </div>
                            </ScrollArea>
                          )}
                        </div>
                      )}
                    </div>
                  </Message>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Evidence */}
        <TabsContent value="evidence">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t("evidence.title")}</CardTitle>
            </CardHeader>
            <CardContent>
              {evidence?.length === 0 && knowledgeChunks?.length === 0 && <Empty><EmptyHeader><EmptyMedia variant="icon"><FileIcon /></EmptyMedia><EmptyTitle>{t("evidence.emptyTitle")}</EmptyTitle><EmptyDescription>{t("evidence.emptyDesc")}</EmptyDescription></EmptyHeader></Empty>}
              {evidence && evidence.length > 0 && (
                <div className="flex flex-col gap-3 mb-6">
                  <h3 className="text-sm font-semibold">{t("evidence.citationEvidence")}</h3>
                  {evidence.map((e) => (
                    <Source key={e.id} href={`#evidence-${e.id}`}>
                      <p className="text-sm">{e.quote_text}</p>
                      <div className="flex gap-2 text-xs text-muted-foreground">
                        <span>{t("evidence.confidence", { value: e.confidence?.toFixed(2) ?? t("common:notAvailable") })}</span>
                      </div>
                    </Source>
                  ))}
                </div>
              )}
              {knowledgeChunks && knowledgeChunks.length > 0 && (
                <div className="flex flex-col gap-3">
                  <h3 className="text-sm font-semibold">{t("evidence.knowledgeChunks", { count: knowledgeChunks.length })}</h3>
                  <ScrollArea className="h-96">
                    <div className="flex flex-col gap-2">
                      {knowledgeChunks.map((chunk) => (
                        <div key={chunk.id} className="rounded-md border p-3 text-sm">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                            <FileIcon className="size-3" />
                            <span>{t("evidence.chunkLabel", { index: chunk.chunk_index })}</span>
                          </div>
                          <p className="text-xs whitespace-pre-wrap line-clamp-4">{chunk.content}</p>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Search */}
        <TabsContent value="search">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t("search.title")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    placeholder={t("search.placeholder")}
                    className="pl-9"
                  />
                </div>
                <Button onClick={handleSearch} disabled={isSearching || !searchQuery.trim()}>
                  {isSearching && <Spinner data-icon="inline-start" />}
                  {t("search.search")}
                </Button>
              </div>
              {searchResults.length > 0 && (
                <div className="flex flex-col gap-3">
                  <p className="text-sm font-medium">{t("search.results", { count: searchResults.length })}</p>
                  {searchResults.map((r) => (
                    <div key={r.chunk_id} className="rounded-md border p-3">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                        <span>{t("search.score", { value: r.score.toFixed(3) })}</span>
                      </div>
                      <p className="text-sm whitespace-pre-wrap line-clamp-6">{r.content}</p>
                    </div>
                  ))}
                </div>
              )}
              {searchResults.length === 0 && searchQuery && !isSearching && (
                <Empty className="min-h-32">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <SearchIcon />
                    </EmptyMedia>
                    <EmptyTitle>{t("search.emptyTitle")}</EmptyTitle>
                    <EmptyDescription>{t("search.emptyDesc")}</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Execution Runs */}
        <TabsContent value="runs">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t("runs.title")}</CardTitle>
            </CardHeader>
            <CardContent>
              {runs?.length === 0 && <Empty><EmptyHeader><EmptyMedia variant="icon"><ActivityIcon /></EmptyMedia><EmptyTitle>{t("runs.emptyTitle")}</EmptyTitle><EmptyDescription>{t("runs.emptyDesc")}</EmptyDescription></EmptyHeader></Empty>}
              <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("runs.type")}</TableHead>
                    <TableHead>{t("runs.status")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs?.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>{r.run_type}</TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            r.status === "succeeded" ? "default" : r.status === "failed" ? "destructive" : "secondary"
                          }
                        >
                          {r.status}
                        </Badge>
                        {r.status === "failed" && (
                          <Button size="sm" variant="outline" className="ml-2" onClick={() => {
                            setConfirmAction({
                              title: t("runs.retryTitle"),
                              description: t("runs.retryDesc", { runType: r.run_type }),
                              onConfirm: () => {
                                retryMut.mutate(r.id);
                              },
                            });
                            setConfirmDialogOpen(true);
                          }}>
                            {t("runs.retry")}
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Review */}
        <TabsContent value="review">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Section selector + threads */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{t("review.title")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <FieldGroup>
                  <Field>
                    <FieldLabel>{t("review.section")}</FieldLabel>
                    <Select
                      value={selectedSectionId ?? ""}
                      onValueChange={(v) => {
                        setSelectedSectionId(v);
                        setSelectedThreadId(null);
                      }}
                    >
                      <SelectTrigger><SelectValue placeholder={t("review.selectSection")} /></SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          {sections?.map((s) => (
                            <SelectItem key={s.id} value={s.id}>{s.title || s.section_key}</SelectItem>
                          ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </Field>
                </FieldGroup>

                {reviewThreads?.length === 0 && (
                  <Empty className="min-h-32">
                    <EmptyHeader>
                      <EmptyMedia variant="icon">
                        <MessageCircleIcon />
                      </EmptyMedia>
                      <EmptyTitle>{t("review.emptyTitle")}</EmptyTitle>
                      <EmptyDescription>{t("review.emptyDesc")}</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                )}
                {reviewThreads?.map((thread) => (
                  <button
                    key={thread.id}
                    className={cn(
                      "flex items-center justify-between rounded-md border p-3 text-left text-sm hover:bg-accent transition-colors",
                      selectedThreadId === thread.id && "border-primary bg-accent"
                    )}
                    onClick={() => setSelectedThreadId(thread.id)}
                  >
                    <span className="font-medium">{t("review.thread", { id: thread.id.slice(0, 8) })}</span>
                    <Badge variant={thread.status === "resolved" ? "default" : "secondary"}>{thread.status}</Badge>
                  </button>
                ))}

                {/* Approve / Reject actions */}
                {selectedSectionId && (
                  <div className="flex flex-col gap-2 pt-2 border-t">
                    <p className="text-xs font-medium text-muted-foreground">{t("review.submitDecision")}</p>
                    <Input
                      value={reviewDecisionComment}
                      onChange={(e) => setReviewDecisionComment(e.target.value)}
                      placeholder={t("review.commentPlaceholder")}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="default"
                        disabled={submitDecisionMut.isPending}
                        onClick={() => submitDecisionMut.mutate({
                          section_id: selectedSectionId,
                          decision: "approved",
                          comment: reviewDecisionComment || null,
                        })}
                      >
                        {submitDecisionMut.isPending && <Spinner data-icon="inline-start" />}
                        {t("review.approve")}
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={submitDecisionMut.isPending}
                        onClick={() => submitDecisionMut.mutate({
                          section_id: selectedSectionId,
                          decision: "rejected",
                          comment: reviewDecisionComment || null,
                        })}
                      >
                        {submitDecisionMut.isPending && <Spinner data-icon="inline-start" />}
                        {t("review.reject")}
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Comments panel */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{t("review.comments")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {!selectedThreadId ? (
                  <Empty className="min-h-40">
                    <EmptyHeader>
                      <EmptyMedia variant="icon">
                        <MessageCircleIcon />
                      </EmptyMedia>
                      <EmptyTitle>{t("review.noThreadSelected")}</EmptyTitle>
                      <EmptyDescription>{t("review.noThreadDesc")}</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                ) : (
                  <>
                    <ScrollArea className="max-h-96">
                      <div className="flex flex-col gap-3 pr-4">
                        {reviewComments?.map((c) => (
                          <div key={c.id} className="border rounded-md p-3 flex flex-col gap-1">
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <Badge variant={c.author_type === "ai" ? "secondary" : "default"}>
                                {c.author_type}
                              </Badge>
                              <span>{c.author_id}</span>
                              <span>{new Date(c.created_at).toLocaleString()}</span>
                            </div>
                            <p className="text-sm whitespace-pre-wrap">{c.body}</p>
                          </div>
                        ))}
                        {reviewComments?.length === 0 && (
                          <Empty className="min-h-32">
                            <EmptyHeader>
                              <EmptyMedia variant="icon">
                                <MessageCircleIcon />
                              </EmptyMedia>
                              <EmptyTitle>{t("review.noComments")}</EmptyTitle>
                              <EmptyDescription>{t("review.noCommentsDesc")}</EmptyDescription>
                            </EmptyHeader>
                          </Empty>
                        )}
                      </div>
                    </ScrollArea>
                    <div className="flex gap-2">
                      <Input
                        value={reviewCommentBody}
                        onChange={(e) => setReviewCommentBody(e.target.value)}
                        placeholder={t("review.addComment")}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && reviewCommentBody.trim() && !addCommentMut.isPending) {
                            addCommentMut.mutate({ thread_id: selectedThreadId, body: reviewCommentBody.trim() });
                          }
                        }}
                      />
                      <Button
                        size="sm"
                        disabled={!reviewCommentBody.trim() || addCommentMut.isPending}
                        onClick={() => addCommentMut.mutate({ thread_id: selectedThreadId, body: reviewCommentBody.trim() })}
                      >
                        {addCommentMut.isPending && <Spinner data-icon="inline-start" />}
                        {t("review.send")}
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Audit */}
        <TabsContent value="audit">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t("audit.title")}</CardTitle>
            </CardHeader>
            <CardContent>
              {auditEvents?.length === 0 ? (
                <Empty className="min-h-40">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <ClipboardCheckIcon />
                    </EmptyMedia>
                    <EmptyTitle>{t("audit.emptyTitle")}</EmptyTitle>
                    <EmptyDescription>{t("audit.emptyDesc")}</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : (
                <ScrollArea className="max-h-[500px]">
                  <div className="flex flex-col gap-3 pr-4">
                    {auditEvents?.map((e) => (
                      <div key={e.id} className="border rounded-md p-3 flex flex-col gap-1">
                        <div className="flex items-center gap-2 text-xs">
                          <Badge variant="outline">{e.event_type}</Badge>
                          <span className="text-muted-foreground">{e.actor_id}</span>
                          <span className="text-muted-foreground ml-auto">
                            {new Date(e.created_at).toLocaleString()}
                          </span>
                        </div>
                        {e.payload && (
                          <p className="text-xs text-muted-foreground font-mono bg-muted rounded p-2 mt-1">
                            {JSON.stringify(e.payload, null, 2)}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Export */}
        <TabsContent value="export">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t("export.title")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {deliverables?.length === 0 ? (
                <Empty className="min-h-40">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <DownloadIcon />
                    </EmptyMedia>
                    <EmptyTitle>{t("export.emptyTitle")}</EmptyTitle>
                    <EmptyDescription>{t("export.emptyDesc")}</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : (
                deliverables?.map((d) => (
                  <div key={d.id} className="flex items-center justify-between border rounded-md p-4">
                    <div>
                      <p className="font-medium">{d.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {d.type} &middot; {d.status}
                        {d.export_status && d.export_status !== "none" && ` · ${t("export.statusLabel", { status: d.export_status })}`}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={d.status !== "approved"}
                        onClick={async () => {
                          try {
                            await exportDeliverableDocx(d.id);
                            toast.success(t("export.docxStarted"));
                          } catch {
                            toast.error(t("export.docxFailed"));
                          }
                        }}
                      >
                        {t("export.exportDocx")}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={d.status !== "approved"}
                        onClick={async () => {
                          try {
                            await exportDeliverablePdf(d.id);
                            toast.success(t("export.pdfStarted"));
                          } catch {
                            toast.error(t("export.pdfFailed"));
                          }
                        }}
                      >
                        {t("export.exportPdf")}
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Ops Dashboard */}
        <TabsContent value="ops">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <RuntimeSummaryCards summary={ops} />

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{t("system.title")}</CardTitle>
              </CardHeader>
              <CardContent>
                {runs?.length === 0 ? (
                  <Empty className="min-h-40">
                    <EmptyHeader>
                      <EmptyMedia variant="icon">
                        <ActivityIcon />
                      </EmptyMedia>
                      <EmptyTitle>{t("system.emptyTitle")}</EmptyTitle>
                      <EmptyDescription>{t("system.emptyDesc")}</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                ) : (
                  <ScrollArea className="max-h-80">
                    <div className="flex flex-col gap-2 pr-4">
                      {runs?.map((r) => (
                        <div key={r.id} className="border rounded-md p-3 text-sm">
                          <div className="flex items-center justify-between mb-1">
                            <Badge variant="outline">{r.run_type}</Badge>
                            <Badge variant={r.status === "succeeded" ? "default" : r.status === "failed" ? "destructive" : "secondary"}>
                              {r.status}
                            </Badge>
                          </div>
                          {r.input_json && (
                            <p className="text-xs text-muted-foreground font-mono bg-muted rounded p-1.5 mt-1 line-clamp-2">
                              {t("system.input")} {JSON.stringify(r.input_json)}
                            </p>
                          )}
                          {r.output_json && (
                            <p className="text-xs text-muted-foreground font-mono bg-muted rounded p-1.5 mt-1 line-clamp-2">
                              {t("system.output")} {JSON.stringify(r.output_json)}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <AlertDialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmAction?.title}</AlertDialogTitle>
            <AlertDialogDescription>{confirmAction?.description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("confirm.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                confirmAction?.onConfirm();
                setConfirmDialogOpen(false);
              }}
            >
              {t("confirm.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
