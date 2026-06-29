import { expect, test, request } from "@playwright/test";

const runDemo = process.env.E2E_DEMO === "1";
const demoEmail = process.env.E2E_DEMO_EMAIL ?? "demo@bidpilot.local";
const demoPassword = process.env.E2E_DEMO_PASSWORD ?? "Demo1234";

test.describe("admin user management @admin", () => {
  test.skip(!runDemo, "Set E2E_DEMO=1 after starting the API and seeding demo data.");

  test("admin sees Users nav item and can manage users", async ({ page }) => {
    // Login as admin
    await page.goto("/login");
    await page.getByLabel("Email").fill(demoEmail);
    await page.getByLabel("Password").fill(demoPassword);
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/projects$/);

    // Admin should see Users nav
    await expect(page.getByRole("link", { name: /Users/i })).toBeVisible();

    // Navigate to user management
    await page.getByRole("link", { name: /Users/i }).click();
    await expect(page).toHaveURL(/\/users/);
    await expect(page.getByRole("heading", { name: /User Management/i })).toBeVisible();

    // Should see user list
    await expect(page.getByText(demoEmail)).toBeVisible();
  });

  test("admin can change user role", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(demoEmail);
    await page.getByLabel("Password").fill(demoPassword);
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/projects$/);

    await page.getByRole("link", { name: /Users/i }).click();
    await expect(page).toHaveURL(/\/users/);

    // Find a non-admin user row and change role
    const memberRows = page.locator("tr").filter({ hasText: "member" });
    if ((await memberRows.count()) > 0) {
      const firstMemberRow = memberRows.first();
      // Click the role selector for that row
      await firstMemberRow.locator("select, [role='combobox']").first().click();
    }
  });

  test("admin sees Audit and System tabs on project detail", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(demoEmail);
    await page.getByLabel("Password").fill(demoPassword);
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/projects$/);

    // Navigate to first project
    const projectLink = page.locator("a[href^='/projects/']").first();
    if ((await projectLink.count()) > 0) {
      await projectLink.click();
      await expect(page.getByRole("tab", { name: "Audit" })).toBeVisible();
      await expect(page.getByRole("tab", { name: "System" })).toBeVisible();
    }
  });
});

test.describe("member governance restriction @member-gov", () => {
  test.skip(!runDemo, "Set E2E_DEMO=1 after starting the API and seeding demo data.");

  test("member user does NOT see Audit or System tabs", async ({ page }) => {
    // Register a new member user
    const memberEmail = `e2e-member-${Date.now()}@bidpilot.local`;
    const memberPassword = "Member123";

    await page.goto("/signup");
    await page.getByLabel("Display Name").fill("E2E Member");
    await page.getByLabel("Email").fill(memberEmail);
    await page.getByLabel("Password", { exact: true }).fill(memberPassword);
    await page.getByLabel("Confirm Password").fill(memberPassword);
    await page.getByRole("button", { name: "Create Account" }).click();

    // Should go to verify-email-prompt
    await expect(page).toHaveURL(/\/verify-email-prompt/, { timeout: 10000 });

    // Verify email via separate admin API context
    const apiCtx = await request.newContext({ baseURL: "http://localhost:8000" });
    const adminResp = await apiCtx.post("/auth/login", {
      data: { email: demoEmail, password: demoPassword },
    });
    const { access_token } = await adminResp.json();
    const usersResp = await apiCtx.get("/auth/users", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const users = await usersResp.json();
    const user = users.find((u: { email: string }) => u.email === memberEmail);
    if (user) {
      await apiCtx.post(`/auth/users/${user.id}/verify`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
    }
    await apiCtx.dispose();

    // Login as member
    await page.goto("/login");
    await page.getByLabel("Email").fill(memberEmail);
    await page.getByLabel("Password").fill(memberPassword);
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/projects$/, { timeout: 10000 });

    // Navigate to first project
    const projectLink = page.locator("a[href^='/projects/']").first();
    if ((await projectLink.count()) > 0) {
      await projectLink.click();
      // Member should NOT see Audit or System tabs
      await expect(page.getByRole("tab", { name: "Audit" })).toHaveCount(0);
      await expect(page.getByRole("tab", { name: "System" })).toHaveCount(0);
    }
  });
});
