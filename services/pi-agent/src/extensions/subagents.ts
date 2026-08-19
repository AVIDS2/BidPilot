import type { ExtensionFactory } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import type { PiRunRequest, PiToolBridgeResponse } from "../contracts.js";
import type { ResolvedSandbox } from "../sandbox.js";

const MAX_TASKS = 8;
const MAX_PROMPT_BYTES = 12 * 1024;

const taskSchema = Type.Object(
  {
    agent: Type.Optional(Type.String({ description: "Specialist profile name, for example researcher or reviewer." })),
    task: Type.String({ description: "Self-contained task for the child agent." }),
    task_id: Type.Optional(Type.String({ description: "Stable id used to correlate a child result." })),
  },
  { additionalProperties: false },
);

const paramsSchema = Type.Object(
  {
    mode: Type.Union([
      Type.Literal("single"),
      Type.Literal("parallel"),
      Type.Literal("chain"),
    ], { description: "single, independent parallel tasks, or sequential chain." }),
    agent: Type.Optional(Type.String({ description: "Specialist profile for single mode." })),
    task: Type.Optional(Type.String({ description: "Task for single mode." })),
    tasks: Type.Optional(Type.Array(taskSchema, { maxItems: MAX_TASKS, description: "Independent tasks for parallel mode." })),
    chain: Type.Optional(Type.Array(taskSchema, { maxItems: MAX_TASKS, description: "Sequential tasks for chain mode." })),
    max_steps: Type.Optional(Type.Integer({ minimum: 1, maximum: 32, description: "Maximum child turns per task." })),
    completion: Type.Optional(Type.Union([
      Type.Literal("foreground"),
      Type.Literal("background"),
    ], {
      description: [
        "How the parent should observe delegated work.",
        "foreground (default) waits for terminal child results so the parent can continue reasoning in this turn.",
        "Use background only when the user explicitly wants the work to continue after this turn.",
      ].join(" "),
    })),
  },
  { additionalProperties: false },
);

function observation(response: PiToolBridgeResponse, sandbox: ResolvedSandbox): string {
  const value = JSON.stringify({
    status: response.kind,
    summary: response.publicSummary,
    error_code: response.errorCode ?? null,
    pause_reason: response.pauseReason ?? null,
    retryable: response.recoverable ?? false,
    data: response.modelPayload,
  }, null, 2);
  if (Buffer.byteLength(value, "utf8") <= sandbox.maxToolObservationBytes) return value;
  return JSON.stringify({
    status: "failed",
    summary: "子 Agent 返回超过观察上限，请拆分任务或减少并发项。",
    error_code: "subagent_observation_too_large",
    retryable: true,
  }, null, 2);
}

function validateArguments(params: Record<string, unknown>): string | null {
  const mode = params.mode;
  if (mode !== "single" && mode !== "parallel" && mode !== "chain") return "mode 必须是 single、parallel 或 chain。";
  const tasks = mode === "single" ? [{ task: params.task }] : (params.tasks ?? params.chain);
  if (mode === "single" && typeof params.task !== "string") return "single 模式需要 task。";
  if (mode !== "single" && (!Array.isArray(tasks) || tasks.length === 0)) return `${mode} 模式需要非空任务列表。`;
  if (Array.isArray(tasks) && tasks.length > MAX_TASKS) return `单次最多派生 ${MAX_TASKS} 个子 Agent。`;
  const encoded = Buffer.byteLength(JSON.stringify(params), "utf8");
  if (encoded > MAX_PROMPT_BYTES) return "子 Agent 任务描述过长，请拆分后再执行。";
  return null;
}

export function subagentsExtension(
  request: PiRunRequest,
  fetchImpl: typeof globalThis.fetch,
  sandbox: ResolvedSandbox,
): ExtensionFactory {
  return (pi) => {
    pi.registerTool({
      name: "spawn_subagents",
      label: "派生子 Agent",
      description: [
        "Delegate a bounded task to governed child agents with isolated context.",
        "Use single for one child, parallel for independent tasks, and chain when each step depends on the previous result.",
        "The server persists every child run.",
        "By default this call waits for child results; use those results before answering the user.",
        "Choose background only when the user explicitly asks for asynchronous execution.",
      ].join(" "),
      parameters: paramsSchema,
      executionMode: "sequential",
      async execute(toolCallId, params, signal) {
        const validationError = validateArguments(params as Record<string, unknown>);
        if (validationError) {
          return {
            content: [{ type: "text", text: JSON.stringify({ status: "failed", summary: validationError, retryable: false }) }],
            details: {
              kind: "failed",
              publicSummary: validationError,
              modelPayload: {},
              recoverable: false,
            } as PiToolBridgeResponse,
            isError: true,
          };
        }
        const response = await fetchImpl(request.toolCallback.url, {
          method: "POST",
          headers: {
            authorization: `Bearer ${request.toolCallback.token}`,
            "content-type": "application/json",
          },
          body: JSON.stringify({
            run_id: request.runId,
            tool_call_id: toolCallId,
            name: "spawn_subagents",
            arguments: params,
            step: 1,
          }),
          signal,
        });
        if (!response.ok) throw new Error(`tool bridge rejected spawn_subagents (${response.status})`);
        const outcome = await response.json() as PiToolBridgeResponse;
        return {
          content: [{ type: "text", text: observation(outcome, sandbox) }],
          details: outcome as PiToolBridgeResponse,
          isError: outcome.kind === "failed" || outcome.kind === "blocked",
          terminate: outcome.kind === "paused" || outcome.kind === "blocked" || (outcome.kind === "failed" && outcome.recoverable === false),
        };
      },
    });
  };
}
