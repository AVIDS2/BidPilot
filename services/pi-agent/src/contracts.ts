import type { ToolExecutionMode } from "@earendil-works/pi-agent-core";
import type { Api, ModelThinkingLevel } from "@earendil-works/pi-ai";

export type PiApi = Extract<Api, "openai-completions" | "openai-responses" | "anthropic-messages">;

export interface PiModelRequest {
  provider: string;
  id: string;
  name?: string;
  api: PiApi;
  baseUrl: string;
  apiKey: string;
  reasoning?: boolean;
  thinkingLevel?: ModelThinkingLevel;
  contextWindow?: number;
  maxTokens?: number;
}

export interface PiToolRequest {
  name: string;
  label: string;
  description: string;
  parameters: Record<string, unknown>;
  executionMode?: ToolExecutionMode;
  /** Structured presentation metadata; never inferred from user text. */
  resourceKind?: "tool" | "skill" | "mcp";
  provider?: string;
}

export interface PiTranscriptMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: number;
}

export interface PiSkillRequest {
  name: string;
  description: string;
}

export interface PiRuntimeResources {
  /** Server-owned inline extensions. Filesystem paths and tenant code are forbidden. */
  extensions: string[];
  /** Level-1 Agent Skills metadata. Full instructions remain behind read_skill. */
  skills: PiSkillRequest[];
}

export interface PiSandboxRequest {
  /** Cloud runs are capability-only. Host workspaces require a separate isolated runner. */
  profile: "governed_cloud";
  hostTools: "disabled";
  network: "bridge_only";
  maxToolInputBytes?: number;
  maxToolObservationBytes?: number;
}

export interface PiRunRequest {
  runId: string;
  sessionId: string;
  systemPrompt: string;
  userMessage: string;
  messages?: PiTranscriptMessage[];
  model: PiModelRequest;
  tools: PiToolRequest[];
  resources: PiRuntimeResources;
  sandbox: PiSandboxRequest;
  toolCallback: {
    url: string;
    token: string;
  };
  maxTurns?: number;
}

export interface PiToolBridgeResponse {
  kind: "succeeded" | "failed" | "paused" | "blocked";
  publicSummary: string;
  modelPayload: Record<string, unknown>;
  publicPayload?: Record<string, unknown>;
  errorCode?: string;
  pauseReason?: string;
  recoverable?: boolean;
}

export interface PiRuntimeEvent {
  type: string;
  [key: string]: unknown;
}
