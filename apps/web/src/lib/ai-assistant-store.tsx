import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useEffect,
  type ReactNode,
  type Dispatch,
} from "react";
import {
  getChatConversationMessages,
  listChatConversations,
  type ChatConversationRead,
} from "@/lib/api";
import { getStoredValue, removeStoredValue, setStoredValue } from "@/lib/browser-storage";

/* ─── Types ─── */

export type AssistantMode = "panel" | "command" | "inline";
export type AssistantReasoningEffort = "low" | "medium" | "high" | "ultra" | "max";
export type AssistantStatus =
  | "idle"
  | "thinking"
  | "needs_input"
  | "needs_confirmation"
  | "executing_tool"
  | "running_workflow"
  | "completed"
  | "failed";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  attachments?: ChatMessageAttachment[];
}

export interface ChatMessageAttachment {
  id: string;
  name: string;
  kind: "file" | "image";
  size: number;
  status: "ready" | "uploaded" | "failed";
  documentId?: string;
  previewUrl?: string;
}

export interface AssistantRequestAttachment {
  id?: string;
  name: string;
  kind: "file" | "image";
  mime_type?: string;
  size?: number;
  extraction_status?: "extracted" | "empty" | "unsupported" | "failed";
  extracted_text?: string;
  document_id?: string;
  error?: string | null;
}

interface SendAssistantOptions {
  displayContent?: string;
  attachments?: ChatMessageAttachment[];
  requestAttachments?: AssistantRequestAttachment[];
  providerConfigId?: string | null;
  reasoningEffort?: AssistantReasoningEffort;
}

export interface AssistantConfirmationRequest {
  messageId?: string;
  toolName: string;
  arguments: Record<string, unknown>;
  message: string;
}

export interface AssistantExecutionItem {
  id: string;
  messageId?: string;
  kind: "intent" | "tool" | "workflow";
  toolName?: string;
  runId?: string;
  status: "pending" | "running" | "succeeded" | "failed";
  title: string;
  summary?: string;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
  errorMessage?: string;
  errorCode?: string;
  currentNode?: string | null;
  nodes?: WorkflowNodeProgress[];
  reviewResult?: WorkflowReviewResult | null;
  isWaitingApproval?: boolean;
  approvalMessage?: string | null;
  isRunning?: boolean;
  timestamp: number;
}

export interface WorkflowNodeProgress {
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  startedAt?: string;
  completedAt?: string;
  error?: string;
}

export interface WorkflowReviewResult {
  score: number;
  feedback?: string;
  pass: boolean;
}

export interface PageContext {
  page: string;
  projectId?: string;
  sectionKey?: string;
}

export interface CommandDef {
  id: string;
  label: string;
  labelEn: string;
  icon: string;
  group: "navigation" | "action" | "ai";
  shortcut?: string;
  action: () => void;
}

export interface InlineSuggestion {
  id: string;
  text: string;
  action: () => void;
}

export interface AIAssistantState {
  /* visibility */
  isOpen: boolean;
  mode: AssistantMode;
  /* chat */
  currentConversationId: string | null;
  conversations: ChatConversationRead[];
  messages: ChatMessage[];
  activeAssistantMessageId: string | null;
  assistantContentBuffers: Record<string, string>;
  status: AssistantStatus;
  executionItems: AssistantExecutionItem[];
  pendingConfirmation: AssistantConfirmationRequest | null;
  sessionError: string | null;
  selectedProviderConfigId: string | null;
  reasoningEffort: AssistantReasoningEffort;
  /* context */
  currentContext: PageContext;
  /* inline suggestions */
  suggestions: InlineSuggestion[];
  /* commands registry */
  commands: CommandDef[];
}

/* ─── Actions ─── */

type Action =
  | { type: "OPEN"; mode?: AssistantMode }
  | { type: "CLOSE" }
  | { type: "TOGGLE"; mode?: AssistantMode }
  | { type: "SET_MODE"; mode: AssistantMode }
  | { type: "SET_CURRENT_CONVERSATION"; conversationId: string | null }
  | { type: "SET_CONVERSATIONS"; conversations: ChatConversationRead[] }
  | { type: "UPDATE_CONVERSATION_TITLE"; conversationId: string; title: string }
  | { type: "ADD_MESSAGE"; message: ChatMessage }
  | { type: "REPLACE_MESSAGES"; messages: ChatMessage[] }
  | { type: "UPDATE_LAST_ASSISTANT"; content: string }
  | { type: "FLUSH_READY_ASSISTANT_CONTENT" }
  | { type: "SET_ACTIVE_ASSISTANT_MESSAGE"; messageId: string | null }
  | { type: "SET_STATUS"; status: AssistantStatus }
  | { type: "ADD_EXECUTION_ITEM"; item: AssistantExecutionItem }
  | { type: "UPDATE_EXECUTION_ITEM"; toolName: string; runId?: string; patch: Partial<AssistantExecutionItem> }
  | { type: "MERGE_WORKFLOW_NODE"; runId: string; node: WorkflowNodeProgress; currentNode?: string | null }
  | { type: "SET_SESSION_ERROR"; message: string; errorCode?: string }
  | { type: "SET_PENDING_CONFIRMATION"; confirmation: AssistantConfirmationRequest | null }
  | { type: "SET_SELECTED_PROVIDER_CONFIG"; providerConfigId: string | null }
  | { type: "SET_REASONING_EFFORT"; effort: AssistantReasoningEffort }
  | { type: "CLEAR_TRANSIENT_STATE" }
  | { type: "CLEAR_MESSAGES" }
  | { type: "SET_CONTEXT"; context: PageContext }
  | { type: "SET_SUGGESTIONS"; suggestions: InlineSuggestion[] }
  | { type: "REGISTER_COMMANDS"; commands: CommandDef[] };

/* ─── Reducer ─── */

const initialState: AIAssistantState = {
  isOpen: false,
  mode: "panel",
  currentConversationId: null,
  conversations: [],
  messages: [],
  activeAssistantMessageId: null,
  assistantContentBuffers: {},
  status: "idle",
  executionItems: [],
  pendingConfirmation: null,
  sessionError: null,
  selectedProviderConfigId: getStoredValue("assistantProviderConfigId"),
  reasoningEffort: parseReasoningEffort(getStoredValue("assistantReasoningEffort")),
  currentContext: { page: "/" },
  suggestions: [],
  commands: [],
};

function parseReasoningEffort(value: string | null): AssistantReasoningEffort {
  if (value === "low" || value === "medium" || value === "high" || value === "ultra" || value === "max") {
    return value;
  }
  return "medium";
}

function createExecutionId(prefix: string, key?: string) {
  const safeKey = key ? `-${key.replace(/[^a-zA-Z0-9_-]/g, "")}` : "";
  return `${prefix}${safeKey}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getLastAssistantMessageId(state: AIAssistantState) {
  for (let i = state.messages.length - 1; i >= 0; i--) {
    if (state.messages[i].role === "assistant") return state.messages[i].id;
  }
  return null;
}

function hasOpenActivity(state: AIAssistantState, messageId: string) {
  return state.executionItems.some(
    (item) => item.messageId === messageId && (item.status === "running" || item.status === "pending"),
  );
}

function appendAssistantContent(state: AIAssistantState, messageId: string, content: string): AIAssistantState {
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === messageId && message.role === "assistant"
        ? { ...message, content: message.content + content }
        : message,
    ),
  };
}

function appendOrBufferAssistantContent(state: AIAssistantState, content: string): AIAssistantState {
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  if (!messageId) return state;
  if (!hasOpenActivity(state, messageId)) {
    return appendAssistantContent(state, messageId, content);
  }
  return {
    ...state,
    assistantContentBuffers: {
      ...state.assistantContentBuffers,
      [messageId]: `${state.assistantContentBuffers[messageId] ?? ""}${content}`,
    },
  };
}

function flushAssistantBuffer(state: AIAssistantState, messageId: string): AIAssistantState {
  const buffered = state.assistantContentBuffers[messageId];
  if (!buffered) return state;
  const nextBuffers = { ...state.assistantContentBuffers };
  delete nextBuffers[messageId];
  return {
    ...appendAssistantContent(state, messageId, buffered),
    assistantContentBuffers: nextBuffers,
  };
}

function flushReadyAssistantBuffers(state: AIAssistantState): AIAssistantState {
  return Object.keys(state.assistantContentBuffers).reduce((nextState, messageId) => {
    if (hasOpenActivity(nextState, messageId)) return nextState;
    return flushAssistantBuffer(nextState, messageId);
  }, state);
}

function reducer(state: AIAssistantState, action: Action): AIAssistantState {
  switch (action.type) {
    case "OPEN":
      return {
        ...state,
        isOpen: true,
        mode: action.mode ?? state.mode,
      };
    case "CLOSE":
      return { ...state, isOpen: false };
    case "TOGGLE":
      if (state.isOpen && (!action.mode || action.mode === state.mode)) {
        return { ...state, isOpen: false };
      }
      return {
        ...state,
        isOpen: true,
        mode: action.mode ?? state.mode,
      };
    case "SET_MODE":
      return { ...state, mode: action.mode };
    case "SET_CURRENT_CONVERSATION":
      return { ...state, currentConversationId: action.conversationId };
    case "SET_CONVERSATIONS":
      return { ...state, conversations: action.conversations };
    case "UPDATE_CONVERSATION_TITLE":
      return {
        ...state,
        conversations: state.conversations.map((conversation) =>
          conversation.id === action.conversationId
            ? { ...conversation, title: action.title }
            : conversation,
        ),
      };
    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };
    case "REPLACE_MESSAGES":
      return {
        ...state,
        messages: action.messages,
        activeAssistantMessageId: null,
        assistantContentBuffers: {},
        executionItems: [],
        pendingConfirmation: null,
        sessionError: null,
      };
    case "UPDATE_LAST_ASSISTANT": {
      return appendOrBufferAssistantContent(state, action.content);
    }
    case "FLUSH_READY_ASSISTANT_CONTENT":
      return flushReadyAssistantBuffers(state);
    case "SET_ACTIVE_ASSISTANT_MESSAGE":
      return { ...state, activeAssistantMessageId: action.messageId };
    case "SET_STATUS":
      return { ...state, status: action.status };
    case "ADD_EXECUTION_ITEM":
      return {
        ...state,
        executionItems: [
          ...state.executionItems,
          { ...action.item, messageId: action.item.messageId ?? state.activeAssistantMessageId ?? undefined },
        ],
      };
    case "UPDATE_EXECUTION_ITEM": {
      let updated = false;
      const executionItems = state.executionItems.map((item) => {
        const matches = action.runId
          ? item.runId === action.runId
          : item.toolName === action.toolName && item.messageId === state.activeAssistantMessageId;
        if (matches) {
          updated = true;
          return { ...item, ...action.patch };
        }
        return item;
      });
      if (!updated) {
        executionItems.push({
          id: createExecutionId("exec", action.runId ?? action.toolName),
          messageId: state.activeAssistantMessageId ?? undefined,
          kind: "tool",
          toolName: action.toolName,
          runId: action.runId,
          status: action.patch.status ?? "pending",
          title: action.toolName,
          timestamp: Date.now(),
          ...action.patch,
        });
      }
      return flushReadyAssistantBuffers({ ...state, executionItems });
    }
    case "MERGE_WORKFLOW_NODE": {
      const executionItems = state.executionItems.map((item) => {
        if (item.runId !== action.runId) return item;
        const status: AssistantExecutionItem["status"] =
          item.status === "failed" || item.status === "succeeded" ? item.status : "running";
        const nodes = item.nodes ?? [];
        const idx = nodes.findIndex((node) => node.name === action.node.name);
        const nextNodes = [...nodes];
        if (idx >= 0) {
          nextNodes[idx] = { ...nextNodes[idx], ...action.node };
        } else {
          nextNodes.push(action.node);
        }
        return {
          ...item,
          nodes: nextNodes,
          currentNode: action.currentNode,
          status,
          isRunning: true,
        };
      });
      return flushReadyAssistantBuffers({ ...state, executionItems });
    }
    case "SET_PENDING_CONFIRMATION":
      return {
        ...state,
        pendingConfirmation: action.confirmation
          ? { ...action.confirmation, messageId: action.confirmation.messageId ?? state.activeAssistantMessageId ?? undefined }
          : null,
      };
    case "SET_SELECTED_PROVIDER_CONFIG":
      return { ...state, selectedProviderConfigId: action.providerConfigId };
    case "SET_REASONING_EFFORT":
      return { ...state, reasoningEffort: action.effort };
    case "SET_SESSION_ERROR":
      return {
        ...state,
        status: "failed",
        sessionError: action.message,
        executionItems: [
          ...state.executionItems,
          {
            id: createExecutionId("exec-error", action.errorCode),
            kind: "tool",
            status: "failed",
            title: action.errorCode ?? "assistant_error",
            errorMessage: action.message,
            errorCode: action.errorCode,
            timestamp: Date.now(),
          },
        ],
      };
    case "CLEAR_TRANSIENT_STATE":
      return {
        ...state,
        pendingConfirmation: null,
        sessionError: null,
      };
    case "CLEAR_MESSAGES":
      return {
        ...state,
        messages: [],
        activeAssistantMessageId: null,
        assistantContentBuffers: {},
        executionItems: [],
        pendingConfirmation: null,
        sessionError: null,
      };
    case "SET_CONTEXT":
      return { ...state, currentContext: action.context };
    case "SET_SUGGESTIONS":
      return { ...state, suggestions: action.suggestions };
    case "REGISTER_COMMANDS":
      return { ...state, commands: action.commands };
    default:
      return state;
  }
}

function handleAssistantSsePart(part: string, dispatch: Dispatch<Action>) {
  const lines = part.split("\n");
  let eventType = "";
  let dataJson = "";
  for (const line of lines) {
    if (line.startsWith("event: ")) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      dataJson = line.slice(6);
    }
  }
  if (!eventType || !dataJson) return;

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(dataJson);
  } catch {
    return;
  }

  const state = typeof parsed.state === "string" ? (parsed.state as AssistantStatus) : undefined;
  if (state) {
    dispatch({ type: "SET_STATUS", status: state });
  }

  if (eventType === "assistant.start") {
    const conversationId = parsed.conversation_id;
    if (typeof conversationId === "string") {
      dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId });
    }
    return;
  }

  if (eventType === "assistant.intent_detected") {
    return;
  }

  if (eventType === "assistant.confirmation_requested") {
    const toolName = String(parsed.tool_name ?? "");
    const args = asRecord(parsed.arguments);
    dispatch({
      type: "SET_PENDING_CONFIRMATION",
      confirmation: {
        toolName,
        arguments: args,
        message: String(parsed.message ?? "Confirm this action"),
      },
    });
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      patch: {
        kind: "tool",
        status: "pending",
        title: toolName,
        arguments: args,
        summary: String(parsed.message ?? ""),
      },
    });
    return;
  }

  if (eventType === "assistant.tool_started") {
    const toolName = String(parsed.tool_name ?? "");
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      patch: {
        kind: "tool",
        status: "running",
        title: toolName,
        arguments: asRecord(parsed.arguments),
      },
    });
    return;
  }

  if (eventType === "assistant.workflow_started") {
    const toolName = String(parsed.tool_name ?? "");
    const result = asRecord(parsed.result);
    const runId = typeof result.run_id === "string" ? result.run_id : undefined;
    dispatch({ type: "CLEAR_TRANSIENT_STATE" });
    dispatch({
      type: "ADD_EXECUTION_ITEM",
      item: {
        id: `workflow-${Date.now()}`,
        kind: "workflow",
        toolName,
        runId,
        status: "running",
        title: toolName,
        arguments: asRecord(parsed.arguments),
        result,
        isRunning: true,
        timestamp: Date.now(),
      },
    });
    if (runId) {
      dispatch({ type: "SET_STATUS", status: "running_workflow" });
      void streamWorkflowRun(runId, dispatch).catch((error) => {
        dispatch({
          type: "UPDATE_EXECUTION_ITEM",
          toolName,
          runId,
          patch: {
            status: "failed",
            isRunning: false,
            errorMessage: error instanceof Error ? error.message : "Workflow stream failed",
          },
        });
        dispatch({ type: "SET_STATUS", status: "failed" });
      });
    }
    return;
  }

  if (eventType === "assistant.tool_succeeded") {
    const toolName = String(parsed.tool_name ?? "");
    const result = asRecord(parsed.result);
    if (typeof result.run_id === "string") {
      dispatch({
        type: "UPDATE_EXECUTION_ITEM",
        toolName,
        runId: result.run_id,
        patch: {
          status: "running",
          result,
          summary: String(parsed.summary ?? ""),
          isRunning: true,
        },
      });
      return;
    }
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      patch: {
        status: "succeeded",
        result,
        summary: String(parsed.summary ?? ""),
      },
    });
    if (toolName === "open_page" && typeof result.route === "string") {
      window.history.pushState({}, "", result.route);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
    return;
  }

  if (eventType === "assistant.tool_failed") {
    const toolName = String(parsed.tool_name ?? "");
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      patch: {
        status: "failed",
        errorMessage: String(parsed.error_message ?? "Tool failed"),
      },
    });
    return;
  }

  if (eventType === "assistant.message" && typeof parsed.content === "string") {
    dispatch({ type: "UPDATE_LAST_ASSISTANT", content: parsed.content });
    return;
  }

  if (eventType === "assistant.end") {
    const conversationId = parsed.conversation_id;
    if (typeof conversationId === "string") {
      dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId });
    }
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

/* ─── Context ─── */

interface AIAssistantContextValue {
  state: AIAssistantState;
  dispatch: Dispatch<Action>;
  /* convenience helpers */
  open: (mode?: AssistantMode) => void;
  close: () => void;
  toggle: (mode?: AssistantMode) => void;
  sendMessage: (
    content: string,
    options?: SendAssistantOptions,
  ) => Promise<void>;
  setSelectedProviderConfig: (providerConfigId: string | null) => void;
  setReasoningEffort: (effort: AssistantReasoningEffort) => void;
  confirmAssistantAction: (approved: boolean) => Promise<void>;
  executeCommand: (commandId: string) => void;
  refreshConversations: () => Promise<void>;
  loadConversation: (conversationId: string) => Promise<void>;
  startNewConversation: () => void;
  updateConversationTitle: (conversationId: string, title: string) => void;
}

const AIAssistantContext = createContext<AIAssistantContextValue | null>(null);

/* ─── Provider ─── */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getAuthToken() {
  return getStoredValue("token");
}

async function streamWorkflowRun(
  runId: string,
  dispatch: Dispatch<Action>,
  onTerminal?: () => void,
) {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE}/drafting/runs/${runId}/stream`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok || !response.body) {
    throw new Error(`Workflow stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const updateWorkflow = (patch: Partial<AssistantExecutionItem>) => {
    dispatch({ type: "UPDATE_EXECUTION_ITEM", toolName: "start_draft_section", runId, patch });
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const parsed = parseSsePart(part);
      if (!parsed) continue;

      const { eventType, data } = parsed;
      if (eventType === "connected") {
        updateWorkflow({
          status: "running",
          isRunning: true,
          currentNode: null,
        });
        dispatch({ type: "SET_STATUS", status: "running_workflow" });
      } else if (eventType === "node_started") {
        const nodeName = typeof data.node_name === "string" ? data.node_name : "unknown";
        dispatch({
          type: "MERGE_WORKFLOW_NODE",
          runId,
          node: { name: nodeName, status: "running", startedAt: new Date().toISOString() },
          currentNode: nodeName,
        });
      } else if (eventType === "node_completed") {
        const nodeName = typeof data.node_name === "string" ? data.node_name : "unknown";
        dispatch({
          type: "MERGE_WORKFLOW_NODE",
          runId,
          node: { name: nodeName, status: "completed", completedAt: new Date().toISOString() },
          currentNode: null,
        });
      } else if (eventType === "review_result") {
        updateWorkflow({
          reviewResult: {
            score: Number(data.score ?? 0),
            feedback: typeof data.feedback === "string" ? data.feedback : "",
            pass: Boolean(data.passed ?? data.pass),
          },
        });
      } else if (eventType === "human_approval_required") {
        updateWorkflow({
          status: "running",
          isWaitingApproval: true,
          approvalMessage: typeof data.draft_preview === "string" ? data.draft_preview : "等待人工审核",
        });
      } else if (eventType === "graph_completed") {
        updateWorkflow({
          status: data.persisted ? "succeeded" : "failed",
          isRunning: false,
          isWaitingApproval: false,
          currentNode: null,
        });
        dispatch({ type: "SET_STATUS", status: data.persisted ? "completed" : "failed" });
        onTerminal?.();
        return;
      } else if (eventType === "graph_error") {
        updateWorkflow({
          status: "failed",
          isRunning: false,
          currentNode: null,
          errorMessage: typeof data.error_message === "string" ? data.error_message : "Workflow failed",
        });
        dispatch({ type: "SET_STATUS", status: "failed" });
        onTerminal?.();
        return;
      }
    }
  }

  onTerminal?.();
}

function parseSsePart(part: string): { eventType: string; data: Record<string, unknown> } | null {
  const lines = part.split("\n");
  let eventType = "";
  let dataJson = "";
  for (const line of lines) {
    if (line.startsWith("event: ")) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      dataJson = line.slice(6);
    }
  }
  if (!eventType || !dataJson) return null;
  try {
    return { eventType, data: JSON.parse(dataJson) as Record<string, unknown> };
  } catch {
    return null;
  }
}


export function isAssistantBusy(status: AssistantStatus) {
  return ["thinking", "executing_tool", "running_workflow"].includes(status);
}

export function AIAssistantProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const open = useCallback(
    (mode?: AssistantMode) => dispatch({ type: "OPEN", mode }),
    [],
  );
  const close = useCallback(() => dispatch({ type: "CLOSE" }), []);
  const toggle = useCallback(
    (mode?: AssistantMode) => dispatch({ type: "TOGGLE", mode }),
    [],
  );

  const refreshConversations = useCallback(async () => {
    try {
      const conversations = await listChatConversations(
        state.currentContext.projectId,
      );
      dispatch({ type: "SET_CONVERSATIONS", conversations });
    } catch (error) {
      console.error("Failed to load chat conversations:", error);
    }
  }, [state.currentContext.projectId]);

  const loadConversation = useCallback(async (conversationId: string) => {
    dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId });
    dispatch({ type: "CLEAR_MESSAGES" });
    dispatch({ type: "SET_STATUS", status: "thinking" });
    try {
      const history = await getChatConversationMessages(conversationId);
      dispatch({
        type: "REPLACE_MESSAGES",
        messages: history.items.map((item, index) => ({
          id: `${conversationId}-${index}`,
          role: item.role,
          content: item.content,
          timestamp: Date.now() + index,
        })),
      });
      dispatch({ type: "OPEN", mode: "panel" });
    } catch (error) {
      console.error("Failed to load chat history:", error);
    } finally {
      dispatch({ type: "SET_STATUS", status: "idle" });
    }
  }, []);

  const updateConversationTitle = useCallback((conversationId: string, title: string) => {
    dispatch({ type: "UPDATE_CONVERSATION_TITLE", conversationId, title });
  }, []);

  const setSelectedProviderConfig = useCallback((providerConfigId: string | null) => {
    if (providerConfigId) {
      setStoredValue("assistantProviderConfigId", providerConfigId);
    } else {
      removeStoredValue("assistantProviderConfigId");
    }
    dispatch({ type: "SET_SELECTED_PROVIDER_CONFIG", providerConfigId });
  }, []);

  const setReasoningEffort = useCallback((effort: AssistantReasoningEffort) => {
    setStoredValue("assistantReasoningEffort", effort);
    dispatch({ type: "SET_REASONING_EFFORT", effort });
  }, []);

  const startNewConversation = useCallback(() => {
    dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId: null });
    dispatch({ type: "CLEAR_MESSAGES" });
    dispatch({ type: "SET_STATUS", status: "idle" });
    dispatch({ type: "OPEN", mode: "panel" });
  }, []);

  useEffect(() => {
    if (state.isOpen && state.mode === "panel") {
      void refreshConversations();
    }
  }, [state.isOpen, state.mode, refreshConversations]);

  const sendAssistantRequest = useCallback(
    async (
      content: string,
      options?: SendAssistantOptions,
      confirmation?: { approved: boolean; tool_name: string; arguments: Record<string, unknown> },
    ) => {
      const displayContent = confirmation
        ? confirmation.approved
          ? "确认执行"
          : "取消操作"
        : (options?.displayContent ?? content).trim();
      if (!displayContent || isAssistantBusy(state.status)) return;

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: displayContent,
        timestamp: Date.now(),
        attachments: options?.attachments,
      };
      dispatch({ type: "CLEAR_TRANSIENT_STATE" });
      dispatch({ type: "ADD_MESSAGE", message: userMsg });
      dispatch({ type: "SET_STATUS", status: "thinking" });

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
      };
      dispatch({ type: "ADD_MESSAGE", message: aiMsg });
      dispatch({ type: "SET_ACTIVE_ASSISTANT_MESSAGE", messageId: aiMsg.id });

      try {
        const token = getAuthToken();
        const response = await fetch(`${API_BASE}/assistant/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: content,
            project_id: state.currentContext.projectId,
            conversation_id: state.currentConversationId,
            provider_config_id: options?.providerConfigId ?? state.selectedProviderConfigId,
            reasoning_effort: options?.reasoningEffort ?? state.reasoningEffort,
            confirmation,
            attachments: options?.requestAttachments ?? [],
          }),
        });

        if (!response.ok) {
          const errText = await response.text().catch(() => "");
          let errorCode = "";
          let errorMessage = `API ${response.status}`;
          try {
            const parsed = JSON.parse(errText);
            errorCode = String(parsed.error ?? "");
            errorMessage = String(parsed.message ?? parsed.detail ?? errorMessage);
          } catch {
            if (errText.trim()) {
              errorMessage = errText;
            }
          }
          throw Object.assign(new Error(errorMessage), {
            status: response.status,
            errorCode,
          });
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (reader) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            handleAssistantSsePart(part, dispatch);
          }
        }
      } catch (err) {
        console.error("AI assistant error:", err);
        const status = typeof (err as { status?: number }).status === "number" ? (err as { status?: number }).status : undefined;
        const errorCode = typeof (err as { errorCode?: string }).errorCode === "string" ? (err as { errorCode?: string }).errorCode : undefined;
        const message = err instanceof Error ? err.message : "Something went wrong. Please try again.";
        const friendly =
          status === 403 || errorCode === "usage_limit_exceeded"
            ? "你的试用额度已用完，请升级计划或稍后再试。"
            : message;
        dispatch({ type: "SET_SESSION_ERROR", message: friendly, errorCode });
      } finally {
        void refreshConversations();
      }
    },
    [
      refreshConversations,
      state.currentContext.projectId,
      state.currentConversationId,
      state.reasoningEffort,
      state.selectedProviderConfigId,
      state.status,
    ],
  );

  const sendMessage = useCallback(
    async (content: string, options?: SendAssistantOptions) => {
      await sendAssistantRequest(content, options);
    },
    [sendAssistantRequest],
  );

  const confirmAssistantAction = useCallback(
    async (approved: boolean) => {
      const pending = state.pendingConfirmation;
      if (!pending) return;
      dispatch({ type: "SET_PENDING_CONFIRMATION", confirmation: null });
      await sendAssistantRequest(pending.message, undefined, {
        approved,
        tool_name: pending.toolName,
        arguments: pending.arguments,
      });
    },
    [sendAssistantRequest, state.pendingConfirmation],
  );

  const executeCommand = useCallback(
    (commandId: string) => {
      const cmd = state.commands.find((c) => c.id === commandId);
      if (cmd) {
        dispatch({ type: "CLOSE" });
        cmd.action();
      }
    },
    [state.commands],
  );

  return (
    <AIAssistantContext.Provider
      value={{
        state,
        dispatch,
        open,
        close,
        toggle,
        sendMessage,
        setSelectedProviderConfig,
        setReasoningEffort,
        confirmAssistantAction,
        executeCommand,
        refreshConversations,
        loadConversation,
        startNewConversation,
        updateConversationTitle,
      }}
    >
      {children}
    </AIAssistantContext.Provider>
  );
}

/* ─── Hook ─── */

export function useAIAssistant() {
  const ctx = useContext(AIAssistantContext);
  if (!ctx) {
    throw new Error("useAIAssistant must be used within AIAssistantProvider");
  }
  return ctx;
}
