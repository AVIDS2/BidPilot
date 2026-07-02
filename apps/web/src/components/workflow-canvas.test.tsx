import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AgentNode } from "./agent-status-stream";
import { WorkflowCanvas } from "./workflow-canvas";

vi.mock("@xyflow/react", async () => {
  const actual = await vi.importActual<typeof import("@xyflow/react")>("@xyflow/react");
  return {
    ...actual,
    ReactFlow: ({
      nodes,
      edges,
    }: {
      nodes: Array<{ id: string; data: { label: string; status: string; statusLabel?: string } }>;
      edges: Array<{ id: string; animated?: boolean; className?: string }>;
    }) => (
      <div data-testid="workflow-canvas">
        <div data-testid="workflow-node-count">{nodes.length}</div>
        <div data-testid="workflow-edge-count">{edges.length}</div>
        {nodes.map((node) => (
          <div
            key={node.id}
            data-testid={`workflow-node-${node.id}`}
            data-status={node.data.status}
            data-status-label={node.data.statusLabel}
          >
            {node.data.label}
            {node.data.statusLabel && <span>{node.data.statusLabel}</span>}
          </div>
        ))}
        {edges.map((edge) => (
          <div
            key={edge.id}
            data-testid={`workflow-edge-${edge.id}`}
            data-animated={String(Boolean(edge.animated))}
            data-class-name={edge.className ?? ""}
          />
        ))}
      </div>
    ),
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    Handle: () => null,
  };
});

describe("WorkflowCanvas", () => {
  it("renders the BidPilot workflow as a React Flow canvas with live node status", () => {
    const nodes: AgentNode[] = [
      { name: "supervisor", status: "completed" },
      { name: "knowledge_retriever", status: "running" },
    ];

    render(<WorkflowCanvas nodes={nodes} currentNode="knowledge_retriever" />);

    expect(screen.getByTestId("workflow-canvas")).toBeTruthy();
    expect(screen.getByTestId("workflow-node-count").textContent).toBe("7");
    expect(screen.getByTestId("workflow-edge-count").textContent).toBe("6");
    expect(screen.getByText("调度规划")).toBeTruthy();
    expect(screen.getByTestId("workflow-node-knowledge_retriever").textContent).toContain("检索证据");
    expect(screen.getByTestId("workflow-node-supervisor").getAttribute("data-status")).toBe("completed");
    expect(screen.getByTestId("workflow-node-supervisor").getAttribute("data-status-label")).toBe("已完成");
    expect(screen.getByTestId("workflow-node-knowledge_retriever").getAttribute("data-status")).toBe("running");
    expect(screen.getByTestId("workflow-node-knowledge_retriever").getAttribute("data-status-label")).toBe("运行中");
    expect(screen.getByTestId("workflow-edge-rfp_parser-knowledge_retriever").getAttribute("data-animated")).toBe("true");
    expect(screen.getByTestId("workflow-edge-rfp_parser-knowledge_retriever").getAttribute("data-class-name")).toContain(
      "workflow-edge-active",
    );
  });

  it("highlights the human approval node when the run is waiting for approval", () => {
    const nodes: AgentNode[] = [
      { name: "supervisor", status: "completed" },
      { name: "quality_reviewer", status: "completed" },
    ];

    render(<WorkflowCanvas nodes={nodes} currentNode={null} isWaitingApproval />);

    const approvalNode = screen
      .getAllByTestId("workflow-node-human_approval")
      .find((node) => node.getAttribute("data-status-label") === "等待确认");

    expect(approvalNode?.getAttribute("data-status")).toBe("running");
    expect(approvalNode?.getAttribute("data-status-label")).toBe("等待确认");
  });
});
