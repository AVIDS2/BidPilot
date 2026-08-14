import { expect, test, type Page } from "@playwright/test";

const projects = [
  { id: "directory-project-a", slug: "city-transport", name: "城市智慧交通平台投标", scenario_package: "bidpilot", status: "active" },
  { id: "directory-project-b", slug: "cloud-procurement", name: "政务云采购响应", scenario_package: "bidpilot", status: "active" },
];

async function prepareDirectoryWorkspaces(page: Page) {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_token", "directory-workspace-token");
    localStorage.setItem("bidpilot_lang", "zh-CN");
    localStorage.setItem("theme", "light");
  });

  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "directory-user",
        email: "directory@example.com",
        display_name: "Directory User",
        role: "member",
        plan: "free",
        email_verified: true,
        org_id: "directory-org",
        org_slug: "directory-org",
      }),
    });
  });
  await page.route("**/auth/me/providers", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ data: [] }) });
  });
  await page.route("**/notifications**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/projects", async (route) => {
    if (route.request().resourceType() !== "fetch") {
      await route.fallback();
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(projects) });
  });
  await page.route("**/bundles**", async (route) => {
    const projectId = new URL(route.request().url()).searchParams.get("project_id");
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(projectId === "directory-project-a" ? [{
        id: "directory-bundle-a",
        project_id: projectId,
        label: "采购公告与公开附件",
        source_type: "buyer_rfp",
        ingest_status: "parsed",
      }] : []),
    });
  });
  await page.route("**/documents**", async (route) => {
    const bundleId = new URL(route.request().url()).searchParams.get("bundle_id");
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(bundleId === "directory-bundle-a" ? {
        items: [{
          id: "directory-document-a",
          bundle_id: "directory-bundle-a",
          storage_key: "city-transport-rfp.pdf",
          source_url: "https://procurement.example.gov.cn/files/city-transport-rfp.pdf",
          mime_type: "application/pdf",
          original_filename: "城市智慧交通采购文件.pdf",
          parse_status: "parsed",
          parse_attempt_count: 1,
          parser_name: "pdf",
          parser_version: "1",
          parse_error_code: null,
          parse_error_detail: null,
          parse_retryable: false,
          index_status: "indexed",
          index_error_code: null,
          version_number: 1,
          supersedes_document_id: null,
        }],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      } : { items: [], total: 0, page: 1, page_size: 100, pages: 0 }),
    });
  });
  await page.route("**/memory/portfolio**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/runtime/runs**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "directory-run-approval",
          kind: "response_drafting",
          status: "awaiting_approval",
          project_id: "directory-project-a",
          project_name: "城市智慧交通平台投标",
          engine: "langgraph",
          created_at: "2026-08-08T10:00:00Z",
          started_at: "2026-08-08T10:00:00Z",
          finished_at: null,
          latest_event_summary: "技术响应草稿等待团队确认",
        },
        {
          id: "directory-run-failed",
          kind: "document_parse",
          status: "failed",
          project_id: "directory-project-b",
          project_name: "政务云采购响应",
          engine: "celery",
          created_at: "2026-08-08T09:00:00Z",
          started_at: "2026-08-08T09:00:00Z",
          finished_at: "2026-08-08T09:05:00Z",
          latest_event_summary: "一份扫描件需要人工补充可读版本",
        },
      ]),
    });
  });
  await page.route("**/readiness/projects/**", async (route) => {
    const projectId = route.request().url().includes("directory-project-a")
      ? "directory-project-a"
      : "directory-project-b";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        project_id: projectId,
        project_name: projects.find((project) => project.id === projectId)?.name,
        mandatory_gaps: projectId === "directory-project-a" ? [{
          id: "directory-requirement-a",
          project_id: projectId,
          section_key: "2.1",
          requirement_text: "补充项目经理类似项目证明和授权材料",
          bid_category: "qualification",
          is_mandatory: true,
          score_weight: 20,
          risk_level: "high",
          coverage_status: "uncovered",
          evidence_status: "missing",
          verification_status: "pending",
          owner_user_id: null,
          reviewer_user_id: null,
          due_at: null,
          source_locator_json: null,
        }] : [],
        evidence_gaps: [],
        contradictions: [],
      }),
    });
  });
}

async function expectTableFitsViewport(page: Page, selector: string) {
  const table = await page.locator(selector).boundingBox();
  const wrapper = await page.locator(selector).locator("xpath=ancestor::div[contains(@class, 'wb-directory-table-group') or contains(@class, 'wb-projects-table-wrap')][1]").boundingBox();
  expect(table).not.toBeNull();
  expect(wrapper).not.toBeNull();
  expect(table!.width).toBeLessThanOrEqual(wrapper!.width + 1);
}

test("目录页在同一操作画布中呈现项目、资料和团队待办", async ({ page }, testInfo) => {
  await prepareDirectoryWorkspaces(page);

  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "投标机会" })).toBeVisible();
  await expect(page.locator(".wb-projects-table")).toBeVisible();
  await expect(page.getByText("城市智慧交通平台投标", { exact: true })).toBeVisible();
  await expect(page.locator(".wb-projects-table-wrap")).toHaveCSS("border-radius", "10px");
  await expectTableFitsViewport(page, ".wb-projects-table");
  await page.screenshot({ path: testInfo.outputPath(`projects-directory-${testInfo.project.name}.png`), fullPage: true });

  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "知识资产" })).toBeVisible();
  await expect(page.getByText("城市智慧交通采购文件.pdf", { exact: true })).toBeVisible();
  await expect(page.getByText(/公开来源/)).toBeVisible();
  await expect(page.locator(".wb-directory-table-group")).toHaveCSS("border-radius", "10px");
  await expectTableFitsViewport(page, ".wb-materials-table");
  await page.screenshot({ path: testInfo.outputPath(`knowledge-directory-${testInfo.project.name}.png`), fullPage: true });

  await page.goto("/my-work");
  await expect(page.getByRole("heading", { name: "我的工作" })).toBeVisible();
  await expect(page.getByText("补齐强制要求的响应依据", { exact: true })).toBeVisible();
  await expect(page.getByText("技术响应草稿等待团队确认", { exact: true })).toBeVisible();
  await expect(page.locator(".wb-workboard-summary")).toHaveCSS("border-radius", "10px");
  await page.screenshot({ path: testInfo.outputPath(`my-work-directory-${testInfo.project.name}.png`), fullPage: true });
});

test("空项目目录保持表格结构并将创建入口居中", async ({ page }) => {
  await prepareDirectoryWorkspaces(page);
  await page.unroute("**/projects");
  await page.route("**/projects", async (route) => {
    const resourceType = route.request().resourceType();
    if (resourceType !== "fetch" && resourceType !== "xhr") {
      await route.fallback();
      return;
    }
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });

  await page.goto("/projects");
  await expect(page.locator(".wb-projects-table")).toBeVisible();
  const emptyCell = page.locator(".wb-projects-table__empty");
  const emptyContent = page.locator(".wb-projects-empty-content");
  await expect(emptyCell).toBeVisible();
  await expect(emptyContent).toBeVisible();
  await expect(emptyCell).toHaveCSS("display", "table-cell");
  const cellBox = await emptyCell.boundingBox();
  const contentBox = await emptyContent.boundingBox();
  expect(cellBox).not.toBeNull();
  expect(contentBox).not.toBeNull();
  expect(contentBox!.x).toBeGreaterThan(cellBox!.x);
  expect(contentBox!.x + contentBox!.width).toBeLessThan(cellBox!.x + cellBox!.width);
});
