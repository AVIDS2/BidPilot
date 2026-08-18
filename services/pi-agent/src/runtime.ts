import { Agent, type AgentEvent, type AgentTool, type StreamFn } from "@earendil-works/pi-agent-core";
import {
  Type,
  type AssistantMessage,
  type Model,
  type SimpleStreamOptions,
} from "@earendil-works/pi-ai";
import { anthropicMessagesApi } from "@earendil-works/pi-ai/api/anthropic-messages.lazy";
import { openAICompletionsApi } from "@earendil-works/pi-ai/api/openai-completions.lazy";
import { openAIResponsesApi } from "@earendil-works/pi-ai/api/openai-responses.lazy";
import type { PiApi, PiRunRequest, PiRuntimeEvent, PiToolBridgeResponse } from "./contracts.js";

type EventSink = (event: PiRuntimeEvent) => void | Promise<void>;

export interface PiRuntimeDependencies {
  fetch?: typeof globalThis.fetch;
  streamFn?: StreamFn;
}

function createModel(request: PiRunRequest): Model<PiApi> {
  return {
    id: request.model.id,
    name: request.model.name ?? request.model.id,
    api: request.model.api,
    provider: request.model.provider,
    baseUrl: request.model.baseUrl.replace(/\/$/, ""),
    reasoning: request.model.reasoning ?? false,
    input: ["text"],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: request.model.contextWindow ?? 128_000,
    maxTokens: request.model.maxTokens ?? 16_384,
  };
}

function providerStream(api: PiApi) {
  if (api === "anthropic-messages") return anthropicMessagesApi().streamSimple;
  if (api === "openai-responses") return openAIResponsesApi().streamSimple;
  return openAICompletionsApi().streamSimple;
}

function createStreamFn(request: PiRunRequest) {
  const stream = providerStream(request.model.api);
  return (model: Model<any>, context: any, options?: SimpleStreamOptions) =>
    stream(model, context, {
      ...options,
      apiKey: request.model.apiKey,
      sessionId: request.sessionId,
      timeoutMs: 120_000,
      maxRetries: 1,
      maxRetryDelayMs: 10_000,
    });
}

function toolObservation(response: PiToolBridgeResponse): string {
  return JSON.stringify(
    {
      status: response.kind,
      summary: response.publicSummary,
      error_code: response.errorCode ?? null,
      pause_reason: response.pauseReason ?? null,
      retryable: response.recoverable ?? false,
      data: response.modelPayload,
    },
    null,
    2,
  );
}

type TurnState = { id: string; step: number };

function createTools(request: PiRunRequest, fetchImpl: typeof globalThis.fetch, turnState: TurnState): AgentTool[] {
  return request.tools.map((definition) => ({
    name: definition.name,
    label: definition.label,
    description: definition.description,
    parameters: Type.Unsafe(definition.parameters),
    executionMode: definition.executionMode ?? "sequential",
    execute: async (toolCallId, params, signal) => {
      const response = await fetchImpl(request.toolCallback.url, {
        method: "POST",
        headers: {
          authorization: `Bearer ${request.toolCallback.token}`,
          "content-type": "application/json",
        },
        body: JSON.stringify({
          run_id: request.runId,
          tool_call_id: toolCallId,
          name: definition.name,
          arguments: params,
          turn_id: turnState.id,
          step: turnState.step,
        }),
        signal,
      });
      if (!response.ok) {
        throw new Error(`tool bridge rejected ${definition.name} (${response.status})`);
      }
      const outcome = (await response.json()) as PiToolBridgeResponse;
      return {
        content: [{ type: "text", text: toolObservation(outcome) }],
        details: outcome,
        terminate:
          outcome.kind === "paused" ||
          outcome.kind === "blocked" ||
          (outcome.kind === "failed" && outcome.recoverable === false),
      };
    },
  }));
}

function textFromAssistant(message: AssistantMessage): string {
  return message.content
    .filter((item): item is Extract<typeof item, { type: "text" }> => item.type === "text")
    .map((item) => item.text)
    .join("");
}

function publicEvent(event: AgentEvent): PiRuntimeEvent | null {
  if (event.type === "message_update") {
    const update = event.assistantMessageEvent;
    if (update.type === "text_delta") return { type: "text.delta", delta: update.delta };
    if (update.type === "thinking_start") return { type: "thinking.started" };
    if (update.type === "thinking_end") return { type: "thinking.completed" };
    return null;
  }
  if (event.type === "turn_start") return { type: "turn.started" };
  if (event.type === "turn_end") {
    const message = event.message.role === "assistant" ? event.message : null;
    return {
      type: "turn.completed",
      text: message ? textFromAssistant(message) : "",
      usage: message?.usage ?? null,
    };
  }
  if (event.type === "tool_execution_start") {
    return {
      type: "tool.started",
      tool_call_id: event.toolCallId,
      name: event.toolName,
      arguments: event.args,
    };
  }
  if (event.type === "tool_execution_update") {
    return { type: "tool.updated", tool_call_id: event.toolCallId, name: event.toolName };
  }
  if (event.type === "tool_execution_end") {
    return {
      type: "tool.completed",
      tool_call_id: event.toolCallId,
      name: event.toolName,
      is_error: event.isError,
      result: event.result.details,
    };
  }
  if (event.type === "agent_start") return { type: "agent.started" };
  return null;
}

export async function runPiAgent(
  request: PiRunRequest,
  sink: EventSink,
  dependencies: PiRuntimeDependencies = {},
): Promise<void> {
  const fetchImpl = dependencies.fetch ?? globalThis.fetch;
  const model = createModel(request);
  let turns = 0;
  const turnState: TurnState = { id: "turn-0", step: 0 };
  const tools = createTools(request, fetchImpl, turnState);
  const agent = new Agent({
    initialState: {
      systemPrompt: request.systemPrompt,
      model,
      thinkingLevel: request.model.thinkingLevel ?? "off",
      tools,
      messages: [],
    },
    streamFn: dependencies.streamFn ?? createStreamFn(request),
    sessionId: request.sessionId,
    toolExecution: "parallel",
    afterToolCall: async ({ result }) => {
      const outcome = result.details as PiToolBridgeResponse | undefined;
      if (!outcome) return undefined;
      const failed = outcome.kind === "failed" || outcome.kind === "blocked";
      return {
        isError: failed,
        terminate:
          outcome.kind === "paused" ||
          outcome.kind === "blocked" ||
          (outcome.kind === "failed" && outcome.recoverable === false),
      };
    },
    shouldStopAfterTurn: () => {
      turns += 1;
      return turns >= (request.maxTurns ?? 24);
    },
  });
  agent.subscribe(async (event) => {
    if (event.type === "turn_start") {
      turnState.step += 1;
      turnState.id = `turn-${turnState.step}`;
    }
    if (event.type === "agent_end") {
      await sink(
        agent.state.errorMessage
          ? { type: "agent.failed", error: agent.state.errorMessage }
          : { type: "agent.completed" },
      );
      return;
    }
    const projected = publicEvent(event);
    if (projected) {
      if (event.type === "turn_start" || event.type.startsWith("tool_execution_")) {
        projected.turn_id = turnState.id;
      }
      await sink(projected);
    }
  });
  await agent.prompt(request.userMessage);
}
