import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import type { AIAssistantState } from "@/features/agent/state/agent-store";
import { ClaudeAgentThread } from "./claude-agent-thread";

vi.mock("@/components/ui/message", () => ({
  MessageContent: ({ children }: { children: ReactNode }) => (
    <div data-testid="assistant-narrative">{children}</div>
  ),
}));

vi.mock("@/features/agent/components/claude-activity-timeline", () => ({
  ClaudeActivityTimeline: ({ items, taskTitle }: { items: Array<{ toolName?: string }>; taskTitle?: string }) => (
    <div data-testid="assistant-timeline">
      {taskTitle ? `${taskTitle}: ` : ""}{items.map((item) => item.toolName).join(",")}
    </div>
  ),
}));

function createState(): AIAssistantState {
  return {
    isOpen: true,
    mode: "panel",
    currentConversationId: "conversation-1",
    conversations: [],
    messages: [
      {
        id: "user-1",
        role: "user",
        content: "帮我核对投标材料",
        timestamp: 1,
      },
      {
        id: "assistant-1",
        role: "assistant",
        // The durable transcript is authoritative for interleaving. The final
        // assembled content must not be rendered again after its narrative parts.
        content: "我已找到可引用的证据。",
        timestamp: 2,
        transcriptParts: [
          { id: "narrative-1", kind: "narrative", text: "我先检索项目资料。", timestamp: 2 },
          { id: "turn-1", kind: "turn", turnId: "turn-search", timestamp: 3 },
          { id: "narrative-2", kind: "narrative", text: "我已找到可引用的证据。", timestamp: 4 },
        ],
      },
    ],
    activeAssistantMessageId: null,
    assistantContentBuffers: {},
    isStreaming: false,
    status: "completed",
    executionItems: [
      {
        id: "execution-1",
        messageId: "assistant-1",
        turnId: "turn-search",
        kind: "tool",
        toolName: "search_projects",
        status: "succeeded",
        title: "搜索项目",
        timestamp: 3,
      },
    ],
    pendingConfirmation: null,
    pendingInput: null,
    sessionError: null,
    selectedProviderConfigId: null,
    reasoningEffort: "medium",
    approvalMode: "full_access",
    currentContext: { page: "agent" },
    suggestions: [],
    commands: [],
  };
}

describe("ClaudeAgentThread", () => {
  it("renders the durable SSE transcript in narrative/tool/narrative order without a duplicate final answer", () => {
    const { container } = render(
      <ClaudeAgentThread
        state={createState()}
        onCancelWorkflow={vi.fn().mockResolvedValue(undefined)}
        onConfigureProvider={vi.fn()}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
      />,
    );

    expect(screen.getByText("帮我核对投标材料")).toBeInTheDocument();
    const orderedBlocks = Array.from(
      container.querySelector(".cr-agent-message")?.children ?? [],
    )
      .map((node) => node.textContent)
      .filter((text): text is string => Boolean(text));

    expect(orderedBlocks).toEqual([
      "我先检索项目资料。",
      "search_projects",
      "我已找到可引用的证据。",
    ]);
    expect(screen.getAllByText("我已找到可引用的证据。")).toHaveLength(1);
  });

  it("waits until the assistant stream ends before exposing the copy action", () => {
    const state = createState();
    state.isStreaming = true;
    state.activeAssistantMessageId = "assistant-1";
    const { rerender } = render(
      <ClaudeAgentThread
        state={state}
        onCancelWorkflow={vi.fn().mockResolvedValue(undefined)}
        onConfigureProvider={vi.fn()}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
      />,
    );

    expect(screen.queryByTitle("Copy")).not.toBeInTheDocument();

    rerender(
      <ClaudeAgentThread
        state={{ ...state, isStreaming: false, activeAssistantMessageId: null }}
        onCancelWorkflow={vi.fn().mockResolvedValue(undefined)}
        onConfigureProvider={vi.fn()}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
      />,
    );

    expect(screen.getByTitle("Copy")).toBeInTheDocument();
  });

  it("keeps a durable reply visible after history replay adds a trace", () => {
    const state = createState();
    state.messages[1] = {
      ...state.messages[1],
      transcriptParts: [{ id: "turn-only", kind: "turn", turnId: "turn-search", timestamp: 3 }],
    };

    render(
      <ClaudeAgentThread
        state={state}
        onCancelWorkflow={vi.fn().mockResolvedValue(undefined)}
        onConfigureProvider={vi.fn()}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
      />,
    );

    expect(screen.getByText("我已找到可引用的证据。")).toBeInTheDocument();
    expect(screen.getByTestId("assistant-timeline")).toBeInTheDocument();
  });

  it("uses a titled public narration once as its tool-turn title", () => {
    const state = createState();
    state.messages[1] = {
      ...state.messages[1],
      content: "",
      transcriptParts: [
        {
          id: "reasoning-1",
          kind: "reasoning",
          text: "先确认项目范围，再读取大纲。",
          title: "先确认项目范围，再读取大纲。",
          source: "harness",
          turnId: "turn-search",
          completed: true,
          timestamp: 2,
        },
        { id: "turn-1", kind: "turn", turnId: "turn-search", timestamp: 3 },
      ],
    };

    render(
      <ClaudeAgentThread
        state={state}
        onCancelWorkflow={vi.fn().mockResolvedValue(undefined)}
        onConfigureProvider={vi.fn()}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
      />,
    );

    expect(screen.getAllByText(/先确认项目范围，再读取大纲。/)).toHaveLength(1);
  });

  it("renders report, execution group, report, execution group in event order", () => {
    const state = createState();
    state.messages[1] = {
      ...state.messages[1],
      content: "",
      transcriptParts: [
        {
          id: "task-title",
          kind: "reasoning",
          text: "招标机会调研",
          title: "招标机会调研",
          source: "harness",
          turnId: "turn-search-1",
          completed: true,
          timestamp: 2,
        },
        { id: "group-1", kind: "turn", turnId: "turn-search", executionGroupId: "group-1", timestamp: 3 },
        { id: "progress-report", kind: "narrative", text: "第一批来源已核对，继续检查公告。", timestamp: 4 },
        { id: "group-2", kind: "turn", turnId: "turn-search", executionGroupId: "group-2", timestamp: 5 },
      ],
    };
    state.executionItems = [
      { ...state.executionItems[0], id: "search-1", turnId: "turn-search", executionGroupId: "group-1", toolName: "first_search" },
      { ...state.executionItems[0], id: "search-2", turnId: "turn-search", executionGroupId: "group-2", toolName: "second_search" },
    ];

    render(
      <ClaudeAgentThread
        state={state}
        onCancelWorkflow={vi.fn().mockResolvedValue(undefined)}
        onConfigureProvider={vi.fn()}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
      />,
    );

    const blocks = screen.getByLabelText("任务执行轨迹").children;
    expect(screen.getAllByTestId("assistant-timeline")).toHaveLength(2);
    expect(Array.from(blocks).map((node) => node.textContent).filter(Boolean)).toEqual([
      "first_search,second_search",
      "第一批来源已核对，继续检查公告。",
      "first_search,second_search",
    ]);
  });

  it("keeps a visible live indicator after narration while the next event is pending", () => {
    const state = createState();
    state.isStreaming = true;
    state.activeAssistantMessageId = "assistant-1";
    state.executionItems = [];

    render(
      <ClaudeAgentThread
        state={state}
        onCancelWorkflow={vi.fn().mockResolvedValue(undefined)}
        onConfigureProvider={vi.fn()}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("正在思考")).toBeInTheDocument();
  });

  it("sends user retry through the durable checkpoint action", () => {
    const onRetryFromCheckpoint = vi.fn();
    const state = createState();
    state.messages[0] = { ...state.messages[0], durableId: "message-checkpoint" };

    render(
      <ClaudeAgentThread
        state={state}
        onCancelWorkflow={vi.fn().mockResolvedValue(undefined)}
        onConfigureProvider={vi.fn()}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
        onRetryFromCheckpoint={onRetryFromCheckpoint}
      />,
    );

    fireEvent.click(screen.getByTitle("从此处重新执行"));
    expect(onRetryFromCheckpoint).toHaveBeenCalledWith("message-checkpoint", "帮我核对投标材料");
  });
});
