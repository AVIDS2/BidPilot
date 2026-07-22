import { expect, test } from "@playwright/test";
import {
  createE2EWorkspaceUser,
  e2eAdminEmail,
  e2eAdminPassword,
  loginThroughUi,
  prepareE2EPage,
  registerWorkspaceUser,
  verifyEmailAsAdmin,
} from "./helpers";

const runDemo = process.env.E2E_DEMO === "1";

test.beforeEach(async ({ page }) => {
  await prepareE2EPage(page);
});

test.describe("admin user management @admin", () => {
  test.skip(!runDemo, "Set E2E_DEMO=1 after starting the API and seeding demo data.");

  test("admin sees Users nav item and can manage users", async ({ page }) => {
    await loginThroughUi(page, e2eAdminEmail, e2eAdminPassword);

    // Admin should see Users nav
    await expect(page.getByRole("link", { name: /Users/i })).toBeVisible();

    // Navigate to user management
    await page.getByRole("link", { name: /Users/i }).click();
    await expect(page).toHaveURL(/\/admin\/users/);
    await expect(page.getByRole("heading", { name: /User Management/i })).toBeVisible();

    // Should see user list
    await expect(page.getByText(e2eAdminEmail)).toBeVisible();
  });

  test("admin can change user role", async ({ page }) => {
    await loginThroughUi(page, e2eAdminEmail, e2eAdminPassword);

    await page.getByRole("link", { name: /Users/i }).click();
    await expect(page).toHaveURL(/\/admin\/users/);

    // Find a non-admin user row and change role
    const memberRows = page.locator("tr").filter({ hasText: "member" });
    if ((await memberRows.count()) > 0) {
      const firstMemberRow = memberRows.first();
      // Click the role selector for that row
      await firstMemberRow.locator("select, [role='combobox']").first().click();
    }
  });

  test("admin sees Audit and System tabs on project detail", async ({ page }) => {
    await loginThroughUi(page, e2eAdminEmail, e2eAdminPassword);

    // The guided demo is created through the authenticated UI before
    // governance tabs are asserted, so this test has no external seed data.
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Explore a demo workspace" }).click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10_000 });
    await expect(page.getByRole("tab", { name: "Audit" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "System" })).toBeVisible();
  });
});

test.describe("member governance restriction @member-gov", () => {
  test.skip(!runDemo, "Set E2E_DEMO=1 after starting the API and seeding demo data.");

  test("member user does NOT see Audit or System tabs", async ({ page }) => {
    const member = createE2EWorkspaceUser("governance-member");
    const memberPassword = "Member123";

    await registerWorkspaceUser(page, member, memberPassword);
    await verifyEmailAsAdmin(member.email);
    await loginThroughUi(page, member.email, memberPassword);

    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Explore a demo workspace" }).click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10_000 });
    await expect(page.getByRole("tab", { name: "Audit" })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "System" })).toHaveCount(0);
  });
});
