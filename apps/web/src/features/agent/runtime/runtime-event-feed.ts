export interface RuntimeEventRead {
  event_id?: string;
  run_id: string;
  parent_event_id?: string | null;
  sequence: number;
  type: string;
  public_summary: string;
  payload: Record<string, unknown>;
  schema_version: string;
  timestamp?: string;
}

export interface RuntimeEventCursor {
  [runId: string]: number;
}

export interface AssistantCompatibilityEvent {
  eventType: string;
  data: Record<string, unknown>;
}

const WORKFLOW_CAPABILITIES = new Set([
  "start_draft_section",
  "start_redraft_section",
  "retry_run",
  "propose_memory_graph",
  "run_section_campaign",
]);

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function runtimeMetadata(event: RuntimeEventRead): Record<string, unknown> {
  const metadata: Record<string, unknown> = {
    runtime_run_id: event.run_id,
    runtime_sequence: event.sequence,
  };
  if (event.event_id) metadata.runtime_event_id = event.event_id;
  if (event.parent_event_id) metadata.runtime_parent_event_id = event.parent_event_id;
  return metadata;
}

function presentationMetadata(payload: Record<string, unknown>): Record<string, unknown> {
  const metadata: Record<string, unknown> = {};
  const kind = asString(payload.presentation_kind);
  const sessionId = asString(payload.presentation_session_id);
  const title = asString(payload.presentation_title);
  if (kind) metadata.presentation_kind = kind;
  if (sessionId) metadata.presentation_session_id = sessionId;
  if (title) metadata.presentation_title = title;
  return metadata;
}

export function isRuntimeSequenceNewer(
  cursors: RuntimeEventCursor,
  runId: string,
  sequence: number,
): boolean {
  return sequence > (cursors[runId] ?? 0);
}

export function isRuntimeEventNewer(cursors: RuntimeEventCursor, event: RuntimeEventRead): boolean {
  return isRuntimeSequenceNewer(cursors, event.run_id, event.sequence);
}

export function advanceRuntimeEventCursor(
  cursors: RuntimeEventCursor,
  event: RuntimeEventRead,
): RuntimeEventCursor {
  if (!isRuntimeEventNewer(cursors, event)) return cursors;
  return { ...cursors, [event.run_id]: event.sequence };
}

export function advanceRuntimeSequenceCursor(
  cursors: RuntimeEventCursor,
  runId: string,
  sequence: number,
): RuntimeEventCursor {
  if (!isRuntimeSequenceNewer(cursors, runId, sequence)) return cursors;
  return { ...cursors, [runId]: sequence };
}

export function isTerminalRuntimeEvent(event: RuntimeEventRead): boolean {
  return ["run.completed", "run.failed", "run.cancelled"].includes(event.type);
}

export interface RecoveredRuntimeMessage {
  runId: string;
  content: string;
  timestamp?: number;
}

/**
 * Recover the user-facing assistant message when the chat row was not written
 * before a browser stream was interrupted. Durable runtime events are already
 * redacted public text, so they are safe to use for transcript recovery.
 */
export function recoverRuntimeMessageFromEvents(
  runId: string,
  events: RuntimeEventRead[],
): RecoveredRuntimeMessage | null {
  const completed = [...events]
    .reverse()
    .find((event) => event.type === "message.completed" && event.public_summary.trim());
  const deltas = events
    .filter((event) => event.type === "message.delta")
    .map((event) => event.public_summary)
    .join("")
    .trim();
  const content = (completed?.public_summary ?? deltas).trim();
  if (!content) return null;

  const timestampSource = completed?.timestamp ?? [...events].reverse().find((event) => event.type === "message.delta")?.timestamp;
  const parsedTimestamp = timestampSource ? Date.parse(timestampSource) : Number.NaN;
  return {
    runId,
    content,
    timestamp: Number.isFinite(parsedTimestamp) ? parsedTimestamp : undefined,
  };
}

/**
 * Convert the durable public event contract into the existing assistant SSE
 * vocabulary. The UI can migrate independently without replaying a tool call.
 */
export function runtimeEventToAssistantEvents(
  event: RuntimeEventRead,
  conversationId?: string | null,
): AssistantCompatibilityEvent[] {
  const payload = asRecord(event.payload);
  const capability = asString(payload.capability) ?? "unknown";
  const actionId = asString(payload.action_id);
  const turnId = asString(payload.turn_id);
  const toolCallId = asString(payload.tool_call_id) ?? actionId;
  const title = asString(payload.title);
  const metadata = { ...runtimeMetadata(event), ...presentationMetadata(payload) };

  switch (event.type) {
    case "plan.proposed":
    case "plan.updated": {
      const stage = asString(payload.stage);
      if (stage === "model_turn") {
        return [{
          eventType: "assistant.turn_started",
          data: {
            ...metadata,
            turn_id: turnId,
            step: payload.step,
            phase: asString(payload.phase),
            completed_capabilities: payload.completed_capabilities ?? [],
            state: "thinking",
          },
        }];
      }
      if (stage === "turn_finished") {
        return [{
          eventType: "assistant.turn_finished",
          data: { ...metadata, turn_id: turnId, summary: event.public_summary, state: "thinking" },
        }];
      }
      if (stage === "task_started") {
        const taskTitle = asString(payload.title) ?? asString(payload.task_title) ?? event.public_summary;
        return [{
          eventType: "assistant.task_started",
          data: {
            ...metadata,
            turn_id: turnId,
            title: taskTitle,
            summary: event.public_summary,
            skill_name: asString(payload.skill_name),
            presentation_kind: asString(payload.presentation_kind),
            presentation_session_id: asString(payload.presentation_session_id) ?? event.event_id,
            presentation_title: asString(payload.presentation_title) ?? taskTitle,
            state: "thinking",
          },
        }];
      }
      if (stage === "tool_plan") {
        return [{
          eventType: "assistant.plan_updated",
          data: {
            ...metadata,
            turn_id: turnId,
            summary: event.public_summary,
            items: payload.items ?? [],
            state: "thinking",
          },
        }];
      }
      if (payload.mode === "needs_input") {
        return [{
          eventType: "assistant.missing_input",
          data: {
            ...metadata,
            tool_name: capability,
            tool_call_id: toolCallId,
            turn_id: turnId,
            missing_fields: payload.missing_fields ?? [],
            message: event.public_summary,
            state: "needs_input",
          },
        }];
      }
      return [];
    }
    case "capability.started":
      return [{
        eventType: "assistant.tool_started",
        data: {
          ...metadata,
          tool_name: capability,
          tool_call_id: toolCallId,
          turn_id: turnId,
          title,
          state: "executing_tool",
        },
      }];
    case "capability.succeeded": {
      const result = Object.fromEntries(
        Object.entries(payload).filter(([key]) => ![
          "capability", "action_id", "turn_id", "tool_call_id", "title",
        ].includes(key)),
      );
      const events: AssistantCompatibilityEvent[] = [];
      if (WORKFLOW_CAPABILITIES.has(capability)) {
        events.push({
          eventType: "assistant.workflow_started",
          data: {
            ...metadata,
            tool_name: capability,
            tool_call_id: toolCallId,
            turn_id: turnId,
            title,
            result,
            state: "running_workflow",
          },
        });
      }
      events.push({
        eventType: "assistant.tool_succeeded",
        data: {
          ...metadata,
          tool_name: capability,
          tool_call_id: toolCallId,
          turn_id: turnId,
          title,
          result,
          summary: event.public_summary,
          state: "completed",
        },
      });
      return events;
    }
    case "capability.progressed": {
      if (capability === "subagent" && payload.phase === "children_spawned") {
        return [{
          eventType: "assistant.subagents_spawned",
          data: {
            ...metadata,
            turn_id: turnId,
            children: payload.children ?? [],
            state: "running_workflow",
          },
        }];
      }
      if (capability === "subagent" && typeof payload.tool === "string") {
        const childTool = asString(payload.tool) ?? "tool";
        const childToolCallId = asString(payload.tool_call_id) ?? toolCallId;
        const phase = asString(payload.phase);
        if (phase === "tool_started") {
          return [{
            eventType: "assistant.tool_started",
            data: {
              ...metadata,
              tool_name: childTool,
              tool_call_id: childToolCallId,
              turn_id: turnId,
              title: event.public_summary,
              state: "executing_tool",
            },
          }];
        }
        if (phase === "tool_failed") {
          return [{
            eventType: "assistant.tool_failed",
            data: {
              ...metadata,
              tool_name: childTool,
              tool_call_id: childToolCallId,
              turn_id: turnId,
              error_message: event.public_summary,
              state: "failed",
            },
          }];
        }
        if (phase === "tool_completed") {
          return [{
            eventType: "assistant.tool_succeeded",
            data: {
              ...metadata,
              tool_name: childTool,
              tool_call_id: childToolCallId,
              turn_id: turnId,
              summary: event.public_summary,
              state: "completed",
            },
          }];
        }
      }
      if (payload.phase !== "provider_retry") return [];
      const nodeName = asString(payload.node);
      return [{
        eventType: nodeName ? "assistant.workflow_provider_retry" : "assistant.tool_progressed",
        data: {
          ...metadata,
          tool_name: capability,
          tool_call_id: toolCallId,
          turn_id: turnId,
          node_name: nodeName,
          error_code: asString(payload.error_code),
          retry_attempt: payload.next_attempt,
          retry_max_attempts: payload.max_attempts,
          state: nodeName ? "running_workflow" : "executing_tool",
        },
      }];
    }
    case "capability.failed": {
      const nodeName = asString(payload.node);
      return [{
        eventType: nodeName ? "assistant.workflow_node_failed" : "assistant.tool_failed",
        data: {
          ...metadata,
          tool_name: capability,
          tool_call_id: toolCallId,
          turn_id: turnId,
          title,
          node_name: nodeName,
          error_message: event.public_summary,
          error_code: asString(payload.reason_code) ?? asString(payload.error_code),
          state: "failed",
        },
      }];
    }
    case "approval.requested": {
      const data: Record<string, unknown> = {
        ...metadata,
        conversation_id: conversationId ?? undefined,
        approval_id: asString(payload.approval_id),
        tool_name: capability,
        tool_call_id: toolCallId,
        turn_id: turnId,
        title,
        arguments: asRecord(payload.arguments),
        message: asString(payload.message) ?? "该操作需要你的确认。",
        requires_typed_confirmation: Boolean(payload.requires_typed_confirmation),
        state: "needs_confirmation",
      };
      const expectedText = asString(payload.expected_text);
      if (expectedText) data.expected_text = expectedText;
      return [
        { eventType: "assistant.confirmation_requested", data },
        {
          eventType: "assistant.end",
          data: {
            ...metadata,
            conversation_id: conversationId ?? undefined,
            state: "needs_confirmation",
          },
        },
      ];
    }
    case "approval.resolved":
      if (payload.status === "approved" || payload.status === "edited") {
        return [{
          eventType: "assistant.tool_started",
          data: {
            ...metadata,
            tool_name: capability,
            tool_call_id: toolCallId,
            turn_id: turnId,
            title,
            state: "executing_tool",
          },
        }];
      }
      return [];
    case "reasoning.delta":
      // Provider thinking streams are private, model-specific CoT. The
      // product trace renders only Harness-authored public narration.
      if (asString(payload.source) !== "harness") return [];
      return [{
        eventType: "assistant.reasoning",
        data: {
          ...metadata,
          turn_id: turnId,
          content: event.public_summary,
          title: asString(payload.title) ?? event.public_summary,
          source: asString(payload.source) ?? "provider",
          state: "thinking",
        },
      }];
    case "reasoning.completed":
      if (asString(payload.source) !== "harness") return [];
      return [{
        eventType: "assistant.reasoning_completed",
        data: {
          ...metadata,
          turn_id: turnId,
          source: asString(payload.source) ?? "provider",
          state: "thinking",
        },
      }];
    case "message.delta":
      return [{
        eventType: "assistant.message",
        data: { ...metadata, turn_id: turnId, content: event.public_summary, state: "thinking" },
      }];
    case "message.completed":
      if (payload.delta_emitted === true) return [];
      return [{
        eventType: "assistant.message",
        data: { ...metadata, turn_id: turnId, content: event.public_summary, state: "completed" },
      }];
    case "run.failed":
      return [
        {
          eventType: "assistant.workflow_failed",
          data: {
            ...metadata,
            tool_name: asString(payload.capability) ?? "workflow",
            error_message: event.public_summary,
            error_code: asString(payload.error_code),
            state: "failed",
          },
        },
        {
          eventType: "assistant.end",
          data: {
          ...metadata,
          conversation_id: conversationId ?? undefined,
          state: asString(payload.state) ?? "failed",
          },
        },
      ];
    case "run.completed":
    case "run.cancelled":
      return [{
        eventType: "assistant.end",
        data: {
          ...metadata,
          conversation_id: conversationId ?? undefined,
          state: asString(payload.state) ?? "completed",
        },
      }];
    default:
      return [];
  }
}
