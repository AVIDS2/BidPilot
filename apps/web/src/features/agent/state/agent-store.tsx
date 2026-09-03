import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
  type Dispatch
} from 'react';
import {
  cancelRuntimeWorkflow,
  forkChatConversation,
  getChatConversationMessages,
  listRuntimeEvents,
  listRuntimeRuns,
  listChatConversations,
  type ChatConversationRead,
  type ChatMessageRead,
  type RuntimeRunListItem
} from '@/lib/api';
import {
  getSessionStoredValue,
  getStoredValue,
  removeSessionStoredValue,
  removeStoredValue,
  setSessionStoredValue,
  setStoredValue
} from '@/lib/browser-storage';
import {
  advanceRuntimeSequenceCursor,
  isRuntimeSequenceNewer,
  isTerminalRuntimeEvent,
  recoverRuntimeMessageFromEvents,
  runtimeEventToAssistantEvents,
  type RuntimeEventCursor
} from '@/features/agent/runtime/runtime-event-feed';
import {
  appendNarrativePart,
  appendReasoningPart,
  completeReasoningPart,
  ensureTurnPart,
  narrativeTextFromParts,
  normalizeTranscriptText,
  type AssistantTranscriptPart
} from '@/features/agent/runtime/assistant-transcript';
import i18n from '@/lib/i18n';

/* ─── Types ─── */

export type AssistantMode = 'panel' | 'command' | 'inline';
export type AssistantReasoningEffort = 'low' | 'medium' | 'high' | 'extra' | 'max';
export type AssistantApprovalMode = 'request_approval' | 'risky_only' | 'full_access' | 'custom';
export type AssistantStatus =
  | 'idle'
  | 'queued'
  | 'thinking'
  | 'needs_input'
  | 'needs_confirmation'
  | 'executing_tool'
  | 'running_workflow'
  | 'completed'
  | 'failed';

export interface ChatMessage {
  id: string;
  /** Server primary key when this message was persisted. */
  durableId?: string;
  /** Durable runtime owner for replaying this response's event tree. */
  runtimeRunId?: string;
  role: 'user' | 'assistant';
  content: string;
  /** Ordered narrative/turn parts for Pi-style interleaved rendering. */
  transcriptParts?: AssistantTranscriptPart[];
  timestamp: number;
  attachments?: ChatMessageAttachment[];
}

export interface ChatMessageAttachment {
  id: string;
  name: string;
  kind: 'file' | 'image';
  size: number;
  status: 'ready' | 'uploaded' | 'failed';
  documentId?: string;
  previewUrl?: string;
}

export interface AssistantRequestAttachment {
  id?: string;
  name: string;
  kind: 'file' | 'image';
  mime_type?: string;
  size?: number;
  extraction_status?: 'extracted' | 'empty' | 'unsupported' | 'failed';
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

/** A harness pause that can be answered through a structured UI instead of a
 * second round of guesswork in free-form chat. */
export interface AssistantInputRequest {
  messageId?: string;
  runtimeRunId?: string;
  toolName: string;
  missingFields: string[];
  message: string;
}

export interface AssistantExecutionItem {
  id: string;
  messageId?: string;
  kind: 'intent' | 'tool' | 'workflow' | 'subagent';
  toolName?: string;
  toolCallId?: string;
  turnId?: string;
  runId?: string;
  runtimeRunId?: string;
  parentRuntimeRunId?: string;
  executionGroupId?: string;
  agentProfile?: string;
  presentationKind?: string;
  presentationSessionId?: string;
  presentationTitle?: string;
  resourceKind?: 'tool' | 'skill' | 'mcp';
  resourceName?: string;
  provider?: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
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
  status: 'pending' | 'running' | 'completed' | 'failed';
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
  group: 'navigation' | 'action' | 'ai';
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
  /** True only after Pi reports a live model-turn/thinking boundary. */
  isThinking: boolean;
  /** True after the user requests a durable Pi cancellation until terminal state. */
  cancellationRequested: boolean;
  status: AssistantStatus;
  executionItems: AssistantExecutionItem[];
  pendingConfirmation: AssistantConfirmationRequest | null;
  pendingInput: AssistantInputRequest | null;
  sessionError: string | null;
  sessionErrorRuntimeRunId: string | null;
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
  | { type: 'OPEN'; mode?: AssistantMode }
  | { type: 'CLOSE' }
  | { type: 'TOGGLE'; mode?: AssistantMode }
  | { type: 'SET_MODE'; mode: AssistantMode }
  | { type: 'SET_CURRENT_CONVERSATION'; conversationId: string | null }
  | { type: 'SET_CONVERSATIONS'; conversations: ChatConversationRead[] }
  | { type: 'UPDATE_CONVERSATION_TITLE'; conversationId: string; title: string }
  | { type: 'ADD_MESSAGE'; message: ChatMessage }
  | { type: 'MERGE_MESSAGES'; messages: ChatMessage[] }
  | { type: 'REPLACE_MESSAGES'; messages: ChatMessage[] }
  | { type: 'SET_LAST_USER_DURABLE_ID'; durableId: string }
  | { type: 'SET_ACTIVE_ASSISTANT_RUNTIME_RUN'; runtimeRunId: string }
  | { type: 'UPDATE_LAST_ASSISTANT'; content: string }
  | { type: 'APPEND_REPLAYED_NARRATIVE'; content: string; dedupe?: boolean }
  | {
      type: 'APPEND_VISIBLE_REASONING';
      content: string;
      turnId?: string;
      title?: string;
      source?: 'provider' | 'harness';
    }
  | { type: 'COMPLETE_VISIBLE_REASONING'; turnId?: string }
  | { type: 'ENSURE_TRANSCRIPT_TURN'; turnId: string }
  | {
      type: 'FINALIZE_OPEN_EXECUTION_ITEMS';
      runtimeRunId?: string;
      failed?: boolean;
      terminalState?: 'completed' | 'failed' | 'cancelled' | 'needs_confirmation' | 'needs_input';
    }
  | { type: 'FLUSH_READY_ASSISTANT_CONTENT' }
  | { type: 'SET_ACTIVE_ASSISTANT_MESSAGE'; messageId: string | null }
  | { type: 'SET_STREAMING'; streaming: boolean }
  | { type: 'SET_THINKING'; thinking: boolean }
  | { type: 'SET_CANCELLATION_REQUESTED'; requested: boolean }
  | { type: 'STOP_ACTIVE_RESPONSE' }
  | { type: 'SET_STATUS'; status: AssistantStatus; runtimeRunId?: string }
  | { type: 'ADD_EXECUTION_ITEM'; item: AssistantExecutionItem }
  | {
      type: 'UPDATE_EXECUTION_ITEM';
      toolName: string;
      toolCallId?: string;
      turnId?: string;
      runId?: string;
      runtimeRunId?: string;
      patch: Partial<AssistantExecutionItem>;
    }
  | {
      type: 'MERGE_WORKFLOW_NODE';
      runId?: string;
      runtimeRunId?: string;
      node: WorkflowNodeProgress;
      currentNode?: string | null;
    }
  | { type: 'SET_SESSION_ERROR'; message: string; errorCode?: string; runtimeRunId?: string }
  | { type: 'SET_PENDING_CONFIRMATION'; confirmation: AssistantConfirmationRequest | null }
  | { type: 'SET_PENDING_INPUT'; request: AssistantInputRequest | null }
  | { type: 'SET_SELECTED_PROVIDER_CONFIG'; providerConfigId: string | null }
  | { type: 'SET_REASONING_EFFORT'; effort: AssistantReasoningEffort }
  | { type: 'SET_APPROVAL_MODE'; mode: AssistantApprovalMode }
  | { type: 'CLEAR_TRANSIENT_STATE' }
  | { type: 'CLEAR_MESSAGES' }
  | { type: 'SET_CONTEXT'; context: PageContext }
  | { type: 'SET_SUGGESTIONS'; suggestions: InlineSuggestion[] }
  | { type: 'REGISTER_COMMANDS'; commands: CommandDef[] };

/* ─── Reducer ─── */

const initialState: AIAssistantState = {
  isOpen: false,
  mode: 'panel',
  currentConversationId: null,
  conversations: [],
  messages: [],
  activeAssistantMessageId: null,
  assistantContentBuffers: {},
  isStreaming: false,
  isThinking: false,
  cancellationRequested: false,
  status: 'idle',
  executionItems: [],
  pendingConfirmation: null,
  pendingInput: null,
  sessionError: null,
  sessionErrorRuntimeRunId: null,
  selectedProviderConfigId: getStoredValue('assistantProviderConfigId'),
  reasoningEffort: parseReasoningEffort(getStoredValue('assistantReasoningEffort')),
  approvalMode: parseApprovalMode(getStoredValue('assistantApprovalMode')),
  currentContext: { page: '/' },
  suggestions: [],
  commands: []
};

function parseReasoningEffort(value: string | null): AssistantReasoningEffort {
  if (value === 'ultra') {
    return 'extra';
  }
  if (
    value === 'low' ||
    value === 'medium' ||
    value === 'high' ||
    value === 'extra' ||
    value === 'max'
  ) {
    return value;
  }
  return 'medium';
}

function parseApprovalMode(value: string | null): AssistantApprovalMode {
  if (
    value === 'request_approval' ||
    value === 'risky_only' ||
    value === 'full_access' ||
    value === 'custom'
  ) {
    return value;
  }
  return 'risky_only';
}

function createExecutionId(prefix: string, key?: string) {
  const safeKey = key ? `-${key.replace(/[^a-zA-Z0-9_-]/g, '')}` : '';
  return `${prefix}${safeKey}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function isOpenExecutionStatus(status: AssistantExecutionItem['status']) {
  return status === 'running' || status === 'pending';
}

/**
 * Accept one projected frame from a durable runtime event.
 *
 * Sequence is the replay cursor, not a unique UI-frame identity: one source
 * event can intentionally produce multiple compatibility events. Event ID and
 * projected event type make live delivery and replay idempotent without
 * dropping the second projection.
 */
export function acceptRuntimeProjection(
  cursors: RuntimeEventCursor,
  seen: Set<string>,
  eventType: string,
  data: Record<string, unknown>
): boolean {
  const runId = typeof data.runtime_run_id === 'string' ? data.runtime_run_id : undefined;
  const sequence = typeof data.runtime_sequence === 'number' ? data.runtime_sequence : undefined;
  if (!runId) return true;
  const eventId = typeof data.runtime_event_id === 'string' ? data.runtime_event_id : undefined;
  const toolCallId = typeof data.tool_call_id === 'string' ? data.tool_call_id : undefined;
  const projectionKeys: string[] = [];
  if (eventId) projectionKeys.push(`${runId}:event:${eventId}:${eventType}`);
  if (sequence !== undefined && Number.isInteger(sequence) && sequence > 0) {
    projectionKeys.push(`${runId}:sequence:${sequence}:${eventType}`);
  }
  // The live Pi adapter can emit tool.started before the durable capability
  // event exists, so that frame has no event id or sequence. Pi's native
  // tool_call_id is the stable bridge identity for live-versus-replay frames.
  if (
    toolCallId &&
    [
      'assistant.tool_started',
      'assistant.tool_succeeded',
      'assistant.tool_failed',
      'assistant.workflow_started',
      'assistant.workflow_node_progressed',
      'assistant.workflow_node_completed',
      'assistant.workflow_node_failed',
      'assistant.confirmation_requested'
    ].includes(eventType)
  ) {
    projectionKeys.push(`${runId}:tool:${toolCallId}:${eventType}`);
  }
  const duplicate = projectionKeys.some((projectionKey) => seen.has(projectionKey));
  for (const projectionKey of projectionKeys) seen.add(projectionKey);
  if (
    sequence !== undefined &&
    Number.isInteger(sequence) &&
    sequence > 0 &&
    isRuntimeSequenceNewer(cursors, runId, sequence)
  ) {
    Object.assign(cursors, advanceRuntimeSequenceCursor(cursors, runId, sequence));
  }
  return !duplicate;
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
  activeAssistantMessageId: string | null
): boolean {
  // Prefer stable tool_call_id so concurrent tools never clobber each other.
  if (action.toolCallId && item.toolCallId) {
    return item.toolCallId === action.toolCallId;
  }
  if (
    action.runId &&
    item.runId === action.runId &&
    (!action.toolName || item.toolName === action.toolName)
  ) {
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

  if (action.runtimeRunId && item.runtimeRunId === action.runtimeRunId && sameTool) {
    if (action.turnId && item.turnId && action.turnId === item.turnId) return true;
    if (!action.toolCallId || !item.toolCallId) return true;
  }

  return sameTool && item.messageId === activeAssistantMessageId && !action.toolCallId;
}

function findExecutionItemIndex(
  items: AssistantExecutionItem[],
  action: {
    toolName: string;
    toolCallId?: string;
    turnId?: string;
    runId?: string;
    runtimeRunId?: string;
  },
  activeAssistantMessageId: string | null
): number {
  if (action.toolCallId) {
    const exactToolCall = items.findIndex((item) => item.toolCallId === action.toolCallId);
    if (exactToolCall >= 0) return exactToolCall;
  }
  if (action.runId) {
    const exactRun = items.findIndex(
      (item) =>
        item.runId === action.runId && (!action.toolName || item.toolName === action.toolName)
    );
    if (exactRun >= 0) return exactRun;
  }

  // Older durable events predate persisted tool_call_id. If there is exactly
  // one open item in the same run/message/tool scope, it is the live Pi card
  // that this durable event completes. Never guess when multiple same-named
  // tools are running concurrently.
  const candidates = items.reduce<number[]>((matches, item, index) => {
    if (action.toolCallId && item.toolCallId) return matches;
    if (
      isOpenExecutionStatus(item.status) &&
      matchExecutionItem(
        { ...item, toolCallId: undefined },
        { ...action, toolCallId: undefined },
        activeAssistantMessageId
      )
    ) {
      matches.push(index);
    }
    return matches;
  }, []);
  return candidates.length === 1 ? candidates[0] : -1;
}

function getLastAssistantMessageId(state: AIAssistantState) {
  for (let i = state.messages.length - 1; i >= 0; i--) {
    if (state.messages[i].role === 'assistant') return state.messages[i].id;
  }
  return null;
}

function hasOpenActivity(state: AIAssistantState, messageId: string) {
  return state.executionItems.some(
    (item) =>
      item.messageId === messageId && (item.status === 'running' || item.status === 'pending')
  );
}

function appendAssistantContent(
  state: AIAssistantState,
  messageId: string,
  content: string
): AIAssistantState {
  return {
    ...state,
    messages: state.messages.map((message) => {
      if (message.id !== messageId || message.role !== 'assistant') return message;
      const transcriptParts = appendNarrativePart(message.transcriptParts, content);
      return {
        ...message,
        content: narrativeTextFromParts(transcriptParts) || message.content + content,
        transcriptParts
      };
    })
  };
}

function appendAssistantReasoning(
  state: AIAssistantState,
  content: string,
  turnId?: string,
  title?: string,
  source?: 'provider' | 'harness'
): AIAssistantState {
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  if (!messageId) return state;
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === messageId && message.role === 'assistant'
        ? {
            ...message,
            transcriptParts: appendReasoningPart(message.transcriptParts, content, {
              turnId,
              title,
              source
            })
          }
        : message
    )
  };
}

function completeAssistantReasoning(state: AIAssistantState, turnId?: string): AIAssistantState {
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  if (!messageId) return state;
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === messageId && message.role === 'assistant'
        ? { ...message, transcriptParts: completeReasoningPart(message.transcriptParts, turnId) }
        : message
    )
  };
}

function ensureAssistantTurnPart(
  state: AIAssistantState,
  turnId: string | undefined
): AIAssistantState {
  if (!turnId) return state;
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  if (!messageId) return state;
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === messageId && message.role === 'assistant'
        ? { ...message, transcriptParts: ensureTurnPart(message.transcriptParts, turnId) }
        : message
    )
  };
}

function latestExecutionGroupId(state: AIAssistantState, turnId: string | undefined) {
  if (!turnId) return undefined;
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  const message = state.messages.find((candidate) => candidate.id === messageId);
  if (!message) return undefined;
  for (let index = message.transcriptParts?.length ?? 0; index > 0; index -= 1) {
    const part = message.transcriptParts?.[index - 1];
    if (part?.kind === 'turn' && part.turnId === turnId) return part.executionGroupId;
  }
  return undefined;
}

function appendReplayedAssistantContent(
  state: AIAssistantState,
  content: string,
  dedupe = false
): AIAssistantState {
  const messageId = state.activeAssistantMessageId ?? getLastAssistantMessageId(state);
  if (!messageId) return state;
  const message = state.messages.find((candidate) => candidate.id === messageId);
  const lastPart = message?.transcriptParts?.at(-1);
  // Durable message.completed records can be repeated by an interrupted
  // cancellation/replay race. Only dedupe complete frames; consecutive delta
  // frames are allowed to contain the same text by design.
  if (
    dedupe &&
    lastPart?.kind === 'narrative' &&
    normalizeTranscriptText(lastPart.text) === normalizeTranscriptText(content)
  ) {
    return state;
  }
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === messageId && message.role === 'assistant'
        ? { ...message, transcriptParts: appendNarrativePart(message.transcriptParts, content) }
        : message
    )
  };
}

function appendOrBufferAssistantContent(
  state: AIAssistantState,
  content: string
): AIAssistantState {
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
    assistantContentBuffers: nextBuffers
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
    case 'OPEN':
      return {
        ...state,
        isOpen: true,
        mode: action.mode ?? state.mode
      };
    case 'CLOSE':
      return { ...state, isOpen: false };
    case 'TOGGLE':
      if (state.isOpen && (!action.mode || action.mode === state.mode)) {
        return { ...state, isOpen: false };
      }
      return {
        ...state,
        isOpen: true,
        mode: action.mode ?? state.mode
      };
    case 'SET_MODE':
      return { ...state, mode: action.mode };
    case 'SET_CURRENT_CONVERSATION':
      return { ...state, currentConversationId: action.conversationId };
    case 'SET_CONVERSATIONS':
      return { ...state, conversations: action.conversations };
    case 'UPDATE_CONVERSATION_TITLE':
      return {
        ...state,
        conversations: state.conversations.map((conversation) =>
          conversation.id === action.conversationId
            ? { ...conversation, title: action.title }
            : conversation
        )
      };
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.message] };
    case 'MERGE_MESSAGES': {
      return { ...state, messages: mergeAssistantMessages(state.messages, action.messages) };
    }
    case 'REPLACE_MESSAGES':
      return {
        ...state,
        messages: action.messages,
        activeAssistantMessageId: null,
        assistantContentBuffers: {},
        executionItems: [],
        pendingConfirmation: null,
        pendingInput: null,
        sessionError: null,
        isThinking: false,
        cancellationRequested: false
      };
    case 'SET_LAST_USER_DURABLE_ID': {
      let messageIndex = -1;
      for (let index = state.messages.length - 1; index >= 0; index -= 1) {
        if (state.messages[index].role === 'user') {
          messageIndex = index;
          break;
        }
      }
      if (messageIndex < 0) return state;
      const messages = [...state.messages];
      messages[messageIndex] = { ...messages[messageIndex], durableId: action.durableId };
      return { ...state, messages };
    }
    case 'SET_ACTIVE_ASSISTANT_RUNTIME_RUN': {
      if (!state.activeAssistantMessageId) return state;
      const messages = state.messages.map((message) =>
        message.id === state.activeAssistantMessageId
          ? { ...message, runtimeRunId: action.runtimeRunId }
          : message
      );
      return { ...state, messages };
    }
    case 'UPDATE_LAST_ASSISTANT': {
      return appendOrBufferAssistantContent(state, action.content);
    }
    case 'APPEND_REPLAYED_NARRATIVE':
      return appendReplayedAssistantContent(state, action.content, action.dedupe);
    case 'APPEND_VISIBLE_REASONING':
      return appendAssistantReasoning(
        state,
        action.content,
        action.turnId,
        action.title,
        action.source
      );
    case 'COMPLETE_VISIBLE_REASONING':
      return completeAssistantReasoning(state, action.turnId);
    case 'ENSURE_TRANSCRIPT_TURN':
      return ensureAssistantTurnPart(state, action.turnId);
    case 'FINALIZE_OPEN_EXECUTION_ITEMS': {
      const executionItems = state.executionItems.map((item) => {
        if (!isOpenExecutionStatus(item.status)) return item;
        // A linked workflow/subagent continues after the parent Pi turn ends.
        // Its durable child run owns the later terminal update, so it must not
        // be treated as an orphaned browser-only tool card.
        if (
          (item.kind === 'workflow' || item.kind === 'subagent') &&
          Boolean(item.runId || item.runtimeRunId)
        ) {
          return item;
        }
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
        // A closed browser stream is not evidence that the provider tool
        // finished. Keep the card and make missing terminal evidence visible
        // instead of silently deleting the user's execution history.
        if (
          action.terminalState === 'needs_confirmation' ||
          action.terminalState === 'needs_input'
        ) {
          return item;
        }
        const cancelled = action.terminalState === 'cancelled';
        return {
          ...item,
          status: cancelled ? ('cancelled' as const) : ('failed' as const),
          isRunning: false,
          isWaitingApproval: false,
          errorMessage:
            item.errorMessage ||
            (cancelled ? '本轮响应已停止。' : '工具执行未收到完成事件，本轮未能确认结果。'),
          summary: item.summary || (cancelled ? '本轮响应已停止' : '工具执行未收到完成事件')
        };
      });
      return flushReadyAssistantBuffers({ ...state, executionItems });
    }
    case 'FLUSH_READY_ASSISTANT_CONTENT':
      return flushReadyAssistantBuffers(state);
    case 'SET_ACTIVE_ASSISTANT_MESSAGE':
      return { ...state, activeAssistantMessageId: action.messageId };
    case 'SET_STREAMING':
      return {
        ...state,
        isStreaming: action.streaming,
        isThinking: action.streaming ? state.isThinking : false
      };
    case 'SET_THINKING':
      return { ...state, isThinking: action.thinking };
    case 'SET_CANCELLATION_REQUESTED':
      return { ...state, cancellationRequested: action.requested };
    case 'STOP_ACTIVE_RESPONSE': {
      const activeMessageId = state.activeAssistantMessageId;
      const executionItems = state.executionItems.map((item) => {
        if (
          item.messageId !== activeMessageId ||
          !isOpenExecutionStatus(item.status) ||
          (item.kind === 'workflow' && Boolean(item.runtimeRunId || item.runId))
        ) {
          return item;
        }
        return {
          ...item,
          status: 'cancelled' as const,
          isRunning: false,
          isWaitingApproval: false,
          summary: item.summary || '本轮响应已停止'
        };
      });
      const hasBackgroundWorkflow = executionItems.some(
        (item) =>
          item.kind === 'workflow' &&
          isOpenExecutionStatus(item.status) &&
          Boolean(item.runtimeRunId || item.runId)
      );
      return flushReadyAssistantBuffers({
        ...state,
        isStreaming: false,
        isThinking: false,
        cancellationRequested: false,
        status: hasBackgroundWorkflow ? 'running_workflow' : 'completed',
        activeAssistantMessageId: null,
        executionItems
      });
    }
    case 'SET_STATUS': {
      // A late generic SSE terminator must not convert a failure or a durable
      // human-input pause into a completed turn. The next user turn resumes it.
      const terminalStatusBelongsToExistingFailure =
        !state.sessionErrorRuntimeRunId ||
        !action.runtimeRunId ||
        state.sessionErrorRuntimeRunId === action.runtimeRunId;
      if (
        action.status === 'completed' &&
        (state.status === 'failed' ||
          state.status === 'needs_input' ||
          state.status === 'needs_confirmation') &&
        terminalStatusBelongsToExistingFailure
      ) {
        return state;
      }
      return { ...state, status: action.status };
    }
    case 'ADD_EXECUTION_ITEM': {
      const baseIncoming = {
        ...action.item,
        messageId: action.item.messageId ?? state.activeAssistantMessageId ?? undefined
      };
      const executionStarted = isOpenExecutionStatus(baseIncoming.status);
      const stateWithClosedReasoning = executionStarted
        ? completeAssistantReasoning(state, baseIncoming.turnId)
        : state;
      const stateWithTurn = ensureAssistantTurnPart(stateWithClosedReasoning, baseIncoming.turnId);
      const incoming = {
        ...baseIncoming,
        executionGroupId:
          baseIncoming.executionGroupId ?? latestExecutionGroupId(stateWithTurn, baseIncoming.turnId)
      };
      const identity = executionIdentity(incoming);
      const existingIndex = identity
        ? stateWithTurn.executionItems.findIndex(
            (item) => executionIdentity(item) === identity
          )
        : -1;
      if (existingIndex < 0) {
        return {
          ...stateWithTurn,
          executionItems: [...stateWithClosedReasoning.executionItems, incoming]
        };
      }

      const existing = stateWithTurn.executionItems[existingIndex];
      const keepTerminalStatus =
        !isOpenExecutionStatus(existing.status) && isOpenExecutionStatus(incoming.status);
      const merged = {
        ...existing,
        ...incoming,
        id: existing.id,
        messageId: existing.messageId ?? incoming.messageId,
        status: keepTerminalStatus ? existing.status : incoming.status,
        isRunning: keepTerminalStatus ? existing.isRunning : incoming.isRunning
      };
      const executionItems = [...stateWithTurn.executionItems];
      executionItems[existingIndex] = merged;
      return { ...stateWithTurn, executionItems };
    }
    case 'UPDATE_EXECUTION_ITEM': {
      const executionStarted =
        action.patch.status === 'pending' || action.patch.status === 'running';
      const stateWithClosedReasoning = executionStarted
        ? completeAssistantReasoning(state, action.turnId ?? action.patch.turnId)
        : state;
      const existingIndex = findExecutionItemIndex(
        stateWithClosedReasoning.executionItems,
        action,
        stateWithClosedReasoning.activeAssistantMessageId
      );
      const executionItems = [...stateWithClosedReasoning.executionItems];
      if (existingIndex >= 0) {
        const item = executionItems[existingIndex];
        // Preserve the first stable ids when later durable events omit them.
        const mergedPatch = { ...action.patch };
        if (Object.prototype.hasOwnProperty.call(action.patch, 'result')) {
          mergedPatch.result = {
            ...item.result,
            ...action.patch.result
          };
        }
        executionItems[existingIndex] = {
          ...item,
          ...mergedPatch,
          toolCallId: mergedPatch.toolCallId ?? item.toolCallId,
          turnId: item.turnId ?? mergedPatch.turnId ?? action.turnId,
          runtimeRunId: item.runtimeRunId ?? mergedPatch.runtimeRunId ?? action.runtimeRunId,
          runId: item.runId ?? mergedPatch.runId ?? action.runId,
          messageId:
            item.messageId ?? stateWithClosedReasoning.activeAssistantMessageId ?? undefined
        };
      } else {
        executionItems.push({
          id: createExecutionId('exec', action.toolCallId ?? action.runId ?? action.toolName),
          messageId: stateWithClosedReasoning.activeAssistantMessageId ?? undefined,
          kind: 'tool',
          toolName: action.toolName,
          toolCallId: action.toolCallId,
          turnId: action.turnId,
          runId: action.runId,
          runtimeRunId: action.runtimeRunId,
          status: action.patch.status ?? 'pending',
          title: action.toolName,
          timestamp: Date.now(),
          ...action.patch
        });
      }
      const withTurn = ensureAssistantTurnPart(
        { ...stateWithClosedReasoning, executionItems },
        action.turnId ?? action.patch.turnId
      );
      const targetIndex = existingIndex >= 0 ? existingIndex : executionItems.length - 1;
      const groupId = latestExecutionGroupId(
        withTurn,
        action.turnId ?? action.patch.turnId
      );
      if (targetIndex >= 0 && groupId && !executionItems[targetIndex].executionGroupId) {
        executionItems[targetIndex] = {
          ...executionItems[targetIndex],
          executionGroupId: groupId
        };
      }
      return flushReadyAssistantBuffers({ ...withTurn, executionItems });
    }
    case 'MERGE_WORKFLOW_NODE': {
      const executionItems = state.executionItems.map((item) => {
        const matches = action.runId
          ? item.runId === action.runId
          : action.runtimeRunId
            ? item.runtimeRunId === action.runtimeRunId
            : false;
        if (!matches) return item;
        const status: AssistantExecutionItem['status'] =
          item.status === 'failed' || item.status === 'succeeded' || item.status === 'cancelled'
            ? item.status
            : 'running';
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
          isRunning: true
        };
      });
      return flushReadyAssistantBuffers({ ...state, executionItems });
    }
    case 'SET_PENDING_CONFIRMATION':
      return {
        ...state,
        pendingConfirmation: action.confirmation
          ? {
              ...action.confirmation,
              messageId:
                action.confirmation.messageId ?? state.activeAssistantMessageId ?? undefined
            }
          : null
      };
    case 'SET_PENDING_INPUT':
      return {
        ...state,
        pendingInput: action.request
          ? {
              ...action.request,
              messageId: action.request.messageId ?? state.activeAssistantMessageId ?? undefined
            }
          : null
      };
    case 'SET_SELECTED_PROVIDER_CONFIG':
      return { ...state, selectedProviderConfigId: action.providerConfigId };
    case 'SET_REASONING_EFFORT':
      return { ...state, reasoningEffort: action.effort };
    case 'SET_APPROVAL_MODE':
      return { ...state, approvalMode: action.mode };
    case 'SET_SESSION_ERROR':
      return {
        ...state,
        status: 'failed',
        sessionError: action.message,
        sessionErrorRuntimeRunId: action.runtimeRunId ?? null,
        isThinking: false,
        cancellationRequested: false
      };
    case 'CLEAR_TRANSIENT_STATE':
      return {
        ...state,
        pendingConfirmation: null,
        pendingInput: null,
        sessionError: null,
        sessionErrorRuntimeRunId: null,
        isThinking: false,
        cancellationRequested: false
      };
    case 'CLEAR_MESSAGES':
      return {
        ...state,
        messages: [],
        activeAssistantMessageId: null,
        assistantContentBuffers: {},
        executionItems: [],
        pendingConfirmation: null,
        pendingInput: null,
        sessionError: null,
        sessionErrorRuntimeRunId: null,
        isThinking: false,
        cancellationRequested: false
      };
    case 'SET_CONTEXT':
      return { ...state, currentContext: action.context };
    case 'SET_SUGGESTIONS':
      return { ...state, suggestions: action.suggestions };
    case 'REGISTER_COMMANDS':
      return { ...state, commands: action.commands };
    default:
      return state;
  }
}

/** Merge optimistic live messages with their server-owned counterparts. */
export function mergeAssistantMessages(
  current: ChatMessage[],
  incoming: ChatMessage[]
): ChatMessage[] {
  const messages = [...current];
  for (const nextMessage of incoming) {
    const index = messages.findIndex(
      (message) =>
        message.id === nextMessage.id ||
        (Boolean(message.durableId) && message.durableId === nextMessage.durableId) ||
        (message.role === nextMessage.role &&
          Boolean(message.runtimeRunId) &&
          message.runtimeRunId === nextMessage.runtimeRunId)
    );
    if (index < 0) {
      messages.push(nextMessage);
      continue;
    }
    messages[index] = {
      ...messages[index],
      ...nextMessage,
      transcriptParts: messages[index].transcriptParts ?? nextMessage.transcriptParts
    };
  }
  messages.sort((left, right) => left.timestamp - right.timestamp);
  return messages;
}

interface AssistantSseHandlingOptions {
  shouldHandleRuntimeEvent?: (eventType: string, data: Record<string, unknown>) => boolean;
  onRuntimeRun?: (runId: string) => void;
  /** Return false when a late event belongs to a conversation no longer visible. */
  onConversation?: (conversationId: string) => boolean | void;
  onTerminal?: () => void;
  /** Build ordered transcript parts without duplicating stored message text. */
  replayOnly?: boolean;
  /** Runtime ids that still have recent outbox/Pi evidence during replay. */
  liveRuntimeRunIds?: ReadonlySet<string>;
  /** Keep polling until a durable terminal event is observed. */
  waitForDurableTerminal?: boolean;
  navigate?: (path: string) => void;
}

function handleAssistantSsePart(
  part: string,
  dispatch: Dispatch<Action>,
  options?: AssistantSseHandlingOptions
) {
  const parsedSse = parseSsePart(part);
  if (!parsedSse) return;
  handleAssistantSseEvent(parsedSse.eventType, parsedSse.data, dispatch, options);
}

function handleAssistantSseEvent(
  eventType: string,
  parsed: Record<string, unknown>,
  dispatch: Dispatch<Action>,
  options?: AssistantSseHandlingOptions
) {
  const runtimeRunId =
    typeof parsed.runtime_run_id === 'string' ? parsed.runtime_run_id : undefined;
  if (runtimeRunId) {
    if (options?.shouldHandleRuntimeEvent && !options.shouldHandleRuntimeEvent(eventType, parsed))
      return;
    options?.onRuntimeRun?.(runtimeRunId);
  }

  const state = asAssistantStatus(parsed.state);
  if (state) {
    dispatch({ type: 'SET_STATUS', status: state, runtimeRunId });
  }

  if (eventType === 'assistant.start') {
    const conversationId = parsed.conversation_id;
    if (typeof conversationId === 'string') {
      const accepted = options?.onConversation?.(conversationId);
      if (accepted === false) return;
      dispatch({ type: 'SET_CURRENT_CONVERSATION', conversationId });
    }
    const userMessageId = parsed.user_message_id;
    if (typeof userMessageId === 'string') {
      dispatch({ type: 'SET_LAST_USER_DURABLE_ID', durableId: userMessageId });
    }
    return;
  }

  if (eventType === 'assistant.intent_detected') {
    return;
  }

  if (eventType === 'assistant.plan_updated') {
    const items = Array.isArray(parsed.items) ? parsed.items : [];
    const titles = items
      .map((item) => asRecord(item).title)
      .filter((title): title is string => typeof title === 'string' && title.length > 0);
    dispatch({
      type: 'APPEND_VISIBLE_REASONING',
      content:
        typeof parsed.summary === 'string' && parsed.summary.trim()
          ? parsed.summary
          : titles.length > 0
            ? `执行计划：${titles.join('、')}。`
            : '已更新执行计划。',
      turnId: typeof parsed.turn_id === 'string' ? parsed.turn_id : undefined,
      title: '执行计划',
      source: 'harness'
    });
    dispatch({
      type: 'COMPLETE_VISIBLE_REASONING',
      turnId: typeof parsed.turn_id === 'string' ? parsed.turn_id : undefined
    });
    return;
  }

  if (eventType === 'assistant.confirmation_requested') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    dispatch({ type: 'SET_STREAMING', streaming: false });
    const toolName = String(parsed.tool_name ?? '');
    const args = asRecord(parsed.arguments);
    dispatch({
      type: 'SET_PENDING_CONFIRMATION',
      confirmation: {
        approvalId: typeof parsed.approval_id === 'string' ? parsed.approval_id : undefined,
        runtimeRunId: typeof parsed.runtime_run_id === 'string' ? parsed.runtime_run_id : undefined,
        toolName,
        arguments: args,
        message: String(parsed.message ?? 'Confirm this action'),
        requiresTypedConfirmation: Boolean(parsed.requires_typed_confirmation),
        expectedText: typeof parsed.expected_text === 'string' ? parsed.expected_text : undefined
      }
    });
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName,
      patch: {
        kind: 'tool',
        status: 'pending',
        title: toolName,
        arguments: args,
        summary: String(parsed.message ?? '')
      }
    });
    // Confirmation is an intentional pause: the server can close this SSE
    // response while the durable run waits for the user's decision. Treat it
    // as a settled stream, not as a lost connection.
    options?.onTerminal?.();
    return;
  }

  if (eventType === 'assistant.missing_input') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    dispatch({ type: 'SET_STREAMING', streaming: false });
    const missingFields = Array.isArray(parsed.missing_fields)
      ? parsed.missing_fields.filter(
          (field): field is string => typeof field === 'string' && field.trim().length > 0
        )
      : [];
    dispatch({
      type: 'SET_PENDING_INPUT',
      request: {
        runtimeRunId,
        toolName: typeof parsed.tool_name === 'string' ? parsed.tool_name : 'assistant',
        missingFields,
        message:
          typeof parsed.message === 'string' && parsed.message.trim()
            ? parsed.message
            : '还需要补充信息才能继续。'
      }
    });
    dispatch({ type: 'SET_STATUS', status: 'needs_input' });
    // A missing field is an intentional durable pause. The same conversation
    // can resume after the user submits the structured values.
    options?.onTerminal?.();
    return;
  }

  if (eventType === 'assistant.turn_started') {
    // Pi emits turn.started before model output. It marks a live model turn,
    // but it is not evidence that the provider returned a thinking block.
    // Only thinking.started may set the user-facing thinking state.
    dispatch({ type: 'SET_THINKING', thinking: false });
    return;
  }

  if (eventType === 'assistant.turn_finished') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    return;
  }

  if (eventType === 'assistant.runtime_state') {
    // Queue, retry and compaction frames describe session lifecycle, not a
    // user-visible reasoning phase. Only native Pi thinking boundaries may
    // drive the thinking indicator.
    if (parsed.phase === 'thinking.started') {
      dispatch({ type: 'SET_THINKING', thinking: true });
    } else if (parsed.phase === 'thinking.completed') {
      dispatch({ type: 'SET_THINKING', thinking: false });
    }
    return;
  }

  if (eventType === 'assistant.task_started') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    const presentationKind =
      typeof parsed.presentation_kind === 'string' ? parsed.presentation_kind : '';
    const resourceKind = typeof parsed.resource_kind === 'string' ? parsed.resource_kind : '';
    const skillName = typeof parsed.skill_name === 'string' ? parsed.skill_name.trim() : '';
    // Skill loading is runtime plumbing, not a user task. The actual business
    // capability that follows remains visible in the chronology; exposing
    // every progressive-disclosure read creates duplicate "preparing" cards
    // when a restored Pi turn loaded more than one skill.
    if (resourceKind === 'skill' || skillName) return;
    const rawTitle = typeof parsed.title === 'string' ? parsed.title.trim() : '';
    const title =
      resourceKind === 'skill' || skillName
        ? presentationKind === 'deep_research'
          ? '准备深度调研'
          : '准备工作步骤'
        : rawTitle;
    const rawSummary = typeof parsed.summary === 'string' ? parsed.summary.trim() : '';
    const summary = resourceKind === 'skill' || skillName ? title : rawSummary || title;
    if (title || summary) {
      dispatch({
        type: 'APPEND_VISIBLE_REASONING',
        // The title is owned by the execution group. Keeping the task-start
        // block title-identical lets the thread suppress that duplicate row.
        content: title || summary,
        title: title || summary,
        turnId: typeof parsed.turn_id === 'string' ? parsed.turn_id : undefined,
        source: 'harness'
      });
    }
    return;
  }

  if (eventType === 'assistant.reasoning' && typeof parsed.content === 'string') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    // Only the Harness may publish user-facing reasoning. Provider thinking
    // tokens are private model state and must never become transcript text.
    if (parsed.source !== 'harness') return;
    dispatch({
      type: 'APPEND_VISIBLE_REASONING',
      content: parsed.content,
      turnId: typeof parsed.turn_id === 'string' ? parsed.turn_id : undefined,
      title: typeof parsed.title === 'string' ? parsed.title : undefined,
      source: 'harness'
    });
    return;
  }

  if (eventType === 'assistant.reasoning_completed') {
    if (parsed.source !== 'harness') return;
    dispatch({
      type: 'COMPLETE_VISIBLE_REASONING',
      turnId: typeof parsed.turn_id === 'string' ? parsed.turn_id : undefined
    });
    return;
  }

  if (eventType === 'assistant.tool_started') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    const toolName = String(parsed.tool_name ?? '');
    const toolCallId = typeof parsed.tool_call_id === 'string' ? parsed.tool_call_id : undefined;
    const resourceKind =
      parsed.resource_kind === 'skill' ||
      parsed.resource_kind === 'mcp' ||
      parsed.resource_kind === 'tool'
        ? parsed.resource_kind
        : undefined;
    if (resourceKind === 'skill' || toolName === 'read_skill') return;
    // Durable CAPABILITY_STARTED events often omit turn_id. Fall back to
    // runtime_run_id so tools still group and render as a turn block.
    const turnId =
      (typeof parsed.turn_id === 'string' && parsed.turn_id) ||
      (runtimeRunId ? `run:${runtimeRunId}` : undefined);
    const title = typeof parsed.title === 'string' && parsed.title ? parsed.title : toolName;
    if (turnId) {
      dispatch({ type: 'ENSURE_TRANSCRIPT_TURN', turnId });
    }
    // Only workflow capabilities own node progress. Read tools like
    // search_projects must not become "0/1 steps" cards.
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName,
      toolCallId,
      turnId,
      runtimeRunId,
      patch: {
        kind: 'tool',
        status: 'running',
        title,
        toolCallId,
        turnId,
        runtimeRunId,
        arguments: asRecord(parsed.arguments),
        isRunning: true,
        presentationKind:
          typeof parsed.presentation_kind === 'string' ? parsed.presentation_kind : undefined,
        presentationSessionId:
          typeof parsed.presentation_session_id === 'string'
            ? parsed.presentation_session_id
            : undefined,
        presentationTitle:
          typeof parsed.presentation_title === 'string' ? parsed.presentation_title : undefined,
        resourceKind,
        resourceName: typeof parsed.resource_name === 'string' ? parsed.resource_name : undefined,
        provider: typeof parsed.provider === 'string' ? parsed.provider : undefined
      }
    });
    dispatch({ type: 'SET_STATUS', status: 'executing_tool' });
    return;
  }

  if (eventType === 'assistant.workflow_started') {
    const toolName = String(parsed.tool_name ?? '');
    const toolCallId = typeof parsed.tool_call_id === 'string' ? parsed.tool_call_id : undefined;
    const turnId =
      (typeof parsed.turn_id === 'string' && parsed.turn_id) ||
      (runtimeRunId ? `run:${runtimeRunId}` : undefined);
    const result = asRecord(parsed.result);
    const runId = typeof result.run_id === 'string' ? result.run_id : undefined;
    const workflowRuntimeRunId =
      typeof result.runtime_run_id === 'string' ? result.runtime_run_id : undefined;
    const workflowIsLive =
      !options?.replayOnly ||
      Boolean(workflowRuntimeRunId && options.liveRuntimeRunIds?.has(workflowRuntimeRunId));
    if (turnId) {
      dispatch({ type: 'ENSURE_TRANSCRIPT_TURN', turnId });
    }
    dispatch({
      type: 'ADD_EXECUTION_ITEM',
      item: {
        id: `workflow-${Date.now()}`,
        kind: 'workflow',
        toolName,
        toolCallId,
        turnId,
        runId,
        runtimeRunId: workflowRuntimeRunId,
        status: workflowIsLive ? 'running' : 'failed',
        title: toolName,
        arguments: asRecord(parsed.arguments),
        result,
        presentationKind:
          typeof parsed.presentation_kind === 'string'
            ? parsed.presentation_kind
            : typeof result.presentation_kind === 'string'
              ? result.presentation_kind
              : undefined,
        presentationSessionId:
          typeof parsed.presentation_session_id === 'string'
            ? parsed.presentation_session_id
            : typeof result.presentation_session_id === 'string'
              ? result.presentation_session_id
              : workflowRuntimeRunId,
        presentationTitle:
          typeof parsed.presentation_title === 'string'
            ? parsed.presentation_title
            : typeof result.presentation_title === 'string'
              ? result.presentation_title
              : undefined,
        isRunning: workflowIsLive,
        errorMessage: workflowIsLive ? undefined : '后台任务状态已过期，未收到完成结果。',
        summary: workflowIsLive ? undefined : '后台任务状态已过期',
        timestamp: Date.now()
      }
    });
    if (workflowRuntimeRunId && workflowIsLive) {
      dispatch({ type: 'SET_STATUS', status: 'running_workflow' });
      void pollRuntimeWorkflow(workflowRuntimeRunId, toolName, dispatch, options).catch((error) => {
        dispatch({
          type: 'UPDATE_EXECUTION_ITEM',
          toolName,
          runtimeRunId: workflowRuntimeRunId,
          patch: {
            status: 'failed',
            isRunning: false,
            errorMessage: error instanceof Error ? error.message : 'Workflow event stream failed'
          }
        });
        dispatch({ type: 'SET_STATUS', status: 'failed' });
      });
    } else if (runId && !options?.replayOnly) {
      dispatch({ type: 'SET_STATUS', status: 'running_workflow' });
      void streamWorkflowRun(runId, toolName, dispatch).catch((error) => {
        dispatch({
          type: 'UPDATE_EXECUTION_ITEM',
          toolName,
          runId,
          patch: {
            status: 'failed',
            isRunning: false,
            errorMessage: error instanceof Error ? error.message : 'Workflow stream failed'
          }
        });
        dispatch({ type: 'SET_STATUS', status: 'failed' });
      });
    }
    return;
  }

  if (eventType === 'assistant.tool_succeeded') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    const toolName = String(parsed.tool_name ?? '');
    const toolCallId = typeof parsed.tool_call_id === 'string' ? parsed.tool_call_id : undefined;
    const resourceKind =
      parsed.resource_kind === 'skill' ||
      parsed.resource_kind === 'mcp' ||
      parsed.resource_kind === 'tool'
        ? parsed.resource_kind
        : undefined;
    if (resourceKind === 'skill' || toolName === 'read_skill') return;
    const turnId =
      (typeof parsed.turn_id === 'string' && parsed.turn_id) ||
      (runtimeRunId ? `run:${runtimeRunId}` : undefined);
    const result = asRecord(parsed.result);
    const linkedRun =
      typeof result.run_id === 'string' || typeof result.runtime_run_id === 'string';
    const linkedRuntimeRunId =
      typeof result.runtime_run_id === 'string' ? result.runtime_run_id : undefined;
    const linkedRunIsLive =
      !options?.replayOnly ||
      Boolean(linkedRuntimeRunId && options.liveRuntimeRunIds?.has(linkedRuntimeRunId));
    if (turnId) {
      dispatch({ type: 'ENSURE_TRANSCRIPT_TURN', turnId });
    }
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName,
      toolCallId,
      turnId,
      runtimeRunId,
      patch: {
        kind: linkedRun ? 'workflow' : 'tool',
        status: linkedRun ? (linkedRunIsLive ? 'running' : 'failed') : 'succeeded',
        result,
        summary: linkedRun && !linkedRunIsLive ? '后台任务状态已过期' : String(parsed.summary ?? ''),
        isRunning: linkedRun && linkedRunIsLive,
        errorMessage:
          linkedRun && !linkedRunIsLive ? '后台任务状态已过期，未收到完成结果。' : undefined,
        toolCallId,
        turnId,
        runtimeRunId,
        title: typeof parsed.title === 'string' && parsed.title ? parsed.title : toolName,
        presentationKind:
          typeof parsed.presentation_kind === 'string' ? parsed.presentation_kind : undefined,
        presentationSessionId:
          typeof parsed.presentation_session_id === 'string'
            ? parsed.presentation_session_id
            : undefined,
        presentationTitle:
          typeof parsed.presentation_title === 'string' ? parsed.presentation_title : undefined,
        resourceKind,
        resourceName: typeof parsed.resource_name === 'string' ? parsed.resource_name : undefined,
        provider: typeof parsed.provider === 'string' ? parsed.provider : undefined
      }
    });
    // A completed tool is not necessarily a completed turn. Pi will emit the
    // next turn/thinking boundary if it continues; an open stream alone is not
    // evidence that the model is thinking.
    if (linkedRun) {
      return;
    }
    // Structured UI actions require an explicit user click. This prevents a
    // vague request such as “can you show the canvas?” from silently
    // navigating away before the user can inspect the target.
    if (
      toolName === 'open_page' &&
      typeof result.route === 'string' &&
      !options?.replayOnly &&
      !asRecord(result.ui_action).type
    ) {
      options?.navigate?.(result.route);
    }
    // Creating a project is an Agent result, not a navigation command. Keep
    // the user in the conversation so the next step can be confirmed there.
    return;
  }

  if (eventType === 'assistant.tool_failed') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    const toolName = String(parsed.tool_name ?? '');
    const toolCallId = typeof parsed.tool_call_id === 'string' ? parsed.tool_call_id : undefined;
    const resourceKind =
      parsed.resource_kind === 'skill' ||
      parsed.resource_kind === 'mcp' ||
      parsed.resource_kind === 'tool'
        ? parsed.resource_kind
        : undefined;
    const turnId =
      (typeof parsed.turn_id === 'string' && parsed.turn_id) ||
      (runtimeRunId ? `run:${runtimeRunId}` : undefined);
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName,
      toolCallId,
      turnId,
      runtimeRunId,
      patch: {
        status: 'failed',
        errorMessage: String(parsed.error_message ?? 'Tool failed'),
        errorCode: typeof parsed.error_code === 'string' ? parsed.error_code : undefined,
        toolCallId,
        turnId,
        resourceKind,
        resourceName: typeof parsed.resource_name === 'string' ? parsed.resource_name : undefined,
        provider: typeof parsed.provider === 'string' ? parsed.provider : undefined
      }
    });
    dispatch({ type: 'SET_STATUS', status: 'failed' });
    return;
  }

  if (eventType === 'assistant.tool_progressed') {
    const toolName = String(parsed.tool_name ?? '');
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName,
      patch: {
        kind: 'tool',
        status: 'running',
        title: toolName,
        summary: undefined,
        errorCode: typeof parsed.error_code === 'string' ? parsed.error_code : undefined,
        retryAttempt: typeof parsed.retry_attempt === 'number' ? parsed.retry_attempt : undefined,
        retryMaxAttempts:
          typeof parsed.retry_max_attempts === 'number' ? parsed.retry_max_attempts : undefined
      }
    });
    dispatch({ type: 'SET_STATUS', status: 'executing_tool' });
    return;
  }

  if (eventType === 'assistant.deep_research_progress') {
    const result = asRecord(parsed.result);
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName: 'start_deep_research',
      toolCallId: typeof parsed.tool_call_id === 'string' ? parsed.tool_call_id : undefined,
      turnId: typeof parsed.turn_id === 'string' ? parsed.turn_id : undefined,
      runtimeRunId,
      patch: {
        kind: 'workflow',
        status: 'running',
        isRunning: true,
        summary: typeof parsed.summary === 'string' ? parsed.summary : undefined,
        presentationKind: 'deep_research',
        presentationSessionId:
          typeof parsed.presentation_session_id === 'string'
            ? parsed.presentation_session_id
            : runtimeRunId,
        presentationTitle:
          typeof parsed.presentation_title === 'string' ? parsed.presentation_title : '深度调研',
        result: {
          ...result,
          phase: typeof parsed.phase === 'string' ? parsed.phase : result.phase
        }
      }
    });
    dispatch({ type: 'SET_STATUS', status: 'running_workflow' });
    return;
  }

  if (eventType === 'assistant.deep_research_completed') {
    const result = asRecord(parsed.result);
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName: 'start_deep_research',
      toolCallId: typeof parsed.tool_call_id === 'string' ? parsed.tool_call_id : undefined,
      turnId: typeof parsed.turn_id === 'string' ? parsed.turn_id : undefined,
      runtimeRunId,
      patch: {
        kind: 'workflow',
        status: parsed.state === 'failed' ? 'failed' : 'succeeded',
        isRunning: false,
        summary: typeof parsed.summary === 'string' ? parsed.summary : undefined,
        errorMessage: typeof parsed.error_message === 'string' ? parsed.error_message : undefined,
        errorCode: typeof parsed.error_code === 'string' ? parsed.error_code : undefined,
        presentationKind: 'deep_research',
        presentationSessionId:
          typeof parsed.presentation_session_id === 'string'
            ? parsed.presentation_session_id
            : runtimeRunId,
        presentationTitle:
          typeof parsed.presentation_title === 'string' ? parsed.presentation_title : '深度调研',
        result: {
          ...result,
          phase: typeof parsed.phase === 'string' ? parsed.phase : result.phase
        }
      }
    });
    dispatch({ type: 'SET_STATUS', status: parsed.state === 'failed' ? 'failed' : 'completed' });
    return;
  }

  if (eventType === 'assistant.workflow_provider_retry') {
    const toolName = String(parsed.tool_name ?? 'workflow');
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName,
      runtimeRunId,
      patch: {
        status: 'running',
        isRunning: true,
        summary: undefined,
        errorCode: typeof parsed.error_code === 'string' ? parsed.error_code : undefined,
        retryAttempt: typeof parsed.retry_attempt === 'number' ? parsed.retry_attempt : undefined,
        retryMaxAttempts:
          typeof parsed.retry_max_attempts === 'number' ? parsed.retry_max_attempts : undefined
      }
    });
    return;
  }

  if (eventType === 'assistant.workflow_node_failed') {
    const nodeName = String(parsed.node_name ?? parsed.tool_name ?? 'workflow');
    dispatch({
      type: 'MERGE_WORKFLOW_NODE',
      runtimeRunId,
      node: {
        name: nodeName,
        status: 'failed',
        error: typeof parsed.error_code === 'string' ? parsed.error_code : undefined
      },
      currentNode: null
    });
    return;
  }

  if (eventType === 'assistant.workflow_failed') {
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName: String(parsed.tool_name ?? 'workflow'),
      runtimeRunId,
      patch: {
        status: 'failed',
        isRunning: false,
        isWaitingApproval: false,
        currentNode: null,
        errorMessage: String(parsed.error_message ?? 'Workflow failed'),
        errorCode: typeof parsed.error_code === 'string' ? parsed.error_code : undefined
      }
    });
    return;
  }

  if (eventType === 'assistant.session_error') {
    dispatch({ type: 'SET_PENDING_CONFIRMATION', confirmation: null });
    dispatch({ type: 'SET_PENDING_INPUT', request: null });
    dispatch({
      type: 'SET_SESSION_ERROR',
      message:
        typeof parsed.message === 'string' && parsed.message.trim()
          ? parsed.message
          : '本次回复未能完成，已安全停止。',
      errorCode: typeof parsed.error_code === 'string' ? parsed.error_code : undefined,
      runtimeRunId
    });
    return;
  }

  if (eventType === 'assistant.message' && typeof parsed.content === 'string') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    if (options?.replayOnly) {
      dispatch({
        type: 'APPEND_REPLAYED_NARRATIVE',
        content: parsed.content,
        dedupe: parsed.state === 'completed'
      });
    } else {
      dispatch({ type: 'UPDATE_LAST_ASSISTANT', content: parsed.content });
    }
    return;
  }

  if (eventType === 'assistant.end') {
    dispatch({ type: 'SET_THINKING', thinking: false });
    // Pi's terminal frame is the authoritative UI boundary. Durable replay is
    // a repair path and must not keep the stop button visible.
    dispatch({ type: 'SET_STREAMING', streaming: false });
    dispatch({ type: 'SET_CANCELLATION_REQUESTED', requested: false });
    const terminalState = state ?? (typeof parsed.state === 'string' ? parsed.state : undefined);
    if (terminalState !== 'needs_confirmation') {
      dispatch({ type: 'SET_PENDING_CONFIRMATION', confirmation: null });
    }
    if (terminalState !== 'needs_input') {
      dispatch({ type: 'SET_PENDING_INPUT', request: null });
    }
    const conversationId = parsed.conversation_id;
    if (typeof conversationId === 'string') {
      const accepted = options?.onConversation?.(conversationId);
      if (accepted === false) return;
      dispatch({ type: 'SET_CURRENT_CONVERSATION', conversationId });
    }
    // Resolve any tool cards still "running" after the stream ends. A missing
    // terminal event is a visible failure, never a reason to erase history.
    dispatch({
      type: 'FINALIZE_OPEN_EXECUTION_ITEMS',
      runtimeRunId,
      failed: parsed.state === 'failed',
      terminalState:
        state === 'failed' || state === 'needs_confirmation' || state === 'needs_input'
          ? state
          : parsed.state === 'cancelled'
            ? 'cancelled'
            : 'completed'
    });
    // A terminal event without an explicit state is still a completed turn.
    // Keeping the previous `thinking` state here leaves the composer stuck
    // even though the server has closed the response successfully.
    dispatch({ type: 'SET_STATUS', status: state ?? 'completed' });
    options?.onTerminal?.();
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asAssistantStatus(value: unknown): AssistantStatus | undefined {
  if (
    value === 'idle' ||
    value === 'queued' ||
    value === 'thinking' ||
    value === 'needs_input' ||
    value === 'needs_confirmation' ||
    value === 'executing_tool' ||
    value === 'running_workflow' ||
    value === 'completed' ||
    value === 'failed'
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
  sendMessage: (content: string, options?: SendAssistantOptions) => Promise<void>;
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

const API_BASE = '/api/bidpilot';

async function streamWorkflowRun(
  runId: string,
  toolName: string,
  dispatch: Dispatch<Action>,
  onTerminal?: () => void
) {
  const response = await fetch(`${API_BASE}/drafting/runs/${runId}/stream`, {
    credentials: 'include'
  });

  if (!response.ok || !response.body) {
    throw new Error(`Workflow stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const updateWorkflow = (patch: Partial<AssistantExecutionItem>) => {
    dispatch({ type: 'UPDATE_EXECUTION_ITEM', toolName, runId, patch });
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';

    for (const part of parts) {
      const parsed = parseSsePart(part);
      if (!parsed) continue;

      const { eventType, data } = parsed;
      if (eventType === 'connected') {
        const runtimeRunId =
          typeof data.runtime_run_id === 'string' ? data.runtime_run_id : undefined;
        updateWorkflow({
          status: 'running',
          isRunning: true,
          currentNode: null,
          runtimeRunId
        });
        dispatch({ type: 'SET_STATUS', status: 'running_workflow' });
      } else if (eventType === 'node_started') {
        const nodeName = typeof data.node_name === 'string' ? data.node_name : 'unknown';
        dispatch({
          type: 'MERGE_WORKFLOW_NODE',
          runId,
          node: { name: nodeName, status: 'running', startedAt: new Date().toISOString() },
          currentNode: nodeName
        });
      } else if (eventType === 'node_completed') {
        const nodeName = typeof data.node_name === 'string' ? data.node_name : 'unknown';
        dispatch({
          type: 'MERGE_WORKFLOW_NODE',
          runId,
          node: { name: nodeName, status: 'completed', completedAt: new Date().toISOString() },
          currentNode: null
        });
      } else if (eventType === 'provider_retry') {
        const nodeName = typeof data.node_name === 'string' ? data.node_name : undefined;
        if (nodeName) {
          dispatch({
            type: 'MERGE_WORKFLOW_NODE',
            runId,
            node: { name: nodeName, status: 'running' },
            currentNode: nodeName
          });
        }
        updateWorkflow({
          status: 'running',
          isRunning: true,
          summary: undefined,
          errorCode: typeof data.error_code === 'string' ? data.error_code : undefined,
          retryAttempt: typeof data.attempt === 'number' ? data.attempt : undefined,
          retryMaxAttempts: typeof data.max_attempts === 'number' ? data.max_attempts : undefined
        });
      } else if (eventType === 'review_result') {
        updateWorkflow({
          reviewResult: {
            score: Number(data.score ?? 0),
            feedback: typeof data.feedback === 'string' ? data.feedback : '',
            pass: Boolean(data.passed ?? data.pass)
          }
        });
      } else if (eventType === 'human_approval_required') {
        updateWorkflow({
          status: 'running',
          isWaitingApproval: true,
          approvalMessage:
            typeof data.draft_preview === 'string' ? data.draft_preview : '等待人工审核'
        });
      } else if (eventType === 'graph_cancellation_requested') {
        updateWorkflow({
          status: 'running',
          isRunning: true,
          isWaitingApproval: false,
          isCancellationRequested: true
        });
      } else if (eventType === 'graph_cancelled') {
        updateWorkflow({
          status: 'cancelled',
          isRunning: false,
          isWaitingApproval: false,
          isCancellationRequested: true,
          currentNode: null
        });
        dispatch({ type: 'SET_STATUS', status: 'completed' });
        onTerminal?.();
        return;
      } else if (eventType === 'graph_completed') {
        updateWorkflow({
          status: data.persisted ? 'succeeded' : 'failed',
          isRunning: false,
          isWaitingApproval: false,
          currentNode: null
        });
        dispatch({ type: 'SET_STATUS', status: data.persisted ? 'completed' : 'failed' });
        onTerminal?.();
        return;
      } else if (eventType === 'graph_error') {
        const cancelled = data.status === 'cancelled';
        const nodeName = typeof data.node_name === 'string' ? data.node_name : undefined;
        const errorCode = typeof data.error_code === 'string' ? data.error_code : undefined;
        if (nodeName && !cancelled) {
          dispatch({
            type: 'MERGE_WORKFLOW_NODE',
            runId,
            node: { name: nodeName, status: 'failed', error: errorCode },
            currentNode: null
          });
        }
        updateWorkflow({
          status: cancelled ? 'cancelled' : 'failed',
          isRunning: false,
          isWaitingApproval: false,
          isCancellationRequested: cancelled,
          currentNode: null,
          errorMessage: cancelled
            ? undefined
            : typeof data.error_message === 'string'
              ? data.error_message
              : 'Workflow failed',
          errorCode
        });
        dispatch({ type: 'SET_STATUS', status: cancelled ? 'completed' : 'failed' });
        onTerminal?.();
        return;
      }
    }
  }

  onTerminal?.();
}

// Polling is only the reconnect fallback; the normal Pi path is Redis-backed
// SSE. Keep the fallback below the public API budget even when a workflow is
// open for several minutes.
const RUNTIME_EVENT_POLL_INTERVAL_MS = 2_000;
const RUNTIME_EVENT_POLL_MAX_ATTEMPTS = 500;

function waitForRuntimePoll() {
  return new Promise<void>((resolve) => window.setTimeout(resolve, RUNTIME_EVENT_POLL_INTERVAL_MS));
}

async function pollRuntimeWorkflow(
  runtimeRunId: string,
  toolName: string,
  dispatch: Dispatch<Action>,
  options?: AssistantSseHandlingOptions
) {
  let afterSequence = 0;

  for (let attempt = 0; attempt < RUNTIME_EVENT_POLL_MAX_ATTEMPTS; attempt += 1) {
    const response = await listRuntimeEvents(runtimeRunId, afterSequence);
    let terminalStatus: AssistantExecutionItem['status'] | null = null;

    for (const event of response.items) {
      afterSequence = Math.max(afterSequence, event.sequence);
      for (const compatibilityEvent of runtimeEventToAssistantEvents(event, null)) {
        handleAssistantSseEvent(
          compatibilityEvent.eventType,
          compatibilityEvent.data,
          dispatch,
          options
        );
      }
      if (event.type === 'run.completed') terminalStatus = 'succeeded';
      if (event.type === 'run.failed') terminalStatus = 'failed';
      if (event.type === 'run.cancelled') terminalStatus = 'cancelled';
    }

    if (terminalStatus) {
      dispatch({
        type: 'UPDATE_EXECUTION_ITEM',
        toolName,
        runtimeRunId,
        patch: {
          status: terminalStatus,
          isRunning: false,
          isWaitingApproval: false,
          currentNode: null
        }
      });
      dispatch({
        type: 'SET_STATUS',
        status: terminalStatus === 'failed' ? 'failed' : 'completed'
      });
      return;
    }

    await waitForRuntimePoll();
  }

  throw new Error('Workflow status polling timed out');
}

function parseSsePart(part: string): { eventType: string; data: Record<string, unknown> } | null {
  const lines = part.split('\n');
  let eventType = '';
  let dataJson = '';
  for (const line of lines) {
    if (line.startsWith('event: ')) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith('data: ')) {
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
  options: AssistantSseHandlingOptions
): Promise<{ replayed: boolean; terminal: boolean }> {
  const response = await listRuntimeEvents(runId, cursors[runId] ?? 0);
  let replayed = false;
  let terminal = false;

  for (const event of response.items) {
    for (const compatibilityEvent of runtimeEventToAssistantEvents(event, conversationId)) {
      replayed = true;
      handleAssistantSseEvent(
        compatibilityEvent.eventType,
        compatibilityEvent.data,
        dispatch,
        options
      );
    }
    terminal ||= isTerminalRuntimeEvent(event);
  }

  return { replayed, terminal };
}

function isRuntimeRunVisibleOpen(run: RuntimeRunListItem): boolean {
  return ['queued', 'running', 'awaiting_approval', 'awaiting_input', 'cancel_requested'].includes(
    run.status
  );
}

function isRuntimeRunInProgress(run: RuntimeRunListItem): boolean {
  return ['queued', 'running', 'cancel_requested'].includes(run.status);
}

function isRuntimeRunPaused(run: RuntimeRunListItem): boolean {
  return run.status === 'awaiting_approval' || run.status === 'awaiting_input';
}

function normalizeRuntimeRuns(value: unknown): RuntimeRunListItem[] {
  if (Array.isArray(value)) return value as RuntimeRunListItem[];
  if (value && typeof value === 'object' && Array.isArray((value as { items?: unknown }).items)) {
    return (value as { items: RuntimeRunListItem[] }).items;
  }
  return [];
}

function assistantStatusForRuntimeRun(run: RuntimeRunListItem): AssistantStatus {
  switch (run.status) {
    case 'queued':
      return 'queued';
    case 'running':
      return 'thinking';
    case 'awaiting_approval':
      return 'needs_confirmation';
    case 'awaiting_input':
      return 'needs_input';
    case 'cancel_requested':
      return 'thinking';
    case 'succeeded':
      return 'completed';
    case 'failed':
      return 'failed';
    case 'cancelled':
    case 'expired':
      return 'completed';
    default:
      return 'thinking';
  }
}

function waitForAssistantRuntimePoll(signal: AbortSignal, milliseconds = 2_000): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    const timeout = window.setTimeout(resolve, milliseconds);
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timeout);
        resolve();
      },
      { once: true }
    );
  });
}

export function isAssistantBusy(status: AssistantStatus) {
  return ['queued', 'thinking', 'executing_tool', 'running_workflow'].includes(status);
}

function toStoredChatMessages(items: ChatMessageRead[]): ChatMessage[] {
  return items.map((item, index) => ({
    id: item.id,
    durableId: item.id,
    runtimeRunId: item.runtime_run_id ?? undefined,
    role: item.role,
    content: item.content,
    timestamp: item.created_at
      ? Date.parse(item.created_at) || Date.now() + index
      : Date.now() + index,
    attachments: item.attachments?.map((attachment) => ({
      id: attachment.assistant_attachment_id ?? attachment.id,
      name: attachment.name,
      kind: attachment.kind,
      size: attachment.size,
      status: attachment.extraction_status === 'failed' ? 'failed' : 'uploaded',
      documentId: attachment.document_id ?? undefined
    }))
  }));
}

function mergeRecoveredRuntimeMessage(
  messages: ChatMessage[],
  recovered: ReturnType<typeof recoverRuntimeMessageFromEvents>
): { messages: ChatMessage[]; messageId?: string } {
  if (!recovered) return { messages };
  const timestamp = recovered.timestamp ?? Date.now();
  const sameTurn = (message: ChatMessage) =>
    message.role === 'assistant' &&
    (recovered.timestamp === undefined || Math.abs(message.timestamp - timestamp) < 120_000);

  const exactIndex = messages.findIndex(
    (message) => sameTurn(message) && message.content.trim() === recovered.content
  );
  if (exactIndex >= 0) {
    return { messages, messageId: messages[exactIndex].id };
  }

  const partialIndex = messages.findIndex(
    (message) =>
      sameTurn(message) &&
      message.content.trim().length > 0 &&
      recovered.content.startsWith(message.content.trim())
  );
  if (partialIndex >= 0) {
    const next = [...messages];
    next[partialIndex] = { ...next[partialIndex], content: recovered.content, timestamp };
    return { messages: next, messageId: next[partialIndex].id };
  }

  const message: ChatMessage = {
    id: `runtime-${recovered.runId}-assistant-message`,
    role: 'assistant',
    content: recovered.content,
    timestamp
  };
  const insertAt = messages.findIndex((item) => item.timestamp > timestamp);
  if (insertAt < 0) return { messages: [...messages, message], messageId: message.id };
  return {
    messages: [...messages.slice(0, insertAt), message, ...messages.slice(insertAt)],
    messageId: message.id
  };
}

function findAssistantMessageNearTimestamp(
  messages: ChatMessage[],
  timestampSource: string | null | undefined
): string | undefined {
  const timestamp = timestampSource ? Date.parse(timestampSource) : Number.NaN;
  if (!Number.isFinite(timestamp)) return undefined;
  const candidates = messages.filter((message) => message.role === 'assistant');
  if (candidates.length === 0) return undefined;
  const closest = candidates.reduce((best, message) =>
    Math.abs(message.timestamp - timestamp) < Math.abs(best.timestamp - timestamp) ? message : best
  );
  // A durable assistant reply is committed immediately after its run. Do not
  // attach an otherwise unplaceable trace to an unrelated conversation turn.
  return Math.abs(closest.timestamp - timestamp) < 120_000 ? closest.id : undefined;
}

export function AIAssistantProvider({
  children,
  navigate
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
  const currentConversationIdRef = useRef<string | null>(state.currentConversationId);
  currentConversationIdRef.current = state.currentConversationId;
  const runtimeEventCursorsRef = useRef<RuntimeEventCursor>({});
  // A single durable RuntimeEvent may intentionally fan out to multiple UI
  // frames (for example workflow_started + tool_succeeded). The fetch cursor
  // still advances by sequence, but live/replay de-duplication must include
  // the projected event type so those frames are both retained.
  const runtimeProjectionKeysRef = useRef<Set<string>>(new Set());
  const activeStreamAbortRef = useRef<AbortController | null>(null);
  const runtimeWatchAbortRef = useRef<AbortController | null>(null);
  const activeAssistantRuntimeRunRef = useRef<string | null>(null);
  const watchedRuntimeRunRef = useRef<string | null>(null);
  const pendingAssistantCancellationRef = useRef(false);
  const pendingAssistantCancellationTimerRef = useRef<number | null>(null);
  // A conversation owns its run and its cancel affordance. The provider is
  // shared by the shell, so a single global run id would make switching
  // conversations cancel whichever task happened to start last.
  const runtimeRunByConversationRef = useRef<Record<string, string>>({});
  const streamAbortByConversationRef = useRef<Record<string, AbortController>>({});
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
  // The full workspace and the shared provider both warm the same conversation
  // list. Share the in-flight request so navigation does not double-hit the
  // API on every mount.
  const conversationRefreshRef = useRef<{
    projectId: string | null | undefined;
    promise: Promise<void>;
  } | null>(null);

  const shouldHandleRuntimeEvent = useCallback(
    (eventType: string, data: Record<string, unknown>) => {
      return acceptRuntimeProjection(
        runtimeEventCursorsRef.current,
        runtimeProjectionKeysRef.current,
        eventType,
        data
      );
    },
    []
  );

  const watchConversationRuntime = useCallback(
    async (conversationId: string, options?: AssistantSseHandlingOptions) => {
      runtimeWatchAbortRef.current?.abort();
      const controller = new AbortController();
      runtimeWatchAbortRef.current = controller;
      const isVisibleConversation = () => currentConversationIdRef.current === conversationId;
      const scopedDispatch: Dispatch<Action> = (action) => {
        // A late poll from an old conversation must never turn the current
        // conversation's composer into a shared stop button.
        if (!controller.signal.aborted && isVisibleConversation()) dispatch(action);
      };
      const watchOptions: AssistantSseHandlingOptions = {
        ...options,
        shouldHandleRuntimeEvent,
        onRuntimeRun: (runId) => {
          if (controller.signal.aborted) return;
          runtimeRunByConversationRef.current[conversationId] = runId;
          if (currentConversationIdRef.current === conversationId) {
            watchedRuntimeRunRef.current = runId;
            options?.onRuntimeRun?.(runId);
          }
        }
      };
      try {
        for (let attempt = 0; attempt < 900 && !controller.signal.aborted; attempt += 1) {
          let runs: RuntimeRunListItem[] = [];
          try {
            runs = normalizeRuntimeRuns(
              await listRuntimeRuns(20, conversationId, undefined, true)
            );
          } catch {
            // A transient reconnect failure must not turn a durable run into a
            // client-visible failure. The next poll retries from the same cursor.
            await waitForAssistantRuntimePoll(
              controller.signal,
              Math.min(5000, 1000 + attempt * 100)
            );
            continue;
          }
          const activeRuns = runs.filter(isRuntimeRunInProgress);
          const pausedRuns = runs.filter(isRuntimeRunPaused);
          const candidates =
            activeRuns.length > 0
              ? [...activeRuns].reverse()
              : pausedRuns.length > 0
                ? [...pausedRuns].reverse()
                : runs.slice(0, 1);
          let replayedTerminal = false;
          for (const run of candidates) {
            if (controller.signal.aborted) return;
            replayedTerminal ||= ['succeeded', 'failed', 'cancelled', 'expired'].includes(
              run.status
            );
            const replay = await replayRuntimeEvents(
              run.id,
              runtimeEventCursorsRef.current,
              conversationId,
              scopedDispatch,
              watchOptions
            );
            replayedTerminal ||= replay.terminal;
          }
          if (!isVisibleConversation()) return;
          const active = activeRuns[0];
          if (!active) {
            const paused = pausedRuns[0];
            if (paused) {
              scopedDispatch({ type: 'SET_STREAMING', streaming: false });
              scopedDispatch({ type: 'SET_CANCELLATION_REQUESTED', requested: false });
              scopedDispatch({ type: 'SET_STATUS', status: assistantStatusForRuntimeRun(paused) });
              delete runtimeRunByConversationRef.current[conversationId];
              watchedRuntimeRunRef.current = null;
              return;
            }
            if (options?.waitForDurableTerminal && !replayedTerminal) {
              await waitForAssistantRuntimePoll(controller.signal);
              continue;
            }
            if (replayedTerminal) options?.onTerminal?.();
            try {
              const history = await getChatConversationMessages(conversationId);
              scopedDispatch({
                type: 'MERGE_MESSAGES',
                messages: toStoredChatMessages(history.items)
              });
            } catch {
              // Runtime events remain the source of truth for the visible trace;
              // a transient chat-history refresh can be retried on next mount.
            }
            const latest = runs[0];
            scopedDispatch({ type: 'SET_STREAMING', streaming: false });
            scopedDispatch({ type: 'SET_CANCELLATION_REQUESTED', requested: false });
            scopedDispatch({
              type: 'SET_STATUS',
              status: latest ? assistantStatusForRuntimeRun(latest) : 'idle'
            });
            delete runtimeRunByConversationRef.current[conversationId];
            watchedRuntimeRunRef.current = null;
            return;
          }
          watchedRuntimeRunRef.current = active.id;
          runtimeRunByConversationRef.current[conversationId] = active.id;
          scopedDispatch({ type: 'SET_STATUS', status: assistantStatusForRuntimeRun(active) });
          scopedDispatch({
            type: 'SET_CANCELLATION_REQUESTED',
            requested: active.status === 'cancel_requested'
          });
          scopedDispatch({ type: 'SET_STREAMING', streaming: true });
          await waitForAssistantRuntimePoll(controller.signal);
        }
      } finally {
        if (runtimeWatchAbortRef.current === controller) {
          runtimeWatchAbortRef.current = null;
        }
      }
    },
    [dispatch, shouldHandleRuntimeEvent]
  );

  const open = useCallback((mode?: AssistantMode) => dispatch({ type: 'OPEN', mode }), []);
  const close = useCallback(() => dispatch({ type: 'CLOSE' }), []);
  const toggle = useCallback((mode?: AssistantMode) => dispatch({ type: 'TOGGLE', mode }), []);

  const refreshConversations = useCallback(async () => {
    const projectId = state.currentContext.projectId;
    const existing = conversationRefreshRef.current;
    if (existing && existing.projectId === projectId) return existing.promise;

    const promise = listChatConversations(projectId)
      .then((conversations) => {
        dispatch({ type: 'SET_CONVERSATIONS', conversations });
      })
      .catch((error) => {
        console.error('Failed to load chat conversations:', error);
      })
      .finally(() => {
        if (conversationRefreshRef.current?.promise === promise) {
          conversationRefreshRef.current = null;
        }
      });
    conversationRefreshRef.current = { projectId, promise };
    return promise;
  }, [state.currentContext.projectId]);

  const loadConversation = useCallback(
    async (conversationId: string) => {
      const loadVersion = ++conversationLoadVersionRef.current;
      const isCurrentLoad = () => conversationLoadVersionRef.current === loadVersion;
      setSessionStoredValue('lastAssistantConversationId', conversationId);
      // The visible composer belongs to the selected conversation. Clear the
      // previous conversation's local cancel target before loading this one.
      runtimeWatchAbortRef.current?.abort();
      // Stop consuming the previous conversation's short-lived SSE projection;
      // this does not cancel its durable Worker run.
      activeStreamAbortRef.current?.abort();
      activeAssistantRuntimeRunRef.current = null;
      watchedRuntimeRunRef.current = null;
      runtimeEventCursorsRef.current = {};
      runtimeProjectionKeysRef.current = new Set();
      pendingAssistantCancellationRef.current = false;
      if (pendingAssistantCancellationTimerRef.current !== null) {
        window.clearTimeout(pendingAssistantCancellationTimerRef.current);
        pendingAssistantCancellationTimerRef.current = null;
      }
      currentConversationIdRef.current = conversationId;
      dispatch({ type: 'SET_CURRENT_CONVERSATION', conversationId });
      dispatch({ type: 'CLEAR_MESSAGES' });
      // Clear previous run tool cards so restored transcript only shows this conversation.
      dispatch({ type: 'CLEAR_TRANSIENT_STATE' });
      dispatch({ type: 'SET_STATUS', status: 'thinking' });
      try {
        const history = await getChatConversationMessages(conversationId);
        if (!isCurrentLoad()) return;
        const messages = toStoredChatMessages(history.items);
        dispatch({
          type: 'REPLACE_MESSAGES',
          messages
        });

        // Replay durable runtime tool events so history shows L1/L2 tool cards,
        // not only plain assistant text. Runtime events also repair a missing
        // chat row when the browser disconnected before the final save commit.
        let restoredMessages = messages;
        const liveRuntimeRunIds = new Set<string>();
        let visibleRuns: RuntimeRunListItem[] = [];
        const runtimeReplay: Array<{
          runId: string;
          messageId?: string;
          events: Awaited<ReturnType<typeof listRuntimeEvents>>['items'];
        }> = [];
        try {
          // Historical terminal runs remain available within the server's
          // recent-history window, while stale queued/open rows are excluded
          // unless their outbox or real Pi execution is still alive.
          const runs = normalizeRuntimeRuns(
            await listRuntimeRuns(12, conversationId, undefined, true)
          );
          if (!isCurrentLoad()) return;
          visibleRuns = runs;
          for (const run of runs) liveRuntimeRunIds.add(run.id);
          for (const activeRun of runs.filter(isRuntimeRunVisibleOpen)) {
            if (!restoredMessages.some((message) => message.runtimeRunId === activeRun.id)) {
              restoredMessages = [
                ...restoredMessages,
                {
                  id: `runtime-${activeRun.id}-assistant-message`,
                  runtimeRunId: activeRun.id,
                  role: 'assistant',
                  content: '',
                  timestamp: Date.parse(activeRun.created_at) || Date.now()
                }
              ];
            }
          }
          // Replay oldest→newest so tool order matches conversation flow.
          for (const run of [...runs].reverse()) {
            const response = await listRuntimeEvents(run.id, 0);
            if (!isCurrentLoad()) return;
            const merged = mergeRecoveredRuntimeMessage(
              restoredMessages,
              recoverRuntimeMessageFromEvents(run.id, response.items)
            );
            restoredMessages = merged.messages;
            runtimeReplay.push({
              runId: run.id,
              messageId:
                restoredMessages.find((message) => message.runtimeRunId === run.id)?.id ??
                merged.messageId ??
                findAssistantMessageNearTimestamp(
                  restoredMessages,
                  run.finished_at ?? run.created_at
                ),
              events: response.items
            });
          }
          if (!isCurrentLoad()) return;
          if (restoredMessages !== messages) {
            dispatch({ type: 'REPLACE_MESSAGES', messages: restoredMessages });
          }

          // A run belongs to its own assistant response, never to whichever
          // response happened to be last when the transcript was restored.
          for (const { runId, messageId, events } of runtimeReplay) {
            if (!messageId) continue;
            dispatch({ type: 'SET_ACTIVE_ASSISTANT_MESSAGE', messageId });
            for (const event of events) {
              for (const compatibilityEvent of runtimeEventToAssistantEvents(
                event,
                conversationId
              )) {
                // Rebuild the public transcript from durable events in sequence.
                // The stored chat row supplies the canonical final text; the
                // replay-only action adds ordered narrative parts without
                // duplicating that text.
                if (
                  compatibilityEvent.eventType !== 'assistant.message' &&
                  compatibilityEvent.eventType !== 'assistant.tool_started' &&
                  compatibilityEvent.eventType !== 'assistant.tool_succeeded' &&
                  compatibilityEvent.eventType !== 'assistant.tool_failed' &&
                  compatibilityEvent.eventType !== 'assistant.turn_started' &&
                  compatibilityEvent.eventType !== 'assistant.turn_finished' &&
                  compatibilityEvent.eventType !== 'assistant.task_started' &&
                  compatibilityEvent.eventType !== 'assistant.reasoning' &&
                  compatibilityEvent.eventType !== 'assistant.reasoning_completed' &&
                  compatibilityEvent.eventType !== 'assistant.session_error' &&
                  compatibilityEvent.eventType !== 'assistant.confirmation_requested' &&
                  compatibilityEvent.eventType !== 'assistant.missing_input' &&
                  compatibilityEvent.eventType !== 'assistant.end'
                ) {
                  continue;
                }
                const replayedContent =
                  typeof compatibilityEvent.data.content === 'string'
                    ? compatibilityEvent.data.content
                    : null;
                if (
                  event.type === 'message.completed' &&
                  compatibilityEvent.eventType === 'assistant.message' &&
                  replayedContent !== null &&
                  restoredMessages.some(
                    (message) =>
                      message.id !== messageId &&
                      message.role === 'assistant' &&
                      Boolean(message.runtimeRunId) &&
                      message.runtimeRunId !== runId &&
                      message.content.trim() === replayedContent.trim()
                  )
                ) {
                  // A background child can persist the same user-facing
                  // completion as its parent bridge run. Keep it on the
                  // durable message that owns the child runtime instead of
                  // rendering the completion twice after reload.
                  continue;
                }
                handleAssistantSseEvent(
                  compatibilityEvent.eventType,
                  compatibilityEvent.data,
                  dispatch,
                  { shouldHandleRuntimeEvent, replayOnly: true, liveRuntimeRunIds }
                );
              }
            }
          }
        } catch (replayError) {
          if (!isCurrentLoad()) return;
          console.error('Failed to restore tool transcript:', replayError);
        }

        if (!isCurrentLoad()) return;
        // Terminal history must not leave stale live rows. Active queued/running
        // runs remain open and are completed by the durable poller below.
        // The live-only snapshot above is the authoritative hand-off to the
        // watcher. A second list request here only recreated the navigation
        // waterfall; the watcher immediately rechecks active rows itself.
        for (const run of visibleRuns.filter(
          (item) => !isRuntimeRunVisibleOpen(item)
        )) {
          dispatch({
            type: 'FINALIZE_OPEN_EXECUTION_ITEMS',
            runtimeRunId: run.id,
            failed: run.status === 'failed',
            terminalState:
              run.status === 'cancelled' || run.status === 'expired'
                ? 'cancelled'
                : run.status === 'failed'
                  ? 'failed'
                  : 'completed'
          });
        }
        const activeRun = visibleRuns.find(isRuntimeRunVisibleOpen);
        if (activeRun) {
          if (isRuntimeRunInProgress(activeRun)) {
            runtimeRunByConversationRef.current[conversationId] = activeRun.id;
            activeAssistantRuntimeRunRef.current = activeRun.id;
            watchedRuntimeRunRef.current = activeRun.id;
          } else {
            delete runtimeRunByConversationRef.current[conversationId];
            activeAssistantRuntimeRunRef.current = null;
            watchedRuntimeRunRef.current = null;
          }
          dispatch({ type: 'SET_STATUS', status: assistantStatusForRuntimeRun(activeRun) });
          dispatch({
            type: 'SET_CANCELLATION_REQUESTED',
            requested: activeRun.status === 'cancel_requested'
          });
          dispatch({ type: 'SET_STREAMING', streaming: isRuntimeRunInProgress(activeRun) });
          if (isRuntimeRunInProgress(activeRun)) void watchConversationRuntime(conversationId);
        } else {
          delete runtimeRunByConversationRef.current[conversationId];
          dispatch({ type: 'SET_CANCELLATION_REQUESTED', requested: false });
          dispatch({ type: 'SET_STATUS', status: 'idle' });
        }
        dispatch({ type: 'SET_ACTIVE_ASSISTANT_MESSAGE', messageId: null });
        dispatch({ type: 'OPEN', mode: 'panel' });
      } catch (error) {
        if (!isCurrentLoad()) return;
        console.error('Failed to load chat history:', error);
        removeSessionStoredValue('lastAssistantConversationId');
        // Keep the conversation selected but restore a visible error instead of a
        // blank transcript that looks like history was deleted.
        dispatch({
          type: 'REPLACE_MESSAGES',
          messages: [
            {
              id: `${conversationId}-load-error`,
              role: 'assistant',
              content: '加载会话历史失败，请重试或新建对话。消息仍保存在服务器上。',
              timestamp: Date.now()
            }
          ]
        });
      } finally {
        // The loaded run status (or its watcher) owns the final UI state. Do not
        // blindly reset it to idle after restoring a queued/running run.
      }
    },
    [shouldHandleRuntimeEvent, watchConversationRuntime]
  );

  const updateConversationTitle = useCallback((conversationId: string, title: string) => {
    dispatch({ type: 'UPDATE_CONVERSATION_TITLE', conversationId, title });
  }, []);

  const setSelectedProviderConfig = useCallback((providerConfigId: string | null) => {
    if (providerConfigId) {
      setStoredValue('assistantProviderConfigId', providerConfigId);
    } else {
      removeStoredValue('assistantProviderConfigId');
    }
    dispatch({ type: 'SET_SELECTED_PROVIDER_CONFIG', providerConfigId });
  }, []);

  const setReasoningEffort = useCallback((effort: AssistantReasoningEffort) => {
    setStoredValue('assistantReasoningEffort', effort);
    dispatch({ type: 'SET_REASONING_EFFORT', effort });
  }, []);

  const setApprovalMode = useCallback((mode: AssistantApprovalMode) => {
    setStoredValue('assistantApprovalMode', mode);
    dispatch({ type: 'SET_APPROVAL_MODE', mode });
  }, []);

  const requestAssistantCancellation = useCallback(
    (
      runtimeRunId: string,
      conversationId: string | null,
      streamController: AbortController | null
    ) => {
      void Promise.resolve()
        .then(() => cancelRuntimeWorkflow(runtimeRunId))
        .then((run) => {
          if (run.status === 'cancelled') {
            streamController?.abort();
            dispatch({ type: 'STOP_ACTIVE_RESPONSE' });
            return;
          }
          if (conversationId) {
            void watchConversationRuntime(conversationId, {
              onTerminal: () => streamController?.abort(),
              waitForDurableTerminal: true
            });
          }
        })
        .catch((error: unknown) => {
          // Keep the server-side run visible if the control request itself
          // fails. The user can retry the stop action instead of silently
          // detaching from a still-running Pi session.
          console.error('Failed to cancel assistant runtime:', error);
          dispatch({ type: 'SET_CANCELLATION_REQUESTED', requested: false });
        });
    },
    [watchConversationRuntime]
  );

  const cancelWorkflow = useCallback(async (runtimeRunId: string) => {
    const run = await cancelRuntimeWorkflow(runtimeRunId);
    const cancelled = run.status === 'cancelled';
    dispatch({
      type: 'UPDATE_EXECUTION_ITEM',
      toolName: 'start_draft_section',
      runtimeRunId,
      patch: {
        status: cancelled ? 'cancelled' : 'running',
        isRunning: !cancelled,
        isWaitingApproval: false,
        isCancellationRequested: true,
        currentNode: cancelled ? null : undefined
      }
    });
    if (cancelled) {
      dispatch({ type: 'SET_STATUS', status: 'completed' });
    }
  }, []);

  const stopAssistantResponse = useCallback(() => {
    const conversationId = currentConversationIdRef.current;
    const streamController = conversationId
      ? (streamAbortByConversationRef.current[conversationId] ?? activeStreamAbortRef.current)
      : activeStreamAbortRef.current;
    const runtimeRunId = conversationId
      ? (runtimeRunByConversationRef.current[conversationId] ??
        (conversationId === currentConversationIdRef.current
          ? (activeAssistantRuntimeRunRef.current ?? watchedRuntimeRunRef.current)
          : undefined))
      : (activeAssistantRuntimeRunRef.current ?? watchedRuntimeRunRef.current);
    dispatch({ type: 'SET_CANCELLATION_REQUESTED', requested: true });
    if (!runtimeRunId) {
      // The initial SSE frame normally carries the durable id immediately.
      // Keep consuming until it arrives so a fast click cannot detach the
      // browser before the server-side run can be cancelled.
      pendingAssistantCancellationRef.current = true;
      if (pendingAssistantCancellationTimerRef.current === null) {
        pendingAssistantCancellationTimerRef.current = window.setTimeout(() => {
          pendingAssistantCancellationTimerRef.current = null;
          if (!pendingAssistantCancellationRef.current) return;
          pendingAssistantCancellationRef.current = false;
          const activeController = currentConversationIdRef.current
            ? (streamAbortByConversationRef.current[currentConversationIdRef.current] ??
              activeStreamAbortRef.current)
            : activeStreamAbortRef.current;
          if (activeController && !activeController.signal.aborted) activeController.abort();
          dispatch({ type: 'STOP_ACTIVE_RESPONSE' });
        }, 500);
      }
      return;
    }
    requestAssistantCancellation(runtimeRunId, conversationId, streamController);
  }, [requestAssistantCancellation]);

  useEffect(
    () => () => {
      for (const controller of Object.values(streamAbortByConversationRef.current)) {
        controller.abort();
      }
      activeStreamAbortRef.current?.abort();
      runtimeWatchAbortRef.current?.abort();
    },
    []
  );

  const startNewConversation = useCallback(() => {
    conversationLoadVersionRef.current += 1;
    currentConversationIdRef.current = null;
    runtimeWatchAbortRef.current?.abort();
    activeStreamAbortRef.current?.abort();
    activeAssistantRuntimeRunRef.current = null;
    watchedRuntimeRunRef.current = null;
    pendingAssistantCancellationRef.current = false;
    if (pendingAssistantCancellationTimerRef.current !== null) {
      window.clearTimeout(pendingAssistantCancellationTimerRef.current);
      pendingAssistantCancellationTimerRef.current = null;
    }
    didAutoRestoreRef.current = true;
    removeSessionStoredValue('lastAssistantConversationId');
    dispatch({ type: 'SET_CURRENT_CONVERSATION', conversationId: null });
    dispatch({ type: 'CLEAR_MESSAGES' });
    dispatch({ type: 'CLEAR_TRANSIENT_STATE' });
    dispatch({ type: 'SET_STATUS', status: 'idle' });
    dispatch({ type: 'OPEN', mode: 'panel' });
  }, []);

  // Always keep the conversation list warm for both the floating panel and
  // the full /agent workspace (workspace does not set isOpen).
  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  // Auto-restore the last conversation once when the assistant surface mounts.
  useEffect(() => {
    if (didAutoRestoreRef.current) return;
    // The route owner restores an explicit ?conversation= selection. Do not
    // start a second mount-time restore from sessionStorage for the same URL;
    // that duplicate replay was the visible navigation delay.
    if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('conversation')) {
      didAutoRestoreRef.current = true;
      return;
    }
    if (state.currentConversationId || state.messages.length > 0) {
      didAutoRestoreRef.current = true;
      return;
    }
    const lastId = getSessionStoredValue('lastAssistantConversationId');
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
      }
    ) => {
      const isConfirmationRequest = Boolean(confirmation);
      const displayContent = isConfirmationRequest
        ? ''
        : (options?.displayContent ?? content).trim();
      const targetConversationId = options?.conversationId ?? state.currentConversationId;
      const targetHasKnownRun = Boolean(
        targetConversationId && runtimeRunByConversationRef.current[targetConversationId]
      );
      if (
        (!displayContent && !isConfirmationRequest) ||
        assistantRequestInFlightRef.current ||
        (targetConversationId === state.currentConversationId && isAssistantBusy(state.status)) ||
        targetHasKnownRun
      )
        return;
      assistantRequestInFlightRef.current = true;
      pendingAssistantCancellationRef.current = false;
      if (targetConversationId && targetConversationId !== state.currentConversationId) {
        setSessionStoredValue('lastAssistantConversationId', targetConversationId);
        currentConversationIdRef.current = targetConversationId;
        dispatch({ type: 'SET_CURRENT_CONVERSATION', conversationId: targetConversationId });
      }

      dispatch({ type: 'CLEAR_TRANSIENT_STATE' });
      dispatch({ type: 'SET_STATUS', status: 'thinking' });

      if (!isConfirmationRequest) {
        const userMsg: ChatMessage = {
          id: `user-${Date.now()}`,
          role: 'user',
          content: displayContent,
          timestamp: Date.now(),
          attachments: options?.attachments
        };
        dispatch({ type: 'ADD_MESSAGE', message: userMsg });

        const aiMsg: ChatMessage = {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: '',
          timestamp: Date.now()
        };
        dispatch({ type: 'ADD_MESSAGE', message: aiMsg });
        dispatch({ type: 'SET_ACTIVE_ASSISTANT_MESSAGE', messageId: aiMsg.id });
      } else if (!state.activeAssistantMessageId) {
        // A restored approval can arrive without the transient placeholder.
        // Keep the approval result attached to the assistant turn instead of
        // manufacturing a user message for the button click.
        const aiMsg: ChatMessage = {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: '',
          timestamp: Date.now()
        };
        dispatch({ type: 'ADD_MESSAGE', message: aiMsg });
        dispatch({ type: 'SET_ACTIVE_ASSISTANT_MESSAGE', messageId: aiMsg.id });
      }

      let activeRuntimeRunId: string | null = null;
      activeAssistantRuntimeRunRef.current = null;
      let activeConversationId = targetConversationId;
      let receivedTerminalEvent = false;
      const abortController = new AbortController();
      activeStreamAbortRef.current = abortController;
      if (targetConversationId) {
        streamAbortByConversationRef.current[targetConversationId] = abortController;
      }
      dispatch({ type: 'SET_STREAMING', streaming: true });
      const sseOptions: AssistantSseHandlingOptions = {
        shouldHandleRuntimeEvent,
        navigate: (path) => navigateRef.current?.(path),
        onRuntimeRun: (runId) => {
          activeRuntimeRunId = runId;
          dispatch({ type: 'SET_ACTIVE_ASSISTANT_RUNTIME_RUN', runtimeRunId: runId });
          if (activeConversationId) {
            runtimeRunByConversationRef.current[activeConversationId] = runId;
          }
          if (!activeConversationId || currentConversationIdRef.current === activeConversationId) {
            activeAssistantRuntimeRunRef.current = runId;
          }
          if (pendingAssistantCancellationRef.current && activeConversationId) {
            pendingAssistantCancellationRef.current = false;
            if (pendingAssistantCancellationTimerRef.current !== null) {
              window.clearTimeout(pendingAssistantCancellationTimerRef.current);
              pendingAssistantCancellationTimerRef.current = null;
            }
            requestAssistantCancellation(runId, activeConversationId, abortController);
          }
        },
        onConversation: (conversationId) => {
          activeConversationId = conversationId;
          if (activeRuntimeRunId) {
            runtimeRunByConversationRef.current[conversationId] = activeRuntimeRunId;
          }
          const ownsVisibleConversation =
            currentConversationIdRef.current === targetConversationId ||
            currentConversationIdRef.current === activeConversationId ||
            (!targetConversationId && currentConversationIdRef.current === null);
          if (!ownsVisibleConversation) return false;
          currentConversationIdRef.current = conversationId;
          streamAbortByConversationRef.current[conversationId] = abortController;
          setSessionStoredValue('lastAssistantConversationId', conversationId);
          if (pendingAssistantCancellationRef.current && activeRuntimeRunId) {
            pendingAssistantCancellationRef.current = false;
            if (pendingAssistantCancellationTimerRef.current !== null) {
              window.clearTimeout(pendingAssistantCancellationTimerRef.current);
              pendingAssistantCancellationTimerRef.current = null;
            }
            requestAssistantCancellation(activeRuntimeRunId, conversationId, abortController);
          }
          return true;
        },
        onTerminal: () => {
          receivedTerminalEvent = true;
        }
      };
      const recoverDurableTimeline = async () => {
        if (!activeRuntimeRunId) return { replayed: false, terminal: receivedTerminalEvent };
        // Redis is an ephemeral fast path. A terminal frame can arrive even
        // when an earlier tool frame was missed, and its high sequence would
        // otherwise make `after_sequence=<terminal>` skip that missing event.
        // Replay the complete run after a terminal boundary; projection keys
        // make already-rendered frames idempotent.
        const replayCursor = receivedTerminalEvent ? {} : runtimeEventCursorsRef.current;
        const recovered = await replayRuntimeEvents(
          activeRuntimeRunId,
          replayCursor,
          activeConversationId,
          dispatch,
          sseOptions
        );
        receivedTerminalEvent ||= recovered.terminal;
        return recovered;
      };

      try {
        const clientRequestId = crypto.randomUUID();
        const response = await fetch(`${API_BASE}/assistant/stream`, {
          method: 'POST',
          credentials: 'include',
          signal: abortController.signal,
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            message: content,
            client_request_id: clientRequestId,
            project_id: state.currentContext.projectId,
            conversation_id: targetConversationId,
            provider_config_id: options?.providerConfigId ?? state.selectedProviderConfigId,
            reasoning_effort: options?.reasoningEffort ?? state.reasoningEffort,
            approval_mode: options?.approvalMode ?? state.approvalMode,
            locale: i18n.resolvedLanguage === 'en' ? 'en' : 'zh-CN',
            confirmation,
            attachments: options?.requestAttachments ?? []
          })
        });

        if (!response.ok) {
          const errText = await response.text().catch(() => '');
          let errorCode = '';
          let errorMessage = `API ${response.status}`;
          try {
            const parsed = JSON.parse(errText);
            errorCode = String(parsed.error ?? '');
            errorMessage = String(parsed.message ?? parsed.detail ?? errorMessage);
          } catch {
            if (errText.trim()) {
              errorMessage = errText;
            }
          }
          throw Object.assign(new Error(errorMessage), {
            status: response.status,
            errorCode
          });
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (reader) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split('\n\n');
          buffer = parts.pop() ?? '';

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
          dispatch({ type: 'STOP_ACTIVE_RESPONSE' });
          return;
        }

        if (receivedTerminalEvent) {
          // The live Pi stream already delivered the authoritative terminal
          // frame. Repair any missed durable frame in the background so the
          // composer is not held on a second full replay request.
          void recoverDurableTimeline().catch((recoveryError) => {
            console.warn('Failed to replay the completed assistant timeline:', recoveryError);
          });
        } else {
          const recovered = await recoverDurableTimeline();
          if (!recovered.terminal) {
            if (activeRuntimeRunId && activeConversationId) {
              // The request is intentionally short-lived now that the Worker
              // owns execution. Continue from the same durable event cursor.
              void watchConversationRuntime(activeConversationId, sseOptions);
            } else {
              dispatch({
                type: 'SET_SESSION_ERROR',
                message: '助手连接中断，但当前任务仍保存在会话中。请稍后重试。',
                errorCode: 'assistant_stream_incomplete',
                runtimeRunId: activeRuntimeRunId ?? undefined
              });
            }
          }
        }
      } catch (err) {
        if (abortController.signal.aborted) {
          dispatch({ type: 'STOP_ACTIVE_RESPONSE' });
          return;
        }
        try {
          const recovered = await recoverDurableTimeline();
          if (recovered.terminal) return;
          if (recovered.replayed && activeRuntimeRunId && activeConversationId) {
            void watchConversationRuntime(activeConversationId, sseOptions);
            return;
          }
        } catch (recoveryError) {
          console.warn('Failed to replay assistant runtime events:', recoveryError);
        }
        const status =
          typeof (err as { status?: number }).status === 'number'
            ? (err as { status?: number }).status
            : undefined;
        const errorCode =
          typeof (err as { errorCode?: string }).errorCode === 'string'
            ? (err as { errorCode?: string }).errorCode
            : undefined;
        const message =
          err instanceof Error ? err.message : 'Something went wrong. Please try again.';
        const providerSelectionUnavailable =
          status === 404 && message === 'Provider config not found';
        if (!providerSelectionUnavailable) {
          console.error('AI assistant request failed', {
            status,
            errorCode: errorCode || undefined
          });
        }
        if (providerSelectionUnavailable) {
          dispatch({ type: 'SET_SELECTED_PROVIDER_CONFIG', providerConfigId: null });
        }
        const friendly =
          status === 403 || errorCode === 'usage_limit_exceeded'
            ? '你的试用额度已用完，请升级计划或稍后再试。'
            : providerSelectionUnavailable
              ? '所选模型配置已不可用，已切回平台默认模型。请确认后重新发送。'
              : message;
        dispatch({
          type: 'SET_SESSION_ERROR',
          message: friendly,
          errorCode,
          runtimeRunId: activeRuntimeRunId ?? undefined
        });
      } finally {
        assistantRequestInFlightRef.current = false;
        if (
          activeConversationId &&
          receivedTerminalEvent &&
          runtimeRunByConversationRef.current[activeConversationId] === activeRuntimeRunId
        ) {
          delete runtimeRunByConversationRef.current[activeConversationId];
        }
        if (activeStreamAbortRef.current === abortController) {
          activeStreamAbortRef.current = null;
          if (activeAssistantRuntimeRunRef.current === activeRuntimeRunId) {
            activeAssistantRuntimeRunRef.current = null;
          }
          if (!activeConversationId || currentConversationIdRef.current === activeConversationId) {
            dispatch({ type: 'SET_STREAMING', streaming: false });
          }
        }
        if (
          activeConversationId &&
          streamAbortByConversationRef.current[activeConversationId] === abortController
        ) {
          delete streamAbortByConversationRef.current[activeConversationId];
        }
        if (receivedTerminalEvent) {
          runtimeWatchAbortRef.current?.abort();
        }
        pendingAssistantCancellationRef.current = false;
        if (pendingAssistantCancellationTimerRef.current !== null) {
          window.clearTimeout(pendingAssistantCancellationTimerRef.current);
          pendingAssistantCancellationTimerRef.current = null;
        }
        void refreshConversations();
      }
    },
    [
      refreshConversations,
      state.currentContext.projectId,
      state.currentConversationId,
      state.activeAssistantMessageId,
      state.reasoningEffort,
      state.approvalMode,
      state.selectedProviderConfigId,
      state.status,
      requestAssistantCancellation,
      watchConversationRuntime,
      shouldHandleRuntimeEvent
    ]
  );

  const sendMessage = useCallback(
    async (content: string, options?: SendAssistantOptions) => {
      await sendAssistantRequest(content, options);
    },
    [sendAssistantRequest]
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
        setSessionStoredValue('lastAssistantConversationId', branch.conversation.id);
        currentConversationIdRef.current = branch.conversation.id;
        dispatch({ type: 'SET_CURRENT_CONVERSATION', conversationId: branch.conversation.id });
        dispatch({ type: 'REPLACE_MESSAGES', messages });
        dispatch({ type: 'SET_STATUS', status: 'idle' });
        dispatch({ type: 'OPEN', mode: 'panel' });
        await sendAssistantRequest(nextContent, {
          displayContent: nextContent,
          conversationId: branch.conversation.id
        });
      } catch (error) {
        console.error('Failed to create assistant checkpoint branch:', error);
        dispatch({
          type: 'SET_SESSION_ERROR',
          message: '无法从该检查点创建新对话，请稍后重试。'
        });
      }
    },
    [sendAssistantRequest, state.currentConversationId, state.status]
  );

  const confirmAssistantAction = useCallback(
    async (approved: boolean, confirmationText?: string) => {
      const pending = state.pendingConfirmation;
      if (!pending) return;
      if (!pending.approvalId) {
        dispatch({
          type: 'SET_SESSION_ERROR',
          message: '这项确认已经失效，请重新发起任务。'
        });
        return;
      }
      dispatch({ type: 'SET_PENDING_CONFIRMATION', confirmation: null });
      // Approval controls are a structured continuation, not a chat turn.
      // Send only the extra typed value; the server keeps the original,
      // authorized action arguments and ignores browser copies of them.
      const confirmationArguments =
        approved && pending.requiresTypedConfirmation
          ? { confirmation_text: confirmationText ?? '' }
          : {};
      await sendAssistantRequest('', undefined, {
        approved,
        tool_name: pending.toolName,
        arguments: confirmationArguments,
        approval_id: pending.approvalId
      });
    },
    [sendAssistantRequest, state.pendingConfirmation]
  );

  const executeCommand = useCallback(
    (commandId: string) => {
      const cmd = state.commands.find((c) => c.id === commandId);
      if (cmd) {
        dispatch({ type: 'CLOSE' });
        cmd.action();
      }
    },
    [state.commands]
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
        updateConversationTitle
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
    throw new Error('useAIAssistant must be used within AIAssistantProvider');
  }
  return ctx;
}
