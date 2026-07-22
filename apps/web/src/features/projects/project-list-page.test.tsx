import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProjectListPage } from "./project-list-page";

// Mock the auth module
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { id: "1", display_name: "Test", email: "test@test.com", role: "member", plan: "starter" },
    token: "mock-token",
    isAuthenticated: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    setUser: vi.fn(),
  }),
}));

// Mock sonner
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// Mock the API module - individual test callbacks override behavior via vi.mocked
vi.mock("@/lib/api", () => ({
  listProjects: vi.fn(),
  createDemoProject: vi.fn(),
  createProject: vi.fn(),
  updateProjectStatus: vi.fn(),
  deleteProject: vi.fn(),
}));

import { listProjects } from "@/lib/api";

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ProjectListPage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  it("shows skeleton while loading", () => {
    // listProjects never resolves, keeping isLoading=true
    vi.mocked(listProjects).mockReturnValue(new Promise(() => {}) as never);

    renderWithProviders(<ProjectListPage />);

    // Skeleton elements should be present
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders project list without error", async () => {
    vi.mocked(listProjects).mockResolvedValue([
      { id: "1", name: "Test Project", slug: "test-project", scenario_package: "bidpilot", status: "active" },
    ] as never);

    renderWithProviders(<ProjectListPage />);
    // Wait for async query to resolve and render the heading
    await waitFor(() => {
      expect(screen.getByText("Projects")).toBeDefined();
    });
  });
});
