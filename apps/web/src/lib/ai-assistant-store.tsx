import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
  type Dispatch,
} from "react";
import {
  cancelRuntimeWorkflow,
  forkChatConversation,
  getChatConversationMessages,
  listRuntimeEvents,
  listRuntimeRuns,
  listChatConversations,
  type ChatConversationRead,
  type ChatMessageRead,
} from "@/lib/api";
import {
  getStoredValue,
  removeStoredValue,
  setStoredValue,
} from "@/lib/browser-storage";
import {
  advanceRuntimeSequenceCursor,
  isRuntimeSequenceNewer,
  isTerminalRuntimeEvent,
  recoverRuntimeMessageFromEvents,
  runtimeEventToAssistantEvents,
  type RuntimeEventCursor,
} from "@/lib/runtime-event-feed";
import {
  appendNarrativePart,
  appendReasoningPart,
  completeReasoningPart,
  ensureTurnPart,
  narrativeTextFromParts,
  type AssistantTranscriptPart,
} from "@/lib/assistant-transcript";
import i18n from "@/lib/i18n";

/* ─── Types ─── */

export type AssistantMode = "panel" | "command" | "inline";
export type AssistantReasoningEffort = "low" | "medium" | "high" | "extra" | "max";
export type AssistantApprovalMode = "request_approval" | "risky_only" | "full_access" | "custom";
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
  /** Server primary key when this message was persisted. */
  durableId?: string;
  /** Durable runtime owner for replaying this response's event tree. */
  runtimeRunId?: string;
  role: "user" | "assistant";
  content: string;
  /** Ordered narrative/turn parts for Pi-style interleaved rendering. */
  transcriptParts?: AssistantTranscriptPart[];
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
  conversationId?: string | null;
  attachments?: ChatMessageAttachment[];
  requestAttachments?: AssistantRequestAttachment[];
  providerConfigId?: string | null;
  reasoningEffort?: AssistantReasoningEffort;
  approvalMode?: AssistantApprovalMode;
}

export interface AssistantConfirmationRequest {
  messageId?: string;
  approvalId?: string;
  runtimeRunId?: string;
  toolName: string;
  arguments: Record<string, unknown>;
  message: string;
  requiresTypedConfirmation?: boolean;
  expectedText?: string;
}

export interface AssistantExecutionItem {
  id: string;
  messageId?: string;
  kind: "intent" | "tool" | "workflow";
  toolName?: string;
  toolCallId?: string;
  turnId?: string;
  runId?: string;
  runtimeRunId?: string;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  title: string;
  summary?: string;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
  errorMessage?: string;
  errorCode?: string;
  retryAttempt?: number;
  retryMaxAttempts?: number;
  currentNode?: string | null;
  nodes?: WorkflowNodeProgress[];
  reviewResult?: WorkflowReviewResult | null;
  isWaitingApproval?: boolean;
  isCancellationRequested?: boolean;
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
  /** True only while this browser is consuming an assistant SSE response. */
  isStreaming: boolean;
  status: AssistantStatus;
  executionItems: AssistantExecutionItem[];
  pendingConfirmation: AssistantConfirmationRequest | null;
  sessionError: string | null;
  selectedProviderConfigId: string | null;
  reasoningEffort: AssistantReasoningEffort;
  approvalMode: AssistantApprovalMode;
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
  | { type: "SET_LAST_USER_DURABLE_ID"; durableId: string }
  | { type: "UPDATE_LAST_ASSISTANT"; content: string }
  | {
      type: "APPEND_VISIBLE_REASONING";
      content: string;
      turnId?: string;
      title?: string;
      source?: "provider" | "harness";
    }
  | { type: "COMPLETE_VISIBLE_REASONING"; turnId?: string }
  | { type: "ENSURE_TRANSCRIPT_TURN"; turnId: string }
  | { type: "FINALIZE_OPEN_EXECUTION_ITEMS"; runtimeRunId?: string; failed?: boolean }
  | { type: "FLUSH_READY_ASSISTANT_CONTENT" }
  | { type: "SET_ACTIVE_ASSISTANT_MESSAGE"; messageId: string | null }
  | { type: "SET_STREAMING"; streaming: boolean }
  | { type: "STOP_ACTIVE_RESPONSE" }
  | { type: "SET_STATUS"; status: AssistantStatus }
  | { type: "ADD_EXECUTION_ITEM"; item: AssistantExecutionItem }
  | {
      type: "UPDATE_EXECUTION_ITEM";
      toolName: string;
      toolCallId?: string;
      turnId?: string;
      runId?: string;
      runtimeRunId?: string;
      patch: Partial<AssistantExecutionItem>;
    }
  | {
      type: "MERGE_WORKFLOW_NODE";
      runId?: string;
      runtimeRunId?: string;
      node: WorkflowNodeProgress;
      currentNode?: string | null;
    }
  | { type: "SET_SESSION_ERROR"; message: string; errorCode?: string }
  | { type: "SET_PENDING_CONFIRMATION"; confirmation: AssistantConfirmationRequest | null }
  | { type: "SET_SELECTED_PROVIDER_CONFIG"; providerConfigId: string | null }
  | { type: "SET_REASONING_EFFORT"; effort: AssistantReasoningEffort }
  | { type: "SET_APPROVAL_MODE"; mode: AssistantApprovalMode }
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
  isStreaming: false,
  status: "idle",
  executionItems: [],
  pendingConfirmation: null,
  sessionError: null,
  selectedProviderConfigId: getStoredValue("assistantProviderConfigId"),
  reasoningEffort: parseReasoningEffort(getStoredValue("assistantReasoningEffort")),
  approvalMode: parseApprovalMode(getStoredValue("assistantApprovalMode")),
  currentContext: { page: "/" },
  suggestions: [],
  commands: [],
};

function parseReasoningEffort(value: string | null): AssistantReasoningEffort {
  if (value === "ultra") {
    return "extra";
  }
  if (value === "low" || value === "medium" || value === "high" || value === "extra" || value === "max") {
    return value;
  }
  return "medium";
}

function parseApprovalMode(value: string | null): AssistantApprovalMode {
  if (value === "request_approval" || value === "risky_only" || value === "full_access" || value === "custom") {
    return value;
  }
  return "risky_only";
}

function createExecutionId(prefix: string, key?: string) {
  const safeKey = key ? `-${key.replace(/[^a-zA-Z0-9_-]/g, "")}` : "";
  return `${prefix}${safeKey}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function isOpenExecutionStatus(status: AssistantExecutionItem["status"]) {
  return status === "running" || status === "pending";
}

function executionIdentity(item: AssistantExecutionItem) {
  if (item.toolCallId) return `tool-call:${item.toolCallId}`;
  if (item.runtimeRunId) return `runtime-run:${item.runtimeRunId}`;
  if (item.runId) return `run:${item.runId}`;
  return null;
}

function matchExecutionItem(
  item: AssistantExecutionItem,
  action: {
    toolName: string;
    toolCallId?: string;
    turnId?: string;
    runId?: string;
    runtimeRunId?: string;
  },
  activeAssistantMessageId: string | null,
): boolean {
  // Prefer stable tool_call_id so concurrent tools never clobber each other.
  if (action.toolCallId && item.toolCallId) {
    return item.toolCallId === action.toolCallId;
  }
  if (action.runId && item.runId === action.runId) {
    return true;
  }

  const sameTool = item.toolName === action.toolName;
  const sameMessage =
    !item.messageId || !activeAssistantMessageId || item.messageId === activeAssistantMessageId;
  const sameRuntime =
    !action.runtimeRunId || !item.runtimeRunId || item.runtimeRunId === action.runtimeRunId;

  // Live harness emits tool_started with tool_call_id; durable CAPABILITY_*
  // events often omit it (or the reverse order). Always merge onto the open
  // card for the same tool in the active message/run so we never leave a
  // ghost "running" card beside the completed one.
  if (sameTool && sameMessage && sameRuntime && isOpenExecutionStatus(item.status)) {
    return true;
  }

  if (
    action.runtimeRunId &&
    item.runtimeRunId === action.runtimeRunId &&
    sameTool
  ) {
    if (action.turnId && item.turnId && action.turnId === item.turnId) return true;
    if (!action.toolCallId || !item.toolCallId) return true;
  }

  return sameTool && item.messageId === activeAssistantMessageId && !action.toolCallId;
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
    messages: state.messages.map((message) => {
      if (message.id !== messageId || message.role !== "assistant") return message;
      const transcriptParts = appendNarrativePart(message.transcriptParts, content);
      return {
        ...message,
        content: narrativeTextFromParts(transcriptParts) || message.content + content,
        transcriptParts,
      };
    }),
  };
}

function appendAssistantReasoning(
  state: AIAssistantState,
  content: string,
  turnId?: string,
  title?: string,
  source?: "provider" | "harness",
): AIAssistantState {
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  if (!messageId) return state;
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === messageId && message.role === "assistant"
        ? {
            ...message,
            transcriptParts: appendReasoningPart(message.transcriptParts, content, {
              turnId,
              title,
              source,
            }),
          }
        : message,
    ),
  };
}

function completeAssistantReasoning(state: AIAssistantState, turnId?: string): AIAssistantState {
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  if (!messageId) return state;
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === messageId && message.role === "assistant"
        ? { ...message, transcriptParts: completeReasoningPart(message.transcriptParts, turnId) }
        : message,
    ),
  };
}

function ensureAssistantTurnPart(state: AIAssistantState, turnId: string | undefined): AIAssistantState {
  if (!turnId) return state;
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  if (!messageId) return state;
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === messageId && message.role === "assistant"
        ? { ...message, transcriptParts: ensureTurnPart(message.transcriptParts, turnId) }
        : message,
    ),
  };
}

function appendOrBufferAssistantContent(state: AIAssistantState, content: string): AIAssistantState {
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  if (!messageId) return state;
  // The runtime is the chronology authority. Rendering immediately preserves
  // reasoning -> tool -> answer order instead of replaying prose at the end.
  return appendAssistantContent(state, messageId, content);
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
    case "SET_LAST_USER_DURABLE_ID": {
      let messageIndex = -1;
      for (let index = state.messages.length - 1; index >= 0; index -= 1) {
        if (state.messages[index].role === "user") {
          messageIndex = index;
          break;
        }
      }
      if (messageIndex < 0) return state;
      const messages = [...state.messages];
      messages[messageIndex] = { ...messages[messageIndex], durableId: action.durableId };
      return { ...state, messages };
    }
    case "UPDATE_LAST_ASSISTANT": {
      return appendOrBufferAssistantContent(state, action.content);
    }
    case "APPEND_VISIBLE_REASONING":
      return appendAssistantReasoning(state, action.content, action.turnId, action.title, action.source);
    case "COMPLETE_VISIBLE_REASONING":
      return completeAssistantReasoning(state, action.turnId);
    case "ENSURE_TRANSCRIPT_TURN":
      return ensureAssistantTurnPart(state, action.turnId);
    case "FINALIZE_OPEN_EXECUTION_ITEMS": {
      const executionItems = state.executionItems.map((item) => {
        if (!isOpenExecutionStatus(item.status)) return item;
        if (action.runtimeRunId && item.runtimeRunId && item.runtimeRunId !== action.runtimeRunId) {
          return item;
        }
        if (
          !action.runtimeRunId &&
          item.messageId &&
          state.activeAssistantMessageId &&
          item.messageId !== state.activeAssistantMessageId
        ) {
          return item;
        }
        const nextStatus: AssistantExecutionItem["status"] = action.failed ? "failed" : "succeeded";
        return {
          ...item,
          status: nextStatus,
          isRunning: false,
          summary:
            item.summary ||
            (action.failed ? "本轮已结束（工具未收到完成事件）" : "本轮已结束"),
        };
      });
      return flushReadyAssistantBuffers({ ...state, executionItems });
    }
    case "FLUSH_READY_ASSISTANT_CONTENT":
      return flushReadyAssistantBuffers(state);
    case "SET_ACTIVE_ASSISTANT_MESSAGE":
      return { ...state, activeAssistantMessageId: action.messageId };
    case "SET_STREAMING":
      return { ...state, isStreaming: action.streaming };
    case "STOP_ACTIVE_RESPONSE": {
      const activeMessageId = state.activeAssistantMessageId;
      const executionItems = state.executionItems.map((item) => {
        if (
          item.messageId !== activeMessageId ||
          !isOpenExecutionStatus(item.status) ||
          (item.kind === "workflow" && Boolean(item.runtimeRunId || item.runId))
        ) {
          return item;
        }
        return {
          ...item,
          status: "cancelled" as const,
          isRunning: false,
          isWaitingApproval: false,
          summary: item.summary || "本轮响应已停止",
        };
      });
      const hasBackgroundWorkflow = executionItems.some(
        (item) =>
          item.kind === "workflow" &&
          isOpenExecutionStatus(item.status) &&
          Boolean(item.runtimeRunId || item.runId),
      );
      return flushReadyAssistantBuffers({
        ...state,
        isStreaming: false,
        status: hasBackgroundWorkflow ? "running_workflow" : "completed",
        activeAssistantMessageId: null,
        executionItems,
      });
    }
    case "SET_STATUS":
      return { ...state, status: action.status };
    case "ADD_EXECUTION_ITEM":
      {
        const incoming = {
          ...action.item,
          messageId: action.item.messageId ?? state.activeAssistantMessageId ?? undefined,
        };
        const identity = executionIdentity(incoming);
        const existingIndex = identity
          ? state.executionItems.findIndex((item) => executionIdentity(item) === identity)
          : -1;
        if (existingIndex < 0) {
          return { ...state, executionItems: [...state.executionItems, incoming] };
        }

        const existing = state.executionItems[existingIndex];
        const keepTerminalStatus =
          !isOpenExecutionStatus(existing.status) && isOpenExecutionStatus(incoming.status);
        const merged = {
          ...existing,
          ...incoming,
          id: existing.id,
          messageId: existing.messageId ?? incoming.messageId,
          status: keepTerminalStatus ? existing.status : incoming.status,
          isRunning: keepTerminalStatus ? existing.isRunning : incoming.isRunning,
        };
        const executionItems = [...state.executionItems];
        executionItems[existingIndex] = merged;
        return { ...state, executionItems };
      }
    case "UPDATE_EXECUTION_ITEM": {
      let updated = false;
      const executionItems = state.executionItems.map((item) => {
        const matches = matchExecutionItem(item, action, state.activeAssistantMessageId);
        if (matches) {
          updated = true;
          // Preserve the first stable ids when later durable events omit them.
          return {
            ...item,
            ...action.patch,
            toolCallId: action.patch.toolCallId ?? item.toolCallId,
            turnId: item.turnId ?? action.patch.turnId ?? action.turnId,
            runtimeRunId: item.runtimeRunId ?? action.patch.runtimeRunId ?? action.runtimeRunId,
            runId: item.runId ?? action.patch.runId ?? action.runId,
            messageId: item.messageId ?? state.activeAssistantMessageId ?? undefined,
          };
        }
        return item;
      });
      if (!updated) {
        executionItems.push({
          id: createExecutionId("exec", action.toolCallId ?? action.runId ?? action.toolName),
          messageId: state.activeAssistantMessageId ?? undefined,
          kind: "tool",
          toolName: action.toolName,
          toolCallId: action.toolCallId,
          turnId: action.turnId,
          runId: action.runId,
          runtimeRunId: action.runtimeRunId,
          status: action.patch.status ?? "pending",
          title: action.toolName,
          timestamp: Date.now(),
          ...action.patch,
        });
      }
      const withTurn = ensureAssistantTurnPart(
        { ...state, executionItems },
        action.turnId ?? action.patch.turnId,
      );
      return flushReadyAssistantBuffers(withTurn);
    }
    case "MERGE_WORKFLOW_NODE": {
      const executionItems = state.executionItems.map((item) => {
        const matches = action.runId
          ? item.runId === action.runId
          : action.runtimeRunId
            ? item.runtimeRunId === action.runtimeRunId
            : false;
        if (!matches) return item;
        const status: AssistantExecutionItem["status"] =
          item.status === "failed" || item.status === "succeeded" || item.status === "cancelled"
            ? item.status
            : "running";
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
    case "SET_APPROVAL_MODE":
      return { ...state, approvalMode: action.mode };
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

interface AssistantSseHandlingOptions {
  shouldHandleRuntimeEvent?: (data: Record<string, unknown>) => boolean;
  onRuntimeRun?: (runId: string) => void;
  onConversation?: (conversationId: string) => void;
  onTerminal?: () => void;
  navigate?: (path: string) => void;
}

function handleAssistantSsePart(
  part: string,
  dispatch: Dispatch<Action>,
  options?: AssistantSseHandlingOptions,
) {
  const parsedSse = parseSsePart(part);
  if (!parsedSse) return;
  handleAssistantSseEvent(parsedSse.eventType, parsedSse.data, dispatch, options);
}

function handleAssistantSseEvent(
  eventType: string,
  parsed: Record<string, unknown>,
  dispatch: Dispatch<Action>,
  options?: AssistantSseHandlingOptions,
) {
  const runtimeRunId = typeof parsed.runtime_run_id === "string" ? parsed.runtime_run_id : undefined;
  if (runtimeRunId) {
    options?.onRuntimeRun?.(runtimeRunId);
    if (options?.shouldHandleRuntimeEvent && !options.shouldHandleRuntimeEvent(parsed)) return;
  }

  const state = asAssistantStatus(parsed.state);
  if (state) {
    dispatch({ type: "SET_STATUS", status: state });
  }

  if (eventType === "assistant.start") {
    const conversationId = parsed.conversation_id;
    if (typeof conversationId === "string") {
      dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId });
      options?.onConversation?.(conversationId);
    }
    const userMessageId = parsed.user_message_id;
    if (typeof userMessageId === "string") {
      dispatch({ type: "SET_LAST_USER_DURABLE_ID", durableId: userMessageId });
    }
    return;
  }

  if (eventType === "assistant.intent_detected") {
    return;
  }

  if (eventType === "assistant.plan_updated") {
    const items = Array.isArray(parsed.items) ? parsed.items : [];
    const titles = items
      .map((item) => asRecord(item).title)
      .filter((title): title is string => typeof title === "string" && title.length > 0);
    dispatch({
      type: "APPEND_VISIBLE_REASONING",
      content: typeof parsed.summary === "string" && parsed.summary.trim()
        ? parsed.summary
        : titles.length > 0 ? `执行计划：${titles.join("、")}。` : "已更新执行计划。",
      turnId: typeof parsed.turn_id === "string" ? parsed.turn_id : undefined,
      title: "执行计划",
      source: "harness",
    });
    dispatch({
      type: "COMPLETE_VISIBLE_REASONING",
      turnId: typeof parsed.turn_id === "string" ? parsed.turn_id : undefined,
    });
    return;
  }

  if (eventType === "assistant.confirmation_requested") {
    const toolName = String(parsed.tool_name ?? "");
    const args = asRecord(parsed.arguments);
    dispatch({
      type: "SET_PENDING_CONFIRMATION",
      confirmation: {
        approvalId: typeof parsed.approval_id === "string" ? parsed.approval_id : undefined,
        runtimeRunId: typeof parsed.runtime_run_id === "string" ? parsed.runtime_run_id : undefined,
        toolName,
        arguments: args,
        message: String(parsed.message ?? "Confirm this action"),
        requiresTypedConfirmation: Boolean(parsed.requires_typed_confirmation),
        expectedText: typeof parsed.expected_text === "string" ? parsed.expected_text : undefined,
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
    // Confirmation is an intentional pause: the server can close this SSE
    // response while the durable run waits for the user's decision. Treat it
    // as a settled stream, not as a lost connection.
    options?.onTerminal?.();
    return;
  }

  if (eventType === "assistant.turn_started") {
    // A turn becomes visible with its first reasoning or tool event. Creating
    // an empty block here would place the tool timeline before streamed
    // provider reasoning and turn a live trace into a replay.
    return;
  }

  if (eventType === "assistant.reasoning" && typeof parsed.content === "string") {
    // Only the Harness may publish user-facing reasoning. Provider thinking
    // tokens are private model state and must never become transcript text.
    if (parsed.source !== "harness") return;
    dispatch({
      type: "APPEND_VISIBLE_REASONING",
      content: parsed.content,
      turnId: typeof parsed.turn_id === "string" ? parsed.turn_id : undefined,
      title: typeof parsed.title === "string" ? parsed.title : undefined,
      source: "harness",
    });
    return;
  }

  if (eventType === "assistant.reasoning_completed") {
    if (parsed.source !== "harness") return;
    dispatch({
      type: "COMPLETE_VISIBLE_REASONING",
      turnId: typeof parsed.turn_id === "string" ? parsed.turn_id : undefined,
    });
    return;
  }

  if (eventType === "assistant.tool_started") {
    const toolName = String(parsed.tool_name ?? "");
    const toolCallId = typeof parsed.tool_call_id === "string" ? parsed.tool_call_id : undefined;
    // Durable CAPABILITY_STARTED events often omit turn_id. Fall back to
    // runtime_run_id so tools still group and render as a turn block.
    const turnId =
      (typeof parsed.turn_id === "string" && parsed.turn_id) ||
      (runtimeRunId ? `run:${runtimeRunId}` : undefined);
    const title = typeof parsed.title === "string" && parsed.title ? parsed.title : toolName;
    if (turnId) {
      dispatch({ type: "ENSURE_TRANSCRIPT_TURN", turnId });
    }
    // Only workflow capabilities own node progress. Read tools like
    // search_projects must not become "0/1 steps" cards.
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      toolCallId,
      turnId,
      runtimeRunId,
      patch: {
        kind: "tool",
        status: "running",
        title,
        toolCallId,
        turnId,
        runtimeRunId,
        arguments: asRecord(parsed.arguments),
        isRunning: true,
      },
    });
    return;
  }

  if (eventType === "assistant.workflow_started") {
    const toolName = String(parsed.tool_name ?? "");
    const toolCallId = typeof parsed.tool_call_id === "string" ? parsed.tool_call_id : undefined;
    const turnId =
      (typeof parsed.turn_id === "string" && parsed.turn_id) ||
      (runtimeRunId ? `run:${runtimeRunId}` : undefined);
    const result = asRecord(parsed.result);
    const runId = typeof result.run_id === "string" ? result.run_id : undefined;
    const workflowRuntimeRunId = typeof result.runtime_run_id === "string" ? result.runtime_run_id : undefined;
    if (turnId) {
      dispatch({ type: "ENSURE_TRANSCRIPT_TURN", turnId });
    }
    dispatch({
      type: "ADD_EXECUTION_ITEM",
      item: {
        id: `workflow-${Date.now()}`,
        kind: "workflow",
        toolName,
        toolCallId,
        turnId,
        runId,
        runtimeRunId: workflowRuntimeRunId,
        status: "running",
        title: toolName,
        arguments: asRecord(parsed.arguments),
        result,
        isRunning: true,
        timestamp: Date.now(),
      },
    });
    if (workflowRuntimeRunId) {
      dispatch({ type: "SET_STATUS", status: "running_workflow" });
      void pollRuntimeWorkflow(workflowRuntimeRunId, toolName, dispatch, options).catch((error) => {
        dispatch({
          type: "UPDATE_EXECUTION_ITEM",
          toolName,
          runtimeRunId: workflowRuntimeRunId,
          patch: {
            status: "failed",
            isRunning: false,
            errorMessage: error instanceof Error ? error.message : "Workflow event stream failed",
          },
        });
        dispatch({ type: "SET_STATUS", status: "failed" });
      });
    } else if (runId) {
      dispatch({ type: "SET_STATUS", status: "running_workflow" });
      void streamWorkflowRun(runId, toolName, dispatch).catch((error) => {
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
    const toolCallId = typeof parsed.tool_call_id === "string" ? parsed.tool_call_id : undefined;
    const turnId =
      (typeof parsed.turn_id === "string" && parsed.turn_id) ||
      (runtimeRunId ? `run:${runtimeRunId}` : undefined);
    const result = asRecord(parsed.result);
    if (turnId) {
      dispatch({ type: "ENSURE_TRANSCRIPT_TURN", turnId });
    }
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      toolCallId,
      turnId,
      runtimeRunId,
      patch: {
        status: "succeeded",
        result,
        summary: String(parsed.summary ?? ""),
        isRunning: false,
        toolCallId,
        turnId,
        runtimeRunId,
        title: typeof parsed.title === "string" && parsed.title ? parsed.title : toolName,
      },
    });
    if (typeof result.run_id === "string" || typeof result.runtime_run_id === "string") {
      return;
    }
    if (toolName === "open_page" && typeof result.route === "string") {
      options?.navigate?.(result.route);
    }
    // Creating a project is an Agent result, not a navigation command. Keep
    // the user in the conversation so the next step can be confirmed there.
    return;
  }

  if (eventType === "assistant.tool_failed") {
    const toolName = String(parsed.tool_name ?? "");
    const toolCallId = typeof parsed.tool_call_id === "string" ? parsed.tool_call_id : undefined;
    const turnId =
      (typeof parsed.turn_id === "string" && parsed.turn_id) ||
      (runtimeRunId ? `run:${runtimeRunId}` : undefined);
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      toolCallId,
      turnId,
      runtimeRunId,
      patch: {
        status: "failed",
        errorMessage: String(parsed.error_message ?? "Tool failed"),
        errorCode: typeof parsed.error_code === "string" ? parsed.error_code : undefined,
        toolCallId,
        turnId,
      },
    });
    return;
  }

  if (eventType === "assistant.tool_progressed") {
    const toolName = String(parsed.tool_name ?? "");
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      patch: {
        kind: "tool",
        status: "running",
        title: toolName,
        summary: undefined,
        errorCode: typeof parsed.error_code === "string" ? parsed.error_code : undefined,
        retryAttempt: typeof parsed.retry_attempt === "number" ? parsed.retry_attempt : undefined,
        retryMaxAttempts: typeof parsed.retry_max_attempts === "number" ? parsed.retry_max_attempts : undefined,
      },
    });
    return;
  }

  if (eventType === "assistant.workflow_provider_retry") {
    const toolName = String(parsed.tool_name ?? "workflow");
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      runtimeRunId,
      patch: {
        status: "running",
        isRunning: true,
        summary: undefined,
        errorCode: typeof parsed.error_code === "string" ? parsed.error_code : undefined,
        retryAttempt: typeof parsed.retry_attempt === "number" ? parsed.retry_attempt : undefined,
        retryMaxAttempts: typeof parsed.retry_max_attempts === "number" ? parsed.retry_max_attempts : undefined,
      },
    });
    return;
  }

  if (eventType === "assistant.workflow_node_failed") {
    const nodeName = String(parsed.node_name ?? parsed.tool_name ?? "workflow");
    dispatch({
      type: "MERGE_WORKFLOW_NODE",
      runtimeRunId,
      node: {
        name: nodeName,
        status: "failed",
        error: typeof parsed.error_code === "string" ? parsed.error_code : undefined,
      },
      currentNode: null,
    });
    return;
  }

  if (eventType === "assistant.workflow_failed") {
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName: String(parsed.tool_name ?? "workflow"),
      runtimeRunId,
      patch: {
        status: "failed",
        isRunning: false,
        isWaitingApproval: false,
        currentNode: null,
        errorMessage: String(parsed.error_message ?? "Workflow failed"),
        errorCode: typeof parsed.error_code === "string" ? parsed.error_code : undefined,
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
      options?.onConversation?.(conversationId);
    }
    // Close any tool cards still "running" after the stream ends. Duplicate
    // CAPABILITY_* events previously left a ghost running card beside the
    // completed one.
    dispatch({ type: "FINALIZE_OPEN_EXECUTION_ITEMS", runtimeRunId, failed: parsed.state === "failed" });
    // A terminal event without an explicit state is still a completed turn.
    // Keeping the previous `thinking` state here leaves the composer stuck
    // even though the server has closed the response successfully.
    dispatch({ type: "SET_STATUS", status: state ?? "completed" });
    options?.onTerminal?.();
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asAssistantStatus(value: unknown): AssistantStatus | undefined {
  if (
    value === "idle" ||
    value === "thinking" ||
    value === "needs_input" ||
    value === "needs_confirmation" ||
    value === "executing_tool" ||
    value === "running_workflow" ||
    value === "completed" ||
    value === "failed"
  ) {
    return value;
  }
  return undefined;
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
  stopAssistantResponse: () => void;
  setSelectedProviderConfig: (providerConfigId: string | null) => void;
  setReasoningEffort: (effort: AssistantReasoningEffort) => void;
  setApprovalMode: (mode: AssistantApprovalMode) => void;
  cancelWorkflow: (runtimeRunId: string) => Promise<void>;
  confirmAssistantAction: (approved: boolean, confirmationText?: string) => Promise<void>;
  executeCommand: (commandId: string) => void;
  refreshConversations: () => Promise<void>;
  loadConversation: (conversationId: string) => Promise<void>;
  startNewConversation: () => void;
  retryFromCheckpoint: (checkpointMessageId: string, content: string) => Promise<void>;
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
  toolName: string,
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
    dispatch({ type: "UPDATE_EXECUTION_ITEM", toolName, runId, patch });
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
        const runtimeRunId = typeof data.runtime_run_id === "string" ? data.runtime_run_id : undefined;
        updateWorkflow({
          status: "running",
          isRunning: true,
          currentNode: null,
          runtimeRunId,
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
      } else if (eventType === "provider_retry") {
        const nodeName = typeof data.node_name === "string" ? data.node_name : undefined;
        if (nodeName) {
          dispatch({
            type: "MERGE_WORKFLOW_NODE",
            runId,
            node: { name: nodeName, status: "running" },
            currentNode: nodeName,
          });
        }
        updateWorkflow({
          status: "running",
          isRunning: true,
          summary: undefined,
          errorCode: typeof data.error_code === "string" ? data.error_code : undefined,
          retryAttempt: typeof data.attempt === "number" ? data.attempt : undefined,
          retryMaxAttempts: typeof data.max_attempts === "number" ? data.max_attempts : undefined,
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
      } else if (eventType === "graph_cancellation_requested") {
        updateWorkflow({
          status: "running",
          isRunning: true,
          isWaitingApproval: false,
          isCancellationRequested: true,
        });
      } else if (eventType === "graph_cancelled") {
        updateWorkflow({
          status: "cancelled",
          isRunning: false,
          isWaitingApproval: false,
          isCancellationRequested: true,
          currentNode: null,
        });
        dispatch({ type: "SET_STATUS", status: "completed" });
        onTerminal?.();
        return;
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
        const cancelled = data.status === "cancelled";
        const nodeName = typeof data.node_name === "string" ? data.node_name : undefined;
        const errorCode = typeof data.error_code === "string" ? data.error_code : undefined;
        if (nodeName && !cancelled) {
          dispatch({
            type: "MERGE_WORKFLOW_NODE",
            runId,
            node: { name: nodeName, status: "failed", error: errorCode },
            currentNode: null,
          });
        }
        updateWorkflow({
          status: cancelled ? "cancelled" : "failed",
          isRunning: false,
          isWaitingApproval: false,
          isCancellationRequested: cancelled,
          currentNode: null,
          errorMessage: cancelled
            ? undefined
            : typeof data.error_message === "string"
              ? data.error_message
              : "Workflow failed",
          errorCode,
        });
        dispatch({ type: "SET_STATUS", status: cancelled ? "completed" : "failed" });
        onTerminal?.();
        return;
      }
    }
  }

  onTerminal?.();
}

const RUNTIME_EVENT_POLL_INTERVAL_MS = 1_200;
const RUNTIME_EVENT_POLL_MAX_ATTEMPTS = 500;

function waitForRuntimePoll() {
  return new Promise<void>((resolve) => window.setTimeout(resolve, RUNTIME_EVENT_POLL_INTERVAL_MS));
}

async function pollRuntimeWorkflow(
  runtimeRunId: string,
  toolName: string,
  dispatch: Dispatch<Action>,
  options?: AssistantSseHandlingOptions,
) {
  let afterSequence = 0;

  for (let attempt = 0; attempt < RUNTIME_EVENT_POLL_MAX_ATTEMPTS; attempt += 1) {
    const response = await listRuntimeEvents(runtimeRunId, afterSequence);
    let terminalStatus: AssistantExecutionItem["status"] | null = null;

    for (const event of response.items) {
      afterSequence = Math.max(afterSequence, event.sequence);
      for (const compatibilityEvent of runtimeEventToAssistantEvents(event, null)) {
        handleAssistantSseEvent(compatibilityEvent.eventType, compatibilityEvent.data, dispatch, options);
      }
      if (event.type === "run.completed") terminalStatus = "succeeded";
      if (event.type === "run.failed") terminalStatus = "failed";
      if (event.type === "run.cancelled") terminalStatus = "cancelled";
    }

    if (terminalStatus) {
      dispatch({
        type: "UPDATE_EXECUTION_ITEM",
        toolName,
        runtimeRunId,
        patch: {
          status: terminalStatus,
          isRunning: false,
          isWaitingApproval: false,
          currentNode: null,
        },
      });
      dispatch({ type: "SET_STATUS", status: terminalStatus === "failed" ? "failed" : "completed" });
      return;
    }

    await waitForRuntimePoll();
  }

  throw new Error("Workflow status polling timed out");
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

async function replayRuntimeEvents(
  runId: string,
  cursors: RuntimeEventCursor,
  conversationId: string | null,
  dispatch: Dispatch<Action>,
  options: AssistantSseHandlingOptions,
): Promise<{ replayed: boolean; terminal: boolean }> {
  const response = await listRuntimeEvents(runId, cursors[runId] ?? 0);
  let replayed = false;
  let terminal = false;

  for (const event of response.items) {
    for (const compatibilityEvent of runtimeEventToAssistantEvents(event, conversationId)) {
      replayed = true;
      handleAssistantSseEvent(compatibilityEvent.eventType, compatibilityEvent.data, dispatch, options);
    }
    terminal ||= isTerminalRuntimeEvent(event);
  }

  return { replayed, terminal };
}


export function isAssistantBusy(status: AssistantStatus) {
  return ["thinking", "executing_tool", "running_workflow"].includes(status);
}

function toStoredChatMessages(items: ChatMessageRead[]): ChatMessage[] {
  return items.map((item, index) => ({
    id: item.id,
    durableId: item.id,
    runtimeRunId: item.runtime_run_id ?? undefined,
    role: item.role,
    content: item.content,
    timestamp: item.created_at ? Date.parse(item.created_at) || Date.now() + index : Date.now() + index,
    attachments: item.attachments?.map((attachment) => ({
      id: attachment.assistant_attachment_id ?? attachment.id,
      name: attachment.name,
      kind: attachment.kind,
      size: attachment.size,
      status: attachment.extraction_status === "failed" ? "failed" : "uploaded",
      documentId: attachment.document_id ?? undefined,
    })),
  }));
}

function mergeRecoveredRuntimeMessage(
  messages: ChatMessage[],
  recovered: ReturnType<typeof recoverRuntimeMessageFromEvents>,
): { messages: ChatMessage[]; messageId?: string } {
  if (!recovered) return { messages };
  const timestamp = recovered.timestamp ?? Date.now();
  const sameTurn = (message: ChatMessage) =>
    message.role === "assistant" &&
    (recovered.timestamp === undefined || Math.abs(message.timestamp - timestamp) < 120_000);

  const exactIndex = messages.findIndex(
    (message) => sameTurn(message) && message.content.trim() === recovered.content,
  );
  if (exactIndex >= 0) {
    return { messages, messageId: messages[exactIndex].id };
  }

  const partialIndex = messages.findIndex(
    (message) =>
      sameTurn(message) &&
      message.content.trim().length > 0 &&
      recovered.content.startsWith(message.content.trim()),
  );
  if (partialIndex >= 0) {
    const next = [...messages];
    next[partialIndex] = { ...next[partialIndex], content: recovered.content, timestamp };
    return { messages: next, messageId: next[partialIndex].id };
  }

  const message: ChatMessage = {
    id: `runtime-${recovered.runId}-assistant-message`,
    role: "assistant",
    content: recovered.content,
    timestamp,
  };
  const insertAt = messages.findIndex((item) => item.timestamp > timestamp);
  if (insertAt < 0) return { messages: [...messages, message], messageId: message.id };
  return {
    messages: [...messages.slice(0, insertAt), message, ...messages.slice(insertAt)],
    messageId: message.id,
  };
}

function findAssistantMessageNearTimestamp(
  messages: ChatMessage[],
  timestampSource: string | null | undefined,
): string | undefined {
  const timestamp = timestampSource ? Date.parse(timestampSource) : Number.NaN;
  if (!Number.isFinite(timestamp)) return undefined;
  const candidates = messages.filter((message) => message.role === "assistant");
  if (candidates.length === 0) return undefined;
  const closest = candidates.reduce((best, message) =>
    Math.abs(message.timestamp - timestamp) < Math.abs(best.timestamp - timestamp) ? message : best,
  );
  // A durable assistant reply is committed immediately after its run. Do not
  // attach an otherwise unplaceable trace to an unrelated conversation turn.
  return Math.abs(closest.timestamp - timestamp) < 120_000 ? closest.id : undefined;
}

export function AIAssistantProvider({
  children,
  navigate,
}: {
  children: ReactNode;
  navigate?: (path: string) => void;
}) {
  const [state, dispatch] = useReducer(reducer, initialState);
  // Navigation is optional: unit tests mount the provider without a Router,
  // and the app shell passes the real router navigate via a wrapper inside
  // BrowserRouter. Without it, tool-driven page transitions are a no-op.
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;
  const runtimeEventCursorsRef = useRef<RuntimeEventCursor>({});
  const activeStreamAbortRef = useRef<AbortController | null>(null);
  const activeAssistantRuntimeRunRef = useRef<string | null>(null);
  // A previous history request may resolve after the user has picked another
  // conversation. Only the newest request is allowed to project server state.
  const conversationLoadVersionRef = useRef(0);
  // Once the user explicitly starts a new conversation, do not let the
  // mount-time restore effect put the previous conversation back.
  const didAutoRestoreRef = useRef(false);
  // React state updates are asynchronous. Keep a synchronous lock as the
  // request boundary so double-clicks cannot create two server runtimes before
  // the busy state reaches the composer.
  const assistantRequestInFlightRef = useRef(false);

  const shouldHandleRuntimeEvent = useCallback((data: Record<string, unknown>) => {
    const runId = typeof data.runtime_run_id === "string" ? data.runtime_run_id : undefined;
    const sequence = typeof data.runtime_sequence === "number" ? data.runtime_sequence : undefined;
    if (!runId || sequence === undefined || !Number.isInteger(sequence) || sequence < 1) return true;
    if (!isRuntimeSequenceNewer(runtimeEventCursorsRef.current, runId, sequence)) return false;
    runtimeEventCursorsRef.current = advanceRuntimeSequenceCursor(
      runtimeEventCursorsRef.current,
      runId,
      sequence,
    );
    return true;
  }, []);

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
    const loadVersion = ++conversationLoadVersionRef.current;
    const isCurrentLoad = () => conversationLoadVersionRef.current === loadVersion;
    setStoredValue("lastAssistantConversationId", conversationId);
    dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId });
    dispatch({ type: "CLEAR_MESSAGES" });
    // Clear previous run tool cards so restored transcript only shows this conversation.
    dispatch({ type: "CLEAR_TRANSIENT_STATE" });
    dispatch({ type: "SET_STATUS", status: "thinking" });
    try {
      const history = await getChatConversationMessages(conversationId);
      if (!isCurrentLoad()) return;
      const messages = toStoredChatMessages(history.items);
      dispatch({
        type: "REPLACE_MESSAGES",
        messages,
      });

      // Replay durable runtime tool events so history shows L1/L2 tool cards,
      // not only plain assistant text. Runtime events also repair a missing
      // chat row when the browser disconnected before the final save commit.
      let restoredMessages = messages;
      const runtimeReplay: Array<{
        runId: string;
        messageId?: string;
        events: Awaited<ReturnType<typeof listRuntimeEvents>>["items"];
      }> = [];
      try {
        const runs = await listRuntimeRuns(12, conversationId);
        if (!isCurrentLoad()) return;
        // Replay oldest→newest so tool order matches conversation flow.
        for (const run of [...runs].reverse()) {
          const response = await listRuntimeEvents(run.id, 0);
          if (!isCurrentLoad()) return;
          const merged = mergeRecoveredRuntimeMessage(
            restoredMessages,
            recoverRuntimeMessageFromEvents(run.id, response.items),
          );
          restoredMessages = merged.messages;
          runtimeReplay.push({
            runId: run.id,
            messageId:
              restoredMessages.find((message) => message.runtimeRunId === run.id)?.id ??
              merged.messageId ??
              findAssistantMessageNearTimestamp(restoredMessages, run.finished_at ?? run.created_at),
            events: response.items,
          });
        }
        if (!isCurrentLoad()) return;
        if (restoredMessages !== messages) {
          dispatch({ type: "REPLACE_MESSAGES", messages: restoredMessages });
        }

        // A run belongs to its own assistant response, never to whichever
        // response happened to be last when the transcript was restored.
        for (const { messageId, events } of runtimeReplay) {
          if (!messageId) continue;
          dispatch({ type: "SET_ACTIVE_ASSISTANT_MESSAGE", messageId });
          for (const event of events) {
            for (const compatibilityEvent of runtimeEventToAssistantEvents(
              event,
              conversationId,
            )) {
              // Text is already in chat history. Reasoning and tool lifecycle
              // are durable trace data and must survive a reload.
              if (
                compatibilityEvent.eventType !== "assistant.tool_started" &&
                compatibilityEvent.eventType !== "assistant.tool_succeeded" &&
                compatibilityEvent.eventType !== "assistant.tool_failed" &&
                compatibilityEvent.eventType !== "assistant.turn_started" &&
                compatibilityEvent.eventType !== "assistant.turn_finished" &&
                compatibilityEvent.eventType !== "assistant.reasoning" &&
                compatibilityEvent.eventType !== "assistant.reasoning_completed"
              ) {
                continue;
              }
              handleAssistantSseEvent(
                compatibilityEvent.eventType,
                compatibilityEvent.data,
                dispatch,
              );
            }
          }
        }
      } catch (replayError) {
        if (!isCurrentLoad()) return;
        console.error("Failed to restore tool transcript:", replayError);
      }

      if (!isCurrentLoad()) return;
      // History is complete — never leave restored tools stuck in "running".
      dispatch({ type: "FINALIZE_OPEN_EXECUTION_ITEMS" });
      dispatch({ type: "SET_ACTIVE_ASSISTANT_MESSAGE", messageId: null });
      dispatch({ type: "OPEN", mode: "panel" });
    } catch (error) {
      if (!isCurrentLoad()) return;
      console.error("Failed to load chat history:", error);
      removeStoredValue("lastAssistantConversationId");
      // Keep the conversation selected but restore a visible error instead of a
      // blank transcript that looks like history was deleted.
      dispatch({
        type: "REPLACE_MESSAGES",
        messages: [
          {
            id: `${conversationId}-load-error`,
            role: "assistant",
            content: "加载会话历史失败，请重试或新建对话。消息仍保存在服务器上。",
            timestamp: Date.now(),
          },
        ],
      });
    } finally {
      if (isCurrentLoad()) {
        dispatch({ type: "SET_STATUS", status: "idle" });
      }
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

  const setApprovalMode = useCallback((mode: AssistantApprovalMode) => {
    setStoredValue("assistantApprovalMode", mode);
    dispatch({ type: "SET_APPROVAL_MODE", mode });
  }, []);

  const cancelWorkflow = useCallback(async (runtimeRunId: string) => {
    const run = await cancelRuntimeWorkflow(runtimeRunId);
    const cancelled = run.status === "cancelled";
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName: "start_draft_section",
      runtimeRunId,
      patch: {
        status: cancelled ? "cancelled" : "running",
        isRunning: !cancelled,
        isWaitingApproval: false,
        isCancellationRequested: true,
        currentNode: cancelled ? null : undefined,
      },
    });
    if (cancelled) {
      dispatch({ type: "SET_STATUS", status: "completed" });
    }
  }, []);

  const stopAssistantResponse = useCallback(() => {
    const controller = activeStreamAbortRef.current;
    if (!controller || controller.signal.aborted) return;
    const runtimeRunId = activeAssistantRuntimeRunRef.current;
    if (!runtimeRunId) {
      // The request has not exposed a durable run ID yet.
      controller.abort();
      return;
    }
    void cancelRuntimeWorkflow(runtimeRunId).catch((error: unknown) => {
      console.error("Failed to cancel assistant runtime:", error);
      controller.abort();
    });
  }, []);

  useEffect(
    () => () => {
      activeStreamAbortRef.current?.abort();
    },
    [],
  );

  const startNewConversation = useCallback(() => {
    conversationLoadVersionRef.current += 1;
    didAutoRestoreRef.current = true;
    removeStoredValue("lastAssistantConversationId");
    dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId: null });
    dispatch({ type: "CLEAR_MESSAGES" });
    dispatch({ type: "CLEAR_TRANSIENT_STATE" });
    dispatch({ type: "SET_STATUS", status: "idle" });
    dispatch({ type: "OPEN", mode: "panel" });
  }, []);

  // Always keep the conversation list warm for both the floating panel and
  // the full /agent workspace (workspace does not set isOpen).
  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  // Auto-restore the last conversation once when the assistant surface mounts.
  useEffect(() => {
    if (didAutoRestoreRef.current) return;
    if (state.currentConversationId || state.messages.length > 0) {
      didAutoRestoreRef.current = true;
      return;
    }
    const lastId = getStoredValue("lastAssistantConversationId");
    if (!lastId) {
      didAutoRestoreRef.current = true;
      return;
    }
    didAutoRestoreRef.current = true;
    void loadConversation(lastId);
  }, [loadConversation, state.currentConversationId, state.messages.length]);

  const sendAssistantRequest = useCallback(
    async (
      content: string,
      options?: SendAssistantOptions,
      confirmation?: {
        approved: boolean;
        tool_name: string;
        arguments: Record<string, unknown>;
        approval_id?: string;
      },
    ) => {
      const displayContent = confirmation
        ? confirmation.approved
          ? "确认执行"
          : "取消操作"
        : (options?.displayContent ?? content).trim();
      if (!displayContent || isAssistantBusy(state.status) || assistantRequestInFlightRef.current) return;
      assistantRequestInFlightRef.current = true;
      const targetConversationId = options?.conversationId ?? state.currentConversationId;
      if (targetConversationId && targetConversationId !== state.currentConversationId) {
        setStoredValue("lastAssistantConversationId", targetConversationId);
        dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId: targetConversationId });
      }

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

      let activeRuntimeRunId: string | null = null;
      activeAssistantRuntimeRunRef.current = null;
      let activeConversationId = targetConversationId;
      let receivedTerminalEvent = false;
      const abortController = new AbortController();
      activeStreamAbortRef.current = abortController;
      dispatch({ type: "SET_STREAMING", streaming: true });
      const sseOptions: AssistantSseHandlingOptions = {
        shouldHandleRuntimeEvent,
        navigate: (path) => navigateRef.current?.(path),
        onRuntimeRun: (runId) => {
          activeRuntimeRunId = runId;
          activeAssistantRuntimeRunRef.current = runId;
        },
        onConversation: (conversationId) => {
          activeConversationId = conversationId;
          setStoredValue("lastAssistantConversationId", conversationId);
        },
        onTerminal: () => {
          receivedTerminalEvent = true;
        },
      };
      const recoverDurableTimeline = async () => {
        if (!activeRuntimeRunId || receivedTerminalEvent) {
          return { replayed: false, terminal: receivedTerminalEvent };
        }
        const recovered = await replayRuntimeEvents(
          activeRuntimeRunId,
          runtimeEventCursorsRef.current,
          activeConversationId,
          dispatch,
          sseOptions,
        );
        receivedTerminalEvent ||= recovered.terminal;
        return recovered;
      };

      try {
        const token = getAuthToken();
        const clientRequestId = crypto.randomUUID();
        const response = await fetch(`${API_BASE}/assistant/stream`, {
          method: "POST",
          signal: abortController.signal,
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: content,
            client_request_id: clientRequestId,
            project_id: state.currentContext.projectId,
            conversation_id: targetConversationId,
            provider_config_id: options?.providerConfigId ?? state.selectedProviderConfigId,
            reasoning_effort: options?.reasoningEffort ?? state.reasoningEffort,
            approval_mode: options?.approvalMode ?? state.approvalMode,
            locale: i18n.resolvedLanguage === "en" ? "en" : "zh-CN",
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
            handleAssistantSsePart(part, dispatch, sseOptions);
          }
        }

        // A proxy is allowed to close a response immediately after an SSE
        // frame. Consume the final unterminated frame before deciding whether
        // this request reached a terminal state.
        if (buffer.trim()) {
          handleAssistantSsePart(buffer, dispatch, sseOptions);
        }

        if (abortController.signal.aborted) {
          dispatch({ type: "STOP_ACTIVE_RESPONSE" });
          return;
        }

        const recovered = await recoverDurableTimeline();
        if (!receivedTerminalEvent && !recovered.terminal) {
          dispatch({
            type: "SET_SESSION_ERROR",
            message: "助手连接已结束，但运行记录未报告终态。已解除待发送队列，请重试或查看运行记录。",
            errorCode: "assistant_stream_incomplete",
          });
        }
      } catch (err) {
        if (abortController.signal.aborted) {
          dispatch({ type: "STOP_ACTIVE_RESPONSE" });
          return;
        }
        try {
          const recovered = await recoverDurableTimeline();
          if (recovered.replayed || recovered.terminal) return;
        } catch (recoveryError) {
          console.warn("Failed to replay assistant runtime events:", recoveryError);
        }
        const status = typeof (err as { status?: number }).status === "number" ? (err as { status?: number }).status : undefined;
        const errorCode = typeof (err as { errorCode?: string }).errorCode === "string" ? (err as { errorCode?: string }).errorCode : undefined;
        const message = err instanceof Error ? err.message : "Something went wrong. Please try again.";
        const providerSelectionUnavailable = status === 404 && message === "Provider config not found";
        if (!providerSelectionUnavailable) {
          console.error("AI assistant request failed", { status, errorCode: errorCode || undefined });
        }
        if (providerSelectionUnavailable) {
          dispatch({ type: "SET_SELECTED_PROVIDER_CONFIG", providerConfigId: null });
        }
        const friendly =
          status === 403 || errorCode === "usage_limit_exceeded"
            ? "你的试用额度已用完，请升级计划或稍后再试。"
            : providerSelectionUnavailable
              ? "所选模型配置已不可用，已切回平台默认模型。请确认后重新发送。"
            : message;
        dispatch({ type: "SET_SESSION_ERROR", message: friendly, errorCode });
      } finally {
        assistantRequestInFlightRef.current = false;
        if (activeStreamAbortRef.current === abortController) {
          activeStreamAbortRef.current = null;
          activeAssistantRuntimeRunRef.current = null;
          dispatch({ type: "SET_STREAMING", streaming: false });
        }
        void refreshConversations();
      }
    },
    [
      refreshConversations,
      state.currentContext.projectId,
      state.currentConversationId,
      state.reasoningEffort,
      state.approvalMode,
      state.selectedProviderConfigId,
      state.status,
      shouldHandleRuntimeEvent,
    ],
  );

  const sendMessage = useCallback(
    async (content: string, options?: SendAssistantOptions) => {
      await sendAssistantRequest(content, options);
    },
    [sendAssistantRequest],
  );

  const retryFromCheckpoint = useCallback(
    async (checkpointMessageId: string, content: string) => {
      const sourceConversationId = state.currentConversationId;
      const nextContent = content.trim();
      if (
        !sourceConversationId ||
        !checkpointMessageId ||
        !nextContent ||
        isAssistantBusy(state.status) ||
        assistantRequestInFlightRef.current
      ) {
        return;
      }

      try {
        const branch = await forkChatConversation(sourceConversationId, checkpointMessageId);
        const messages = toStoredChatMessages(branch.items);
        setStoredValue("lastAssistantConversationId", branch.conversation.id);
        dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId: branch.conversation.id });
        dispatch({ type: "REPLACE_MESSAGES", messages });
        dispatch({ type: "SET_STATUS", status: "idle" });
        dispatch({ type: "OPEN", mode: "panel" });
        await sendAssistantRequest(nextContent, {
          displayContent: nextContent,
          conversationId: branch.conversation.id,
        });
      } catch (error) {
        console.error("Failed to create assistant checkpoint branch:", error);
        dispatch({
          type: "SET_SESSION_ERROR",
          message: "无法从该检查点创建新对话，请稍后重试。",
        });
      }
    },
    [sendAssistantRequest, state.currentConversationId, state.status],
  );

  const confirmAssistantAction = useCallback(
    async (approved: boolean, confirmationText?: string) => {
      const pending = state.pendingConfirmation;
      if (!pending) return;
      dispatch({ type: "SET_PENDING_CONFIRMATION", confirmation: null });
      const confirmationArguments =
        approved && pending.requiresTypedConfirmation
          ? { ...pending.arguments, confirmation_text: confirmationText ?? "" }
          : pending.arguments;
      await sendAssistantRequest(approved ? "确认执行" : "取消操作", undefined, {
        approved,
        tool_name: pending.toolName,
        arguments: confirmationArguments,
        approval_id: pending.approvalId,
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
        stopAssistantResponse,
        setSelectedProviderConfig,
        setReasoningEffort,
        setApprovalMode,
        cancelWorkflow,
        confirmAssistantAction,
        executeCommand,
        refreshConversations,
        loadConversation,
        startNewConversation,
        retryFromCheckpoint,
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
