import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { AIAssistantProvider, useAIAssistant } from "@/lib/ai-assistant-store";
import { AIAssistantPanel } from "./AIAssistantPanel";

vi.mock("@/lib/api", () => ({
  listChatConversations: vi.fn().mockResolvedValue([]),
  getChatConversationMessages: vi.fn(),
  renameChatConversation: vi.fn(),
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
});
