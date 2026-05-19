import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProviderSettingsPage } from "./provider-settings-page";

// Mock the API module before any imports resolve
vi.mock("@/lib/api", () => ({
  listProviderConfigs: vi.fn().mockResolvedValue({ data: [] }),
  createProviderConfig: vi.fn(),
  updateProviderConfig: vi.fn(),
  deleteProviderConfig: vi.fn(),
  testProviderConnection: vi.fn(),
}));

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={qc}>
      {ui}
    </QueryClientProvider>,
  );
}

describe("ProviderSettingsPage", () => {
  it("renders the page title", async () => {
    renderWithProviders(<ProviderSettingsPage />);
    await waitFor(() => {
      expect(screen.getByText(/AI Provider Settings/i)).toBeDefined();
    });
  });

  it("renders the page description", async () => {
    renderWithProviders(<ProviderSettingsPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/Configure your AI provider connections/i),
      ).toBeDefined();
    });
  });

  it("renders the Add Provider button", async () => {
    renderWithProviders(<ProviderSettingsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Add Provider/i)).toBeDefined();
    });
  });

  it("shows empty state when no providers", async () => {
    renderWithProviders(<ProviderSettingsPage />);
    await waitFor(() => {
      expect(screen.getByText(/No providers configured yet/i)).toBeDefined();
    });
  });
});
