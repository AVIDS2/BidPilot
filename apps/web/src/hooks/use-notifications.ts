import { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = '/api/bidpilot';

export type NotificationType =
  | 'draft_completed'
  | 'review_approved'
  | 'export_ready'
  | 'hitl_required'
  | 'agent_task'
  | string;

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  description: string;
  body?: string;
  read: boolean;
  created_at: string;
  link?: string;
}

interface NotificationApiRow {
  id: string;
  type: string;
  title: string;
  body?: string | null;
  description?: string | null;
  read: boolean;
  created_at?: string | null;
  link?: string | null;
}

function normalizeNotification(row: NotificationApiRow): Notification {
  const description = (row.description || row.body || '').trim();
  return {
    id: row.id,
    type: row.type,
    title: row.title,
    description,
    body: row.body || undefined,
    read: Boolean(row.read),
    created_at: row.created_at || new Date().toISOString(),
    link: row.link || undefined
  };
}

async function fetchNotifications(): Promise<Notification[]> {
  const res = await fetch(`${API_BASE}/notifications`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include'
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body}`);
  }
  const data = (await res.json()) as NotificationApiRow[];
  return Array.isArray(data) ? data.map(normalizeNotification) : [];
}

async function markAsReadApi(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/notifications/${id}/read`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include'
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body}`);
  }
}

async function markAllAsReadApi(): Promise<void> {
  const res = await fetch(`${API_BASE}/notifications/read-all`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include'
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body}`);
  }
}

const DEFAULT_POLL_INTERVAL_MS = 30_000;

function mergeById(existing: Notification[], incoming: Notification[]): Notification[] {
  const map = new Map<string, Notification>();
  for (const item of existing) map.set(item.id, item);
  for (const item of incoming) map.set(item.id, item);
  return [...map.values()].sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export function useNotifications(options?: {
  pollIntervalMs?: number;
  enabled?: boolean;
  /** Prefer SSE wake stream; falls back to polling on error. Default true. */
  preferSse?: boolean;
}) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [transport, setTransport] = useState<'sse' | 'poll'>('poll');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const pollIntervalMs = options?.pollIntervalMs ?? DEFAULT_POLL_INTERVAL_MS;
  const enabled = options?.enabled ?? true;
  const preferSse = options?.preferSse ?? true;

  const unreadCount = notifications.filter((n) => !n.read).length;

  const load = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    try {
      const data = await fetchNotifications();
      setNotifications(data);
    } catch {
      // Silently fail — the user may not have auth or the endpoint may not exist yet.
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  const markAsRead = useCallback(
    async (id: string) => {
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
      try {
        await markAsReadApi(id);
      } catch {
        await load();
      }
    },
    [load]
  );

  const markAllAsRead = useCallback(async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    try {
      await markAllAsReadApi();
    } catch {
      await load();
    }
  }, [load]);

  useEffect(() => {
    if (!enabled) return;
    void load();

    let cancelled = false;

    const startPolling = () => {
      if (cancelled) return;
      setTransport('poll');
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = setInterval(() => {
        void load();
      }, pollIntervalMs);
    };

    const stopPolling = () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };

    const startSse = () => {
      if (!preferSse || typeof EventSource === 'undefined') {
        startPolling();
        return;
      }
      const url = `${API_BASE}/notifications/stream`;
      try {
        const source = new EventSource(url);
        sourceRef.current = source;
        setTransport('sse');
        // Keep a slow poll as eventual consistency backup while SSE is primary.
        stopPolling();
        intervalRef.current = setInterval(
          () => {
            void load();
          },
          Math.max(pollIntervalMs, 60_000)
        );

        source.addEventListener('notification', (event) => {
          try {
            const raw = JSON.parse((event as MessageEvent).data) as NotificationApiRow;
            const item = normalizeNotification(raw);
            setNotifications((prev) => mergeById(prev, [item]));
            setLoading(false);
          } catch {
            // ignore malformed frames
          }
        });
        source.addEventListener('ready', () => {
          setLoading(false);
        });
        source.onerror = () => {
          source.close();
          sourceRef.current = null;
          if (!cancelled) startPolling();
        };
      } catch {
        startPolling();
      }
    };

    startSse();

    return () => {
      cancelled = true;
      stopPolling();
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
      }
    };
  }, [enabled, load, pollIntervalMs, preferSse]);

  return {
    notifications,
    unreadCount,
    loading,
    markAsRead,
    markAllAsRead,
    refresh: load,
    transport
  };
}
