import { expect, request, type Page } from "@playwright/test";

export const e2eApiBaseURL = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";
export const e2eAdminEmail = process.env.E2E_ADMIN_EMAIL ?? process.env.E2E_DEMO_EMAIL ?? "e2e-admin@bidpilot.local";
export const e2eAdminPassword = process.env.E2E_ADMIN_PASSWORD ?? process.env.E2E_DEMO_PASSWORD ?? "E2eAdmin123";

export interface E2EWorkspaceUser {
  email: string;
  displayName: string;
  organizationName: string;
  organizationSlug: string;
}

export function createE2EWorkspaceUser(prefix: string): E2EWorkspaceUser {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const normalizedPrefix = prefix.toLowerCase().replace(/[^a-z0-9-]/g, "-");
  return {
    email: `e2e-${normalizedPrefix}-${suffix}@bidpilot.local`,
    displayName: `E2E ${prefix}`,
    organizationName: `E2E ${prefix} ${suffix}`,
    organizationSlug: `e2e-${normalizedPrefix}-${suffix}`,
  };
}

export async function prepareE2EPage(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("bidpilot_e2e_initialized") === "1") {
      return;
    }
    localStorage.clear();
    localStorage.setItem("bidpilot_lang", "en");
    sessionStorage.setItem("bidpilot_e2e_initialized", "1");
  });
}

export async function registerWorkspaceUser(
  page: Page,
  user: E2EWorkspaceUser,
  password: string,
) {
  await page.goto("/signup");
  await page.getByLabel("Display Name").fill(user.displayName);
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Organization Name").fill(user.organizationName);
  await page.getByLabel("Organization Slug").fill(user.organizationSlug);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL(/\/verify-email-prompt/, { timeout: 10_000 });
}

export async function verifyEmailAsAdmin(email: string) {
  const apiContext = await request.newContext({ baseURL: e2eApiBaseURL });
  try {
    const loginResponse = await apiContext.post("/auth/login", {
      data: { email: e2eAdminEmail, password: e2eAdminPassword },
    });
    expect(loginResponse.ok(), "E2E admin must be available in the isolated test API").toBeTruthy();
    const { access_token: accessToken } = await loginResponse.json() as { access_token?: string };
    expect(accessToken, "E2E admin login must return an access token").toBeTruthy();

    const usersResponse = await apiContext.get("/auth/users", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(usersResponse.ok(), "E2E admin must be able to list users").toBeTruthy();
    const users = await usersResponse.json() as { items?: Array<{ id: string; email: string }> };
    const user = users.items?.find((candidate) => candidate.email === email);
    if (!user) {
      throw new Error(`E2E registration was not visible to the admin for ${email}`);
    }

    const verifyResponse = await apiContext.post(`/auth/users/${user.id}/verify`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(verifyResponse.ok(), "E2E admin must be able to verify the registered user").toBeTruthy();
  } finally {
    await apiContext.dispose();
  }
}

export async function loginThroughUi(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 10_000 });
}
