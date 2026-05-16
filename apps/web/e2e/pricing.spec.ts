import { expect, test } from "@playwright/test";

test.describe("Pricing page", () => {
  test("displays three pricing tiers", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByText("Starter")).toBeVisible();
    await expect(page.getByText("Professional")).toBeVisible();
    await expect(page.getByText("Enterprise")).toBeVisible();
  });

  test("has CTA buttons", async ({ page }) => {
    await page.goto("/pricing");
    const buttons = page.getByRole("button");
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test("starter CTA navigates to login when unauthenticated", async ({ page }) => {
    await page.goto("/pricing");
    await page.getByRole("button", { name: /Get Started|Upgrade|Sign up/i }).first().click();
    // Should navigate to login or signup
    await expect(page).toHaveURL(/\/(login|signup)/);
  });
});
