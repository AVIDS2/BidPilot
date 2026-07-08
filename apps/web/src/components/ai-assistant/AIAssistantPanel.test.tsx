import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { AIAssistantProvider, useAIAssistant } from "@/lib/ai-assistant-store";
import { AIAssistantPanel } from "./AIAssistantPanel";

vi.mock("@/lib/api", () => ({
  listChatConversations: vi.fn().mockResolvedValue([]),
  listProviderConfigs: vi.fn().mockResolvedValue({ data: [] }),
  getChatConversationMessages: vi.fn(),
  renameChatConversation: vi.fn(),
  deleteChatConversation: vi.fn(),
  listBundles: vi.fn().mockResolvedValue([]),
  createBundle: vi.fn(),
  uploadDocument: vi.fn(),
  uploadAssistantAttachment: vi.fn(),
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

async function expandActivityDetails() {
  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Expand activity details" })).toHaveAttribute("aria-expanded", "false");
  });
  fireEvent.click(screen.getByRole("button", { name: "Expand activity details" }));
  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Collapse activity details" })).toHaveAttribute("aria-expanded", "true");
  });
}

describe("AIAssistantPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
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

  it("sends selected model config and reasoning effort with assistant requests", async () => {
    const { listProviderConfigs } = await import("@/lib/api");
    vi.mocked(listProviderConfigs).mockResolvedValue({
      data: [
        {
          id: "provider-1",
          user_id: "u1",
          provider_type: "openai",
          api_key: "sk-****",
          api_url: "https://api.example.com/v1",
          model: "gpt-5.5",
          label: "GPT-5.5",
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
    });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: streamFrom(
        [
          'event: assistant.start\ndata: {"conversation_id":"c-model","state":"thinking"}',
          'event: assistant.message\ndata: {"content":"ok","state":"completed"}',
          'event: assistant.end\ndata: {"conversation_id":"c-model","full_response":"ok"}',
        ].join("\n\n") + "\n\n",
      ),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));

    fireEvent.click(await screen.findByRole("button", { name: "Select model" }));
    fireEvent.click(await screen.findByText("GPT-5.5"));
    fireEvent.click(screen.getByRole("button", { name: "Select reasoning effort" }));
    fireEvent.click(screen.getByText("extra"));
    fireEvent.click(screen.getByRole("button", { name: "Select approval mode" }));
    fireEvent.click(screen.getByText("Request approval"));

    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Use my selected model" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const requestBody = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(requestBody.provider_config_id).toBe("provider-1");
    expect(requestBody.reasoning_effort).toBe("extra");
    expect(requestBody.approval_mode).toBe("request_approval");
  });

  it("closes history before opening the attachment menu", async () => {
    const { listChatConversations } = await import("@/lib/api");
    vi.mocked(listChatConversations).mockResolvedValue([
      {
        id: "c-menu",
        project_id: null,
        title: "Menu overlap check",
        created_at: new Date().toISOString(),
      },
    ]);

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.click(screen.getByTitle("Conversation history"));

    expect(await screen.findByPlaceholderText("Search conversations...")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add attachment" }));

    expect(screen.getByText("Upload file")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Search conversations...")).not.toBeInTheDocument();
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
    expect(screen.getByText("Open page completed")).toBeInTheDocument();
    expect(screen.getByText("done")).toBeInTheDocument();
    expect(screen.queryByText("raw detail should be hidden until expanded")).not.toBeInTheDocument();
    expect(
      screen.getByText("Open page completed").compareDocumentPosition(screen.getByText("已打开项目页。")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    await expandActivityDetails();

    await waitFor(() => {
      expect(screen.getByText("raw detail should be hidden until expanded")).toBeInTheDocument();
    });
  });

  it("sanitizes raw tool payloads from activity details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c6","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"search_projects","arguments":{"query":"test"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"search_projects","result":{"projects":[{"id":"p1","name":"test"}],"count":1},"summary":"content=\'{\\"projects\\":[{\\"id\\":\\"p1\\"}]}\' name=\'search_projects\' tool_call_id=\'call_123\'","state":"completed"}',
            'event: assistant.message\ndata: {"content":"找到 1 个项目。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c6","full_response":"找到 1 个项目。"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Search test projects" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("找到 1 个项目。")).toBeInTheDocument();
    });

    await expandActivityDetails();

    expect(screen.getByText("Search projects")).toBeInTheDocument();
    expect(screen.getByText("Returned 1 results")).toBeInTheDocument();
    expect(screen.queryByText(/tool_call_id/)).not.toBeInTheDocument();
    expect(screen.queryByText(/content='/)).not.toBeInTheDocument();
  });

  it("renders platform tool names as user-facing labels", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-tools","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"get_project_summary","arguments":{"project_id":"p1"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"get_project_summary","result":{"name":"test","status":"active"},"summary":"项目 test 当前为 active。","state":"completed"}',
            'event: assistant.tool_started\ndata: {"tool_name":"list_project_bundles","arguments":{"project_id":"p1"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"list_project_bundles","result":{"bundles":[],"count":0},"summary":"暂无资料包。","state":"completed"}',
            'event: assistant.tool_started\ndata: {"tool_name":"list_deliverables","arguments":{"project_id":"p1"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"list_deliverables","result":{"deliverables":[],"count":0},"summary":"暂无交付物。","state":"completed"}',
            'event: assistant.tool_started\ndata: {"tool_name":"list_sections","arguments":{"project_id":"p1"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"list_sections","result":{"sections":[],"count":0},"summary":"暂无章节。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"我查看了项目概况。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-tools","full_response":"我查看了项目概况。"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "查看项目状态" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("我查看了项目概况。")).toBeInTheDocument();
    });

    await expandActivityDetails();

    expect(screen.getByText("Read project overview")).toBeInTheDocument();
    expect(screen.getByText("Check material bundles")).toBeInTheDocument();
    expect(screen.getByText("Check deliverables")).toBeInTheDocument();
    expect(screen.getByText("Check sections")).toBeInTheDocument();
    expect(screen.queryByText("get_project_summary")).not.toBeInTheDocument();
    expect(screen.queryByText("list_project_bundles")).not.toBeInTheDocument();
    expect(screen.queryByText("list_deliverables")).not.toBeInTheDocument();
    expect(screen.queryByText("list_sections")).not.toBeInTheDocument();
  });

  it("renders user attachments without leaking backend attachment context", async () => {
    const { uploadAssistantAttachment } = await import("@/lib/api");
    vi.mocked(uploadAssistantAttachment).mockResolvedValue({
      id: "att-1",
      name: "proposal.docx",
      kind: "file",
      mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      size: 5,
      extraction_status: "extracted",
      extracted_text: "",
    });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: streamFrom(
        [
          'event: assistant.start\ndata: {"conversation_id":"c7","state":"thinking"}',
          'event: assistant.message\ndata: {"content":"我会参考这个文件。","state":"completed"}',
          'event: assistant.end\ndata: {"conversation_id":"c7","full_response":"我会参考这个文件。"}',
        ].join("\n\n") + "\n\n",
      ),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.click(screen.getByRole("button", { name: "Add attachment" }));

    const fileInput = container.querySelector('input[type="file"]:not([accept])') as HTMLInputElement;
    const file = new File(["hello"], "proposal.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => {
      expect(uploadAssistantAttachment).toHaveBeenCalledWith(file, "file");
      expect(screen.getByText("proposal.docx")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "请分析这个文档" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    expect(screen.getByText("请分析这个文档")).toBeInTheDocument();
    expect(screen.queryByText(/附件上下文/)).not.toBeInTheDocument();
    const requestBody = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(requestBody.message).toBe("请分析这个文档");
    expect(requestBody.message).not.toContain("selected locally");
    expect(requestBody.attachments).toEqual([
      expect.objectContaining({
        id: "att-1",
        name: "proposal.docx",
        kind: "file",
        extraction_status: "extracted",
      }),
    ]);
    expect(requestBody.attachments[0].extracted_text).toBe("");
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
      expect(screen.getByText("Open page completed")).toBeInTheDocument();
    });

    fireEvent.change(input, { target: { value: "Search Acme projects" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("第二轮完成。")).toBeInTheDocument();
      expect(screen.getByText("Search projects completed")).toBeInTheDocument();
    });

    const firstTool = screen.getAllByText("Open page completed")[0];
    const secondUserMessage = screen.getByText("Search Acme projects");
    expect(firstTool.compareDocumentPosition(secondUserMessage) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("buffers assistant text until running tool activity finishes", async () => {
    let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
    const encoder = new TextEncoder();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: new ReadableStream({
          start(streamController) {
            controller = streamController;
          },
        }),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Search projects before answering" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(controller).not.toBeNull();
    });

    controller!.enqueue(
      encoder.encode(
        [
          'event: assistant.start\ndata: {"conversation_id":"c-buffer","state":"thinking"}',
          'event: assistant.tool_started\ndata: {"tool_name":"search_projects","arguments":{"query":"test"},"state":"executing_tool"}',
          'event: assistant.message\ndata: {"content":"找到 test 项目。","state":"completed"}',
        ].join("\n\n") + "\n\n",
      ),
    );

    await waitFor(() => {
      expect(screen.getByText("Search projects running")).toBeInTheDocument();
    });
    expect(screen.queryByText("找到 test 项目。")).not.toBeInTheDocument();

    controller!.enqueue(
      encoder.encode(
        [
          'event: assistant.tool_succeeded\ndata: {"tool_name":"search_projects","result":{"count":1},"summary":"找到 1 个项目。","state":"completed"}',
          'event: assistant.end\ndata: {"conversation_id":"c-buffer","full_response":"找到 test 项目。"}',
        ].join("\n\n") + "\n\n",
      ),
    );
    controller!.close();

    await waitFor(() => {
      expect(screen.getByText("找到 test 项目。")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Search projects completed").compareDocumentPosition(screen.getByText("找到 test 项目。")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
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

  it("exposes a visible rename action for history conversations", async () => {
    const { listChatConversations, renameChatConversation } = await import("@/lib/api");
    vi.mocked(listChatConversations).mockResolvedValue([
      {
        id: "c-visible-rename",
        project_id: null,
        title: "Visible rename",
        created_at: new Date().toISOString(),
      },
    ]);
    vi.mocked(renameChatConversation).mockResolvedValue({
      id: "c-visible-rename",
      project_id: null,
      title: "Renamed from button",
      created_at: new Date().toISOString(),
    });

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.click(screen.getByTitle("Conversation history"));

    await screen.findByText("Visible rename");
    const row = screen.getByText("Visible rename").closest("[data-conversation-row]");
    expect(row).not.toBeNull();
    fireEvent.mouseEnter(row as HTMLElement);
    fireEvent.click(screen.getByTitle("Rename conversation"));

    const input = await screen.findByLabelText("Rename conversation");
    fireEvent.change(input, { target: { value: "Renamed from button" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(renameChatConversation).toHaveBeenCalledWith("c-visible-rename", "Renamed from button");
    });
  });

  it("deletes a history conversation and refreshes the list", async () => {
    const { deleteChatConversation, listChatConversations } = await import("@/lib/api");
    vi.mocked(listChatConversations)
      .mockResolvedValueOnce([
        {
          id: "c-delete",
          project_id: null,
          title: "Delete me",
          created_at: new Date().toISOString(),
        },
      ])
      .mockResolvedValueOnce([]);
    vi.mocked(deleteChatConversation).mockResolvedValue(undefined);

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.click(screen.getByTitle("Conversation history"));

    await screen.findByText("Delete me");
    const row = screen.getByText("Delete me").closest("[data-conversation-row]");
    expect(row).not.toBeNull();
    fireEvent.mouseEnter(row as HTMLElement);
    fireEvent.click(screen.getByTitle("Delete conversation"));

    await waitFor(() => {
      expect(deleteChatConversation).toHaveBeenCalledWith("c-delete");
      expect(listChatConversations).toHaveBeenCalledTimes(2);
    });
    expect(screen.queryByText("Delete me")).not.toBeInTheDocument();
  });

  it("switches the active conversation immediately while messages load", async () => {
    const { getChatConversationMessages, listChatConversations } = await import("@/lib/api");
    vi.mocked(listChatConversations).mockResolvedValue([
      {
        id: "c-slow",
        project_id: null,
        title: "Slow conversation",
        created_at: new Date().toISOString(),
      },
    ]);
    vi.mocked(getChatConversationMessages).mockImplementation(
      () =>
        new Promise(() => {
          // Keep the request pending to prove the active title updates optimistically.
        }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.click(screen.getByTitle("Conversation history"));

    fireEvent.click(await screen.findByText("Slow conversation"));

    await waitFor(() => {
      expect(screen.getByText("Slow conversation")).toBeInTheDocument();
    });
    expect(screen.queryByPlaceholderText("Search conversations...")).not.toBeInTheDocument();
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
      expect(screen.getByText("已启动章节起草工作流，运行 ID：run-1。")).toBeInTheDocument();
    });
    await expandActivityDetails();
    await waitFor(() => {
      expect(screen.getAllByText((_content, element) => element?.textContent === "Draft section · completed").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("1 of 1 steps completed")).toBeInTheDocument();
  });
});

