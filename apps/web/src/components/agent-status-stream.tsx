import { useState, useEffect, useRef, useCallback } from "react";
import { getStoredValue } from "@/lib/browser-storage";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type AgentNodeStatus = "pending" | "running" | "completed" | "failed";

export interface AgentNode {
  name: string;
  status: AgentNodeStatus;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface ReviewResult {
  score: number;
  feedback: string;
  pass: boolean;
}

export interface AgentStreamState {
  currentNode: string | null;
  nodes: AgentNode[];
  completedNodes: AgentNode[];
  pendingNodes: AgentNode[];
  reviewResult: ReviewResult | null;
  isWaitingApproval: boolean;
  approvalMessage: string | null;
  isRunning: boolean;
  error: string | null;
}

function mergeNode(nodes: AgentNode[], update: Partial<AgentNode> & { name: string }): AgentNode[] {
  const idx = nodes.findIndex((n) => n.name === update.name);
  if (idx >= 0) {
    const merged = { ...nodes[idx], ...update };
    const next = [...nodes];
    next[idx] = merged;
    return next;
  }
  const { name: _name, ...rest } = update;
  return [...nodes, { name: _name, status: update.status ?? "pending", ...rest }];
}

export function useAgentStream(runId: string | null): AgentStreamState {
  const [state, setState] = useState<AgentStreamState>({
    currentNode: null,
    nodes: [],
    completedNodes: [],
    pendingNodes: [],
    reviewResult: null,
    isWaitingApproval: false,
    approvalMessage: null,
    isRunning: false,
    error: null,
  });

  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);

  const recalcDerived = useCallback((nodes: AgentNode[]) => {
    return {
      completedNodes: nodes.filter((n) => n.status === "completed"),
      pendingNodes: nodes.filter((n) => n.status === "pending"),
    };
  }, []);

  const processEvent = useCallback(
    (event: string, data: unknown) => {
      setState((prev) => {
        let next = { ...prev };
        const parsed = data as Record<string, unknown>;

        switch (event) {
          case "node_start": {
            const name = parsed.node as string;
            next.currentNode = name;
            next.nodes = mergeNode(next.nodes, { name, status: "running", started_at: new Date().toISOString() });
            next.isRunning = true;
            break;
          }
          case "node_complete": {
            const name = parsed.node as string;
            next.nodes = mergeNode(next.nodes, { name, status: "completed", completed_at: new Date().toISOString() });
            next.currentNode = null;
            break;
          }
          case "node_error": {
            const name = parsed.node as string;
            const errorMsg = parsed.error as string | undefined;
            next.nodes = mergeNode(next.nodes, { name, status: "failed", error: errorMsg });
            next.currentNode = null;
            break;
          }
          case "review_result": {
            next.reviewResult = {
              score: parsed.score as number,
              feedback: parsed.feedback as string,
              pass: parsed.pass as boolean,
            };
            break;
          }
          case "approval_required": {
            next.isWaitingApproval = true;
            next.approvalMessage = (parsed.message as string) ?? null;
            break;
          }
          case "approval_granted": {
            next.isWaitingApproval = false;
            next.approvalMessage = null;
            break;
          }
          case "run_complete": {
            next.isRunning = false;
            break;
          }
          case "run_error": {
            next.isRunning = false;
            next.error = (parsed.error as string) ?? "Agent run failed";
            break;
          }
          case "error": {
            next.error = (parsed.message as string) ?? "Unknown error";
            break;
          }
          default:
            break;
        }

        const derived = recalcDerived(next.nodes);
        return { ...next, ...derived };
      });
    },
    [recalcDerived],
  );

  useEffect(() => {
    if (!runId) {
      setState({
        currentNode: null,
        nodes: [],
        completedNodes: [],
        pendingNodes: [],
        reviewResult: null,
        isWaitingApproval: false,
        approvalMessage: null,
        isRunning: false,
        error: null,
      });
      return;
    }

    let cancelled = false;

    function connect() {
      if (cancelled) return;

      const token = getStoredValue("token");
      const url = `${API_BASE}/drafting/runs/${runId}/stream`;
      const es = token ? new EventSource(url, { withCredentials: false }) : new EventSource(url);
      esRef.current = es;

      es.onopen = () => {
        retryCountRef.current = 0;
        if (!cancelled) {
          setState((prev) => ({ ...prev, error: null, isRunning: true }));
        }
      };

      es.addEventListener("node_start", (e) => {
        if (!cancelled) processEvent("node_start", JSON.parse(e.data));
      });
      es.addEventListener("node_complete", (e) => {
        if (!cancelled) processEvent("node_complete", JSON.parse(e.data));
      });
      es.addEventListener("node_error", (e) => {
        if (!cancelled) processEvent("node_error", JSON.parse(e.data));
      });
      es.addEventListener("review_result", (e) => {
        if (!cancelled) processEvent("review_result", JSON.parse(e.data));
      });
      es.addEventListener("approval_required", (e) => {
        if (!cancelled) processEvent("approval_required", JSON.parse(e.data));
      });
      es.addEventListener("approval_granted", (e) => {
        if (!cancelled) processEvent("approval_granted", JSON.parse(e.data));
      });
      es.addEventListener("run_complete", (e) => {
        if (!cancelled) processEvent("run_complete", JSON.parse(e.data));
      });
      es.addEventListener("run_error", (e) => {
        if (!cancelled) processEvent("run_error", JSON.parse(e.data));
      });
      es.addEventListener("error", () => {
        if (cancelled) return;
        // The EventSource onerror fires on disconnect; attempt reconnect with backoff
        es.close();
        const delay = Math.min(1000 * 2 ** retryCountRef.current, 30000);
        retryCountRef.current += 1;
        reconnectTimerRef.current = setTimeout(() => connect(), delay);
      });

      // Fallback: generic message handler for events without a named listener
      es.onmessage = (e) => {
        if (cancelled) return;
        try {
          const parsed = JSON.parse(e.data);
          if (parsed.event) {
            processEvent(parsed.event, parsed);
          }
        } catch {
          // ignore non-JSON messages
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      esRef.current?.close();
      esRef.current = null;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [runId, processEvent]);

  return state;
}
