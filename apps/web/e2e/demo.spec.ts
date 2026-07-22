import { expect, test } from "@playwright/test";
import {
  createE2EWorkspaceUser,
  loginThroughUi,
  prepareE2EPage,
  registerWorkspaceUser,
  verifyEmailAsAdmin,
} from "./helpers";

const runDemo = process.env.E2E_DEMO === "1";
const DEMO_PROJECT_NAME = "演示 · 智慧社区 AI 治理平台投标";

test.beforeEach(async ({ page }) => {
  await prepareE2EPage(page);
});

test.describe("guided BidPilot demo workspace @demo", () => {
  test.skip(!runDemo, "Set E2E_DEMO=1 after starting an isolated API and bootstrapping its E2E admin.");

  test("registers an isolated workspace, creates the built-in demo, and reads its governed source trace", async ({ page }) => {
    const user = createE2EWorkspaceUser("guided-demo");
    const password = "TestPass123";

    await registerWorkspaceUser(page, user, password);
    await verifyEmailAsAdmin(user.email);
    await loginThroughUi(page, user.email, password);

    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Explore a demo workspace" }).click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: DEMO_PROJECT_NAME })).toBeVisible();

    for (const tabName of ["Bundles", "Requirements", "Project knowledge", "Evidence", "Runs"]) {
      await expect(page.getByRole("tab", { name: tabName })).toBeVisible();
    }

    await page.getByRole("tab", { name: "Requirements" }).click();
    await expect(page.getByText("Requirement Ledger", { exact: true })).toBeVisible();

    await page.getByRole("tab", { name: "Evidence" }).click();
    await expect(page.getByText("Citation Evidence", { exact: true })).toBeVisible();

    await page.getByRole("tab", { name: "Bundles" }).click();
    await expect(page.getByText("内置演示资料包", { exact: true })).toBeVisible();
  });
});
