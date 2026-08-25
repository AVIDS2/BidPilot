import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi } from "vitest";
import { AgentEnvironmentPanel } from "./agent-environment-panel";

vi.mock("@/lib/api", () => ({
  listProjects: vi.fn().mockResolvedValue([{ id: "p1", name: "常州项目", slug: "changzhou", scenario_package: "招标响应", status: "active" }]),
  listRuntimeRuns: vi.fn().mockResolvedValue([
    { id: "run-1", kind: "subagent", status: "running", project_id: "p1", project_name: "常州项目", engine: "pi_subagent_worker", created_at: "2026-08-25T12:00:00Z", started_at: "2026-08-25T12:00:00Z", finished_at: null, latest_event_summary: "正在核对官方来源" },
    { id: "run-2", kind: "deep_research", status: "awaiting_approval", project_id: "p1", project_name: "常州项目", engine: "deep_research_worker", created_at: "2026-08-25T12:01:00Z", started_at: null, finished_at: null, latest_event_summary: "等待确认研究范围" },
  ]),
}));

describe("AgentEnvironmentPanel", () => {
  it("renders live runs and the server-owned Pi resource contract", async () => {
    const onOpenRun = vi.fn();
    render(<AgentEnvironmentPanel onOpenRun={onOpenRun} />);

    expect(await screen.findByText("工作概览")).toBeInTheDocument();
    expect(screen.getByText("正在处理")).toBeInTheDocument();
    expect(screen.getByText("子 Agent")).toBeInTheDocument();
    expect(screen.getByText("深度调研")).toBeInTheDocument();
    expect(screen.getByText("项目工作区")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /子 Agent/ }));
    expect(onOpenRun).toHaveBeenCalledWith("run-1");
  });
});
