import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/lib/auth";
import { AccountPage } from "./account-page";

vi.mock("@/lib/api", () => ({
  getBillingSummary: vi.fn().mockResolvedValue({
    data: {
      plan: "starter",
      status: "active",
      stripe_customer_id: null,
      monthly_workflow_limit: 3,
      monthly_workflow_used: 1,
      monthly_workflow_remaining: 2,
      trial_window_start: "2026-06-01T00:00:00Z",
    },
  }),
  updateCurrentUser: vi.fn(),
  updateSubscription: vi.fn(),
}));

vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return {
    ...actual,
    useAuth: () => ({
      user: {
        id: "user-1",
        email: "user@example.com",
        display_name: "Demo User",
        role: "admin",
        plan: "starter",
      },
      logout: vi.fn(),
      setUser: vi.fn(),
    }),
  };
});

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <BrowserRouter>
        <AuthProvider>{ui}</AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("AccountPage", () => {
  it("renders billing summary", async () => {
    renderWithProviders(<AccountPage />);

    expect(await screen.findByText("Billing status")).not.toBeNull();
    expect(await screen.findByText("Usage this month")).not.toBeNull();
  });
});
