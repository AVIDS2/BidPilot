import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createFauxCore,
  fauxAssistantMessage,
  fauxThinking,
  fauxToolCall,
  fauxText,
} from "@earendil-works/pi-ai/providers/faux";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";
import { InMemoryCredentialStore } from "@earendil-works/pi-ai";
import { runPiAgent } from "./runtime.js";
import type { PiRunRequest } from "./contracts.js";

function request(): PiRunRequest {
  return {
    runId: "run-test",
    sessionId: "session-test",
    systemPrompt: "You are a test execution assistant.",
    userMessage: "读取项目状态并汇报结果。",
    model: {
      provider: "test-provider",
      id: "test-model",
      api: "openai-completions",
      baseUrl: "http://test.invalid/v1",
      apiKey: "test-key",
      thinkingLevel: "off",
    },
    tools: [
      {
        name: "get_project_status",
        label: "读取项目状态",
        description: "读取当前项目状态",
        parameters: { type: "object", properties: {}, additionalProperties: false },
        executionMode: "parallel",
      },
    ],
    toolCallback: { url: "http://tool.test/execute", token: "token" },
    maxTurns: 4,
  };
}

async function testRuntime(streamSimple: ReturnType<typeof createFauxCore>["streamSimple"]): Promise<ModelRuntime> {
  const runtime = await ModelRuntime.create({
    credentials: new InMemoryCredentialStore(),
    modelsPath: null,
    refreshOnCreate: false,
  });
  runtime.registerProvider("test-provider", {
    api: "openai-completions",
    baseUrl: "http://test.invalid/v1",
    apiKey: "test-key",
    streamSimple,
    models: [{
      id: "test-model",
      name: "Test model",
      reasoning: true,
      input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 16_000,
      maxTokens: 2_000,
    }],
  });
  return runtime;
}

test("Pi AgentSession completes a tool turn and returns native lifecycle events", async () => {
  const faux = createFauxCore({ api: "openai-completions", provider: "test-provider", models: [{ id: "test-model" }] });
  faux.setResponses([
    fauxAssistantMessage([
      fauxText("我先读取项目状态。"),
      fauxToolCall("get_project_status", {}, { id: "tool-1" }),
    ]),
    fauxAssistantMessage("项目当前正常。"),
  ]);
  const runtime = await testRuntime(faux.streamSimple);
  const callbackCalls: string[] = [];
  const events: string[] = [];
  await runPiAgent(request(), (event) => {
    events.push(event.type);
  }, {
    createModelRuntime: async () => runtime,
    fetch: async (input) => {
      callbackCalls.push(String(input));
      return new Response(JSON.stringify({
        kind: "succeeded",
        publicSummary: "已读取项目状态",
        modelPayload: { status: "healthy" },
      }), { status: 200, headers: { "content-type": "application/json" } });
    },
  });

  assert.equal(callbackCalls.length, 1);
  assert.ok(events.includes("agent.started"));
  assert.ok(events.includes("text.delta"));
  assert.ok(events.includes("tool.started"));
  assert.ok(events.includes("tool.completed"));
  assert.ok(events.includes("agent.completed"));
  assert.equal(events.includes("agent.failed"), false);
});

test("private provider thinking is never projected as text", async () => {
  const faux = createFauxCore({ api: "openai-completions", provider: "test-provider", models: [{ id: "test-model", reasoning: true }] });
  faux.setResponses([
    fauxAssistantMessage([fauxThinking("private chain of thought"), fauxText("可公开的结论")]),
  ]);
  const runtime = await testRuntime(faux.streamSimple);
  const projected: Array<Record<string, unknown>> = [];
  await runPiAgent(request(), (event) => {
    projected.push(event);
  }, {
    createModelRuntime: async () => runtime,
  });

  const text = projected
    .filter((event) => event.type === "text.delta")
    .map((event) => String(event.delta ?? ""))
    .join("");
  assert.equal(text, "可公开的结论");
  assert.equal(text.includes("private chain of thought"), false);
  assert.ok(projected.some((event) => event.type === "thinking.started"));
  assert.ok(projected.some((event) => event.type === "thinking.completed"));
});

test("a non-recoverable tool failure terminates without another model turn", async () => {
  const faux = createFauxCore({ api: "openai-completions", provider: "test-provider", models: [{ id: "test-model" }] });
  faux.setResponses([
    fauxAssistantMessage(fauxToolCall("get_project_status", {}, { id: "tool-failed" })),
  ]);
  const runtime = await testRuntime(faux.streamSimple);
  const projected: Array<Record<string, unknown>> = [];
  await runPiAgent(request(), (event) => {
    projected.push(event);
  }, {
    createModelRuntime: async () => runtime,
    fetch: async () => new Response(JSON.stringify({
      kind: "failed",
      publicSummary: "项目不存在",
      modelPayload: { project_id: "missing" },
      errorCode: "project_not_found",
      recoverable: false,
    }), { status: 200, headers: { "content-type": "application/json" } }),
  });

  assert.equal(faux.state.callCount, 1);
  const completed = projected.find((event) => event.type === "tool.completed");
  assert.equal(completed?.is_error, true);
  assert.ok(projected.some((event) => event.type === "agent.completed"));
});

test("independent read tools execute in parallel through the governed bridge", async () => {
  const faux = createFauxCore({ api: "openai-completions", provider: "test-provider", models: [{ id: "test-model" }] });
  faux.setResponses([
    fauxAssistantMessage([
      fauxToolCall("read_a", {}, { id: "tool-a" }),
      fauxToolCall("read_b", {}, { id: "tool-b" }),
    ]),
    fauxAssistantMessage("两项读取均已完成。"),
  ]);
  const runtime = await testRuntime(faux.streamSimple);
  const parallelRequest = request();
  parallelRequest.tools = ["read_a", "read_b"].map((name) => ({
    name,
    label: name,
    description: `执行 ${name}`,
    parameters: { type: "object", properties: {}, additionalProperties: false },
    executionMode: "parallel",
  }));
  let active = 0;
  let maxActive = 0;
  await runPiAgent(parallelRequest, () => undefined, {
    createModelRuntime: async () => runtime,
    fetch: async () => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => setTimeout(resolve, 40));
      active -= 1;
      return new Response(JSON.stringify({
        kind: "succeeded",
        publicSummary: "读取完成",
        modelPayload: { ok: true },
      }), { status: 200, headers: { "content-type": "application/json" } });
    },
  });

  assert.equal(maxActive, 2);
});
