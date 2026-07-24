import { useState, useEffect, useCallback, useRef } from "react";
import { getStoredValue } from "@/lib/browser-storage";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type NotificationType =
  | "draft_completed"
  | "review_approved"
  | "export_ready"
  | "hitl_required"
  | "agent_task"
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

function getAuthHeaders(): Record<string, string> {
  const token = getStoredValue("token");
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

function normalizeNotification(row: NotificationApiRow): Notification {
  const description = (row.description || row.body || "").trim();
  return {
    id: row.id,
    type: row.type,
    title: row.title,
    description,
    body: row.body || undefined,
    read: Boolean(row.read),
    created_at: row.created_at || new Date().toISOString(),
    link: row.link || undefined,
  };
}

async function fetchNotifications(): Promise<Notification[]> {
  const res = await fetch(`${API_BASE}/notifications`, {
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  const data = (await res.json()) as NotificationApiRow[];
  return Array.isArray(data) ? data.map(normalizeNotification) : [];
}

async function markAsReadApi(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/notifications/${id}/read`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
}

async function markAllAsReadApi(): Promise<void> {
  const res = await fetch(`${API_BASE}/notifications/read-all`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
}

const DEFAULT_POLL_INTERVAL_MS = 15_000;

export function useNotifications(options?: { pollIntervalMs?: number; enabled?: boolean }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollIntervalMs = options?.pollIntervalMs ?? DEFAULT_POLL_INTERVAL_MS;
  const enabled = options?.enabled ?? true;

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
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: true } : n)),
      );
      try {
        await markAsReadApi(id);
      } catch {
        await load();
      }
    },
    [load],
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
    intervalRef.current = setInterval(() => {
      void load();
    }, pollIntervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [enabled, load, pollIntervalMs]);

  return { notifications, unreadCount, loading, markAsRead, markAllAsRead, refresh: load };
}
