import { expect, test, request } from "@playwright/test";

const runWithAPI = process.env.E2E_DEMO === "1";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
});

// --- Static page tests (no API needed) ---

test("shows landing page for unauthenticated users", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/AI-Powered Document Execution/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /Get Started/i })).toBeVisible();
});

test("renders login page with forgot password link", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome to DocPilot" })).toBeVisible();
  await expect(page.getByText("Forgot password?")).toBeVisible();
});

test("renders signup page with password strength hint", async ({ page }) => {
  await page.goto("/signup");
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
  await expect(page.getByText(/uppercase.*lowercase.*digit/i)).toBeVisible();
});

test("forgot password page renders", async ({ page }) => {
  await page.goto("/forgot-password");
  await expect(page.getByRole("heading", { name: "Forgot Password" })).toBeVisible();
  await expect(page.getByText("Send Reset Link")).toBeVisible();
});

test("reset password page shows invalid link without token", async ({ page }) => {
  await page.goto("/reset-password");
  await expect(page.getByText(/invalid reset link/i)).toBeVisible();
});

// --- API-dependent tests (require E2E_DEMO=1 with backend running) ---

test.describe("auth flow with API backend @api", () => {
  test.skip(!runWithAPI, "Set E2E_DEMO=1 after starting the API server.");

  test("forgot password page accepts email and shows confirmation", async ({ page }) => {
    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill("test@example.com");
    await page.getByRole("button", { name: "Send Reset Link" }).click();
    await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  });

  /** Helper: verify a newly registered user's email via admin API.
   *  Uses a separate API request context to avoid cookie pollution. */
  async function adminVerifyEmail(userEmail: string) {
    const apiCtx = await request.newContext({ baseURL: "http://localhost:8000" });
    // Login as admin
    const loginResp = await apiCtx.post("/auth/login", {
      data: { email: "demo@docpilot.ai", password: "Demo1234" },
    });
    const { access_token } = await loginResp.json();

    // List users and find the target
    const usersResp = await apiCtx.get("/auth/users", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const users = await usersResp.json();
    const user = users.find((u: { email: string }) => u.email === userEmail);
    if (user) {
      await apiCtx.post(`/auth/users/${user.id}/verify`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
    }
    await apiCtx.dispose();
  }

  test("register, verify email, login, and view account page", async ({ page }) => {
    const email = `e2e-${Date.now()}@docpilot.local`;
    const password = "TestPass123";

    // Register
    await page.goto("/signup");
    await page.getByLabel("Display Name").fill("E2E Test User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm Password").fill(password);
    await page.getByRole("button", { name: "Create Account" }).click();

    // Should redirect to verify-email-prompt (email verification required)
    await expect(page).toHaveURL(/\/verify-email-prompt/, { timeout: 10000 });
    await expect(page.getByText("Check your email", { exact: true })).toBeVisible();

    // Admin verifies the user via API
    await adminVerifyEmail(email);

    // Now login
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Login" }).click();

    await expect(page).toHaveURL(/\/projects$/, { timeout: 10000 });
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();

    // Navigate to account via user dropdown menu
    await page.getByRole("button", { name: /E2E Test User/i }).click();
    await page.getByRole("menuitem", { name: /Account/i }).click();
    await expect(page).toHaveURL(/\/account/);
    await expect(page.getByRole("main").getByText(email, { exact: true })).toBeVisible();
  });

  test("member user does not see Users nav item", async ({ page }) => {
    const email = `e2e-member-${Date.now()}@docpilot.local`;
    const password = "TestPass123";

    await page.goto("/signup");
    await page.getByLabel("Display Name").fill("Member User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm Password").fill(password);
    await page.getByRole("button", { name: "Create Account" }).click();

    // Verify email via admin API
    await adminVerifyEmail(email);

    // Login
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Login" }).click();

    await expect(page).toHaveURL(/\/projects$/, { timeout: 10000 });

    // Member should NOT see Users nav
    await expect(page.getByRole("link", { name: /Users/i })).toHaveCount(0);
  });

  test("logout and redirect to login", async ({ page }) => {
    const email = `e2e-logout-${Date.now()}@docpilot.local`;
    const password = "TestPass123";

    await page.goto("/signup");
    await page.getByLabel("Display Name").fill("Logout User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm Password").fill(password);
    await page.getByRole("button", { name: "Create Account" }).click();

    // Verify email via admin API
    await adminVerifyEmail(email);

    // Login
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/projects$/, { timeout: 10000 });

    // Logout via user dropdown menu
    await page.getByRole("button", { name: /Logout User/i }).click();
    await page.getByRole("menuitem", { name: /Log out/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
