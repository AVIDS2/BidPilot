import { expect, request, test, type Page } from "@playwright/test";
import {
  loginThroughUi,
  prepareE2EPage,
  registerWorkspaceUser,
  verifyEmailAsAdmin,
} from "./helpers";

const runLive = process.env.E2E_LIVE === "1";
const registerLiveUser = process.env.E2E_LIVE_REGISTER === "1";
const liveEmail = process.env.E2E_LIVE_EMAIL ?? "e2e-product-chain@updates.rglens.com";
const livePassword = process.env.E2E_LIVE_PASSWORD ?? "E2eProductChain123!";
const liveApiUrl = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";

async function apiJson<T>(
  page: Page,
  path: string,
): Promise<T> {
  return page.evaluate(async ({ requestPath, apiBaseUrl }) => {
    const token = window.localStorage.getItem("bidpilot_token");
    const response = await fetch(`${apiBaseUrl}${requestPath}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      throw new Error(`${requestPath} failed with ${response.status}: ${await response.text()}`);
    }
    return response.json();
  }, { requestPath: path, apiBaseUrl: liveApiUrl });
}

async function assertBidPilotApi(): Promise<void> {
  const apiContext = await request.newContext({ baseURL: liveApiUrl });
  try {
    const response = await apiContext.get("/openapi.json");
    if (!response.ok) {
      throw new Error(`OpenAPI probe failed with ${response.status()}`);
    }
    const document = await response.json() as { info?: { title?: string } };
    expect(document.info?.title).toBe("DocPilot API");
  } finally {
    await apiContext.dispose();
  }
}

test.describe.serial("本地真实产品链路", () => {
  test("通过浏览器注册隔离工作区", async ({ page }, testInfo) => {
    test.skip(!registerLiveUser, "Set E2E_LIVE_REGISTER=1 to register the isolated local test user.");
    test.skip(testInfo.project.name !== "chromium", "The live registration creates one fixed isolated account.");
    await prepareE2EPage(page);
    await assertBidPilotApi();
    const workspaceSuffix = Date.now();
    await registerWorkspaceUser(page, {
      email: liveEmail,
      displayName: "E2E Product Chain",
      organizationName: `E2E Product Chain ${workspaceSuffix}`,
      organizationSlug: `e2e-product-chain-${workspaceSuffix}`,
    }, livePassword);
  });

  test("用户手动创建项目、上传资料，并向当前项目的 Agent 询问状态", async ({ page }, testInfo) => {
    test.skip(!runLive, "Set E2E_LIVE=1 after the local test user has verified their email.");
    test.skip(testInfo.project.name !== "chromium", "Run the live chain once against the isolated local workspace.");
    test.setTimeout(330_000);

    await prepareE2EPage(page);
    await assertBidPilotApi();
    await verifyEmailAsAdmin(liveEmail);
    await loginThroughUi(page, liveEmail, livePassword);
    await page.goto("/projects");

    const projectName = `E2E 手动链路 ${Date.now()}`;
    await page.getByRole("button", { name: "新建机会" }).first().click();
    await page.getByLabel("机会名称").fill(projectName);
    await page.getByRole("button", { name: "创建机会" }).click();
    await expect(page).toHaveURL(/\/projects\/[^/]+$/, { timeout: 15_000 });

    const projectId = new URL(page.url()).pathname.split("/").at(-1);
    expect(projectId).toBeTruthy();
    await expect(page.getByRole("heading", { name: projectName })).toBeVisible();

    await page.getByRole("button", { name: "上传资料" }).first().click();
    await expect(page.getByRole("heading", { name: "上传项目资料" })).toBeVisible();
    await page.locator('input[type="file"]').setInputFiles({
      name: "e2e-rfp.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("项目名称：E2E 投标响应\n要求：说明技术方案、交付计划与团队资质。", "utf-8"),
    });
    await page.getByRole("button", { name: "上传并解析" }).click();
    await expect(page.getByText("1 份资料已上传，正在自动解析。", { exact: true })).toBeVisible({ timeout: 20_000 });

    await expect.poll(async () => {
      const bundles = await apiJson<Array<{ id: string }>>(page, `/bundles?project_id=${projectId}`);
      if (!bundles[0]) return null;
      const documents = await apiJson<{ items: Array<{ parse_status: string; index_status: string; original_filename: string }> }>(
        page,
        `/documents?bundle_id=${bundles[0].id}`,
      );
      return documents.items.find((item) => item.original_filename === "e2e-rfp.txt") ?? null;
    }, { timeout: 90_000, intervals: [1_000, 2_000, 4_000] }).toMatchObject({
      parse_status: "parsed",
      index_status: "indexed",
    });

    await page.getByRole("button", { name: "询问 Agent" }).click();
    await expect(page).toHaveURL(new RegExp(`/agent\\?project_id=${projectId}`));

    const prompt = "请查看当前项目的资料处理状态和投标准备缺口。";
    const responsePromise = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/assistant/stream" && response.request().method() === "POST",
    );
    await page.getByRole("textbox", { name: "Ask me anything..." }).fill(prompt);
    await page.getByRole("button", { name: "Send" }).click();
    const assistantResponse = await responsePromise;
    expect(assistantResponse.status()).toBe(200);
    expect(assistantResponse.request().postDataJSON()).toMatchObject({
      message: prompt,
      project_id: projectId,
    });
    const assistantStream = await assistantResponse.text();
    expect(assistantStream).toContain("event: assistant.end");
    expect(assistantStream).not.toContain('"state": "failed"');
    expect(assistantStream).toContain("已完成解析并建立检索索引");
    expect(assistantStream).not.toContain("暂无入库资料");
    expect(assistantStream).not.toContain("尚未完成解析入库");

    await expect(page.getByTestId("claude-agent-thread").getByText(prompt, { exact: true })).toBeVisible();
    await expect
      .poll(async () => page.locator('[data-testid="agent-conversation-pane"]').innerText(), {
        timeout: 60_000,
        intervals: [1_000, 2_000, 4_000],
      })
      .not.toContain("助手连接已结束，但运行记录未报告终态");

    // Continue through the visible workbench. The API is used only to wait for
    // asynchronous workers and confirm the durable state produced by the UI.
    await page.goto(`/projects/${projectId}`);
    await page.getByRole("button", { name: "章节" }).click();
    await page.getByRole("button", { name: "新建交付物" }).click();
    await expect(page.getByRole("heading", { name: "新建交付物" })).toBeVisible();
    await page.getByLabel("交付物名称").fill("E2E 技术响应文件");
    await page.getByRole("button", { name: "创建交付物" }).click();
    await expect(page.getByLabel("章节标题")).toBeVisible({ timeout: 15_000 });

    await page.getByLabel("章节标题").fill("技术方案");
    await page.getByLabel("章节标识").fill("technical-approach");
    await page.getByRole("button", { name: "添加章节" }).click();
    await expect(page.getByRole("heading", { name: "章节详情" })).toBeVisible({ timeout: 15_000 });

    await expect.poll(async () => {
      const items = await apiJson<Array<{ id: string; title: string; status: string }>>(page, `/deliverables?project_id=${projectId}`);
      return items.find((item) => item.title === "E2E 技术响应文件") ?? null;
    }, { timeout: 20_000, intervals: [500, 1_000, 2_000] }).not.toBeNull();

    const deliverableId = (await apiJson<Array<{ id: string; title: string }>>(page, `/deliverables?project_id=${projectId}`))
      .find((item) => item.title === "E2E 技术响应文件")?.id;
    if (!deliverableId) {
      throw new Error("E2E delivery was not created by the visible workbench flow");
    }
    await expect.poll(async () => {
      const items = await apiJson<Array<{ id: string; section_key: string }>>(page, `/deliverables/${deliverableId}/sections`);
      return items.find((item) => item.section_key === "technical-approach") ?? null;
    }, { timeout: 20_000, intervals: [500, 1_000, 2_000] }).not.toBeNull();

    const sectionId = (await apiJson<Array<{ id: string; section_key: string }>>(page, `/deliverables/${deliverableId}/sections`))
      .find((item) => item.section_key === "technical-approach")?.id;
    if (!sectionId) {
      throw new Error("E2E target section was not created by the visible workbench flow");
    }

    const draftResponsePromise = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/drafting/sections" && response.request().method() === "POST",
    );
    await page.getByRole("button", { name: "生成初稿" }).click();
    const draftResponse = await draftResponsePromise;
    expect(draftResponse.status()).toBe(202);
    const draftPayload = await draftResponse.json() as { run_id?: string };
    const draftRunId = draftPayload.run_id;
    if (!draftRunId) {
      throw new Error("Draft endpoint accepted the request without returning run_id");
    }

    await expect.poll(async () => {
      const runs = await apiJson<Array<{ id: string; run_type: string; status: string }>>(page, `/execution/runs?project_id=${projectId}`);
      return runs.find((run) => run.id === draftRunId && run.run_type === "draft_section") ?? null;
    }, { timeout: 20_000, intervals: [500, 1_000, 2_000] }).not.toBeNull();

    await expect.poll(async () => {
      const run = await apiJson<{ status: string; output_json: Record<string, unknown> | null }>(page, `/execution/runs/${draftRunId}`);
      if (run.status === "failed") {
        throw new Error(`Drafting worker failed: ${JSON.stringify(run.output_json ?? {})}`);
      }
      return run.status;
    }, { timeout: 150_000, intervals: [1_000, 2_000, 4_000] }).toMatch(/^(awaiting_human|succeeded)$/);

    await expect.poll(async () => {
      const versions = await apiJson<Array<{ id: string; content_markdown: string }>>(page, `/versions?section_id=${sectionId}`);
      return versions[0] ?? null;
    }, { timeout: 30_000, intervals: [1_000, 2_000, 4_000] }).toMatchObject({
      content_markdown: expect.any(String),
    });

    await page.getByRole("button", { name: "进入审阅" }).click();
    await expect(page.getByRole("heading", { name: "审阅" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByLabel("审核意见")).toBeVisible({ timeout: 20_000 });
    await page.getByLabel("审核意见").fill("E2E 人工审核通过：可进入交付。");
    await page.getByRole("button", { name: "批准版本" }).click();

    await expect.poll(async () => {
      const items = await apiJson<Array<{ id: string; status: string }>>(page, `/deliverables?project_id=${projectId}`);
      return items.find((item) => item.id === deliverableId)?.status ?? null;
    }, { timeout: 90_000, intervals: [1_000, 2_000, 4_000] }).toBe("approved");

    await page.getByRole("button", { name: "交付" }).click();
    const exportDocx = page.getByRole("button", { name: "导出 E2E 技术响应文件 为 DOCX" });
    await expect(exportDocx).toBeEnabled({ timeout: 15_000 });
    const downloadPromise = page.waitForEvent("download");
    await exportDocx.click();
    const download = await downloadPromise;
    await expect(download.suggestedFilename()).toMatch(/\.docx$/i);
    await download.cancel();

    await page.screenshot({ path: testInfo.outputPath("live-product-chain.png"), fullPage: true });
  });
});
