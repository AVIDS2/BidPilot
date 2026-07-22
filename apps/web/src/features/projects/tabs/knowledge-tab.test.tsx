import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getMemoryEvidenceMap,
  getMemoryCompilation,
  listProjectMemory,
  reviewMemoryGraphItem,
  startMemoryCompilation,
  startMemoryGraphExtraction,
  type MemoryRead,
} from "@/lib/api";

import { KnowledgeTab } from "./knowledge-tab";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    approveMemory: vi.fn(),
    getMemoryEvidenceMap: vi.fn(),
    getMemoryCompilation: vi.fn(),
    listProjectMemory: vi.fn(),
    reviewMemoryGraphItem: vi.fn(),
    startMemoryCompilation: vi.fn(),
    startMemoryGraphExtraction: vi.fn(),
  };
});

vi.mock("@xyflow/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@xyflow/react")>();
  return {
    ...actual,
    ReactFlow: ({
      nodes,
      edges,
    }: {
      nodes: Array<{ id: string; data: { label: ReactNode } }>;
      edges: Array<{ id: string }>;
    }) => (
      <div data-testid="knowledge-react-flow">
        <span data-testid="knowledge-node-count">{nodes.length}</span>
        <span data-testid="knowledge-edge-count">{edges.length}</span>
        {nodes.map((node) => <div key={node.id}>{node.data.label}</div>)}
      </div>
    ),
    Background: () => null,
    Controls: () => null,
  };
});

const records: MemoryRead[] = [
  {
    id: "memory-active",
    org_id: "org-1",
    project_id: "project-1",
    owner_user_id: null,
    scope: "project_shared",
    kind: "summary",
    status: "active",
    title: "Tender summary",
    body_markdown: "The tender requires an ISO 27001 certificate.",
    citations: [
      {
        source_type: "knowledge_chunk",
        source_id: "chunk-1",
        label: "tender.pdf · Chunk 3",
        locator_json: { page: 12, chunk_index: 2 },
      },
    ],
    expires_at: null,
    created_at: "2026-07-17T10:00:00Z",
    updated_at: "2026-07-17T10:00:00Z",
  },
  {
    id: "memory-proposed",
    org_id: "org-1",
    project_id: "project-1",
    owner_user_id: null,
    scope: "project_shared",
    kind: "risk",
    status: "proposed",
    title: "Compliance position",
    body_markdown: "Confirm the supplier certificate before submission.",
    citations: [
      {
        source_type: "requirement_item",
        source_id: "requirement-1",
        label: "Qualification requirement",
        locator_json: { section: "3.2" },
      },
    ],
    graph_proposal: {
      schema_version: "bidpilot.memory-graph/v1",
      entities: [
        {
          item_id: "entity-supplier-certificate",
          canonical_name: "Supplier certificate",
          entity_type: "qualification",
          evidence_labels: ["Qualification requirement"],
          review_status: "pending",
          review_note: null,
        },
        {
          item_id: "entity-bid-submission",
          canonical_name: "Bid submission",
          entity_type: "deliverable",
          evidence_labels: ["Qualification requirement"],
          review_status: "pending",
          review_note: null,
        },
      ],
      relations: [
        {
          item_id: "relation-submission-requires-certificate",
          subject: "Bid submission",
          predicate: "requires",
          object: "Supplier certificate",
          evidence_labels: ["Qualification requirement"],
          review_status: "pending",
          review_note: null,
        },
      ],
    },
    expires_at: null,
    created_at: "2026-07-17T10:02:00Z",
    updated_at: "2026-07-17T10:02:00Z",
  },
];

function renderTab(canApprove = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <KnowledgeTab projectId="project-1" canApprove={canApprove} />
    </QueryClientProvider>,
  );
}

describe("KnowledgeTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listProjectMemory).mockResolvedValue(records);
    vi.mocked(getMemoryCompilation).mockResolvedValue({
      id: "compile-1",
      project_id: "project-1",
      bundle_id: null,
      status: "succeeded",
      input_source_count: 2,
      result_json: { proposals_created: 1 },
      error_code: null,
      created_at: "2026-07-17T10:00:00Z",
      started_at: "2026-07-17T10:00:01Z",
      finished_at: "2026-07-17T10:00:02Z",
    });
    vi.mocked(getMemoryEvidenceMap).mockResolvedValue({
      project_id: "project-1",
      nodes: [
        {
          id: "memory:memory-active",
          node_type: "memory",
          label: "Tender summary",
          memory_kind: "summary",
          source_type: null,
        },
        {
          id: "source:stable-source-1",
          node_type: "source",
          label: "tender.pdf · Chunk 3",
          memory_kind: null,
          source_type: "knowledge_chunk",
        },
      ],
      edges: [
        {
          id: "edge:memory-active:stable-source-1",
          source: "memory:memory-active",
          target: "source:stable-source-1",
          predicate: "cites",
        },
      ],
      truncated: false,
    });
  });

  it("shows a source-backed ledger and keeps graph proposals in item-level review", async () => {
    renderTab();

    expect(await screen.findByRole("button", { name: "Inspect knowledge record Tender summary" })).toBeDefined();
    expect(screen.getByText("Project Knowledge")).toBeDefined();
    expect(screen.getByRole("button", { name: "Inspect knowledge record Compliance position" })).toBeDefined();
    expect(screen.getAllByText("Qualification requirement").length).toBeGreaterThan(0);
    expect(screen.getByTestId("bid-wiki-provenance-map")).toBeDefined();
    expect(await screen.findByTestId("knowledge-react-flow")).toBeDefined();
    expect(getMemoryEvidenceMap).toHaveBeenCalledWith("project-1");
    expect(screen.getByTestId("knowledge-node-count").textContent).toBe("2");
    expect(screen.getByTestId("knowledge-edge-count").textContent).toBe("1");
    expect(screen.getByTestId("memory-graph-proposal-review")).toBeDefined();
    expect(screen.getByText("Supplier certificate")).toBeDefined();
    expect(screen.getByText("Bid submission")).toBeDefined();
    expect(screen.queryByRole("button", { name: "Approve knowledge record Compliance position" })).toBeNull();
    expect(screen.getAllByText("Pending review").length).toBeGreaterThan(0);
  });

  it("lets an approver record one graph item decision", async () => {
    vi.mocked(reviewMemoryGraphItem).mockResolvedValue({
      item_id: "entity-supplier-certificate",
      item_type: "entity",
      decision: "accepted",
      decision_note: null,
      reviewed_at: "2026-07-21T10:00:00Z",
    });
    renderTab();

    fireEvent.click(await screen.findByRole("button", { name: "Accept graph item Supplier certificate" }));

    await waitFor(() => {
      expect(reviewMemoryGraphItem).toHaveBeenCalledWith("memory-proposed", {
        item_id: "entity-supplier-certificate",
        decision: "accepted",
      });
    });
  });

  it("queues a bounded Bid Wiki compilation instead of auto-writing shared memory", async () => {
    vi.mocked(startMemoryCompilation).mockResolvedValue({
      id: "compile-1",
      project_id: "project-1",
      bundle_id: null,
      status: "queued",
      input_source_count: 2,
      result_json: null,
      error_code: null,
      created_at: "2026-07-17T10:00:00Z",
      started_at: null,
      finished_at: null,
    });
    renderTab();

    fireEvent.click(await screen.findByRole("button", { name: "Generate suggestions" }));

    await waitFor(() => {
      expect(startMemoryCompilation).toHaveBeenCalledWith({ project_id: "project-1" });
    });
    expect(await screen.findByText("Suggestions are ready for review")).toBeDefined();
    expect(screen.getByText("1 reviewable suggestion(s) created.")).toBeDefined();
  });

  it("queues a reviewable entity-relation proposal from selected approved knowledge", async () => {
    vi.mocked(startMemoryGraphExtraction).mockResolvedValue({
      run_id: "graph-run-1",
      runtime_run_id: "runtime-graph-1",
      project_id: "project-1",
      memory_record_id: "memory-active",
      status: "queued",
      reused: false,
    });
    renderTab();

    fireEvent.click(await screen.findByRole("button", { name: "Inspect knowledge record Tender summary" }));
    fireEvent.click(await screen.findByRole("button", { name: "Generate entity-relation proposal" }));

    await waitFor(() => {
      expect(startMemoryGraphExtraction).toHaveBeenCalledWith({
        project_id: "project-1",
        memory_record_id: "memory-active",
      });
    });
  });

  it("keeps approval controls hidden for project collaborators without approval permission", async () => {
    renderTab(false);

    await screen.findByText("Project Knowledge");
    expect(listProjectMemory).toHaveBeenCalledWith("project-1", false);
    expect(screen.queryByRole("button", { name: /Approve knowledge record/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Accept graph item/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Generate suggestions" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Generate entity-relation proposal" })).toBeNull();
  });
});
