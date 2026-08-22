import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth", () => ({
  AuthProvider: ({ children }: { children: unknown }) => children,
  useAuth: () => ({ isAuthenticated: true }),
}));

vi.mock("@/components/platform-shell", () => ({
  PlatformShell: () => <div data-testid="legacy-platform-shell" />,
}));

vi.mock("./features/agent/agent-workspace-page", () => ({
  AgentWorkspacePage: () => <div data-testid="source-migrated-agent-workspace" />,
}));

vi.mock("@/features/agent/components/AgentWakeResume", () => ({
  AgentWakeResume: () => null,
}));

vi.mock("@/components/ui/tooltip", () => ({
  TooltipProvider: ({ children }: { children: unknown }) => children,
}));

vi.mock("@/features/agent/state/agent-store", () => ({
  AIAssistantProvider: ({ children }: { children: unknown }) => children,
}));

import { App } from "./app";

describe("Agent route", () => {
  it("mounts the Agent workspace inside the shared platform route", async () => {
    window.history.replaceState({}, "", "/agent");

    render(<App />);

    expect(await screen.findByTestId("source-migrated-agent-workspace", undefined, { timeout: 15_000 })).toBeInTheDocument();
    expect(screen.queryByTestId("legacy-platform-shell")).not.toBeInTheDocument();
  }, 20_000);
});
