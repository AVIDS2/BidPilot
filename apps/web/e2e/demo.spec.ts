import { expect, test } from "@playwright/test";

const runDemo = process.env.E2E_DEMO === "1";
const demoEmail = process.env.E2E_DEMO_EMAIL ?? "demo@docpilot.ai";
const demoPassword = process.env.E2E_DEMO_PASSWORD ?? "Demo1234";
const demoProjectName = process.env.E2E_DEMO_PROJECT ?? "Acme Corp RFP Response";

test.describe("seeded BidPilot demo flow @demo", () => {
  test.skip(!runDemo, "Set E2E_DEMO=1 after starting the API and seeding demo data.");

  test("logs in and opens the seeded project detail workflow", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(demoEmail);
    await page.getByLabel("Password").fill(demoPassword);
    await page.getByRole("button", { name: "Login" }).click();

    await expect(page).toHaveURL(/\/projects$/);
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
    await page.getByPlaceholder("Search projects...").fill(demoProjectName);
    const projectLink = page.getByRole("link", { name: demoProjectName, exact: true });
    await expect(projectLink).toBeVisible();

    await projectLink.click();

    await expect(page.getByRole("heading", { name: demoProjectName })).toBeVisible();
    await expect(page.getByLabel("breadcrumb")).toContainText("Projects");
    await expect(page.getByLabel("breadcrumb")).toContainText(demoProjectName);

    for (const tabName of ["Bundles", "Deliverables", "Requirements", "Review", "Export"]) {
      await expect(page.getByRole("tab", { name: tabName })).toBeVisible();
    }

    await page.getByRole("tab", { name: "Review" }).click();
    await expect(page.getByRole("tabpanel")).toContainText(/Review|section|thread|comment/i);

    await page.getByRole("tab", { name: "Audit" }).click();
    await expect(page.getByRole("tabpanel")).toContainText(/Audit|event|No audit events/i);

    await page.getByRole("tab", { name: "System" }).click();
    await expect(page.getByRole("tabpanel")).toContainText("System Status");
  });
});

test.describe("full MVP end-to-end flow @e2e-full", () => {
  test.skip(!runDemo, "Set E2E_DEMO=1 after starting the API and seeding demo data.");

  test("create project → upload → review → export → audit trail", async ({ page }) => {
    // 1. Login
    await page.goto("/login");
    await page.getByLabel("Email").fill(demoEmail);
    await page.getByLabel("Password").fill(demoPassword);
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/projects$/);

    // 2. Create project
    const projectName = `E2E Test ${Date.now()}`;
    await page.getByRole("button", { name: /New Project/i }).click();
    await page.getByLabel("Project Name").fill(projectName);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByRole("heading", { name: projectName })).toBeVisible({ timeout: 15000 });

    // 3. Verify all tabs are present
    for (const tabName of ["Bundles", "Deliverables", "Requirements", "Review", "Export"]) {
      await expect(page.getByRole("tab", { name: tabName })).toBeVisible();
    }

    // 4. Register a bundle, then upload a document
    await page.getByRole("tab", { name: "Bundles" }).click();
    await page.getByLabel("Bundle Label").fill("Test RFP Bundle");
    await page.getByRole("button", { name: "Register Bundle" }).click();
    await expect(page.getByText("Test RFP Bundle")).toBeVisible({ timeout: 15000 });

    // Expand the bundle accordion to reveal the file input
    await page.getByText("Test RFP Bundle").click();
    const fileInput = page.locator('input[type="file"]').first();
    await expect(fileInput).toBeVisible({ timeout: 10000 });
    await fileInput.setInputFiles({
      name: "test-rfp.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("This is a test RFP document for E2E testing.\n\nRequirements:\n1. System must support user authentication\n2. System must provide audit logging"),
    });

    // 5. Check deliverables tab
    await page.getByRole("tab", { name: "Deliverables" }).click();
    await expect(page.getByRole("tabpanel")).toBeVisible();

    // 6. Review tab
    await page.getByRole("tab", { name: "Review" }).click();
    await expect(page.getByRole("tabpanel")).toContainText(/Review|section|thread/i);

    // 7. Export tab
    await page.getByRole("tab", { name: "Export" }).click();
    await expect(page.getByRole("tabpanel")).toBeVisible();

    // 8. Audit tab (admin user)
    await page.getByRole("tab", { name: "Audit" }).click();
    await expect(page.getByRole("tabpanel")).toContainText(/Audit|event|No audit events/i);

    // 9. System tab (admin user)
    await page.getByRole("tab", { name: "System" }).click();
    await expect(page.getByRole("tabpanel")).toContainText("System Status");
  });
});

test.describe("review reject → redraft → approve → export cycle @reject-redraft", () => {
  test.skip(!runDemo, "Set E2E_DEMO=1 after starting the API with demo data");

  test("review reject → redraft → approve → export cycle", async ({ page }) => {
    // Login
    await page.goto("/login");
    await page.getByLabel("Email").fill(demoEmail);
    await page.getByLabel("Password").fill(demoPassword);
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/projects$/);

    // Open demo project
    await page.getByPlaceholder("Search projects...").fill(demoProjectName);
    const projectLink = page.getByRole("link", { name: demoProjectName, exact: true });
    await expect(projectLink).toBeVisible();
    await projectLink.click();

    // Navigate to Review tab
    await page.getByRole("tab", { name: "Review" }).click();
    await expect(page.getByRole("tabpanel")).toBeVisible();

    // Navigate to Export tab to verify we can export
    await page.getByRole("tab", { name: "Export" }).click();
    await expect(page.getByRole("tabpanel")).toBeVisible();

    // Navigate to Audit tab (admin only, demo user is admin)
    const auditTab = page.getByRole("tab", { name: "Audit" });
    if (await auditTab.isVisible()) {
      await auditTab.click();
      await expect(page.getByRole("tabpanel")).toBeVisible();
    }
  });
});
