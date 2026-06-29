import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AgentNode } from "./agent-status-stream";
import { WorkflowCanvas } from "./workflow-canvas";

vi.mock("@xyflow/react", async () => {
  const actual = await vi.importActual<typeof import("@xyflow/react")>("@xyflow/react");
  return {
    ...actual,
    ReactFlow: ({ nodes, edges }: { nodes: Array<{ id: string; data: { label: string; status: string } }>; edges: Array<{ id: string }> }) => (
      <div data-testid="workflow-canvas">
        <div data-testid="workflow-node-count">{nodes.length}</div>
        <div data-testid="workflow-edge-count">{edges.length}</div>
        {nodes.map((node) => (
          <div key={node.id} data-testid={`workflow-node-${node.id}`} data-status={node.data.status}>
            {node.data.label}
          </div>
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
    expect(screen.getByText("检索证据")).toBeTruthy();
    expect(screen.getByTestId("workflow-node-supervisor").getAttribute("data-status")).toBe("completed");
    expect(screen.getByTestId("workflow-node-knowledge_retriever").getAttribute("data-status")).toBe("running");
  });
});
