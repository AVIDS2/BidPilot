import { act, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
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

function renderTimeline(items: AssistantExecutionItem[]) {
  return render(
    <MemoryRouter>
      <ClaudeActivityTimeline items={items} />
    </MemoryRouter>,
  );
}

describe("ClaudeActivityTimeline", () => {
  it("keeps nested detail grids mounted when collapsed and marks only running workflow nodes", () => {
    const { container } = renderTimeline([runningWorkflow]);

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
    const { container } = renderTimeline([completedTool]);

    fireEvent.click(screen.getByRole("button", { name: "Expand activity details" }));
    fireEvent.click(screen.getByRole("button", { name: /(?:执行回合|Turn) 1/ }));
    fireEvent.click(screen.getByRole("button", { name: "Show Search projects details" }));
    expect(container.querySelector(".cr-public-summary")).toHaveTextContent("Found 3 projects.");

    fireEvent.click(screen.getByRole("button", { name: "Hide Search projects details" }));
    expect(container.querySelector(".cr-public-summary")).toHaveTextContent("Found 3 projects.");

    act(() => vi.advanceTimersByTime(320));
    expect(container.querySelector(".cr-public-summary")).not.toBeInTheDocument();
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
    renderTimeline([searchTool]);

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

  it("shows concrete export facts and real project actions instead of a generic completion line", () => {
    const exportTool: AssistantExecutionItem = {
      id: "export-completed",
      kind: "tool",
      toolName: "export_deliverable",
      status: "succeeded",
      title: "导出交付物",
      summary: "交付物「技术响应文件」导出已就绪，可直接下载或打开交付页。",
      timestamp: 1,
      runtimeRunId: "runtime-export-1",
      result: {
        project_id: "project-1",
        deliverable_id: "deliverable-1",
        deliverable_title: "技术响应文件",
        format: "docx",
        status: "ready",
        download_path: "/exports/export-1/docx",
      },
    };
    renderTimeline([exportTool]);

    fireEvent.click(screen.getByRole("button", { name: "Expand activity details" }));
    fireEvent.click(screen.getByRole("button", { name: /(?:执行回合|Turn) 1/ }));
    fireEvent.click(screen.getByRole("button", { name: /Show .*deliverable details/i }));

    expect(screen.getAllByText("技术响应文件")).toHaveLength(2);
    expect(screen.getByText("文件已生成")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download DOCX/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看交付物" })).toBeInTheDocument();
    expect(screen.getByText("运行记录")).toBeInTheDocument();
  });

  it("shows a concrete failure message and stable error code", () => {
    const failedTool: AssistantExecutionItem = {
      id: "failed-download",
      kind: "tool",
      toolName: "fetch_url_to_project",
      status: "failed",
      title: "导入远程资料",
      timestamp: 1,
      errorMessage: "远程服务器拒绝了附件下载请求。",
      errorCode: "remote_download_forbidden",
    };
    renderTimeline([failedTool]);

    expect(screen.getByText("远程服务器拒绝了附件下载请求。")).toBeInTheDocument();
    expect(screen.getByText("错误代码：remote_download_forbidden")).toBeInTheDocument();
  });

  it("links a section workflow to the project orchestration canvas", () => {
    const workflow: AssistantExecutionItem = {
      ...runningWorkflow,
      id: "workflow-with-project",
      status: "succeeded",
      result: {
        project_id: "project-1",
        section_key: "technical-approach",
      },
    };
    renderTimeline([workflow]);

    fireEvent.click(screen.getByRole("button", { name: "Expand activity details" }));
    fireEvent.click(screen.getByRole("button", { name: /(?:执行回合|Turn) 1/ }));
    fireEvent.click(screen.getByRole("button", { name: /Show .*section.* details/i }));

    expect(screen.getByRole("button", { name: "查看任务编排" })).toBeInTheDocument();
  });

  it("renders a model-proposed canvas action as an explicit click target", () => {
    const openCanvas: AssistantExecutionItem = {
      id: "open-workflow-canvas",
      kind: "tool",
      toolName: "open_page",
      status: "succeeded",
      title: "打开页面",
      summary: "已准备好任务编排画布入口，请点击打开。",
      timestamp: 1,
      result: {
        route: "/projects/project-1?surface=workflow",
        ui_action: {
          type: "canvas",
          label: "打开任务编排画布",
          route: "/projects/project-1?surface=workflow",
        },
      },
    };
    renderTimeline([openCanvas]);

    fireEvent.click(screen.getByRole("button", { name: "Expand activity details" }));
    fireEvent.click(screen.getByRole("button", { name: /(?:执行回合|Turn) 1/ }));
    fireEvent.click(screen.getByRole("button", { name: /Show .*page details/i }));

    expect(screen.getByRole("button", { name: "打开任务编排画布" })).toBeInTheDocument();
  });
});
