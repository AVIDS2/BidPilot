import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authState = vi.hoisted(() => ({
  isAuthenticated: true,
  user: {
    id: "platform-shell-user",
    email: "platform-shell@example.com",
    display_name: "Platform Shell User",
    role: "admin",
    plan: "starter",
  },
  logout: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  AuthProvider: ({ children }: { children: unknown }) => children,
  useAuth: () => authState,
}));

vi.mock("@/components/ai-assistant/AIAssistantPanel", () => ({
  AIAssistantPanel: () => null,
}));

vi.mock("@/components/ai-assistant/CommandPalette", () => ({
  CommandPalette: () => null,
}));

vi.mock("@/components/ai-assistant/FloatingAssistant", () => ({
  FloatingAssistant: () => null,
}));

vi.mock("@/components/notification-bell", () => ({
  NotificationBell: () => null,
}));

vi.mock("@/components/ai-assistant/InlineSuggestion", () => ({
  InlineSuggestionBar: () => null,
}));

vi.mock("@/hooks/use-ai-assistant-hotkeys", () => ({
  useAIAssistantHotkeys: () => undefined,
}));

vi.mock("@/lib/ai-assistant-store", () => ({
  AIAssistantProvider: ({ children }: { children: unknown }) => children,
  useAIAssistant: () => ({
    state: { isOpen: false, mode: "panel" },
    toggle: () => undefined,
    dispatch: vi.fn(),
  }),
}));

import { App } from "./app";

describe("App authenticated workspace shell", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.pushState({}, "", "/pricing");
  });

  it("loads the lazy platform shell around an authenticated public route", async () => {
    render(<App />);

    expect((await screen.findAllByText("Pricing", { exact: true }, { timeout: 15_000 })).length).toBeGreaterThan(0);
    expect(screen.getByText("Dashboard", { exact: true })).toBeInTheDocument();
    expect(screen.getByText("Projects", { exact: true })).toBeInTheDocument();
  }, 20_000);
});
