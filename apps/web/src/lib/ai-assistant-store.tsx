import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  type ReactNode,
  type Dispatch,
} from "react";

/* ─── Types ─── */

export type AssistantMode = "panel" | "command" | "inline";
export type AssistantStatus = "idle" | "processing" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
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
  messages: ChatMessage[];
  status: AssistantStatus;
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
  | { type: "ADD_MESSAGE"; message: ChatMessage }
  | { type: "UPDATE_LAST_ASSISTANT"; content: string }
  | { type: "SET_STATUS"; status: AssistantStatus }
  | { type: "CLEAR_MESSAGES" }
  | { type: "SET_CONTEXT"; context: PageContext }
  | { type: "SET_SUGGESTIONS"; suggestions: InlineSuggestion[] }
  | { type: "REGISTER_COMMANDS"; commands: CommandDef[] };

/* ─── Reducer ─── */

const initialState: AIAssistantState = {
  isOpen: false,
  mode: "panel",
  messages: [],
  status: "idle",
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
    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };
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
    case "CLEAR_MESSAGES":
      return { ...state, messages: [] };
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

/* ─── Context ─── */

interface AIAssistantContextValue {
  state: AIAssistantState;
  dispatch: Dispatch<Action>;
  /* convenience helpers */
  open: (mode?: AssistantMode) => void;
  close: () => void;
  toggle: (mode?: AssistantMode) => void;
  sendMessage: (content: string) => Promise<void>;
  executeCommand: (commandId: string) => void;
}

const AIAssistantContext = createContext<AIAssistantContextValue | null>(null);

/* ─── Provider ─── */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || state.status === "processing") return;

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: content.trim(),
        timestamp: Date.now(),
      };
      dispatch({ type: "ADD_MESSAGE", message: userMsg });
      dispatch({ type: "SET_STATUS", status: "processing" });

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
      };
      dispatch({ type: "ADD_MESSAGE", message: aiMsg });

      try {
        const token = localStorage.getItem("docpilot_token");
        const response = await fetch(`${API_BASE}/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: content.trim(),
            conversation_history: state.messages.map((m) => ({
              role: m.role,
              content: m.content,
            })),
          }),
        });

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        while (reader) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === "content" && data.content) {
                  dispatch({
                    type: "UPDATE_LAST_ASSISTANT",
                    content: data.content,
                  });
                }
              } catch {
                /* skip invalid JSON */
              }
            }
          }
        }
      } catch (err) {
        console.error("AI chat error:", err);
        dispatch({
          type: "UPDATE_LAST_ASSISTANT",
          content: "\n\nSorry, something went wrong. Please try again.",
        });
      } finally {
        dispatch({ type: "SET_STATUS", status: "idle" });
      }
    },
    [state.messages, state.status],
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
      value={{ state, dispatch, open, close, toggle, sendMessage, executeCommand }}
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
