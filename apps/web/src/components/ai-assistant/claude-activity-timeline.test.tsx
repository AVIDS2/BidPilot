import { act, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi } from "vitest";
import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";
import { ClaudeActivityTimeline } from "./claude-activity-timeline";

const runningWorkflow: AssistantExecutionItem = {
  id: "workflow-running",
  kind: "workflow",
  toolName: "start_draft_section",
  status: "running",
  title: "Draft section",
  timestamp: 1,
  nodes: [
    { name: "memory_context", status: "completed" },
    { name: "section_drafter", status: "running" },
    { name: "quality_reviewer", status: "pending" },
  ],
};

describe("ClaudeActivityTimeline", () => {
  it("keeps nested detail grids mounted when collapsed and marks only running workflow nodes", () => {
    const { container } = render(<ClaudeActivityTimeline items={[runningWorkflow]} />);

    expect(screen.getByTestId("assistant-runtime-workflow-running").querySelector(".cr-runtime-timeline")).toHaveClass("is-running");
    expect(container.querySelector(".cr-runtime-node.is-running")).toBeInTheDocument();

    const detailGrid = container.querySelector(".cr-tool-grid");
    const detailGridInner = container.querySelector(".cr-tool-grid-inner");
    expect(detailGrid).toHaveClass("is-open");
    expect(detailGridInner).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Collapse activity details" }));

    expect(detailGrid).not.toHaveClass("is-open");
    expect(container.querySelector(".cr-tool-grid-inner")).toBe(detailGridInner);
  });

  it("keeps a tool detail mounted through its closing grid transition", () => {
    vi.useFakeTimers();
    const completedTool: AssistantExecutionItem = {
      id: "search-completed",
      kind: "tool",
      toolName: "search_projects",
      status: "succeeded",
      title: "Search projects",
      summary: "Found 3 projects.",
      timestamp: 1,
    };
    render(<ClaudeActivityTimeline items={[completedTool]} />);

    fireEvent.click(screen.getByRole("button", { name: "Expand activity details" }));
    fireEvent.click(screen.getByRole("button", { name: /(?:执行回合|Turn) 1/ }));
    fireEvent.click(screen.getByRole("button", { name: "Show Search projects details" }));
    expect(screen.getByText("Found 3 projects.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Hide Search projects details" }));
    expect(screen.getByText("Found 3 projects.")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(320));
    expect(screen.queryByText("Found 3 projects.")).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("renders public web search sources from the capability result", () => {
    const searchTool: AssistantExecutionItem = {
      id: "web-search-completed",
      kind: "tool",
      toolName: "web_search",
      status: "succeeded",
      title: "Web search",
      timestamp: 1,
      result: {
        query: "招标文件响应模板",
        count: 2,
        items: [
          {
            title: "公共采购招标文件指南",
            url: "https://example.com/procurement-guide",
            snippet: "用于编制招标响应的公开指南。",
          },
          {
            title: "Unsafe source",
            url: "javascript:alert(1)",
            snippet: "This must not render.",
          },
        ],
      },
    };
    render(<ClaudeActivityTimeline items={[searchTool]} />);

    fireEvent.click(screen.getByRole("button", { name: "Expand activity details" }));
    fireEvent.click(screen.getByRole("button", { name: /(?:执行回合|Turn) 1/ }));
    fireEvent.click(screen.getByRole("button", { name: /Show .*search.* details/i }));

    expect(screen.getByText("公共采购招标文件指南")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /公共采购招标文件指南/ })).toHaveAttribute(
      "href",
      "https://example.com/procurement-guide",
    );
    expect(screen.queryByText("Unsafe source")).not.toBeInTheDocument();
  });
});
