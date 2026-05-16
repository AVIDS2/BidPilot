import { expect, test } from "@playwright/test";

const runWithAPI = process.env.E2E_DEMO === "1";
const demoEmail = process.env.E2E_DEMO_EMAIL ?? "demo@docpilot.ai";

test.describe("Account page", () => {
  test("redirects to login when unauthenticated", async ({ page }) => {
    await page.goto("/account");
    // Should redirect to login
    await page.waitForURL(/\/login/);
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows user profile after login", async ({ page }) => {
    test.skip(!runWithAPI, "Set E2E_DEMO=1 after starting the API with demo data");

    await page.goto("/login");
    await page.getByLabel("Email").fill(demoEmail);
    await page.getByLabel("Password").fill("Demo1234");
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/projects$/);

    await page.goto("/account");
    await expect(page.getByText(demoEmail, { exact: true })).toBeVisible();
    await expect(page.getByText(/Plan|Starter|Professional|Enterprise/i).first()).toBeVisible();
  });
});
