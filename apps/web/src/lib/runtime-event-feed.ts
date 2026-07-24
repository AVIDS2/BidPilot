export interface RuntimeEventRead {
  run_id: string;
  sequence: number;
  type: string;
  public_summary: string;
  payload: Record<string, unknown>;
  schema_version: string;
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
  return {
    runtime_run_id: event.run_id,
    runtime_sequence: event.sequence,
  };
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
  const metadata = runtimeMetadata(event);

  switch (event.type) {
    case "capability.started":
      return [{
        eventType: "assistant.tool_started",
        data: { ...metadata, tool_name: capability, state: "executing_tool" },
      }];
    case "capability.succeeded": {
      const result = { ...payload };
      delete result.capability;
      const events: AssistantCompatibilityEvent[] = [];
      if (WORKFLOW_CAPABILITIES.has(capability)) {
        events.push({
          eventType: "assistant.workflow_started",
          data: { ...metadata, tool_name: capability, result, state: "running_workflow" },
        });
      }
      events.push({
        eventType: "assistant.tool_succeeded",
        data: {
          ...metadata,
          tool_name: capability,
          result,
          summary: event.public_summary,
          state: "completed",
        },
      });
      return events;
    }
    case "capability.progressed": {
      if (payload.phase !== "provider_retry") return [];
      const nodeName = asString(payload.node);
      return [{
        eventType: nodeName ? "assistant.workflow_provider_retry" : "assistant.tool_progressed",
        data: {
          ...metadata,
          tool_name: capability,
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
          node_name: nodeName,
          error_message: event.public_summary,
          error_code: asString(payload.error_code),
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
        arguments: asRecord(payload.arguments),
        message: asString(payload.message) ?? "该操作需要你的确认。",
        requires_typed_confirmation: Boolean(payload.requires_typed_confirmation),
        state: "needs_confirmation",
      };
      const expectedText = asString(payload.expected_text);
      if (expectedText) data.expected_text = expectedText;
      return [{ eventType: "assistant.confirmation_requested", data }];
    }
    case "approval.resolved":
      if (payload.status === "approved" || payload.status === "edited") {
        return [{
          eventType: "assistant.tool_started",
          data: { ...metadata, tool_name: capability, state: "executing_tool" },
        }];
      }
      return [];
    case "message.completed":
      return [{
        eventType: "assistant.message",
        data: { ...metadata, content: event.public_summary, state: "completed" },
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
            state: "failed",
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
          state: "completed",
        },
      }];
    default:
      return [];
  }
}
