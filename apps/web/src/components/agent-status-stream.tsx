import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE = '/api/bidpilot';

export type AgentNodeStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface AgentNode {
  name: string;
  status: AgentNodeStatus;
  started_at?: string;
  completed_at?: string;
  error?: string;
  summary?: string;
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
  return [...nodes, { name: _name, status: update.status ?? 'pending', ...rest }];
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
    error: null
  });

  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);

  const recalcDerived = useCallback((nodes: AgentNode[]) => {
    return {
      completedNodes: nodes.filter((n) => n.status === 'completed'),
      pendingNodes: nodes.filter((n) => n.status === 'pending')
    };
  }, []);

  const processEvent = useCallback(
    (event: string, data: unknown) => {
      setState((prev) => {
        const next = { ...prev };
        const parsed = data as Record<string, unknown>;

        switch (event) {
          case 'node_start':
          case 'node_started': {
            const name = (parsed.node_name ?? parsed.node) as string;
            next.currentNode = name;
            next.nodes = mergeNode(next.nodes, {
              name,
              status: 'running',
              started_at: new Date().toISOString()
            });
            next.isRunning = true;
            break;
          }
          case 'node_complete':
          case 'node_completed': {
            const name = (parsed.node_name ?? parsed.node) as string;
            next.nodes = mergeNode(next.nodes, {
              name,
              status: 'completed',
              completed_at: new Date().toISOString(),
              summary: parsed.result_summary as string | undefined
            });
            next.currentNode = null;
            break;
          }
          case 'node_error':
          case 'graph_error': {
            const name = (parsed.node_name ??
              parsed.node ??
              next.currentNode ??
              'workflow') as string;
            const errorMsg = (parsed.error_message ?? parsed.error) as string | undefined;
            next.nodes = mergeNode(next.nodes, { name, status: 'failed', error: errorMsg });
            next.currentNode = null;
            next.error = errorMsg ?? 'Agent run failed';
            break;
          }
          case 'review_result': {
            next.reviewResult = {
              score: parsed.score as number,
              feedback: parsed.feedback as string,
              pass: parsed.pass as boolean
            };
            break;
          }
          case 'approval_required':
          case 'human_approval_required': {
            next.isWaitingApproval = true;
            next.approvalMessage =
              ((parsed.message ?? parsed.draft_preview) as string | undefined) ?? null;
            break;
          }
          case 'approval_granted': {
            next.isWaitingApproval = false;
            next.approvalMessage = null;
            break;
          }
          case 'run_complete':
          case 'graph_completed': {
            next.isRunning = false;
            break;
          }
          case 'run_error': {
            next.isRunning = false;
            next.error = (parsed.error as string) ?? 'Agent run failed';
            break;
          }
          case 'error': {
            next.error = (parsed.message as string) ?? 'Unknown error';
            break;
          }
          default:
            break;
        }

        const derived = recalcDerived(next.nodes);
        return { ...next, ...derived };
      });
    },
    [recalcDerived]
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
        error: null
      });
      return;
    }

    let cancelled = false;

    function scheduleReconnect() {
      const delay = Math.min(1000 * 2 ** retryCountRef.current, 30000);
      retryCountRef.current += 1;
      reconnectTimerRef.current = setTimeout(() => void connect(), delay);
    }

    async function connect() {
      if (cancelled) return;

      const url = `${API_BASE}/drafting/runs/${runId}/stream`;
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await fetch(url, {
          credentials: 'include',
          signal: controller.signal
        });

        if (!response.ok || !response.body) {
          throw new Error(`Workflow stream failed: ${response.status}`);
        }

        retryCountRef.current = 0;
        if (!cancelled) {
          setState((prev) => ({ ...prev, error: null, isRunning: true }));
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!cancelled) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split(/\r?\n\r?\n/);
          buffer = parts.pop() ?? '';

          for (const part of parts) {
            const parsed = parseSsePart(part);
            if (parsed && !cancelled) {
              processEvent(parsed.eventType, parsed.data);
            }
          }
        }

        const trailing = parseSsePart(buffer);
        if (trailing && !cancelled) {
          processEvent(trailing.eventType, trailing.data);
        }
      } catch (error) {
        if (cancelled || controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : 'Workflow stream disconnected';
        setState((prev) => ({ ...prev, error: message, isRunning: false }));
        scheduleReconnect();
      }
    }

    void connect();

    return () => {
      cancelled = true;
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [runId, processEvent]);

  return state;
}

function parseSsePart(part: string): { eventType: string; data: Record<string, unknown> } | null {
  const lines = part.split(/\r?\n/);
  let eventType = '';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (!eventType || dataLines.length === 0) return null;

  try {
    return { eventType, data: JSON.parse(dataLines.join('\n')) as Record<string, unknown> };
  } catch {
    return null;
  }
}
