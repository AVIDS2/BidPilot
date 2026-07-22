import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  listRuntimeRuns: vi.fn(),
  listRuntimeEvents: vi.fn(),
}));

import { listRuntimeEvents, listRuntimeRuns } from "@/lib/api";
import { RunCenterPage } from "./run-center-page";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RunCenterPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RunCenterPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders safe aggregate run data and replays only public event summaries", async () => {
    vi.mocked(listRuntimeRuns).mockResolvedValue([
      {
        id: "run-1",
        kind: "assistant_turn",
        status: "awaiting_approval",
        project_id: "project-1",
        project_name: "Proposal Alpha",
        engine: "langgraph_operator",
        created_at: "2026-07-20T08:00:00Z",
        started_at: "2026-07-20T08:00:00Z",
        finished_at: null,
        latest_event_summary: "Waiting for approval to create a project.",
      },
    ]);
    vi.mocked(listRuntimeEvents).mockResolvedValue({
      items: [
        {
          run_id: "run-1",
          sequence: 1,
          type: "plan.proposed",
          public_summary: "Prepared a governed plan.",
          payload: { private_trace: "must-not-render" },
          schema_version: "1.0",
        },
      ],
    });

    renderPage();

    expect(await screen.findByText("Proposal Alpha")).toBeInTheDocument();
    await screen.findAllByText("Agent task");
    expect(screen.getAllByText("Agent task").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Open project/i })).toHaveAttribute("href", "/projects/project-1?tab=runs");
    expect(await screen.findByText("Prepared a governed plan.")).toBeInTheDocument();
    expect(screen.queryByText("must-not-render")).not.toBeInTheDocument();
    await waitFor(() => expect(listRuntimeEvents).toHaveBeenCalledWith("run-1"));
  });

  it("filters the visible rows without creating a second data request", async () => {
    vi.mocked(listRuntimeRuns).mockResolvedValue([
      {
        id: "run-1",
        kind: "assistant_turn",
        status: "succeeded",
        project_id: null,
        project_name: null,
        engine: "deterministic",
        created_at: "2026-07-20T08:00:00Z",
        started_at: "2026-07-20T08:00:00Z",
        finished_at: "2026-07-20T08:01:00Z",
        latest_event_summary: "Completed.",
      },
    ]);
    vi.mocked(listRuntimeEvents).mockResolvedValue({ items: [] });

    renderPage();

    await screen.findAllByText("Agent task");
    fireEvent.click(screen.getByRole("button", { name: /Needs attention/i }));

    expect(await screen.findByText("No visible runs yet")).toBeInTheDocument();
    expect(listRuntimeRuns).toHaveBeenCalledTimes(1);
  });
});
