import { describe, expect, it } from "vitest";
import {
  advanceRuntimeEventCursor,
  advanceRuntimeSequenceCursor,
  isRuntimeEventNewer,
  isRuntimeSequenceNewer,
  isTerminalRuntimeEvent,
  runtimeEventToAssistantEvents,
  type RuntimeEventRead,
} from "./runtime-event-feed";

function runtimeEvent(overrides: Partial<RuntimeEventRead> = {}): RuntimeEventRead {
  return {
    run_id: "runtime-1",
    sequence: 2,
    type: "capability.succeeded",
    public_summary: "找到 2 个项目。",
    payload: { capability: "search_projects", count: 2 },
    schema_version: "1.0",
    ...overrides,
  };
}

describe("runtime event feed", () => {
  it("advances a cursor only for a newer event in the same run", () => {
    const first = runtimeEvent({ sequence: 2 });
    const cursor = advanceRuntimeEventCursor({}, first);

    expect(cursor).toEqual({ "runtime-1": 2 });
    expect(isRuntimeEventNewer(cursor, runtimeEvent({ sequence: 2 }))).toBe(false);
    expect(advanceRuntimeEventCursor(cursor, runtimeEvent({ sequence: 1 }))).toBe(cursor);
    expect(advanceRuntimeEventCursor(cursor, runtimeEvent({ sequence: 3 }))).toEqual({ "runtime-1": 3 });
    expect(isRuntimeSequenceNewer(cursor, "runtime-1", 2)).toBe(false);
    expect(advanceRuntimeSequenceCursor(cursor, "runtime-1", 4)).toEqual({ "runtime-1": 4 });
  });

  it("translates a public capability result without leaking a raw tool dump", () => {
    const events = runtimeEventToAssistantEvents(runtimeEvent(), "conversation-1");

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      eventType: "assistant.tool_succeeded",
      data: {
        runtime_run_id: "runtime-1",
        runtime_sequence: 2,
        tool_name: "search_projects",
        result: { count: 2 },
        summary: "找到 2 个项目。",
        state: "completed",
      },
    });
  });

  it("marks only terminal lifecycle events as terminal", () => {
    expect(isTerminalRuntimeEvent(runtimeEvent({ type: "run.completed" }))).toBe(true);
    expect(isTerminalRuntimeEvent(runtimeEvent({ type: "run.failed" }))).toBe(true);
    expect(isTerminalRuntimeEvent(runtimeEvent({ type: "capability.started" }))).toBe(false);
  });

  it("treats an entity-relation proposal as a workflow without exposing source details", () => {
    const events = runtimeEventToAssistantEvents(
      runtimeEvent({
        payload: {
          capability: "propose_memory_graph",
          run_id: "execution-run-1",
          runtime_run_id: "workflow-run-1",
          reused: false,
        },
        public_summary: "实体关系提案已启动。",
      }),
      "conversation-1",
    );

    expect(events).toEqual([
      {
        eventType: "assistant.workflow_started",
        data: {
          runtime_run_id: "runtime-1",
          runtime_sequence: 2,
          tool_name: "propose_memory_graph",
          result: {
            run_id: "execution-run-1",
            runtime_run_id: "workflow-run-1",
            reused: false,
          },
          state: "running_workflow",
        },
      },
      {
        eventType: "assistant.tool_succeeded",
        data: {
          runtime_run_id: "runtime-1",
          runtime_sequence: 2,
          tool_name: "propose_memory_graph",
          result: {
            run_id: "execution-run-1",
            runtime_run_id: "workflow-run-1",
            reused: false,
          },
          summary: "实体关系提案已启动。",
          state: "completed",
        },
      },
    ]);
  });

  it("translates provider retry and terminal failure with stable recovery codes", () => {
    const retryEvents = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: "capability.progressed",
        public_summary: "模型服务暂时不可用，正在重试。",
        payload: {
          capability: "section_drafter",
          node: "section_drafter",
          phase: "provider_retry",
          error_code: "provider_rate_limited",
          next_attempt: 2,
          max_attempts: 3,
        },
      }),
      "conversation-1",
    );
    expect(retryEvents).toEqual([
      {
        eventType: "assistant.workflow_provider_retry",
        data: {
          runtime_run_id: "runtime-1",
          runtime_sequence: 2,
          tool_name: "section_drafter",
          node_name: "section_drafter",
          error_code: "provider_rate_limited",
          retry_attempt: 2,
          retry_max_attempts: 3,
          state: "running_workflow",
        },
      },
    ]);

    const failureEvents = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: "run.failed",
        public_summary: "工作流未能完成。",
        payload: { error_code: "provider_auth_failed" },
      }),
      "conversation-1",
    );
    expect(failureEvents).toEqual([
      {
        eventType: "assistant.workflow_failed",
        data: {
          runtime_run_id: "runtime-1",
          runtime_sequence: 2,
          tool_name: "workflow",
          error_message: "工作流未能完成。",
          error_code: "provider_auth_failed",
          state: "failed",
        },
      },
      {
        eventType: "assistant.end",
        data: {
          runtime_run_id: "runtime-1",
          runtime_sequence: 2,
          conversation_id: "conversation-1",
          state: "failed",
        },
      },
    ]);
  });
});
