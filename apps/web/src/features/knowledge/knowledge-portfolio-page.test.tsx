import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  listKnowledgePortfolio: vi.fn(),
}));

import { listKnowledgePortfolio } from "@/lib/api";
import { KnowledgePortfolioPage } from "./knowledge-portfolio-page";

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <KnowledgePortfolioPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("KnowledgePortfolioPage", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renders safe portfolio metadata and deep-links into a project Bid Wiki", async () => {
    vi.mocked(listKnowledgePortfolio).mockResolvedValue([
      {
        project_id: "project-1",
        project_name: "Proposal Alpha",
        active_shared_count: 7,
        proposed_shared_count: 2,
        latest_shared_memory_at: "2026-07-20T08:00:00Z",
        latest_compilation_status: "succeeded",
        latest_compilation_at: "2026-07-20T08:01:00Z",
      },
    ]);

    renderPage();

    expect(await screen.findByText("Proposal Alpha")).toBeInTheDocument();
    expect(screen.getByText("7 shared records")).toBeInTheDocument();
    expect(screen.getByText("2 proposals awaiting review")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open Bid Wiki/i })).toHaveAttribute("href", "/projects/project-1?tab=knowledge");
    expect(listKnowledgePortfolio).toHaveBeenCalledWith(50);
  });

  it("filters already-visible portfolio rows without issuing another request", async () => {
    vi.mocked(listKnowledgePortfolio).mockResolvedValue([
      {
        project_id: "project-1",
        project_name: "Needs Review",
        active_shared_count: 1,
        proposed_shared_count: 1,
        latest_shared_memory_at: null,
        latest_compilation_status: null,
        latest_compilation_at: null,
      },
      {
        project_id: "project-2",
        project_name: "No Review Access",
        active_shared_count: 3,
        proposed_shared_count: null,
        latest_shared_memory_at: null,
        latest_compilation_status: null,
        latest_compilation_at: null,
      },
    ]);

    renderPage();
    await screen.findByText("Needs Review");
    fireEvent.click(screen.getByRole("button", { name: /Needs review/i }));

    expect(screen.getByText("Needs Review")).toBeInTheDocument();
    expect(screen.queryByText("No Review Access")).not.toBeInTheDocument();
    expect(listKnowledgePortfolio).toHaveBeenCalledTimes(1);
  });
});
