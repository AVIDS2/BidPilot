import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RuntimeSummaryCards } from "./runtime-summary";

describe("RuntimeSummaryCards", () => {
  it("renders healthy runtime summary metrics", () => {
    render(<RuntimeSummaryCards summary={{ queue_depth: 2, failed_runs: 0, draft_success_rate: 0.98 }} />);

    expect(screen.getByText("Healthy")).not.toBeNull();
    expect(screen.getByText("2")).not.toBeNull();
    expect(screen.getByText("0")).not.toBeNull();
    expect(screen.getByText("98%")).not.toBeNull();
  });

  it("renders attention-needed status for degraded metrics", () => {
    render(<RuntimeSummaryCards summary={{ queue_depth: 12, failed_runs: 1, draft_success_rate: 0.82 }} />);

    expect(screen.getByText("Attention needed")).not.toBeNull();
    expect(screen.getByText("12")).not.toBeNull();
    expect(screen.getByText("1")).not.toBeNull();
    expect(screen.getByText("82%")).not.toBeNull();
  });

  it("renders loading skeletons while summary is unavailable", () => {
    render(<RuntimeSummaryCards />);

    expect(screen.getByText("System Status")).not.toBeNull();
    expect(screen.getByLabelText("Loading runtime summary")).not.toBeNull();
  });
});
