import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { AIAssistantProvider, useAIAssistant } from "@/lib/ai-assistant-store";
import { AIAssistantPanel } from "./AIAssistantPanel";

vi.mock("@/lib/api", () => ({
  listChatConversations: vi.fn().mockResolvedValue([]),
  getChatConversationMessages: vi.fn(),
  renameChatConversation: vi.fn(),
  deleteChatConversation: vi.fn(),
  listBundles: vi.fn().mockResolvedValue([]),
  createBundle: vi.fn(),
  uploadDocument: vi.fn(),
}));

function streamFrom(text: string) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

function OpenPanelButton() {
  const { open } = useAIAssistant();
  return <button onClick={() => open("panel")}>Open assistant</button>;
}

function renderPanel() {
  return render(
    <AIAssistantProvider>
      <OpenPanelButton />
      <AIAssistantPanel />
    </AIAssistantProvider>,
  );
}

describe("AIAssistantPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders confirmation cards from assistant events", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c1","state":"thinking"}',
            'event: assistant.confirmation_requested\ndata: {"tool_name":"create_project","arguments":{"name":"Acme Bid","scenario_package":"bidpilot"},"message":"需要你确认：我将创建项目「Acme Bid」。"}',
            'event: assistant.message\ndata: {"content":"需要你确认：我将创建项目「Acme Bid」。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c1","full_response":"需要你确认：我将创建项目「Acme Bid」。"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Create a project named Acme Bid" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("Confirm action")).toBeInTheDocument();
    });
    expect(screen.getAllByText("create_project").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Acme Bid/).length).toBeGreaterThan(0);
  });

  it("does not render intent trace cards in the default chat flow", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c2","state":"thinking"}',
            'event: assistant.intent_detected\ndata: {"mode":"answer","tool_name":"answer"}',
            'event: assistant.message\ndata: {"content":"这是直接回答。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c2","full_response":"这是直接回答。"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "What is this?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("这是直接回答。")).toBeInTheDocument();
    });
    expect(screen.queryByText("Intent: answer")).not.toBeInTheDocument();
    expect(screen.queryByText("Intent detected")).not.toBeInTheDocument();
  });

  it("keeps the composer editable while the assistant is responding", async () => {
    const fetchMock = vi.fn().mockImplementation(
      () =>
        new Promise(() => {
          // Keep the request open so the assistant remains busy.
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));

    const input = screen.getByPlaceholderText("Ask me anything...");
    fireEvent.change(input, { target: { value: "Tell me the status" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    expect(screen.getByPlaceholderText("Ask me anything...")).not.toBeDisabled();
  });

  it("opens an attachment menu from the composer", async () => {
    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));

    fireEvent.click(screen.getByRole("button", { name: "Add attachment" }));

    expect(screen.getByText("Upload file")).toBeInTheDocument();
    expect(screen.getByText("Upload image")).toBeInTheDocument();
    expect(screen.getByText("Add from project")).toBeInTheDocument();
  });

  it("renders completed tool activity as a compact expandable event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c3","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"open_page","arguments":{"route":"/projects"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"open_page","result":{"route":"/projects"},"summary":"raw detail should be hidden until expanded","state":"completed"}',
            'event: assistant.message\ndata: {"content":"已打开项目页。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c3","full_response":"已打开项目页。"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Open projects" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getAllByText("已打开项目页。").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("open_page")).toBeInTheDocument();
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.queryByText("raw detail should be hidden until expanded")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show tool details" }));

    expect(screen.getByText("raw detail should be hidden until expanded")).toBeInTheDocument();
  });

  it("keeps tool activity attached to the assistant turn that produced it", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c5","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"open_page","arguments":{"route":"/projects"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"open_page","result":{"route":"/projects"},"summary":"已打开项目页。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"第一轮完成。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c5","full_response":"第一轮完成。"}',
          ].join("\n\n") + "\n\n",
        ),
      })
      .mockResolvedValueOnce({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c5","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"search_projects","arguments":{"query":"Acme"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"search_projects","result":{"count":1},"summary":"找到 1 个项目。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"第二轮完成。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c5","full_response":"第二轮完成。"}',
          ].join("\n\n") + "\n\n",
        ),
      });
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));

    const input = screen.getByPlaceholderText("Ask me anything...");
    fireEvent.change(input, { target: { value: "Open projects" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("第一轮完成。")).toBeInTheDocument();
      expect(screen.getByText("open_page")).toBeInTheDocument();
    });

    fireEvent.change(input, { target: { value: "Search Acme projects" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("第二轮完成。")).toBeInTheDocument();
      expect(screen.getByText("search_projects")).toBeInTheDocument();
    });

    const firstTool = screen.getByText("open_page");
    const secondUserMessage = screen.getByText("Search Acme projects");
    expect(firstTool.compareDocumentPosition(secondUserMessage) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("supports renaming a conversation from history", async () => {
    const { listChatConversations, renameChatConversation } = await import("@/lib/api");
    vi.mocked(listChatConversations).mockResolvedValue([
      {
        id: "c1",
        project_id: null,
        title: "Old title",
        created_at: new Date().toISOString(),
      },
    ]);
    vi.mocked(renameChatConversation).mockResolvedValue({
      id: "c1",
      project_id: null,
      title: "New title",
      created_at: new Date().toISOString(),
    });

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));

    await waitFor(() => {
      expect(listChatConversations).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByTitle("Conversation history"));

    await waitFor(() => {
      expect(screen.getByText("Old title")).toBeInTheDocument();
    });

    fireEvent.doubleClick(screen.getByText("Old title"));

    const input = await screen.findByLabelText("Rename conversation");
    fireEvent.change(input, { target: { value: "New title" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(renameChatConversation).toHaveBeenCalledWith("c1", "New title");
    });
  });

  it("renders LangGraph workflow progress from run stream", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/assistant/stream")) {
        return Promise.resolve({
          ok: true,
          body: streamFrom(
            [
              'event: assistant.start\ndata: {"conversation_id":"c4","state":"thinking"}',
              'event: assistant.workflow_started\ndata: {"tool_name":"start_draft_section","arguments":{"section_key":"technical-approach"},"result":{"run_id":"run-1","status":"queued"},"state":"running_workflow"}',
              'event: assistant.tool_succeeded\ndata: {"tool_name":"start_draft_section","result":{"run_id":"run-1","status":"queued"},"summary":"已启动章节起草工作流，运行 ID：run-1。","state":"completed"}',
              'event: assistant.message\ndata: {"content":"已启动章节起草工作流，运行 ID：run-1。","state":"completed"}',
              'event: assistant.end\ndata: {"conversation_id":"c4","full_response":"已启动章节起草工作流，运行 ID：run-1。"}',
            ].join("\n\n") + "\n\n",
          ),
        });
      }
      if (url.includes("/drafting/runs/run-1/stream")) {
        return Promise.resolve({
          ok: true,
          body: streamFrom(
            [
              'event: connected\ndata: {"run_id":"run-1","status":"running"}',
              'event: node_started\ndata: {"node_name":"section_drafter"}',
              'event: node_completed\ndata: {"node_name":"section_drafter","result_summary":"Draft created"}',
              'event: graph_completed\ndata: {"persisted":true,"status":"succeeded"}',
            ].join("\n\n") + "\n\n",
          ),
        });
      }
      return Promise.resolve({ ok: true, body: streamFrom("") });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Draft technical section" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("section_drafter")).toBeInTheDocument();
    });
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("1 of 1 steps completed")).toBeInTheDocument();
  });
});
