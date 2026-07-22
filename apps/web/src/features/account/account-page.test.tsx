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
      entitlement_source: "organization",
      seat_limit: 1,
      is_billing_owner: true,
      monthly_workflow_limit: 3,
      monthly_workflow_used: 1,
      monthly_workflow_remaining: 2,
      monthly_assistant_limit: 100,
      monthly_assistant_used: 4,
      monthly_assistant_remaining: 96,
      monthly_indexing_limit: 5,
      monthly_indexing_used: 1,
      monthly_indexing_remaining: 4,
      official_model_usage: {
        input_tokens: 120,
        output_tokens: 30,
        reasoning_tokens: 0,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        total_tokens: 150,
        reserved_tokens: 0,
        token_limit: null,
        remaining_tokens: null,
        cost_available: false,
      },
      byok_model_usage: {
        input_tokens: 0,
        output_tokens: 0,
        reasoning_tokens: 0,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        total_tokens: 0,
        reserved_tokens: 0,
        token_limit: null,
        remaining_tokens: null,
        cost_available: false,
      },
      trial_window_start: "2026-06-01T00:00:00Z",
    },
  }),
  getOrganizationEntitlements: vi.fn().mockResolvedValue({
    org_id: "org-1",
    plan: "starter",
    subscription_status: "active",
    source: "organization",
    seat_limit: 1,
    active_member_count: 1,
    available_seats: 0,
    seat_overage_count: 0,
    capacity_enforced: true,
    project_limit: 3,
    monthly_workflow_limit: 3,
    monthly_assistant_limit: 100,
    monthly_indexing_limit: 5,
    is_billing_owner: true,
  }),
  createBillingPortal: vi.fn(),
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
        org_id: "org-1",
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
    expect(await screen.findByText("Assistant messages")).not.toBeNull();
    expect(await screen.findByText("Document indexing jobs")).not.toBeNull();
    expect(await screen.findByText("Model token metering")).not.toBeNull();
    expect(await screen.findByText("Workspace capacity")).not.toBeNull();
    expect(await screen.findByText("1 of 1 seats in use")).not.toBeNull();
  });
});
