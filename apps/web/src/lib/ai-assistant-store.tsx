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

/* ─── Types ─── */

export type AssistantMode = "panel" | "command" | "inline";
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
}

export interface AssistantConfirmationRequest {
  toolName: string;
  arguments: Record<string, unknown>;
  message: string;
}

export interface AssistantExecutionItem {
  id: string;
  kind: "intent" | "tool" | "workflow";
  toolName?: string;
  status: "pending" | "running" | "succeeded" | "failed";
  title: string;
  summary?: string;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
  errorMessage?: string;
  errorCode?: string;
  timestamp: number;
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
  status: AssistantStatus;
  executionItems: AssistantExecutionItem[];
  pendingConfirmation: AssistantConfirmationRequest | null;
  sessionError: string | null;
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
  | { type: "ADD_MESSAGE"; message: ChatMessage }
  | { type: "REPLACE_MESSAGES"; messages: ChatMessage[] }
  | { type: "UPDATE_LAST_ASSISTANT"; content: string }
  | { type: "SET_STATUS"; status: AssistantStatus }
  | { type: "ADD_EXECUTION_ITEM"; item: AssistantExecutionItem }
  | { type: "UPDATE_EXECUTION_ITEM"; toolName: string; patch: Partial<AssistantExecutionItem> }
  | { type: "SET_SESSION_ERROR"; message: string; errorCode?: string }
  | { type: "SET_PENDING_CONFIRMATION"; confirmation: AssistantConfirmationRequest | null }
  | { type: "CLEAR_EXECUTION" }
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
  status: "idle",
  executionItems: [],
  pendingConfirmation: null,
  sessionError: null,
  currentContext: { page: "/" },
  suggestions: [],
  commands: [],
};

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
    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };
    case "REPLACE_MESSAGES":
      return { ...state, messages: action.messages };
    case "UPDATE_LAST_ASSISTANT": {
      const msgs = [...state.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant") {
          msgs[i] = { ...msgs[i], content: msgs[i].content + action.content };
          break;
        }
      }
      return { ...state, messages: msgs };
    }
    case "SET_STATUS":
      return { ...state, status: action.status };
    case "ADD_EXECUTION_ITEM":
      return { ...state, executionItems: [...state.executionItems, action.item] };
    case "UPDATE_EXECUTION_ITEM": {
      let updated = false;
      const executionItems = state.executionItems.map((item) => {
        if (item.toolName === action.toolName) {
          updated = true;
          return { ...item, ...action.patch };
        }
        return item;
      });
      if (!updated) {
        executionItems.push({
          id: `exec-${Date.now()}`,
          kind: "tool",
          toolName: action.toolName,
          status: action.patch.status ?? "pending",
          title: action.toolName,
          timestamp: Date.now(),
          ...action.patch,
        });
      }
      return { ...state, executionItems };
    }
    case "SET_PENDING_CONFIRMATION":
      return { ...state, pendingConfirmation: action.confirmation };
    case "SET_SESSION_ERROR":
      return {
        ...state,
        status: "failed",
        sessionError: action.message,
        executionItems: [
          ...state.executionItems,
          {
            id: `exec-error-${Date.now()}`,
            kind: "tool",
            status: "failed",
            title: action.errorCode ?? "assistant_error",
            errorMessage: action.message,
            errorCode: action.errorCode,
            timestamp: Date.now(),
          },
        ],
      };
    case "CLEAR_EXECUTION":
      return { ...state, executionItems: [], pendingConfirmation: null, sessionError: null };
    case "CLEAR_MESSAGES":
      return { ...state, messages: [], executionItems: [], pendingConfirmation: null, sessionError: null };
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
    dispatch({
      type: "ADD_EXECUTION_ITEM",
      item: {
        id: `workflow-${Date.now()}`,
        kind: "workflow",
        toolName,
        status: "running",
        title: toolName,
        arguments: asRecord(parsed.arguments),
        result: asRecord(parsed.result),
        timestamp: Date.now(),
      },
    });
    return;
  }

  if (eventType === "assistant.tool_succeeded") {
    const toolName = String(parsed.tool_name ?? "");
    const result = asRecord(parsed.result);
    dispatch({
      type: "UPDATE_EXECUTION_ITEM",
      toolName,
      patch: {
        status: "succeeded",
        result,
        summary: String(parsed.summary ?? ""),
      },
    });
    dispatch({ type: "CLEAR_EXECUTION" });
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
  sendMessage: (content: string) => Promise<void>;
  confirmAssistantAction: (approved: boolean) => Promise<void>;
  executeCommand: (commandId: string) => void;
  refreshConversations: () => Promise<void>;
  loadConversation: (conversationId: string) => Promise<void>;
  startNewConversation: () => void;
}

const AIAssistantContext = createContext<AIAssistantContextValue | null>(null);

/* ─── Provider ─── */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
    dispatch({ type: "SET_STATUS", status: "thinking" });
    try {
      const history = await getChatConversationMessages(conversationId);
      dispatch({ type: "SET_CURRENT_CONVERSATION", conversationId });
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
      confirmation?: { approved: boolean; tool_name: string; arguments: Record<string, unknown> },
    ) => {
      const displayContent = confirmation
        ? confirmation.approved
          ? "确认执行"
          : "取消操作"
        : content.trim();
      if (!displayContent || isAssistantBusy(state.status)) return;

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: displayContent,
        timestamp: Date.now(),
      };
      dispatch({ type: "ADD_MESSAGE", message: userMsg });
      dispatch({ type: "SET_STATUS", status: "thinking" });

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
      };
      dispatch({ type: "ADD_MESSAGE", message: aiMsg });

      try {
        const token = localStorage.getItem("docpilot_token");
        const response = await fetch(`${API_BASE}/assistant/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: displayContent,
            project_id: state.currentContext.projectId,
            conversation_id: state.currentConversationId,
            confirmation,
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
    [refreshConversations, state.currentContext.projectId, state.currentConversationId, state.status],
  );

  const sendMessage = useCallback(
    async (content: string) => {
      await sendAssistantRequest(content);
    },
    [sendAssistantRequest],
  );

  const confirmAssistantAction = useCallback(
    async (approved: boolean) => {
      const pending = state.pendingConfirmation;
      if (!pending) return;
      dispatch({ type: "SET_PENDING_CONFIRMATION", confirmation: null });
      await sendAssistantRequest(pending.message, {
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
        confirmAssistantAction,
        executeCommand,
        refreshConversations,
        loadConversation,
        startNewConversation,
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
