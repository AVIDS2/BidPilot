import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi } from "vitest";
import { AgentEnvironmentPanel } from "./agent-environment-panel";

vi.mock("@/lib/api", () => ({
  getPiRuntimeContract: vi.fn().mockResolvedValue({
    data: {
      version: "1",
      sandbox: { profile: "governed_cloud", hostTools: "disabled", network: "bridge_only", maxToolInputBytes: 131072, maxToolObservationBytes: 524288 },
      extensions: ["bidpilot-governance", "bidpilot-skills", "bidpilot-subagents"],
      skills: [{ name: "deep-research", description: "Research", version: "1.1.0", resources: ["references/source-quality.md"] }],
      tool_count: 44,
      parallel_tool_count: 21,
      mcp_servers: [],
    },
  }),
  listRuntimeRuns: vi.fn().mockResolvedValue([
    { id: "run-1", kind: "subagent", status: "running", project_id: "p1", project_name: "常州项目", engine: "pi_subagent_worker", created_at: "2026-08-25T12:00:00Z", started_at: "2026-08-25T12:00:00Z", finished_at: null, latest_event_summary: "正在核对官方来源" },
    { id: "run-2", kind: "deep_research", status: "awaiting_approval", project_id: "p1", project_name: "常州项目", engine: "deep_research_worker", created_at: "2026-08-25T12:01:00Z", started_at: null, finished_at: null, latest_event_summary: "等待确认研究范围" },
  ]),
}));

describe("AgentEnvironmentPanel", () => {
  it("renders live runs and the server-owned Pi resource contract", async () => {
    const onOpenRun = vi.fn();
    render(<AgentEnvironmentPanel onOpenRun={onOpenRun} />);

    expect(await screen.findByText("运行环境")).toBeInTheDocument();
    expect(screen.getByText("2 个运行中")).toBeInTheDocument();
    expect(screen.getByText("子 Agent")).toBeInTheDocument();
    expect(screen.getByText("深度调研")).toBeInTheDocument();
    expect(screen.getByText("44 工具 · 1 Skills")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /子 Agent/ }));
    expect(onOpenRun).toHaveBeenCalledWith("run-1");

    fireEvent.click(screen.getByRole("button", { name: /已注册资源/ }));
    await waitFor(() => expect(screen.getByText("deep-research")).toBeInTheDocument());
  });
});
