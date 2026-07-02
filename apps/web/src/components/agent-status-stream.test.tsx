import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setStoredValue } from "@/lib/browser-storage";
import { useAgentStream } from "./agent-status-stream";

function sse(events: Array<[string, Record<string, unknown>]>) {
  return `${events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}`).join("\n\n")}\n\n`;
}

function streamResponse(payload: string) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(payload));
        controller.close();
      },
    }),
    {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    },
  );
}

describe("useAgentStream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("tracks backend node_started and node_completed events", async () => {
    const encoder = new TextEncoder();
    let streamController: ReadableStreamDefaultController<Uint8Array>;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            streamController = controller;
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result, unmount } = renderHook(() => useAgentStream("run-1"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    act(() => {
      streamController.enqueue(
        encoder.encode(sse([["node_started", { node_name: "knowledge_retriever", timestamp: "2026-06-29T10:00:00Z" }]])),
      );
    });

    await waitFor(() => {
      expect(result.current.currentNode).toBe("knowledge_retriever");
      expect(result.current.nodes[0]).toMatchObject({
        name: "knowledge_retriever",
        status: "running",
      });
    });

    act(() => {
      streamController.enqueue(
        encoder.encode(
          sse([
            [
              "node_completed",
              {
                node_name: "knowledge_retriever",
                result_summary: "Retrieved 3 evidence chunks",
                timestamp: "2026-06-29T10:00:03Z",
              },
            ],
          ]),
        ),
      );
      streamController.close();
    });

    await waitFor(() => {
      expect(result.current.currentNode).toBeNull();
      expect(result.current.completedNodes).toHaveLength(1);
      expect(result.current.nodes[0]).toMatchObject({
        name: "knowledge_retriever",
        status: "completed",
      });
    });

    unmount();
  });

  it("connects with the stored auth token when streaming over fetch", async () => {
    setStoredValue("token", "test-token");
    const fetchMock = vi.fn().mockResolvedValue(
      streamResponse(
        sse([
          ["node_started", { node_name: "knowledge_retriever" }],
          ["node_completed", { node_name: "knowledge_retriever" }],
          ["graph_completed", { persisted: true }],
        ]),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useAgentStream("run-1"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/drafting/runs/run-1/stream"),
      expect.objectContaining({
        headers: { Authorization: "Bearer test-token" },
      }),
    );
    await waitFor(() => {
      expect(result.current.completedNodes).toHaveLength(1);
      expect(result.current.isRunning).toBe(false);
    });
  });
});
