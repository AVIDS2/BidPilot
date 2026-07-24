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
  downloadAssistantArtifact: vi.fn(),
  listRuntimeEvents: vi.fn().mockResolvedValue({ items: [] }),
  cancelRuntimeWorkflow: vi.fn(),
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
  // L2/L3 now default open (Pi/CC-style). Only click if still collapsed.
  await waitFor(() => {
    expect(
      screen.queryByRole("button", { name: "Expand activity details" }) ||
        screen.queryByRole("button", { name: "Collapse activity details" }),
    ).toBeTruthy();
  });
  const collapse = screen.queryByRole("button", {
    name: "Collapse activity details",
  });
  if (collapse) {
    expect(collapse).toHaveAttribute("aria-expanded", "true");
    return;
  }
  fireEvent.click(
    screen.getByRole("button", { name: "Expand activity details" }),
  );
  await waitFor(() => {
    expect(
      screen.getByRole("button", { name: "Collapse activity details" }),
    ).toHaveAttribute("aria-expanded", "true");
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

  it("renders the workspace variant without opening the side panel", async () => {
    render(
      <AIAssistantProvider>
        <AIAssistantPanel variant="workspace" />
      </AIAssistantProvider>,
    );

    expect(await screen.findByText("Welcome to BidPilot!")).toBeInTheDocument();
    const composer = screen.getByTestId("assistant-composer");
    expect(composer).toContainElement(
      screen.getByRole("textbox", { name: "Ask me anything..." }),
    );
    expect(screen.getByTestId("assistant-conversation-pane")).toContainElement(
      composer,
    );
  });

  it("opens the created workspace after a governed project action succeeds", async () => {
    window.history.replaceState({}, "", "/dashboard");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"demo-conversation","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"create_demo_workspace","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"create_demo_workspace","result":{"id":"demo-project-id"},"summary":"演示工作区已准备好。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"demo-conversation","state":"completed"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Create a demo workspace" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/projects/demo-project-id");
    });
    window.history.replaceState({}, "", "/");
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

  it("replays durable runtime events after an assistant stream is interrupted", async () => {
    const { listRuntimeEvents } = await import("@/lib/api");
    vi.mocked(listRuntimeEvents).mockResolvedValue({
      items: [
        {
          run_id: "runtime-replay-1",
          sequence: 3,
          type: "capability.succeeded",
          public_summary: "找到 2 个项目。",
          payload: { capability: "search_projects", count: 2 },
          schema_version: "1.0",
        },
        {
          run_id: "runtime-replay-1",
          sequence: 4,
          type: "message.completed",
          public_summary: "当前共有 2 个项目。",
          payload: {},
          schema_version: "1.0",
        },
        {
          run_id: "runtime-replay-1",
          sequence: 5,
          type: "run.completed",
          public_summary: "任务已完成。",
          payload: {},
          schema_version: "1.0",
        },
      ],
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-replay","runtime_run_id":"runtime-replay-1","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"runtime_run_id":"runtime-replay-1","runtime_sequence":2,"tool_name":"search_projects","state":"executing_tool"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Show my projects" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(listRuntimeEvents).toHaveBeenCalledWith("runtime-replay-1", 2);
    });
    expect(screen.getByText("当前共有 2 个项目。")).toBeInTheDocument();
    expect(screen.queryByText("stream interrupted")).not.toBeInTheDocument();
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

    expect(
      screen.getByPlaceholderText("Ask me anything..."),
    ).not.toBeDisabled();
  });

  it("clears an unavailable selected provider without silently retrying on the platform model", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: vi
          .fn()
          .mockResolvedValue(
            JSON.stringify({ detail: "Provider config not found" }),
          ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Show my projects" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(
      await screen.findAllByText(
        "所选模型配置已不可用，已切回平台默认模型。请确认后重新发送。",
      ),
    ).toHaveLength(2);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("requests cancellation only for a workflow that exposes its runtime bridge id", async () => {
    const { cancelRuntimeWorkflow, listRuntimeEvents } = await import(
      "@/lib/api"
    );
    vi.mocked(cancelRuntimeWorkflow).mockResolvedValue({
      id: "workflow-runtime-1",
      kind: "workflow_bridge",
      status: "cancel_requested",
      project_id: "project-1",
      conversation_id: "conversation-1",
      execution_run_id: "execution-run-1",
      engine: "langgraph_workflow",
      trace_id: "trace-1",
      parent_run_id: null,
    });
    vi.mocked(listRuntimeEvents).mockImplementation(
      () =>
        new Promise(() => {
          // Keep the durable workflow live while the cancellation affordance is exercised.
        }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"conversation-1","state":"thinking"}',
            'event: assistant.workflow_started\ndata: {"tool_name":"start_draft_section","result":{"run_id":"execution-run-1","runtime_run_id":"workflow-runtime-1"},"state":"running_workflow"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Generate the technical approach" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    const cancelButton = await screen.findByRole("button", {
      name: "Cancel workflow",
    });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(cancelRuntimeWorkflow).toHaveBeenCalledWith("workflow-runtime-1");
    });
    expect(
      screen.getByText("Cancellation requested. Stopping at a safe boundary."),
    ).toBeInTheDocument();
  });

  it("shows a safe provider recovery action when a workflow fails", async () => {
    const { listRuntimeEvents } = await import("@/lib/api");
    vi.mocked(listRuntimeEvents).mockResolvedValue({
      items: [
        {
          run_id: "workflow-provider-error",
          sequence: 1,
          type: "capability.progressed",
          public_summary: "模型服务暂时不可用，正在重试。",
          payload: {
            capability: "start_draft_section",
            node: "section_drafter",
            phase: "provider_retry",
            error_code: "provider_rate_limited",
            next_attempt: 2,
            max_attempts: 3,
          },
          schema_version: "1.0",
        },
        {
          run_id: "workflow-provider-error",
          sequence: 2,
          type: "run.failed",
          public_summary: "Workflow step could not finish.",
          payload: {
            capability: "start_draft_section",
            error_code: "provider_auth_failed",
          },
          schema_version: "1.0",
        },
      ],
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"conversation-provider-error","state":"thinking"}',
            'event: assistant.workflow_started\ndata: {"tool_name":"start_draft_section","result":{"run_id":"execution-provider-error","runtime_run_id":"workflow-provider-error"},"state":"running_workflow"}',
            'event: assistant.end\ndata: {"conversation_id":"conversation-provider-error","state":"completed"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Generate a technical approach" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(
      await screen.findByText(
        "Model service authentication failed. Check the key and permissions, then test the connection again.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Open model settings" }),
    );
    expect(window.location.pathname).toBe("/settings/providers");
    window.history.replaceState({}, "", "/");
  });

  it("opens an attachment menu from the composer", async () => {
    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));

    fireEvent.click(screen.getByRole("button", { name: "Add attachment" }));

    expect(await screen.findByText("Upload file")).toBeInTheDocument();
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
          provider_id: "openai",
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

    fireEvent.click(
      await screen.findByRole("button", { name: "Select model" }),
    );
    fireEvent.click(await screen.findByText("GPT-5.5"));
    fireEvent.click(
      screen.getByRole("button", { name: "Select reasoning effort" }),
    );
    fireEvent.click(screen.getByText("extra"));
    fireEvent.click(
      screen.getByRole("button", { name: "Select approval mode" }),
    );
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

    expect(
      await screen.findByPlaceholderText("Search conversations..."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add attachment" }));

    expect(screen.getByText("Upload file")).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText("Search conversations..."),
    ).not.toBeInTheDocument();
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
    expect(screen.getAllByText("done").length).toBeGreaterThan(0);
    // L2/L3 default open: summary detail is visible without an expand click.
    expect(
      screen.getByText("raw detail should be hidden until expanded"),
    ).toBeInTheDocument();
    expect(
      screen
        .getByText("Open page completed")
        .compareDocumentPosition(screen.getAllByText("已打开项目页。")[0]) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    await expandActivityDetails();
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
      mime_type:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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

    const fileInput = container.querySelector(
      'input[type="file"]:not([accept])',
    ) as HTMLInputElement;
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
    expect(
      firstTool.compareDocumentPosition(secondUserMessage) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("streams assistant text while tool activity is still running", async () => {
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
          'event: assistant.tool_started\ndata: {"tool_name":"search_projects","tool_call_id":"call-1","arguments":{"query":"test"},"state":"executing_tool"}',
          'event: assistant.message\ndata: {"content":"找到 test 项目。","state":"thinking"}',
        ].join("\n\n") + "\n\n",
      ),
    );

    await waitFor(() => {
      expect(screen.getByText("Search projects running")).toBeInTheDocument();
      // Streaming harness interleaves narrative with tools; text must not wait.
      expect(screen.getByText("找到 test 项目。")).toBeInTheDocument();
    });

    controller!.enqueue(
      encoder.encode(
        [
          'event: assistant.tool_succeeded\ndata: {"tool_name":"search_projects","tool_call_id":"call-1","result":{"count":1},"summary":"找到 1 个项目。","state":"completed"}',
          'event: assistant.end\ndata: {"conversation_id":"c-buffer","full_response":"找到 test 项目。"}',
        ].join("\n\n") + "\n\n",
      ),
    );
    controller!.close();

    await waitFor(() => {
      expect(screen.getByText("Search projects completed")).toBeInTheDocument();
      expect(screen.getByText("找到 test 项目。")).toBeInTheDocument();
    });
  });

  it("supports renaming a conversation from history", async () => {
    const { listChatConversations, renameChatConversation } = await import(
      "@/lib/api"
    );
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
    const { listChatConversations, renameChatConversation } = await import(
      "@/lib/api"
    );
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
    const row = screen
      .getByText("Visible rename")
      .closest("[data-conversation-row]");
    expect(row).not.toBeNull();
    fireEvent.mouseEnter(row as HTMLElement);
    fireEvent.click(screen.getByTitle("Rename conversation"));

    const input = await screen.findByLabelText("Rename conversation");
    fireEvent.change(input, { target: { value: "Renamed from button" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(renameChatConversation).toHaveBeenCalledWith(
        "c-visible-rename",
        "Renamed from button",
      );
    });
  });

  it("deletes a history conversation and refreshes the list", async () => {
    const { deleteChatConversation, listChatConversations } = await import(
      "@/lib/api"
    );
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
    const row = screen
      .getByText("Delete me")
      .closest("[data-conversation-row]");
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
    const { getChatConversationMessages, listChatConversations } = await import(
      "@/lib/api"
    );
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
    expect(
      screen.queryByPlaceholderText("Search conversations..."),
    ).not.toBeInTheDocument();
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
      expect(
        screen.getAllByText("已启动章节起草工作流，运行 ID：run-1。").length,
      ).toBeGreaterThan(0);
    });
    await expandActivityDetails();
    await waitFor(() => {
      expect(
        screen.getAllByText(
          (_content, element) =>
            element?.textContent === "Draft section · completed",
        ).length,
      ).toBeGreaterThan(0);
    });
    expect(screen.getByText("1 of 1 steps completed")).toBeInTheDocument();
  });

  it("offers authenticated downloads for Agent-generated artifacts", async () => {
    const { downloadAssistantArtifact } = await import("@/lib/api");
    vi.mocked(downloadAssistantArtifact).mockResolvedValue(undefined);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-download","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"export_deliverable","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"export_deliverable","result":{"format":"docx","status":"ready","download_path":"/export/deliverables/123e4567-e89b-12d3-a456-426614174000/docx"},"summary":"交付物已生成，可下载。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"交付物已生成，可下载。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-download","full_response":"交付物已生成，可下载。"}',
          ].join("\n\n") + "\n\n",
        ),
      }),
    );

    renderPanel();
    fireEvent.click(screen.getByText("Open assistant"));
    fireEvent.change(screen.getByPlaceholderText("Ask me anything..."), {
      target: { value: "Export the deliverable" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await expandActivityDetails();
    const downloadButton = await screen.findByRole("button", {
      name: "Download DOCX",
    });
    fireEvent.click(downloadButton);
    await waitFor(() => {
      expect(downloadAssistantArtifact).toHaveBeenCalledWith(
        "/export/deliverables/123e4567-e89b-12d3-a456-426614174000/docx",
        "bidpilot-docx.docx",
      );
    });
  });
});
