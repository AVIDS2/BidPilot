import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  DownloadIcon,
  FileSearchIcon,
  FilterXIcon,
  ListChecksIcon,
  Loader2Icon,
  PlusIcon,
  SearchIcon,
  ShieldCheckIcon,
  UserRoundCheckIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group";
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  getRequirement,
  type BidReadinessSummary,
  type ReadinessPackRead,
  type RequirementCreateInput,
  type RequirementItemRead,
  type RequirementUpdateInput,
} from "@/lib/api";

interface RequirementPerson {
  id: string;
  displayName: string;
  role?: "owner" | "manager" | "contributor" | "reviewer" | "viewer" | "admin";
}

interface BulkAssignmentInput {
  requirementIds: string[];
  lockVersions: Record<string, number>;
  ownerUserId?: string | null;
  reviewerUserId?: string | null;
}

interface RequirementsTabProps {
  projectId: string;
  requirements: RequirementItemRead[];
  readiness?: BidReadinessSummary;
  loading?: boolean;
  loadError?: boolean;
  readinessLoading?: boolean;
  readinessError?: boolean;
  people: RequirementPerson[];
  currentUserId?: string | null;
  onCreateRequirement: (data: Omit<RequirementCreateInput, "project_id">) => Promise<unknown> | unknown;
  onUpdateRequirement: (id: string, data: RequirementUpdateInput) => Promise<void>;
  onBulkAssign: (data: BulkAssignmentInput) => Promise<void>;
  onVerifyEvidence: (requirementId: string, linkId: string) => Promise<void>;
  onVerifyClaim: (requirementId: string, claimId: string) => Promise<void>;
  onGeneratePack: () => Promise<ReadinessPackRead>;
  onDownloadPack: (packId: string, format: "xlsx" | "docx") => void;
  creating?: boolean;
  updating?: boolean;
  bulkAssigning?: boolean;
  reviewing?: boolean;
}

const ALL = "all";

function statusVariant(value: string | undefined): "default" | "secondary" | "destructive" | "outline" {
  if (["covered", "sufficient", "verified", "confirmed"].includes(value ?? "")) return "default";
  if (["uncovered", "disputed", "conflicting", "missing", "high", "critical"].includes(value ?? "")) return "destructive";
  if (["partial", "weak", "pending", "normal"].includes(value ?? "")) return "secondary";
  return "outline";
}

function toDisplayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  if (Array.isArray(value)) return value.map(toDisplayValue).filter(Boolean).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function RequirementsTab({
  projectId,
  requirements,
  readiness,
  loading = false,
  loadError = false,
  readinessLoading = false,
  readinessError = false,
  people,
  currentUserId,
  onCreateRequirement,
  onUpdateRequirement,
  onBulkAssign,
  onVerifyEvidence,
  onVerifyClaim,
  onGeneratePack,
  onDownloadPack,
  creating = false,
  updating = false,
  bulkAssigning = false,
  reviewing = false,
}: RequirementsTabProps) {
  const { t } = useTranslation("projects");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(ALL);
  const [coverage, setCoverage] = useState(ALL);
  const [evidence, setEvidence] = useState(ALL);
  const [risk, setRisk] = useState(ALL);
  const [verification, setVerification] = useState(ALL);
  const [owner, setOwner] = useState(ALL);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectedRequirementId, setSelectedRequirementId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newSectionKey, setNewSectionKey] = useState("");
  const [newRequirementText, setNewRequirementText] = useState("");
  const [newCategory, setNewCategory] = useState("technical");
  const [newRisk, setNewRisk] = useState("normal");
  const [newMandatory, setNewMandatory] = useState(false);
  const [latestPack, setLatestPack] = useState<ReadinessPackRead | null>(null);
  const [generatingPack, setGeneratingPack] = useState(false);
  const [bulkAssignResetKey, setBulkAssignResetKey] = useState(0);

  const personById = useMemo(
    () => new Map(people.map((person) => [person.id, person])),
    [people],
  );
  const ownerCandidates = useMemo(
    () => people.filter((person) => !person.role || ["owner", "manager", "contributor", "admin"].includes(person.role)),
    [people],
  );
  const reviewerCandidates = useMemo(
    () => people.filter((person) => !person.role || ["owner", "manager", "reviewer", "admin"].includes(person.role)),
    [people],
  );
  const currentUserCanOwn = !currentUserId || ownerCandidates.some((person) => person.id === currentUserId);

  const categoryOptions = useMemo(
    () => Array.from(new Set(requirements.map((item) => item.bid_profile?.bid_category).filter(Boolean) as string[])).sort(),
    [requirements],
  );

  const filteredRequirements = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase();
    return requirements.filter((item) => {
      const profile = item.bid_profile;
      const matchesSearch = !normalizedSearch || [
        item.requirement_text,
        item.original_text,
        item.section_key,
        item.source_document_name,
      ].some((value) => value?.toLocaleLowerCase().includes(normalizedSearch));
      const matchesOwner = owner === ALL
        || (owner === "unassigned" ? !item.owner_user_id : item.owner_user_id === owner);
      return matchesSearch
        && (category === ALL || profile?.bid_category === category)
        && (coverage === ALL || profile?.coverage_status === coverage)
        && (evidence === ALL || profile?.evidence_status === evidence)
        && (risk === ALL || profile?.risk_level === risk)
        && (verification === ALL || item.verification_status === verification)
        && matchesOwner;
    });
  }, [category, coverage, evidence, owner, requirements, risk, search, verification]);

  const visibleIds = useMemo(
    () => filteredRequirements.map((item) => item.id),
    [filteredRequirements],
  );
  const selectedRequirements = filteredRequirements.filter((item) => selectedIds.has(item.id));
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));
  const someVisibleSelected = visibleIds.some((id) => selectedIds.has(id)) && !allVisibleSelected;
  const activeFilterCount = [category, coverage, evidence, risk, verification, owner]
    .filter((value) => value !== ALL).length + (search.trim() ? 1 : 0);

  const detailQuery = useQuery({
    queryKey: ["requirement-detail", projectId, selectedRequirementId],
    queryFn: () => getRequirement(selectedRequirementId!),
    enabled: Boolean(selectedRequirementId),
    staleTime: 15_000,
  });

  useEffect(() => {
    const visibleIdSet = new Set(visibleIds);
    setSelectedIds((current) => {
      const next = new Set([...current].filter((id) => visibleIdSet.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [visibleIds]);

  const toggleRequirement = (requirementId: string, checked: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(requirementId);
      else next.delete(requirementId);
      return next;
    });
  };

  const toggleVisible = (checked: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      visibleIds.forEach((id) => {
        if (checked) next.add(id);
        else next.delete(id);
      });
      return next;
    });
  };

  const runBulkAssignment = async (data: BulkAssignmentInput) => {
    try {
      await onBulkAssign(data);
      setSelectedIds(new Set());
      setBulkAssignResetKey((current) => current + 1);
    } catch {
      // The parent mutation owns the user-facing error and refreshes stale ledger data.
    }
  };

  const bulkPayload = () => ({
    requirementIds: selectedRequirements.map((item) => item.id),
    lockVersions: Object.fromEntries(selectedRequirements.map((item) => [item.id, item.lock_version])),
  });

  const resetFilters = () => {
    setSearch("");
    setCategory(ALL);
    setCoverage(ALL);
    setEvidence(ALL);
    setRisk(ALL);
    setVerification(ALL);
    setOwner(ALL);
  };

  const createRequirement = async () => {
    const requirementText = newRequirementText.trim();
    const sectionKey = newSectionKey.trim();
    if (!requirementText || !sectionKey) return;
    try {
      await onCreateRequirement({
        section_key: sectionKey,
        requirement_text: requirementText,
        priority: newRisk === "high" || newRisk === "critical" ? "high" : "normal",
        bid_profile: {
          bid_category: newCategory,
          is_mandatory: newMandatory,
          risk_level: newRisk,
        },
      });
      setNewRequirementText("");
      setNewSectionKey("");
      setNewMandatory(false);
      setShowCreate(false);
    } catch {
      // The parent mutation reports the error and the form remains intact for retry.
    }
  };

  const generatePack = async () => {
    setGeneratingPack(true);
    try {
      setLatestPack(await onGeneratePack());
    } catch {
      // The parent mutation reports the error.
    } finally {
      setGeneratingPack(false);
    }
  };

  const label = (value: string | undefined) => t(`requirements.ledger.values.${value}`, {
    defaultValue: value ?? t("requirements.ledger.notAvailable"),
  });

  const renderLocator = (locator: Record<string, unknown> | null) => {
    if (!locator) return t("requirements.ledger.notAvailable");
    const fields = [
      ["page", t("requirements.ledger.locator.page")],
      ["section", t("requirements.ledger.locator.section")],
      ["table", t("requirements.ledger.locator.table")],
      ["text_anchor", t("requirements.ledger.locator.anchor")],
      ["bbox", t("requirements.ledger.locator.region")],
    ] as const;
    const parts = fields
      .map(([key, fieldLabel]) => {
        const value = toDisplayValue(locator[key]);
        return value ? `${fieldLabel} ${value}` : "";
      })
      .filter(Boolean);
    return parts.join(" · ") || t("requirements.ledger.notAvailable");
  };

  const latestPackIsCurrent = Boolean(
    latestPack
      && readiness
      && !readinessError
      && latestPack.source_fingerprint === readiness.source_fingerprint,
  );
  const latestPackOutdated = Boolean(
    latestPack
      && readiness
      && !readinessLoading
      && !readinessError
      && !latestPackIsCurrent,
  );
  const readinessMetrics = readiness
    ? [
      ["mandatory", readiness.counts.mandatory, readiness.mandatory_gaps.length],
      ["coverage", readiness.counts.covered, readiness.counts.total],
      ["evidence", readiness.counts.covered + readiness.counts.partial, readiness.counts.total],
      ["assigned", readiness.counts.assigned, readiness.counts.total],
    ]
    : [];
  const readinessMetricKeys = ["mandatory", "coverage", "evidence", "assigned"];

  return (
    <div className="flex min-w-0 flex-col gap-5">
      <section className="rounded-xl border bg-card p-4 sm:p-5" aria-labelledby="requirement-ledger-title">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <ListChecksIcon className="text-primary" aria-hidden />
              <h2 id="requirement-ledger-title" className="text-lg font-semibold">
                {t("requirements.ledger.title")}
              </h2>
            </div>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              {t("requirements.ledger.description")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {latestPackIsCurrent && latestPack?.xlsx_storage_key && (
              <Button variant="outline" size="sm" onClick={() => onDownloadPack(latestPack.id, "xlsx")}>
                <DownloadIcon data-icon="inline-start" />
                {t("requirements.ledger.downloadXlsx")}
              </Button>
            )}
            {latestPackIsCurrent && latestPack?.docx_storage_key && (
              <Button variant="outline" size="sm" onClick={() => onDownloadPack(latestPack.id, "docx")}>
                <DownloadIcon data-icon="inline-start" />
                {t("requirements.ledger.downloadDocx")}
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setShowCreate((value) => !value)}>
              <PlusIcon data-icon="inline-start" />
              {t("requirements.ledger.addRequirement")}
            </Button>
            <Button size="sm" disabled={generatingPack} onClick={generatePack}>
              {generatingPack ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : <FileSearchIcon data-icon="inline-start" />}
              {t("requirements.ledger.generatePack")}
            </Button>
            {latestPackOutdated && (
              <p className="w-full text-xs text-amber-700 dark:text-amber-300">
                {t("requirements.ledger.packOutdated")}
              </p>
            )}
          </div>
        </div>

        <div className="mt-5 grid gap-5 border-t pt-5 lg:grid-cols-[minmax(220px,0.8fr)_minmax(0,2.2fr)]">
          <div className="flex items-end gap-3">
            {readinessLoading ? (
              <Skeleton className="h-11 w-20" />
            ) : (
              <strong className="text-4xl font-semibold tabular-nums">
                {readinessError || !readiness ? "--" : `${Math.round(readiness.readiness_score)}%`}
              </strong>
            )}
            <div className="pb-1 text-sm text-muted-foreground">
              <p>{t("requirements.ledger.readiness")}</p>
              <p className="text-xs">
                {readinessError ? t("requirements.ledger.readinessUnavailable") : t("requirements.ledger.notWinProbability")}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-4">
            {readinessLoading && Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-14 w-full" />
            ))}
            {!readinessLoading && (readinessError || !readiness) && readinessMetricKeys.map((key) => (
              <div key={key} className="min-w-0 border-l pl-3">
                <p className="text-xs text-muted-foreground">{t(`requirements.ledger.metrics.${key}`)}</p>
                <p className="mt-1 text-lg font-medium tabular-nums">--</p>
              </div>
            ))}
            {!readinessLoading && readinessMetrics.map(([key, value, total]) => (
              <div key={String(key)} className="min-w-0 border-l pl-3">
                <p className="text-xs text-muted-foreground">{t(`requirements.ledger.metrics.${key}`)}</p>
                <p className="mt-1 text-lg font-medium tabular-nums">
                  {key === "mandatory" ? total : `${value}/${total}`}
                </p>
                {key === "mandatory" && (
                  <p className="text-xs text-destructive">
                    {t("requirements.ledger.gaps", { count: Number(total) })}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        <Progress value={readinessError || !readiness ? null : readiness.readiness_score} className="mt-4 gap-2">
          <ProgressLabel className="sr-only">{t("requirements.ledger.readiness")}</ProgressLabel>
          <ProgressValue className="sr-only" />
        </Progress>
      </section>

      {showCreate && (
        <section className="rounded-xl border bg-card p-4" aria-label={t("requirements.ledger.addRequirement")}>
          <FieldGroup className="grid gap-4 md:grid-cols-2 xl:grid-cols-[minmax(150px,0.7fr)_minmax(260px,2fr)_minmax(150px,0.8fr)_minmax(130px,0.7fr)_auto] xl:items-end">
            <Field>
              <FieldLabel htmlFor="new-requirement-section">{t("requirements.sectionKey")}</FieldLabel>
              <Input id="new-requirement-section" value={newSectionKey} onChange={(event) => setNewSectionKey(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel htmlFor="new-requirement-text">{t("requirements.requirementText")}</FieldLabel>
              <Input id="new-requirement-text" value={newRequirementText} onChange={(event) => setNewRequirementText(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel>{t("requirements.ledger.category")}</FieldLabel>
              <Select value={newCategory} onValueChange={(value) => setNewCategory(value ?? "technical")}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent><SelectGroup>
                  {["technical", "qualification", "commercial", "delivery", "formatting", "submission"].map((value) => (
                    <SelectItem key={value} value={value}>{label(value)}</SelectItem>
                  ))}
                </SelectGroup></SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>{t("requirements.ledger.risk")}</FieldLabel>
              <Select value={newRisk} onValueChange={(value) => setNewRisk(value ?? "normal")}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent><SelectGroup>
                  {["low", "normal", "high", "critical"].map((value) => (
                    <SelectItem key={value} value={value}>{label(value)}</SelectItem>
                  ))}
                </SelectGroup></SelectContent>
              </Select>
            </Field>
            <div className="flex flex-wrap items-center gap-3 md:pb-0.5">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={newMandatory} onCheckedChange={(value) => setNewMandatory(Boolean(value))} />
                {t("requirements.ledger.mandatory")}
              </label>
              <Button disabled={creating || !newSectionKey.trim() || !newRequirementText.trim()} onClick={createRequirement}>
                {creating && <Loader2Icon data-icon="inline-start" className="animate-spin" />}
                {t("requirements.add")}
              </Button>
            </div>
          </FieldGroup>
        </section>
      )}

      <section className="min-w-0 overflow-hidden rounded-xl border bg-card" aria-label={t("requirements.ledger.title")}>
        <div className="flex flex-col gap-3 border-b p-3 lg:flex-row lg:items-center lg:justify-between">
          <InputGroup className="w-full lg:max-w-sm">
            <InputGroupAddon><SearchIcon aria-hidden /></InputGroupAddon>
            <InputGroupInput
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("requirements.ledger.searchPlaceholder")}
            />
          </InputGroup>
          <div className="flex flex-wrap gap-2">
            <FilterSelect value={category} onValueChange={setCategory} label={t("requirements.ledger.category")} options={categoryOptions} valueLabel={label} />
            <FilterSelect value={coverage} onValueChange={setCoverage} label={t("requirements.ledger.coverage")} options={["uncovered", "partial", "covered", "disputed", "not_applicable", "accepted_risk"]} valueLabel={label} />
            <FilterSelect value={evidence} onValueChange={setEvidence} label={t("requirements.ledger.evidence")} options={["missing", "weak", "sufficient", "conflicting", "not_required"]} valueLabel={label} />
            <FilterSelect value={risk} onValueChange={setRisk} label={t("requirements.ledger.risk")} options={["low", "normal", "high", "critical"]} valueLabel={label} />
            <FilterSelect value={verification} onValueChange={setVerification} label={t("requirements.ledger.verification")} options={["unverified", "verified", "rejected"]} valueLabel={label} />
            <Select value={owner} onValueChange={(value) => setOwner(value ?? ALL)}>
              <SelectTrigger size="sm" aria-label={t("requirements.ledger.owner")}><SelectValue>{owner === ALL ? t("requirements.ledger.owner") : owner === "unassigned" ? t("requirements.ledger.unassigned") : personById.get(owner)?.displayName ?? t("requirements.ledger.owner")}</SelectValue></SelectTrigger>
              <SelectContent><SelectGroup>
                <SelectItem value={ALL}>{t("requirements.ledger.allOwners")}</SelectItem>
                <SelectItem value="unassigned">{t("requirements.ledger.unassigned")}</SelectItem>
                {people.map((person) => <SelectItem key={person.id} value={person.id}>{person.displayName}</SelectItem>)}
              </SelectGroup></SelectContent>
            </Select>
            {activeFilterCount > 0 && (
              <Button variant="ghost" size="sm" onClick={resetFilters}>
                <FilterXIcon data-icon="inline-start" />
                {t("requirements.ledger.clearFilters", { count: activeFilterCount })}
              </Button>
            )}
          </div>
        </div>

        {selectedRequirements.length > 0 && (
          <div className="flex flex-col gap-3 border-b bg-muted/30 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm font-medium">
              {t("requirements.ledger.selected", { count: selectedRequirements.length })}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {currentUserId && currentUserCanOwn && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={bulkAssigning}
                  onClick={() => void runBulkAssignment({ ...bulkPayload(), ownerUserId: currentUserId })}
                >
                  <UserRoundCheckIcon data-icon="inline-start" />
                  {t("requirements.ledger.assignToMe")}
                </Button>
              )}
              <Select
                key={`owner-${bulkAssignResetKey}`}
                onValueChange={(value) => {
                  if (typeof value !== "string" || !value) return;
                  void runBulkAssignment({ ...bulkPayload(), ownerUserId: value === "unassigned" ? null : value });
                }}
              >
                <SelectTrigger size="sm" disabled={bulkAssigning} aria-label={t("requirements.ledger.assignOwner")}><SelectValue placeholder={t("requirements.ledger.assignOwner")} /></SelectTrigger>
                <SelectContent><SelectGroup>
                  <SelectItem value="unassigned">{t("requirements.ledger.unassignOwner")}</SelectItem>
                  {ownerCandidates.map((person) => <SelectItem key={person.id} value={person.id}>{person.displayName}</SelectItem>)}
                </SelectGroup></SelectContent>
              </Select>
              <Select
                key={`reviewer-${bulkAssignResetKey}`}
                onValueChange={(value) => {
                  if (typeof value !== "string" || !value) return;
                  void runBulkAssignment({ ...bulkPayload(), reviewerUserId: value === "unassigned" ? null : value });
                }}
              >
                <SelectTrigger size="sm" disabled={bulkAssigning} aria-label={t("requirements.ledger.assignReviewer")}><SelectValue placeholder={t("requirements.ledger.assignReviewer")} /></SelectTrigger>
                <SelectContent><SelectGroup>
                  <SelectItem value="unassigned">{t("requirements.ledger.unassignReviewer")}</SelectItem>
                  {reviewerCandidates.map((person) => <SelectItem key={person.id} value={person.id}>{person.displayName}</SelectItem>)}
                </SelectGroup></SelectContent>
              </Select>
              <Button variant="ghost" size="sm" disabled={bulkAssigning} onClick={() => setSelectedIds(new Set())}>{t("requirements.ledger.clearSelection")}</Button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex flex-col gap-2 p-4">
            {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-12 w-full" />)}
          </div>
        ) : loadError ? (
          <Empty className="min-h-72">
            <EmptyHeader>
              <EmptyMedia variant="icon"><AlertTriangleIcon /></EmptyMedia>
              <EmptyTitle>{t("requirements.ledger.loadFailed")}</EmptyTitle>
              <EmptyDescription>{t("requirements.ledger.loadFailedDescription")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : filteredRequirements.length === 0 ? (
          <Empty className="min-h-72">
            <EmptyHeader>
              <EmptyMedia variant="icon"><ListChecksIcon /></EmptyMedia>
              <EmptyTitle>{requirements.length ? t("requirements.ledger.noMatches") : t("requirements.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{requirements.length ? t("requirements.ledger.noMatchesDescription") : t("requirements.emptyDesc")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <Table className="min-w-[960px] xl:min-w-[1120px]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    checked={allVisibleSelected}
                    indeterminate={someVisibleSelected}
                    onCheckedChange={(value) => toggleVisible(Boolean(value))}
                    aria-label={t("requirements.ledger.selectAll")}
                  />
                </TableHead>
                <TableHead className="min-w-80">{t("requirements.ledger.requirement")}</TableHead>
                <TableHead>{t("requirements.ledger.category")}</TableHead>
                <TableHead>{t("requirements.ledger.coverage")}</TableHead>
                <TableHead>{t("requirements.ledger.evidence")}</TableHead>
                <TableHead>{t("requirements.ledger.owner")}</TableHead>
                <TableHead>{t("requirements.ledger.verification")}</TableHead>
                <TableHead className="min-w-52">{t("requirements.ledger.source")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRequirements.map((item) => {
                const profile = item.bid_profile;
                const ownerPerson = item.owner_user_id ? personById.get(item.owner_user_id) : undefined;
                return (
                  <TableRow key={item.id} data-state={selectedIds.has(item.id) ? "selected" : undefined}>
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.has(item.id)}
                        onCheckedChange={(value) => toggleRequirement(item.id, Boolean(value))}
                        aria-label={t("requirements.ledger.selectRequirement", { requirement: item.requirement_text })}
                      />
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      <button className="block max-w-xl text-left" onClick={() => setSelectedRequirementId(item.id)}>
                        <span className="line-clamp-2 font-medium leading-5">{item.requirement_text}</span>
                        <span className="mt-1 block text-xs text-muted-foreground">
                          {item.section_key}
                          {typeof profile?.score_weight === "number" ? ` · ${t("requirements.ledger.scoreWeight", { value: profile.score_weight })}` : ""}
                        </span>
                      </button>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col items-start gap-1">
                        <Badge variant="outline">{label(profile?.bid_category)}</Badge>
                        {profile?.is_mandatory && <Badge variant="destructive">{t("requirements.ledger.mandatory")}</Badge>}
                      </div>
                    </TableCell>
                    <TableCell><Badge variant={statusVariant(profile?.coverage_status)}>{label(profile?.coverage_status)}</Badge></TableCell>
                    <TableCell><Badge variant={statusVariant(profile?.evidence_status)}>{label(profile?.evidence_status)}</Badge></TableCell>
                    <TableCell>
                      <span className={ownerPerson ? "text-sm" : "text-sm text-muted-foreground"}>
                        {item.owner_user_id ? ownerPerson?.displayName ?? t("requirements.ledger.unknownMember") : t("requirements.ledger.unassigned")}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col items-start gap-1">
                        <Badge variant={statusVariant(item.verification_status)}>{label(item.verification_status)}</Badge>
                        {typeof item.extraction_confidence === "number" && (
                          <span className="text-xs text-muted-foreground">{Math.round(item.extraction_confidence * 100)}%</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-auto max-w-52 justify-start px-0 py-1 text-left"
                        aria-label={t("requirements.ledger.inspectSourceFor", { requirement: item.requirement_text })}
                        onClick={() => setSelectedRequirementId(item.id)}
                      >
                        <FileSearchIcon data-icon="inline-start" />
                        <span className="truncate">{item.source_document_name ?? renderLocator(item.source_locator_json)}</span>
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}

        <div className="flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground">
          <span>{t("requirements.ledger.showing", { visible: filteredRequirements.length, total: requirements.length })}</span>
          {readiness && readiness.contradictions.length > 0 && (
            <span className="flex items-center gap-1 text-destructive">
              <AlertTriangleIcon aria-hidden />
              {t("requirements.ledger.contradictions", { count: readiness.contradictions.length })}
            </span>
          )}
        </div>
      </section>

      <Sheet open={Boolean(selectedRequirementId)} onOpenChange={(open) => !open && setSelectedRequirementId(null)}>
        <SheetContent className="w-full gap-0 sm:max-w-2xl">
          <SheetHeader className="border-b pr-12">
            <SheetTitle>{t("requirements.ledger.inspectorTitle")}</SheetTitle>
            <SheetDescription>{t("requirements.ledger.inspectorDescription")}</SheetDescription>
          </SheetHeader>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {detailQuery.isLoading && (
              <div className="flex flex-col gap-3">
                <Skeleton className="h-7 w-4/5" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-36 w-full" />
              </div>
            )}
            {detailQuery.isError && (
              <div className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">
                {t("requirements.ledger.detailLoadFailed")}
              </div>
            )}
            {detailQuery.data && (
              <RequirementInspector
                key={`${detailQuery.data.id}:${detailQuery.data.lock_version}`}
                requirement={detailQuery.data}
                people={personById}
                label={label}
                renderLocator={renderLocator}
                updating={updating}
                onUpdate={onUpdateRequirement}
                onVerifyEvidence={onVerifyEvidence}
                onVerifyClaim={onVerifyClaim}
                reviewing={reviewing}
                t={t}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function FilterSelect({
  value,
  onValueChange,
  label,
  options,
  valueLabel,
}: {
  value: string;
  onValueChange: (value: string) => void;
  label: string;
  options: string[];
  valueLabel: (value: string | undefined) => string;
}) {
  return (
    <Select value={value} onValueChange={(next) => onValueChange(next ?? ALL)}>
        <SelectTrigger size="sm" aria-label={label}><SelectValue>{value === ALL ? label : valueLabel(value)}</SelectValue></SelectTrigger>
      <SelectContent><SelectGroup>
        <SelectItem value={ALL}>{label}</SelectItem>
        {options.map((option) => <SelectItem key={option} value={option}>{valueLabel(option)}</SelectItem>)}
      </SelectGroup></SelectContent>
    </Select>
  );
}

function RequirementInspector({
  requirement,
  people,
  label,
  renderLocator,
  updating,
  onUpdate,
  onVerifyEvidence,
  onVerifyClaim,
  reviewing,
  t,
}: {
  requirement: Awaited<ReturnType<typeof getRequirement>>;
  people: Map<string, RequirementPerson>;
  label: (value: string | undefined) => string;
  renderLocator: (locator: Record<string, unknown> | null) => string;
  updating: boolean;
  onUpdate: (id: string, data: RequirementUpdateInput) => Promise<void>;
  onVerifyEvidence: (requirementId: string, linkId: string) => Promise<void>;
  onVerifyClaim: (requirementId: string, claimId: string) => Promise<void>;
  reviewing: boolean;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  const [editing, setEditing] = useState(false);
  const [sectionKey, setSectionKey] = useState(requirement.section_key);
  const [requirementText, setRequirementText] = useState(requirement.requirement_text);
  const profile = requirement.bid_profile;
  const verifiedEvidenceIds = new Set(
    requirement.evidence_links
      .filter((link) => link.relation_type === "supports" && link.verification_status === "verified")
      .map((link) => link.evidence_id),
  );

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{label(profile?.bid_category)}</Badge>
          {profile?.is_mandatory && <Badge variant="destructive">{t("requirements.ledger.mandatory")}</Badge>}
          <Badge variant={statusVariant(profile?.coverage_status)}>{label(profile?.coverage_status)}</Badge>
          <Badge variant={statusVariant(profile?.evidence_status)}>{label(profile?.evidence_status)}</Badge>
        </div>
        {editing ? (
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="requirement-inspector-section">{t("requirements.sectionKey")}</FieldLabel>
              <Input id="requirement-inspector-section" value={sectionKey} onChange={(event) => setSectionKey(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel htmlFor="requirement-inspector-text">{t("requirements.requirementText")}</FieldLabel>
              <Textarea id="requirement-inspector-text" value={requirementText} onChange={(event) => setRequirementText(event.target.value)} rows={5} />
            </Field>
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={updating || !sectionKey.trim() || !requirementText.trim()}
                onClick={async () => {
                  try {
                    await onUpdate(requirement.id, {
                      lock_version: requirement.lock_version,
                      section_key: sectionKey.trim(),
                      requirement_text: requirementText.trim(),
                    });
                    setEditing(false);
                  } catch {
                    // Keep the editor open so the user can retry after the ledger refreshes.
                  }
                }}
              >
                {t("requirements.save")}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setEditing(false)}>{t("requirements.cancel")}</Button>
            </div>
          </FieldGroup>
        ) : (
          <>
            <h3 className="text-lg font-semibold leading-7">{requirement.requirement_text}</h3>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>{t("requirements.edit")}</Button>
              {requirement.verification_status !== "verified" && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={updating}
                  onClick={() => {
                    void onUpdate(requirement.id, {
                      lock_version: requirement.lock_version,
                      verification_status: "verified",
                    }).catch(() => undefined);
                  }}
                >
                  <ShieldCheckIcon data-icon="inline-start" />
                  {t("requirements.ledger.verifyExtraction")}
                </Button>
              )}
            </div>
          </>
        )}
      </section>

      <section className="rounded-lg border p-4">
        <h4 className="text-sm font-semibold">{t("requirements.ledger.sourceClause")}</h4>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{requirement.original_text ?? requirement.requirement_text}</p>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-muted-foreground">{t("requirements.ledger.sourceFile")}</dt><dd className="mt-1 break-all font-medium">{requirement.source_document_name ?? t("requirements.ledger.notAvailable")}</dd></div>
          <div><dt className="text-xs text-muted-foreground">{t("requirements.ledger.location")}</dt><dd className="mt-1 break-words leading-5">{renderLocator(requirement.source_locator_json)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">{t("requirements.ledger.owner")}</dt><dd className="mt-1">{requirement.owner_user_id ? people.get(requirement.owner_user_id)?.displayName ?? requirement.owner_user_id : t("requirements.ledger.unassigned")}</dd></div>
          <div><dt className="text-xs text-muted-foreground">{t("requirements.ledger.reviewer")}</dt><dd className="mt-1">{requirement.reviewer_user_id ? people.get(requirement.reviewer_user_id)?.displayName ?? requirement.reviewer_user_id : t("requirements.ledger.unassigned")}</dd></div>
        </dl>
      </section>

      <TraceSection
        title={t("requirements.ledger.linkedEvidence", { count: requirement.evidence_links.length })}
        empty={t("requirements.ledger.noEvidence")}
      >
        {requirement.evidence_links.map((link) => (
          <article key={link.id} className="rounded-lg border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Badge variant={statusVariant(link.verification_status)}>{label(link.verification_status)}</Badge>
              <span className="text-xs text-muted-foreground">{link.source_document_name ?? t("requirements.ledger.unknownSource")}</span>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{link.quote_text}</p>
            <p className="mt-2 text-xs text-muted-foreground">{renderLocator(link.locator_json)}</p>
            {link.verification_status !== "verified" && (
              <Button
                className="mt-3"
                variant="outline"
                size="sm"
                disabled={reviewing}
                onClick={() => {
                  void onVerifyEvidence(requirement.id, link.id).catch(() => undefined);
                }}
              >
                <ShieldCheckIcon data-icon="inline-start" />
                {t("requirements.ledger.verifyEvidence")}
              </Button>
            )}
          </article>
        ))}
      </TraceSection>

      <TraceSection title={t("requirements.ledger.claims", { count: requirement.claims.length })} empty={t("requirements.ledger.noClaims")}>
        {requirement.claims.map((claim) => {
          const claimEvidenceReady = claim.claim_type !== "factual" || (
            claim.evidence_ids.length > 0
            && claim.evidence_ids.every((evidenceId) => verifiedEvidenceIds.has(evidenceId))
          );
          return (
            <article key={claim.id} className="rounded-lg border p-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant={statusVariant(claim.status)}>{label(claim.status)}</Badge>
                <Badge variant="outline">{label(claim.claim_type)}</Badge>
                {claim.created_by_actor === "ai" && <Badge variant="secondary">{t("requirements.ledger.aiProposed")}</Badge>}
              </div>
              <p className="mt-2 text-sm leading-6">{claim.claim_text}</p>
              {claim.status !== "verified" && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={reviewing || !claimEvidenceReady}
                    onClick={() => {
                      void onVerifyClaim(requirement.id, claim.id).catch(() => undefined);
                    }}
                  >
                    <ShieldCheckIcon data-icon="inline-start" />
                    {t("requirements.ledger.verifyClaim")}
                  </Button>
                  {!claimEvidenceReady && (
                    <span className="text-xs text-muted-foreground">
                      {t("requirements.ledger.verifyClaimEvidenceFirst")}
                    </span>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </TraceSection>

      <TraceSection title={t("requirements.ledger.decisions", { count: requirement.decisions.length })} empty={t("requirements.ledger.noDecisions")}>
        {requirement.decisions.map((decision) => (
          <article key={decision.id} className="rounded-lg border p-3">
            <div className="flex flex-wrap gap-2"><Badge variant={statusVariant(decision.status)}>{label(decision.status)}</Badge><Badge variant="outline">{label(decision.decision_type)}</Badge></div>
            <p className="mt-2 text-sm leading-6">{decision.rationale}</p>
          </article>
        ))}
      </TraceSection>

      <div className="flex items-start gap-2 rounded-lg border p-3 text-xs text-muted-foreground">
        <CheckCircle2Icon className="mt-0.5 shrink-0 text-primary" aria-hidden />
        <p>{t("requirements.ledger.traceRule")}</p>
      </div>
    </div>
  );
}

function TraceSection({ title, empty, children }: { title: string; empty: string; children: ReactNode }) {
  const childCount = Array.isArray(children) ? children.length : children ? 1 : 0;
  return (
    <section>
      <h4 className="text-sm font-semibold">{title}</h4>
      {childCount ? <div className="mt-3 flex flex-col gap-2">{children}</div> : <p className="mt-2 text-sm text-muted-foreground">{empty}</p>}
    </section>
  );
}
