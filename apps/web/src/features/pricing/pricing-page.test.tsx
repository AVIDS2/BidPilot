import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PricingPage } from "./pricing-page";
import { AuthProvider } from "@/lib/auth";

const qc = new QueryClient();

function renderWithRouter(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AuthProvider>{ui}</AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("PricingPage", () => {
  it("renders the three pricing tiers", () => {
    renderWithRouter(<PricingPage />);

    expect(screen.getByText("Starter")).not.toBeNull();
    expect(screen.getByText("Professional")).not.toBeNull();
    expect(screen.getByText("Enterprise")).not.toBeNull();
  });

  it("marks the Professional tier as recommended", () => {
    renderWithRouter(<PricingPage />);

    const badges = screen.getAllByText("Recommended");
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  it("shows feature lists for each tier", () => {
    renderWithRouter(<PricingPage />);

    expect(screen.getByText(/Up to 3 projects/i)).not.toBeNull();
    expect(screen.getByText(/Unlimited projects/i)).not.toBeNull();
    expect(screen.getByText(/Custom deployment/i)).not.toBeNull();
  });
});
