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

function renderTimeline(
  items: AssistantExecutionItem[],
  onOpenWorkflowCanvas?: (projectId: string) => void,
) {
  return render(
    <MemoryRouter>
      <ClaudeActivityTimeline items={items} onOpenWorkflowCanvas={onOpenWorkflowCanvas} />
    </MemoryRouter>,
  );
}

describe("ClaudeActivityTimeline", () => {
  it("interpolates the aggregate status for a multi-action turn", () => {
    const secondWorkflow: AssistantExecutionItem = {
      ...runningWorkflow,
      id: "workflow-running-2",
      toolName: "get_project_summary",
      title: "Read project",
      turnId: "turn-shared",
    };
    const { container } = renderTimeline([
      { ...runningWorkflow, turnId: "turn-shared" },
      secondWorkflow,
    ]);

    expect(container.querySelector(".cr-task-turn-summary")).toHaveTextContent(/2/);
    expect(container.textContent).not.toContain("{{status}}");
  });

  it("keeps every timeline level closed until the reader opens it", () => {
    const { container, rerender } = renderTimeline([runningWorkflow]);
    const taskSummary = container.querySelector(".cr-task-turn-summary")!;

    expect(taskSummary).toHaveAttribute("aria-expanded", "false");
    expect(container.querySelector(".cr-group-status.is-running .cr-status-copy")).toBeInTheDocument();
    expect(screen.queryByTestId("assistant-runtime-workflow-running")).not.toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <ClaudeActivityTimeline items={[{ ...runningWorkflow, status: "failed" }]} />
      </MemoryRouter>,
    );
    const failedTaskSummary = container.querySelector(".cr-task-turn-summary")!;
    expect(failedTaskSummary).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(failedTaskSummary);
    const toolSummary = screen.getByRole("button", { name: /Show .*section.* details/i });
    expect(toolSummary).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(toolSummary);
    const runtime = screen.getByTestId("assistant-runtime-workflow-running");
    const runtimeSummary = runtime.querySelector(".cr-runtime-summary")!;
    expect(runtimeSummary).toHaveAttribute("aria-expanded", "false");
    expect(runtime.querySelector(".cr-runtime-status")).toBeInTheDocument();

    fireEvent.click(runtimeSummary);
    expect(runtimeSummary).toHaveAttribute("aria-expanded", "true");
    expect(runtime.querySelector(".cr-runtime-timeline")).toHaveClass("is-running");
    expect(runtime.querySelector(".cr-runtime-node.is-running")).toBeInTheDocument();
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

    fireEvent.click(container.querySelector(".cr-task-turn-summary")!);
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
    const { container } = renderTimeline([searchTool]);

    fireEvent.click(container.querySelector(".cr-task-turn-summary")!);
    fireEvent.click(screen.getByRole("button", { name: /Show .*search.* details/i }));

    expect(screen.getByText("公共采购招标文件指南")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /公共采购招标文件指南/ })).toHaveAttribute(
      "href",
      "https://example.com/procurement-guide",
    );
    expect(screen.queryByText("Unsafe source")).not.toBeInTheDocument();
    expect(screen.queryByText("2 results")).not.toBeInTheDocument();
    expect(screen.queryByText(/招标文件响应模板/)).not.toBeInTheDocument();
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
    const { container } = renderTimeline([exportTool]);

    fireEvent.click(container.querySelector(".cr-task-turn-summary")!);
    fireEvent.click(screen.getByRole("button", { name: /Show .*deliverable details/i }));

    expect(screen.getAllByText("技术响应文件")).toHaveLength(2);
    expect(screen.getByText("文件已生成，可下载或查看")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download DOCX/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看交付物" })).toBeInTheDocument();
    expect(screen.queryByText("运行记录")).not.toBeInTheDocument();
    expect(screen.queryByText("工具输入与返回")).not.toBeInTheDocument();
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
    const { container } = renderTimeline([failedTool]);

    fireEvent.click(container.querySelector(".cr-task-turn-summary")!);
    fireEvent.click(screen.getByRole("button", { name: /Show .* details/i }));

    expect(screen.getByText("远程服务器拒绝了附件下载请求。")).toBeInTheDocument();
    expect(screen.getByText("错误代码：remote_download_forbidden")).toBeInTheDocument();
  });

  it("opens a section workflow in the conversation canvas", () => {
    const workflow: AssistantExecutionItem = {
      ...runningWorkflow,
      id: "workflow-with-project",
      status: "succeeded",
      result: {
        project_id: "project-1",
        section_key: "technical-approach",
      },
    };
    const onOpenWorkflowCanvas = vi.fn();
    const { container } = renderTimeline([workflow], onOpenWorkflowCanvas);

    fireEvent.click(container.querySelector(".cr-task-turn-summary")!);
    fireEvent.click(screen.getByRole("button", { name: /Show .*section.* details/i }));

    fireEvent.click(screen.getByRole("button", { name: "打开响应工作流" }));
    expect(onOpenWorkflowCanvas).toHaveBeenCalledWith("project-1");
  });

  it("renders a model-proposed canvas action as an explicit click target", () => {
    const openCanvas: AssistantExecutionItem = {
      id: "open-workflow-canvas",
      kind: "tool",
      toolName: "open_page",
      status: "succeeded",
      title: "打开页面",
      summary: "已准备好响应工作流入口，请点击打开。",
      timestamp: 1,
      result: {
        route: "/projects/project-1?surface=workflow",
        ui_action: {
          type: "canvas",
          label: "打开响应工作流",
          route: "/projects/project-1?surface=workflow",
        },
      },
    };
    const onOpenWorkflowCanvas = vi.fn();
    const { container } = renderTimeline([openCanvas], onOpenWorkflowCanvas);

    fireEvent.click(container.querySelector(".cr-task-turn-summary")!);
    fireEvent.click(screen.getByRole("button", { name: /Show .*page details/i }));

    fireEvent.click(screen.getByRole("button", { name: "打开响应工作流" }));
    expect(onOpenWorkflowCanvas).toHaveBeenCalledWith("project-1");
  });

  it("renders child agents inside their parent run and keeps every level closed", () => {
    const parent: AssistantExecutionItem = {
      id: "spawn-agents",
      kind: "tool",
      toolName: "spawn_subagents",
      runtimeRunId: "parent-run",
      turnId: "run:parent-run",
      status: "succeeded",
      title: "委派并行调研",
      timestamp: 1,
    };
    const child: AssistantExecutionItem = {
      id: "subagent-child",
      kind: "subagent",
      toolName: "subagent",
      runtimeRunId: "child-run",
      parentRuntimeRunId: "parent-run",
      turnId: "run:child-run",
      agentProfile: "researcher",
      status: "running",
      title: "researcher 子 Agent",
      timestamp: 2,
    };
    const childTool: AssistantExecutionItem = {
      id: "subagent-search",
      kind: "tool",
      toolName: "web_search",
      toolCallId: "child-call-1",
      runtimeRunId: "child-run",
      parentRuntimeRunId: "parent-run",
      turnId: "run:child-run",
      status: "running",
      title: "联网搜索",
      timestamp: 3,
    };
    const { container } = renderTimeline([parent, child, childTool]);

    expect(container.querySelectorAll(":scope .cr-task-turns > .cr-task-turn")).toHaveLength(1);
    expect(container.querySelector(".cr-task-turn > .cr-command-grid")).not.toHaveClass("is-open");

    fireEvent.click(container.querySelector(".cr-task-turn-summary")!);
    expect(container.querySelector(".cr-task-turn > .cr-command-grid")).toHaveClass("is-open");
    expect(container.querySelector(".cr-subagent-turns")).toBeInTheDocument();
    expect(screen.getByText("researcher 子 Agent")).toBeInTheDocument();
    expect(container.querySelector(".cr-subagent-turns .cr-task-turn-summary")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });
});
