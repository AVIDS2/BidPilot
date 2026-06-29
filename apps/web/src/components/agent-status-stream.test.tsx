import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAgentStream } from "./agent-status-stream";

type EventCallback = (event: MessageEvent<string>) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];

  listeners = new Map<string, EventCallback[]>();
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  closed = false;

  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, callback: EventCallback) {
    const callbacks = this.listeners.get(event) ?? [];
    callbacks.push(callback);
    this.listeners.set(event, callbacks);
  }

  close() {
    this.closed = true;
  }

  emit(event: string, data: unknown) {
    const payload = new MessageEvent(event, { data: JSON.stringify(data) });
    this.listeners.get(event)?.forEach((callback) => callback(payload));
  }
}

describe("useAgentStream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    MockEventSource.instances = [];
  });

  it("tracks backend node_started and node_completed events", async () => {
    vi.stubGlobal("EventSource", MockEventSource);

    const { result, unmount } = renderHook(() => useAgentStream("run-1"));
    const source = MockEventSource.instances[0];

    act(() => {
      source.onopen?.();
      source.emit("node_started", {
        node_name: "knowledge_retriever",
        timestamp: "2026-06-29T10:00:00Z",
      });
    });

    await waitFor(() => {
      expect(result.current.currentNode).toBe("knowledge_retriever");
      expect(result.current.nodes[0]).toMatchObject({
        name: "knowledge_retriever",
        status: "running",
      });
    });

    act(() => {
      source.emit("node_completed", {
        node_name: "knowledge_retriever",
        result_summary: "Retrieved 3 evidence chunks",
        timestamp: "2026-06-29T10:00:03Z",
      });
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
    expect(source.closed).toBe(true);
  });
});
