import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getRequirement } from "@/lib/api";
import type {
  BidReadinessSummary,
  RequirementClaimRead,
  RequirementDetailRead,
  RequirementItemRead,
  ReadinessPackRead,
} from "@/lib/api";

import { RequirementsTab } from "./requirements-tab";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getRequirement: vi.fn(),
  };
});

const requirements: RequirementItemRead[] = [
  {
    id: "req-1",
    project_id: "project-1",
    section_key: "qualification",
    requirement_text: "Provide a valid ISO 27001 certificate",
    original_text: "The bidder shall provide a valid ISO 27001 certificate.",
    source_document_id: "source-1",
    source_document_name: "tender.pdf",
    source_locator_json: { page: 12, section: "3.2", text_anchor: "ISO 27001" },
    priority: "high",
    status: "draft",
    owner_user_id: null,
    reviewer_user_id: null,
    due_at: null,
    verification_status: "unverified",
    extraction_confidence: 0.96,
    lock_version: 1,
    updated_at: "2026-07-14T10:00:00Z",
    bid_profile: {
      id: "profile-1",
      requirement_id: "req-1",
      bid_category: "qualification",
      is_mandatory: true,
      score_weight: 5,
      risk_level: "high",
      coverage_status: "uncovered",
      evidence_status: "missing",
      deadline_at: null,
      submission_metadata_json: null,
      updated_at: "2026-07-14T10:00:00Z",
    },
  },
  {
    id: "req-2",
    project_id: "project-1",
    section_key: "technical",
    requirement_text: "Describe the disaster recovery plan",
    original_text: null,
    source_document_id: null,
    source_document_name: null,
    source_locator_json: null,
    priority: "normal",
    status: "confirmed",
    owner_user_id: "user-1",
    reviewer_user_id: null,
    due_at: null,
    verification_status: "verified",
    extraction_confidence: 0.88,
    lock_version: 3,
    updated_at: "2026-07-14T10:00:00Z",
    bid_profile: {
      id: "profile-2",
      requirement_id: "req-2",
      bid_category: "technical",
      is_mandatory: false,
      score_weight: 10,
      risk_level: "normal",
      coverage_status: "covered",
      evidence_status: "sufficient",
      deadline_at: null,
      submission_metadata_json: null,
      updated_at: "2026-07-14T10:00:00Z",
    },
  },
];

const readiness: BidReadinessSummary = {
  formula_version: "1.0",
  project_id: "project-1",
  project_name: "Smart community bid",
  generated_at: "2026-07-14T10:00:00Z",
  source_fingerprint: "fingerprint",
  score_label: "response_readiness",
  readiness_score: 72,
  counts: {
    total: 2,
    mandatory: 1,
    scored: 2,
    covered: 1,
    partial: 0,
    uncovered: 1,
    disputed: 0,
    not_applicable: 0,
    accepted_risk: 0,
    verified: 1,
    assigned: 1,
  },
  scores: {
    mandatory_closure: 0,
    scored_coverage: 0.67,
    verification: 0.5,
    assignment: 0.5,
  },
  requirements: [],
  mandatory_gaps: [],
  evidence_gaps: [],
  contradictions: [],
  overdue: [],
  qualifications: [],
  workload: { unassigned: 1, by_owner: { "user-1": 1 } },
};

const detail: RequirementDetailRead = {
  ...requirements[0],
  evidence_links: [
    {
      id: "link-1",
      requirement_id: "req-1",
      evidence_id: "evidence-1",
      relation_type: "supports",
      verification_status: "unverified",
      quote_text: "The supplier holds ISO 27001 certification.",
      source_document_id: "source-2",
      source_document_name: "supplier-profile.pdf",
      locator_json: { page: 4 },
      confidence: 0.94,
      created_at: "2026-07-14T10:00:00Z",
    },
  ],
  claims: [
    {
      id: "claim-1",
      project_id: "project-1",
      requirement_id: "req-1",
      claim_text: "The supplier holds ISO 27001 certification.",
      claim_type: "factual",
      status: "draft",
      coverage_role: "direct",
      section_version_id: "version-1",
      generation_run_id: "run-1",
      created_by_actor: "ai",
      created_by_user_id: null,
      evidence_ids: ["evidence-1"],
      created_at: "2026-07-14T10:00:00Z",
      updated_at: "2026-07-14T10:00:00Z",
    } satisfies RequirementClaimRead,
  ],
  decisions: [],
};

function renderTab(overrides: Partial<React.ComponentProps<typeof RequirementsTab>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const props: React.ComponentProps<typeof RequirementsTab> = {
    projectId: "project-1",
    requirements,
    readiness,
    people: [{ id: "user-1", displayName: "Alex Chen" }],
    currentUserId: "user-1",
    onCreateRequirement: vi.fn(),
    onUpdateRequirement: vi.fn().mockResolvedValue(undefined),
    onBulkAssign: vi.fn().mockResolvedValue(undefined),
    onVerifyEvidence: vi.fn().mockResolvedValue(undefined),
    onVerifyClaim: vi.fn().mockResolvedValue(undefined),
    onGeneratePack: vi.fn().mockResolvedValue({
      id: "pack-1",
      project_id: "project-1",
      version_number: 1,
      formula_version: "1.0",
      source_fingerprint: "fingerprint",
      status: "ready",
      summary_json: {},
      xlsx_storage_key: "packs/pack-1.xlsx",
      docx_storage_key: "packs/pack-1.docx",
      generated_by_user_id: "user-1",
      created_at: "2026-07-14T10:00:00Z",
    } satisfies ReadinessPackRead),
    onDownloadPack: vi.fn(),
    ...overrides,
  };

  return {
    ...render(
      <QueryClientProvider client={client}>
        <RequirementsTab {...props} />
      </QueryClientProvider>,
    ),
    client,
    props,
  };
}

describe("RequirementsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRequirement).mockResolvedValue(detail);
  });

  it("shows readiness, filters the ledger, and bulk assigns selected rows", async () => {
    const { props } = renderTab();

    expect(screen.getByText("Requirement Ledger")).toBeDefined();
    expect(screen.getAllByText("72%").length).toBeGreaterThan(0);
    expect(screen.getByText("Provide a valid ISO 27001 certificate")).toBeDefined();

    fireEvent.change(screen.getByPlaceholderText("Search requirements..."), {
      target: { value: "disaster" },
    });
    expect(screen.queryByText("Provide a valid ISO 27001 certificate")).toBeNull();
    expect(screen.getByText("Describe the disaster recovery plan")).toBeDefined();

    fireEvent.change(screen.getByPlaceholderText("Search requirements..."), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByLabelText("Select requirement Provide a valid ISO 27001 certificate"));
    fireEvent.click(screen.getByRole("button", { name: "Assign to me" }));

    expect(props.onBulkAssign).toHaveBeenCalledWith({
      requirementIds: ["req-1"],
      lockVersions: { "req-1": 1 },
      ownerUserId: "user-1",
    });
    await waitFor(() => expect(screen.queryByText("1 selected")).toBeNull());
  });

  it("opens a source-backed trace inspector", async () => {
    renderTab();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Inspect source for Provide a valid ISO 27001 certificate",
      }),
    );

    await waitFor(() => expect(getRequirement).toHaveBeenCalledWith("req-1"));
    expect(await screen.findByText("Source & trace")).toBeDefined();
    expect(screen.getAllByText("tender.pdf").length).toBeGreaterThan(0);
    expect(screen.getAllByText("The supplier holds ISO 27001 certification.").length).toBeGreaterThan(0);
    expect(screen.getByText("supplier-profile.pdf")).toBeDefined();
  });

  it("requires evidence verification before an AI-proposed factual claim can be verified", async () => {
    const { props } = renderTab();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Inspect source for Provide a valid ISO 27001 certificate",
      }),
    );

    await screen.findByText("AI proposed");
    fireEvent.click(screen.getByRole("button", { name: "Verify evidence" }));
    expect(props.onVerifyEvidence).toHaveBeenCalledWith("req-1", "link-1");
    expect(screen.getByRole("button", { name: "Verify claim" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("Verify the linked evidence before verifying this factual claim.")).toBeDefined();
  });

  it("allows a reviewer to verify a factual claim after its linked evidence is verified", async () => {
    vi.mocked(getRequirement).mockResolvedValue({
      ...detail,
      evidence_links: detail.evidence_links.map((link) => ({
        ...link,
        verification_status: "verified",
      })),
    });
    const { props } = renderTab();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Inspect source for Provide a valid ISO 27001 certificate",
      }),
    );

    await screen.findByRole("button", { name: "Verify claim" });
    fireEvent.click(screen.getByRole("button", { name: "Verify claim" }));
    expect(props.onVerifyClaim).toHaveBeenCalledWith("req-1", "claim-1");
  });

  it("generates a versioned readiness pack and exposes both downloads", async () => {
    const { props } = renderTab();

    fireEvent.click(screen.getByRole("button", { name: "Generate readiness pack" }));

    await waitFor(() => expect(props.onGeneratePack).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("button", { name: "Download XLSX" })).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Download DOCX" }));
    expect(props.onDownloadPack).toHaveBeenCalledWith("pack-1", "docx");
  });

  it("hides an out-of-date readiness pack after the ledger fingerprint changes", async () => {
    const view = renderTab();

    fireEvent.click(screen.getByRole("button", { name: "Generate readiness pack" }));
    await screen.findByRole("button", { name: "Download XLSX" });

    view.rerender(
      <QueryClientProvider client={view.client}>
        <RequirementsTab
          {...view.props}
          readiness={{ ...readiness, source_fingerprint: "changed-fingerprint" }}
        />
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("button", { name: "Download XLSX" })).toBeNull();
    expect(screen.getByText("This pack is out of date. Generate a new pack before downloading.")).toBeDefined();
  });

  it("keeps requirement edits open when the optimistic update fails", async () => {
    const onUpdateRequirement = vi.fn().mockRejectedValue(new Error("conflict"));
    renderTab({ onUpdateRequirement });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Inspect source for Provide a valid ISO 27001 certificate",
      }),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Requirement Text"), {
      target: { value: "Provide a current ISO 27001 certificate" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onUpdateRequirement).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Save" })).toBeDefined();
    expect(screen.getByDisplayValue("Provide a current ISO 27001 certificate")).toBeDefined();
  });

  it("does not present service failures as an empty or zero-readiness project", () => {
    renderTab({
      requirements: [],
      readiness: undefined,
      loadError: true,
      readinessError: true,
    });

    expect(screen.getByText("The Requirement Ledger could not be loaded")).toBeDefined();
    expect(screen.getByText("Readiness is temporarily unavailable")).toBeDefined();
    expect(screen.queryByText("No requirements")).toBeNull();
  });
});
