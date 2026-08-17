export type AgentUiAction =
  | {
      type: "canvas";
      label: string;
      route: string;
      projectId: string;
    }
  | {
      type: "external-link";
      label: string;
      href: string;
    };

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safeLabel(value: unknown, fallback: string): string {
  if (typeof value !== "string") {
    return fallback;
  }

  const label = value.replace(/\s+/g, " ").trim();
  return label.length > 0 && label.length <= 80 ? label : fallback;
}

function projectRoute(value: unknown): { route: string; projectId: string } | null {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
    return null;
  }

  const [pathname, query = ""] = value.split("?", 2);
  const match = /^\/projects\/([^/#?]+)$/.exec(pathname);
  if (!match || !match[1]) {
    return null;
  }

  const route = query ? `${pathname}?${query}` : pathname;
  return { route, projectId: decodeURIComponent(match[1]) };
}

function externalHref(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }

  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null;
  }
}

/**
 * Accept only the small, server-projected UI action contract. Model prose and
 * arbitrary tool payloads must never become executable UI controls.
 */
export function parseAgentUiAction(value: unknown): AgentUiAction | null {
  if (!isRecord(value) || typeof value.type !== "string") {
    return null;
  }

  if (value.type === "canvas") {
    const parsedRoute = projectRoute(value.route);
    if (!parsedRoute) {
      return null;
    }

    return {
      type: "canvas",
      label: safeLabel(value.label, "打开工作流画布"),
      ...parsedRoute,
    };
  }

  if (value.type === "link") {
    const href = externalHref(value.href);
    if (!href) {
      return null;
    }

    return {
      type: "external-link",
      label: safeLabel(value.label, "打开链接"),
      href,
    };
  }

  return null;
}
