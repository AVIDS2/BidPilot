import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_lang", "en");
  });
});

test.describe("Pricing page", () => {
  test("displays three pricing tiers", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByRole("heading", { name: "Starter", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Professional", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Enterprise", exact: true })).toBeVisible();
  });

  test("has CTA buttons", async ({ page }) => {
    await page.goto("/pricing");
    const buttons = page.getByRole("link", { name: /Get Started|Start Trial|Contact Sales/ });
    await expect(buttons.first()).toBeVisible();
    const count = await buttons.count();
    expect(count).toBe(3);
  });

  test("starter CTA navigates to login when unauthenticated", async ({ page }) => {
    await page.goto("/pricing");
    await page.getByRole("link", { name: "Get Started", exact: true }).click();
    // Should navigate to login or signup
    await expect(page).toHaveURL(/\/(login|signup)/);
  });
});
