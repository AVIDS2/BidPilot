import { expect, test } from "@playwright/test";
import { e2eAdminEmail, e2eAdminPassword, loginThroughUi, prepareE2EPage } from "./helpers";

const runWithAPI = process.env.E2E_DEMO === "1";

test.beforeEach(async ({ page }) => {
  await prepareE2EPage(page);
});

test.describe("Account page", () => {
  test("redirects to login when unauthenticated", async ({ page }) => {
    await page.goto("/account");
    // Should redirect to login
    await page.waitForURL(/\/login/);
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows user profile after login", async ({ page }) => {
    test.skip(!runWithAPI, "Set E2E_DEMO=1 after starting the API with demo data");

    await loginThroughUi(page, e2eAdminEmail, e2eAdminPassword);

    await page.goto("/account");
    await expect(page.getByText(e2eAdminEmail, { exact: true })).toBeVisible();
    await expect(page.getByText(/Plan|Starter|Professional|Enterprise/i).first()).toBeVisible();
  });
});
