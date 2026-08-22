import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProviderSettingsPageV2 } from "./provider-settings-page-v2";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { role: "admin", org_slug: "leho-workspace" } }),
}));

vi.mock("@/lib/api", () => ({
  listProviderConfigs: vi.fn().mockResolvedValue({
    data: [{
      id: "provider-1",
      user_id: "visual-user",
      provider_type: "openai",
      provider_id: "deepseek",
      api_key: "sk-••••test",
      api_url: "https://api.deepseek.com",
      model: "deepseek-chat",
      label: "团队 DeepSeek",
      is_active: true,
      created_at: "2026-08-19T08:00:00Z",
      updated_at: "2026-08-19T08:00:00Z",
    }],
  }),
  createProviderConfig: vi.fn(),
  updateProviderConfig: vi.fn(),
  deleteProviderConfig: vi.fn(),
  testProviderConnection: vi.fn(),
  listProviderModels: vi.fn(),
  getPiModelCatalog: vi.fn().mockResolvedValue({
    data: {
      source: "pi-ai",
      version: "0.84.2",
      providers: [{ id: "deepseek", name: "DeepSeek" }],
      models: [{
        id: "deepseek-v4-flash",
        name: "DeepSeek V4 Flash",
        provider: "deepseek",
        api: "openai-completions",
        base_url: "https://api.deepseek.com/v1",
        reasoning: true,
        input: ["text"],
        context_window: 128000,
        max_tokens: 8192,
        cost: {},
      }],
    },
  }),
  getPiRuntimeContract: vi.fn().mockResolvedValue({
    data: {
      version: "2.0",
      sandbox: {
        profile: "governed_cloud",
        hostTools: "disabled",
        network: "bridge_only",
        maxToolInputBytes: 65536,
        maxToolObservationBytes: 131072,
      },
      extensions: ["subagents", "opportunity-deep-research"],
      skills: [{ name: "opportunity-deep-research", description: "公开机会调研" }],
      tool_count: 18,
      parallel_tool_count: 7,
    },
  }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={["/settings/providers"]}>
      <QueryClientProvider client={queryClient}>
        <ProviderSettingsPageV2 />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("ProviderSettingsPageV2", () => {
  afterEach(() => vi.clearAllMocks());

  it("renders the server-owned Pi boundary and uses the pi-ai model catalog", async () => {
    renderPage();

    expect(await screen.findByText("Pi Agent 运行边界")).toBeInTheDocument();
    expect(screen.getByText("受治理云环境")).toBeInTheDocument();
    expect(screen.getByText("仅业务桥接")).toBeInTheDocument();
    expect(screen.getByText("18 个工具 · 1 个技能")).toBeInTheDocument();
    expect(screen.getByText("subagents · opportunity-deep-research")).toBeInTheDocument();

    expect(await screen.findByText("Pi 原生模型目录")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /DeepSeek V4 Flash/ }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("deepseek-v4-flash")).toBeInTheDocument();
      expect(screen.getByDisplayValue("https://api.deepseek.com")).toBeInTheDocument();
    });
  });
});
