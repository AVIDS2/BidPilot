import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getBillingSummary,
  getNotificationPreferences,
  getOrganizationEntitlements,
  updateCurrentUser,
  updateNotificationPreferences,
} from "@/lib/api";

import { AccountPage } from "./account-page";

vi.mock("@/lib/api", () => ({
  createBillingPortal: vi.fn(),
  getBillingSummary: vi.fn(),
  getNotificationPreferences: vi.fn(),
  getOrganizationEntitlements: vi.fn(),
  updateCurrentUser: vi.fn(),
  updateNotificationPreferences: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {
      id: "user-1",
      email: "user@example.com",
      display_name: "Demo User",
      role: "admin",
      plan: "professional",
      org_id: "org-1",
    },
    logout: vi.fn(),
    setUser: vi.fn(),
  }),
}));

const billingSummary = {
  data: {
    plan: "professional",
    status: "active",
    stripe_customer_id: "cus-1",
    entitlement_source: "organization" as const,
    seat_limit: 5,
    is_billing_owner: true,
    monthly_workflow_limit: 20,
    monthly_workflow_used: 4,
    monthly_workflow_remaining: 16,
    monthly_assistant_limit: 500,
    monthly_assistant_used: 12,
    monthly_assistant_remaining: 488,
    monthly_indexing_limit: 100,
    monthly_indexing_used: 8,
    monthly_indexing_remaining: 92,
    official_model_usage: {
      input_tokens: 100,
      output_tokens: 20,
      reasoning_tokens: 0,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      total_tokens: 120,
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
    trial_window_start: "2026-08-01T00:00:00Z",
  },
};

const notificationPreferences = {
  in_app_enabled: true,
  email_enabled: true,
  review_updates: true,
  agent_updates: true,
  radar_updates: false,
  material_updates: true,
};

function renderAccount() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AccountPage />
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("AccountPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getBillingSummary).mockResolvedValue(billingSummary);
    vi.mocked(getOrganizationEntitlements).mockResolvedValue({
      org_id: "org-1",
      plan: "professional",
      subscription_status: "active",
      source: "organization",
      seat_limit: 5,
      active_member_count: 3,
      available_seats: 2,
      seat_overage_count: 0,
      capacity_enforced: true,
      project_limit: 20,
      monthly_workflow_limit: 20,
      monthly_assistant_limit: 500,
      monthly_indexing_limit: 100,
      is_billing_owner: true,
    });
    vi.mocked(getNotificationPreferences).mockResolvedValue(notificationPreferences);
    vi.mocked(updateCurrentUser).mockResolvedValue({
      id: "user-1",
      email: "user@example.com",
      display_name: "Updated User",
      role: "admin",
      plan: "professional",
      org_id: "org-1",
    });
    vi.mocked(updateNotificationPreferences).mockImplementation(async (payload) => ({
      ...notificationPreferences,
      ...payload,
    }));
  });

  it("uses the shadcn settings composition for profile content", async () => {
    renderAccount();

    expect(await screen.findByTestId("account-profile-card")).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "账户设置分区" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "个人资料" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("显示名称")).toHaveValue("Demo User");
    expect(screen.getByLabelText("邮箱")).toBeDisabled();
  });

  it("submits profile changes through the existing account API", async () => {
    renderAccount();

    const input = await screen.findByLabelText("显示名称");
    fireEvent.change(input, { target: { value: "Updated User" } });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

    await waitFor(() => {
      expect(vi.mocked(updateCurrentUser).mock.calls[0]?.[0]).toEqual({ display_name: "Updated User" });
    });
  });

  it("uses switches for notification preferences and updates the cached state", async () => {
    renderAccount();
    fireEvent.click(screen.getByRole("tab", { name: "通知" }));

    const switchControl = await screen.findByRole("switch", { name: "站内通知" });
    fireEvent.click(switchControl);

    await waitFor(() => {
      expect(vi.mocked(updateNotificationPreferences).mock.calls[0]?.[0]).toEqual({ in_app_enabled: false });
    });
    expect(screen.getByRole("switch", { name: "站内通知" })).toHaveAttribute("aria-checked", "false");
  });

  it("renders security fields and organization usage in separate tabs", async () => {
    renderAccount();
    fireEvent.click(screen.getByRole("tab", { name: "安全" }));
    expect(await screen.findByLabelText("当前密码")).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByLabelText("新密码")).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("tab", { name: "组织与用量" }));
    expect(await screen.findByText("起草工作流")).toBeInTheDocument();
    expect(screen.getByText("4 / 20")).toBeInTheDocument();
    expect(screen.getByText("成员席位")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /管理套餐/ })).toBeInTheDocument();
  });
});
