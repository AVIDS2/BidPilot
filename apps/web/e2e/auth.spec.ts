import { expect, test } from "@playwright/test";
import {
  createE2EWorkspaceUser,
  loginThroughUi,
  prepareE2EPage,
  registerWorkspaceUser,
  verifyEmailAsAdmin,
} from "./helpers";

const runWithAPI = process.env.E2E_DEMO === "1";

test.beforeEach(async ({ page }) => {
  await prepareE2EPage(page);
});

// --- Static page tests (no API needed) ---

test("shows landing page for unauthenticated users", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: /Get Started/i }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Login", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign Up", exact: true })).toBeVisible();
});

test("renders login page with forgot password link", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("link", { name: "Forgot password?" })).toBeVisible();
});

test("renders signup page with password strength hint", async ({ page }) => {
  await page.goto("/signup");
  await expect(page.getByLabel("Display Name")).toBeVisible();
  await expect(page.getByText(/uppercase.*lowercase.*digit/i)).toBeVisible();
});

test("restores non-sensitive signup fields after returning from verification prompt", async ({ page }) => {
  await page.route("**/auth/register", async (route) => {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: "signup-draft-user",
        email: "draft@example.com",
        display_name: "Draft User",
        role: "owner",
        plan: "free",
        email_verified: false,
        org_id: "draft-org",
        org_slug: "draft-org",
      }),
    });
  });

  await page.goto("/signup");
  await page.getByLabel("Display Name").fill("Draft User");
  await page.getByLabel("Email").fill("draft@example.com");
  await page.getByLabel("Organization Name").fill("Draft Organization");
  await page.getByLabel("Organization Slug").fill("draft-org");
  await page.getByLabel("Password", { exact: true }).fill("DraftPass123");
  await page.getByLabel("Confirm Password").fill("DraftPass123");
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL(/\/verify-email-prompt/);

  await page.goBack();
  await expect(page).toHaveURL(/\/signup/);
  await expect(page.getByLabel("Display Name")).toHaveValue("Draft User");
  await expect(page.getByLabel("Email")).toHaveValue("draft@example.com");
  await expect(page.getByLabel("Organization Name")).toHaveValue("Draft Organization");
  await expect(page.getByLabel("Organization Slug")).toHaveValue("draft-org");
  // The browser may preserve the password in its in-memory history entry, but
  // the recoverable session draft must never contain either password field.
  const draft = await page.evaluate(() => sessionStorage.getItem("bidpilot_registration_draft"));
  expect(draft).not.toContain("DraftPass123");
});

test("forgot password page renders", async ({ page }) => {
  await page.goto("/forgot-password");
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send Reset Link" })).toBeVisible();
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

  test("register, verify email, login, and view account page", async ({ page }) => {
    const user = createE2EWorkspaceUser("account");
    const password = "TestPass123";

    await registerWorkspaceUser(page, user, password);
    await expect(page.getByText("Check your email", { exact: true })).toBeVisible();

    await verifyEmailAsAdmin(user.email);
    await loginThroughUi(page, user.email, password);
    await expect(page.getByText(/Welcome back/i).first()).toBeVisible();

    await page.goto("/account");
    await expect(page).toHaveURL(/\/account/);
    await expect(page.getByRole("main").getByText(user.email, { exact: true })).toBeVisible();
  });

  test("member user does not see Users nav item", async ({ page }) => {
    const user = createE2EWorkspaceUser("member");
    const password = "TestPass123";

    await registerWorkspaceUser(page, user, password);
    await verifyEmailAsAdmin(user.email);
    await loginThroughUi(page, user.email, password);

    // Member should NOT see Users nav
    await expect(page.getByRole("link", { name: /Users/i })).toHaveCount(0);
  });

  test("logout and redirect to login", async ({ page }) => {
    const user = createE2EWorkspaceUser("logout");
    const password = "TestPass123";

    await registerWorkspaceUser(page, user, password);
    await verifyEmailAsAdmin(user.email);
    await loginThroughUi(page, user.email, password);

    // Logout via user dropdown menu
    await page.getByRole("button", { name: new RegExp(user.displayName, "i") }).click();
    await page.getByRole("menuitem", { name: /Log out/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
