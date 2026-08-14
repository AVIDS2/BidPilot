import { expect, test, type Page } from "@playwright/test";

async function prepareAdminWorkspace(page: Page) {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_token", "settings-visual-test-token");
    localStorage.setItem("bidpilot_lang", "zh-CN");
    localStorage.setItem("theme", "light");
  });

  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "settings-admin",
        email: "admin@bidpilot.local",
        display_name: "BidPilot 管理员",
        role: "admin",
        plan: "pro",
        email_verified: true,
        org_id: "bidpilot-org",
        org_slug: "bidpilot-org",
      }),
    });
  });
  await page.route("**/auth/billing-summary", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        data: {
          plan: "pro",
          status: "active",
          is_billing_owner: true,
          monthly_workflow_limit: 120,
          monthly_workflow_used: 36,
          monthly_assistant_limit: 800,
          monthly_assistant_used: 210,
          monthly_indexing_limit: 500,
          monthly_indexing_used: 82,
        },
      }),
    });
  });
  await page.route("**/organizations/current/entitlements", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        plan: "pro",
        subscription_status: "active",
        active_member_count: 4,
        seat_limit: 8,
        available_seats: 4,
        project_limit: 30,
        monthly_workflow_limit: 120,
        monthly_assistant_limit: 800,
        monthly_indexing_limit: 500,
        is_billing_owner: true,
      }),
    });
  });
  await page.route("**/organizations", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        { id: "bidpilot-org", name: "BidPilot", slug: "bidpilot" },
      ]),
    });
  });
  await page.route("**/auth/me/providers", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          {
            id: "provider-openai",
            provider_type: "openai",
            provider_id: "openai",
            label: "OpenAI production",
            api_url: "https://api.openai.com/v1",
            model: "gpt-4o",
            is_active: true,
          },
        ],
      }),
    });
  });
  await page.route("**/webhooks/overview", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        summary: {
          active_endpoint_count: 1,
          delivery_count: 4,
          failed_delivery_count: 1,
          pending_delivery_count: 1,
        },
        supported_events: ["radar.notice.matched", "radar.notice.saved", "radar.notice.converted"],
        endpoints: [{
          id: "webhook-feishu",
          name: "飞书招采通知",
          target_url: "https://automation.example.com/bidpilot",
          events: ["radar.notice.matched", "radar.notice.converted"],
          is_active: true,
          signing_secret_hint: "bpwh_...8f23",
          created_at: "2026-08-08T08:00:00Z",
          updated_at: "2026-08-08T08:00:00Z",
        }],
        deliveries: [{
          id: "delivery-1",
          endpoint_id: "webhook-feishu",
          endpoint_name: "飞书招采通知",
          event_type: "radar.notice.matched",
          status: "delivered",
          attempt_count: 1,
          max_attempts: 5,
          available_at: null,
          last_http_status: 204,
          last_error_code: null,
          delivered_at: "2026-08-08T08:05:00Z",
          created_at: "2026-08-08T08:05:00Z",
          payload: {},
        }, {
          id: "delivery-2",
          endpoint_id: "webhook-feishu",
          endpoint_name: "飞书招采通知",
          event_type: "radar.notice.converted",
          status: "pending",
          attempt_count: 2,
          max_attempts: 5,
          available_at: "2026-08-08T08:35:00Z",
          last_http_status: 503,
          last_error_code: "upstream_5xx",
          delivered_at: null,
          created_at: "2026-08-08T08:10:00Z",
          payload: {},
        }],
      }),
    });
  });
  await page.route("**/webhooks/endpoints/webhook-feishu/rotate-secret", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        endpoint: {
          id: "webhook-feishu", name: "飞书招采通知", target_url: "https://automation.example.com/bidpilot", events: ["radar.notice.matched", "radar.notice.converted"], is_active: true, signing_secret_hint: "bpwh_...d11a", created_at: "2026-08-08T08:00:00Z", updated_at: "2026-08-08T08:20:00Z",
        },
        signing_secret: "bpwh_test_secret_after_rotation",
      }),
    });
  });
  await page.route("**/notifications", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
}

test("keeps account, organization, and model settings as a single useful workbench", async ({ page }, testInfo) => {
  await prepareAdminWorkspace(page);

  const pages = [
    { path: "/account", title: "账户与个性化", evidence: "个人资料", evidenceRole: "heading", screenshot: "account" },
    { path: "/administration", title: "组织设置", evidence: "组织操作", evidenceRole: "heading", screenshot: "organization" },
    { path: "/settings/providers", title: "集成与模型", evidence: "OpenAI production", evidenceRole: "heading", screenshot: "providers" },
    { path: "/settings/webhooks", title: "Webhook", evidence: "飞书招采通知", evidenceRole: "text", screenshot: "webhooks" },
  ];

  for (const current of pages) {
    await page.goto(current.path);
    await expect(page.getByRole("heading", { name: current.title, exact: true })).toBeVisible();
    await expect(page.locator(".wb-settings-page")).toBeVisible();
    const evidence = current.evidenceRole === "heading"
      ? page.getByRole("heading", { name: current.evidence, exact: true })
      : page.getByText(current.evidence, { exact: true });
    await expect(evidence).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`settings-${current.screenshot}-${testInfo.project.name}.png`),
      fullPage: true,
    });

    if (current.path === "/settings/webhooks") {
      await page.getByTitle("轮换签名密钥").click();
      await expect(page.getByRole("heading", { name: "保存签名密钥" })).toBeVisible();
      await expect(page.getByText("bpwh_test_secret_after_rotation", { exact: true })).toBeVisible();
    }
  }
});
