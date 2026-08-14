import { expect, test, type Page } from "@playwright/test";

async function prepareRadarWorkspace(page: Page) {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_token", "radar-visual-test-token");
    localStorage.setItem("bidpilot_lang", "zh-CN");
    localStorage.setItem("theme", "light");
  });
  await page.route("**/auth/me", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ id: "radar-admin", email: "radar@bidpilot.local", display_name: "雷达管理员", role: "admin", plan: "pro", email_verified: true, org_id: "radar-org", org_slug: "bidpilot" }) });
  });
  await page.route("**/auth/me/providers", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ data: [] }) });
  });
  await page.route("**/notifications", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/radar/overview**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        summary: {
          active_source_count: 2,
          source_attention_count: 0,
          active_subscription_count: 3,
          recommended_count: 1,
          saved_count: 1,
          due_soon_count: 1,
          trends: [
            { day: "2026-08-03", notice_count: 0 }, { day: "2026-08-04", notice_count: 1 }, { day: "2026-08-05", notice_count: 0 },
            { day: "2026-08-06", notice_count: 2 }, { day: "2026-08-07", notice_count: 1 }, { day: "2026-08-08", notice_count: 1 },
          ],
        },
        sources: [{ id: "source-1", name: "江苏政府采购公告", kind: "rss", endpoint_url: "https://example.gov.cn/notices.xml", is_active: true, polling_interval_minutes: 60, last_polled_at: "2026-08-08T08:00:00Z", last_success_at: "2026-08-08T08:00:00Z", last_error_code: null, notice_count: 18 }, { id: "source-2", name: "上海公共资源交易", kind: "json_feed", endpoint_url: "https://example.gov.cn/feed.json", is_active: true, polling_interval_minutes: 60, last_polled_at: "2026-08-08T08:00:00Z", last_success_at: "2026-08-08T08:00:00Z", last_error_code: null, notice_count: 9 }],
        subscriptions: [{ id: "subscription-1", name: "华东数字化采购", keywords: ["数据治理", "云平台"], regions: ["上海", "江苏"], categories: ["软件服务"], budget_min: null, budget_max: null, is_active: true, match_count: 4, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-08T00:00:00Z" }],
        notices: [{ id: "notice-1", source_id: "source-1", source_name: "江苏政府采购公告", external_id: "notice-20260808", title: "省级数据治理平台建设项目", buyer_name: "江苏省数据局", notice_type: "tender", region: "江苏", category: "软件服务", budget_amount: 1800000, published_at: "2026-08-08T00:00:00Z", deadline_at: "2026-08-15T10:00:00Z", source_url: "https://example.gov.cn/notices/1", summary: "面向省级数据治理与共享交换能力建设。", status: "new", converted_project_id: null, created_at: "2026-08-08T08:00:00Z", matches: [{ subscription_id: "subscription-1", subscription_name: "华东数字化采购", score: 92, reasons: ["标题命中关键词：数据治理", "区域命中：江苏"] }] }],
      }),
    });
  });
}

test("雷达只呈现真实来源、趋势与可解释的机会匹配", async ({ page }, testInfo) => {
  await prepareRadarWorkspace(page);
  await page.goto("/radar");

  await expect(page.getByRole("heading", { name: "招采雷达" })).toBeVisible();
  await expect(page.getByLabel("2 个来源正在采集")).toBeVisible();
  await expect(page.getByRole("heading", { name: "新增机会趋势" })).toBeVisible();
  await expect(page.getByText("省级数据治理平台建设项目", { exact: true })).toBeVisible();
  await page.getByText("省级数据治理平台建设项目", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "匹配理由" })).toBeVisible();
  await expect(page.locator(".wb-radar-notice-sheet__matches").getByText(/标题命中关键词：数据治理/)).toBeVisible();
  await expect(page.getByRole("button", { name: "转为项目" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath(`radar-${testInfo.project.name}.png`), fullPage: true });
});
