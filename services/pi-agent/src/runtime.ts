import type { AgentEvent } from "@earendil-works/pi-agent-core";
import {
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager,
  SettingsManager,
  createAgentSession,
  defineTool,
  type AgentSessionEvent,
  type ToolDefinition,
} from "@earendil-works/pi-coding-agent";
import {
  InMemoryCredentialStore,
  Type,
  type AssistantMessage,
  type Model,
} from "@earendil-works/pi-ai";
import type { PiApi, PiRunRequest, PiRuntimeEvent, PiToolBridgeResponse } from "./contracts.js";
import { buildTrustedExtensions, resolveSandbox, type ResolvedSandbox } from "./sandbox.js";

type EventSink = (event: PiRuntimeEvent) => void | Promise<void>;

export interface PiRuntimeDependencies {
  fetch?: typeof globalThis.fetch;
  createModelRuntime?: () => Promise<ModelRuntime>;
}

async function createModelRuntime(request: PiRunRequest): Promise<{ runtime: ModelRuntime; model: Model<PiApi> }> {
  const runtime = await ModelRuntime.create({
    credentials: new InMemoryCredentialStore(),
    modelsPath: null,
    refreshOnCreate: false,
  });
  const nativeModel = runtime.getModel(request.model.provider, request.model.id) as Model<PiApi> | undefined;
  if (nativeModel) {
    await runtime.setRuntimeApiKey(request.model.provider, request.model.apiKey);
    return { runtime, model: nativeModel };
  }
  runtime.registerProvider(request.model.provider, {
    name: request.model.provider,
    baseUrl: request.model.baseUrl.replace(/\/$/, ""),
    apiKey: request.model.apiKey,
    api: request.model.api,
    models: [
      {
        id: request.model.id,
        name: request.model.name ?? request.model.id,
        api: request.model.api,
        reasoning: request.model.reasoning ?? false,
        input: ["text"],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: request.model.contextWindow ?? 128_000,
        maxTokens: request.model.maxTokens ?? 16_384,
      },
    ],
  });
  const model = runtime.getModel(request.model.provider, request.model.id) as Model<PiApi> | undefined;
  if (!model) throw new Error(`Pi model registration failed: ${request.model.provider}/${request.model.id}`);
  return { runtime, model };
}

function toolObservation(response: PiToolBridgeResponse, sandbox: ResolvedSandbox): string {
  const observation = JSON.stringify(
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
  const bytes = Buffer.byteLength(observation, "utf8");
  if (bytes <= sandbox.maxToolObservationBytes) return observation;
  return JSON.stringify(
    {
      status: "failed",
      summary: "工具结果超过单次模型观察上限，请使用筛选、分页或更窄的查询重试。",
      error_code: "tool_observation_too_large",
      retryable: true,
      data: { original_bytes: bytes, limit_bytes: sandbox.maxToolObservationBytes },
    },
    null,
    2,
  );
}

type TurnState = { id: string; step: number };

function createTools(
  request: PiRunRequest,
  fetchImpl: typeof globalThis.fetch,
  turnState: TurnState,
  sandbox: ResolvedSandbox,
): ToolDefinition[] {
  return request.tools.map((definition) =>
    defineTool({
      name: definition.name,
      label: definition.label,
      description: definition.description,
      promptSnippet: `${definition.name}: ${definition.description}`,
      parameters: Type.Unsafe(definition.parameters),
      executionMode: definition.executionMode ?? "sequential",
      execute: async (toolCallId, params, signal) => {
        let outcome: PiToolBridgeResponse;
        try {
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
            outcome = {
              kind: "failed",
              publicSummary: "执行服务拒绝了本次操作，本轮已停止。",
              modelPayload: { tool: definition.name, http_status: response.status },
              errorCode: "pi_bridge_rejected",
              recoverable: false,
            };
          } else {
            outcome = (await response.json()) as PiToolBridgeResponse;
          }
        } catch (error) {
          if (signal?.aborted) throw error;
          outcome = {
            kind: "failed",
            publicSummary: "执行服务暂时不可达，本轮已停止，未执行该操作。",
            modelPayload: { tool: definition.name, failure: "bridge_unreachable" },
            errorCode: "pi_bridge_unreachable",
            recoverable: false,
          };
        }
        return {
          content: [{ type: "text", text: toolObservation(outcome, sandbox) }],
          details: outcome,
          terminate:
            outcome.kind === "paused" ||
            outcome.kind === "blocked" ||
            (outcome.kind === "failed" && outcome.recoverable === false),
        };
      },
    }),
  );
}

function textFromAssistant(message: AssistantMessage): string {
  return message.content
    .filter((item): item is Extract<typeof item, { type: "text" }> => item.type === "text")
    .map((item) => item.text)
    .join("");
}

function coreEvent(event: AgentSessionEvent): AgentEvent | null {
  if (
    event.type === "queue_update" ||
    event.type === "compaction_start" ||
    event.type === "compaction_end" ||
    event.type === "auto_retry_start" ||
    event.type === "auto_retry_end" ||
    event.type === "agent_end" ||
    event.type === "agent_settled" ||
    event.type === "entry_appended" ||
    event.type === "session_info_changed" ||
    event.type === "thinking_level_changed" ||
    event.type === "summarization_retry_scheduled" ||
    event.type === "summarization_retry_attempt_start" ||
    event.type === "summarization_retry_finished" ||
    event.type === "bash_execution_update"
  ) {
    return null;
  }
  return event as AgentEvent;
}

function publicCoreEvent(event: AgentEvent): PiRuntimeEvent | null {
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

function publicSessionEvent(event: AgentSessionEvent): PiRuntimeEvent | null {
  if (event.type === "queue_update") {
    return {
      type: "queue.updated",
      steering: event.steering.length,
      follow_up: event.followUp.length,
    };
  }
  if (event.type === "compaction_start") {
    return { type: "compaction.started", reason: event.reason };
  }
  if (event.type === "compaction_end") {
    return {
      type: "compaction.completed",
      reason: event.reason,
      aborted: event.aborted,
      will_retry: event.willRetry,
    };
  }
  if (event.type === "auto_retry_start") {
    return {
      type: "retry.started",
      attempt: event.attempt,
      max_attempts: event.maxAttempts,
      delay_ms: event.delayMs,
    };
  }
  if (event.type === "auto_retry_end") {
    return { type: "retry.completed", attempt: event.attempt, success: event.success };
  }
  const core = coreEvent(event);
  return core ? publicCoreEvent(core) : null;
}

function enrichToolLifecycleEvent(
  event: PiRuntimeEvent,
  request: PiRunRequest,
): PiRuntimeEvent {
  if (!event.type.startsWith("tool.")) return event;
  const toolName = typeof event.name === "string" ? event.name : "";
  const definition = request.tools.find((tool) => tool.name === toolName);
  if (!definition) return event;
  const enriched: PiRuntimeEvent = {
    ...event,
    title: definition.label,
    resource_kind: definition.resourceKind ?? "tool",
  };
  if (definition.provider) enriched.provider = definition.provider;
  if (definition.resourceKind === "skill") {
    const args = event.arguments;
    if (args && typeof args === "object" && !Array.isArray(args)) {
      const name = (args as Record<string, unknown>).name;
      if (typeof name === "string" && name.trim()) enriched.resource_name = name.trim();
    }
  }
  return enriched;
}

export function agentTerminalEvent(
  eventType: AgentSessionEvent["type"],
  errorMessage?: string,
): PiRuntimeEvent | null {
  if (eventType !== "agent_settled") return null;
  return errorMessage
    ? { type: "agent.failed", error: errorMessage }
    : { type: "agent.completed" };
}

export async function runPiAgent(
  request: PiRunRequest,
  sink: EventSink,
  dependencies: PiRuntimeDependencies = {},
): Promise<void> {
  const fetchImpl = dependencies.fetch ?? globalThis.fetch;
  const sandbox = resolveSandbox(request);
  const registered = dependencies.createModelRuntime
    ? { runtime: await dependencies.createModelRuntime(), model: undefined }
    : await createModelRuntime(request);
  let model = registered.model;
  if (!model) {
    model = registered.runtime.getModel(request.model.provider, request.model.id) as Model<PiApi> | undefined;
  }
  if (!model) throw new Error(`Pi model is unavailable: ${request.model.provider}/${request.model.id}`);

  const turnState: TurnState = { id: "turn-0", step: 0 };
  const tools = createTools(request, fetchImpl, turnState, sandbox);
  const cwd = process.cwd();
  const settingsManager = SettingsManager.inMemory({
    defaultThinkingLevel: request.model.thinkingLevel ?? "off",
    steeringMode: "all",
    followUpMode: "all",
    retry: {
      enabled: true,
      maxRetries: 2,
      baseDelayMs: 1_000,
      provider: { maxRetryDelayMs: 10_000, maxRetries: 1, timeoutMs: 120_000 },
    },
    httpIdleTimeoutMs: 120_000,
  });
  const resourceLoader = new DefaultResourceLoader({
    cwd,
    agentDir: cwd,
    settingsManager,
    noExtensions: true,
    noSkills: true,
    noPromptTemplates: true,
    noThemes: true,
    noContextFiles: true,
    systemPrompt: request.systemPrompt,
    extensionFactories: buildTrustedExtensions(request, sandbox, fetchImpl),
  });
  await resourceLoader.reload();
  const { session } = await createAgentSession({
    cwd,
    modelRuntime: registered.runtime,
    model,
    thinkingLevel: request.model.thinkingLevel ?? "off",
    noTools: "builtin",
    customTools: tools,
    resourceLoader,
    sessionManager: SessionManager.inMemory(cwd),
    settingsManager,
  });

  let turns = 0;
  let terminalEmitted = false;
  let terminalDelivery: Promise<void> | null = null;
  const emitTerminal = () => {
    if (terminalEmitted) return;
    const terminal = agentTerminalEvent("agent_settled", session.state.errorMessage);
    if (!terminal) return;
    terminalEmitted = true;
    terminalDelivery = Promise.resolve().then(() => sink(terminal));
  };
  session.agent.afterToolCall = async ({ result }) => {
    const outcome = result.details as PiToolBridgeResponse | undefined;
    // Preserve Pi's native termination hint for governance blocks. A blocked
    // call has an empty details object rather than a bridge outcome.
    if (!outcome || !["succeeded", "failed", "paused", "blocked"].includes(outcome.kind)) {
      return { isError: true, terminate: result.terminate === true };
    }
    const failed = outcome.kind === "failed" || outcome.kind === "blocked";
    return {
      isError: failed,
      terminate:
        outcome.kind === "paused" ||
        outcome.kind === "blocked" ||
        (outcome.kind === "failed" && outcome.recoverable === false),
    };
  };
  session.agent.shouldStopAfterTurn = () => {
    turns += 1;
    return turns >= (request.maxTurns ?? 24);
  };
  const unsubscribe = session.subscribe(async (event) => {
    if (event.type === "turn_start") {
      turnState.step += 1;
      turnState.id = `turn-${turnState.step}`;
    }
    if (event.type === "agent_settled") {
      emitTerminal();
      return;
    }
    const projected = publicSessionEvent(event);
    if (projected) {
      const enriched = enrichToolLifecycleEvent(projected, request);
      if (event.type === "turn_start" || event.type.startsWith("tool_execution_")) {
        enriched.turn_id = turnState.id;
      }
      await sink(enriched);
    }
  });

  try {
    await session.prompt(request.userMessage, { expandPromptTemplates: false, source: "rpc" });
    await session.waitForIdle();
    emitTerminal();
    await terminalDelivery;
  } finally {
    unsubscribe();
    session.dispose();
  }
}
