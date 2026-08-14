import { expect, test, type Page } from "@playwright/test";

async function prepareAuthenticatedAgent(page: Page) {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_token", "visual-test-token");
    localStorage.setItem("bidpilot_lang", "en");
    localStorage.setItem("theme", "light");
  });

  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "visual-user",
        email: "visual@example.com",
        display_name: "Visual User",
        role: "admin",
        plan: "free",
        email_verified: true,
        org_id: "visual-org",
        org_slug: "visual-org",
      }),
    });
  });
  await page.route("**/auth/me/providers", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ data: [] }),
    });
  });
  await page.route("**/chat/conversations**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
  await page.route("**/notifications", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
}

test("keeps the Agent composer inside the conversation pane at every viewport", async ({
  page,
}, testInfo) => {
  await prepareAuthenticatedAgent(page);
  await page.goto("/agent");

  const conversationPane = page.getByTestId("agent-conversation-pane");
  const composer = page.getByTestId("linear-agent-composer");
  const textarea = page.getByRole("textbox", { name: "Ask me anything..." });
  const sendButton = page.getByRole("button", { name: "Send" });
  await expect(conversationPane).toBeVisible();
  await expect(composer).toBeVisible();
  await expect(textarea).toBeVisible();
  await expect(sendButton).toBeVisible();
  await expect(page.getByText("收集招标附件", { exact: true })).toBeVisible();
  // Idle is the absence of a run, not a decorative status tag in the header.
  await expect(page.getByText("就绪", { exact: true })).toHaveCount(0);

  const [paneBox, composerBox, textareaBox, sendBox] = await Promise.all([
    conversationPane.boundingBox(),
    composer.boundingBox(),
    textarea.boundingBox(),
    sendButton.boundingBox(),
  ]);
  expect(paneBox).not.toBeNull();
  expect(composerBox).not.toBeNull();
  expect(textareaBox).not.toBeNull();
  expect(sendBox).not.toBeNull();
  expect(composerBox!.x).toBeGreaterThanOrEqual(paneBox!.x - 1);
  expect(composerBox!.x + composerBox!.width).toBeLessThanOrEqual(
    paneBox!.x + paneBox!.width + 1,
  );
  expect(composerBox!.y + composerBox!.height).toBeLessThanOrEqual(
    paneBox!.y + paneBox!.height + 1,
  );
  expect(sendBox!.x).toBeGreaterThan(textareaBox!.x);
  expect(sendBox!.y).toBeLessThanOrEqual(
    textareaBox!.y + textareaBox!.height + 1,
  );

  await page.screenshot({
    path: testInfo.outputPath(
      `agent-workspace-${testInfo.project.name}-initial.png`,
    ),
    fullPage: true,
  });

  // The full-page Agent workspace keeps a single conversation canvas on both
  // layouts. The footer history control is intentionally desktop-only.
  if (testInfo.project.name === "chromium") {
    await expect(page.getByRole("button", { name: "Chat history" })).toBeVisible();

    // The desktop account menu is part of the shared workbench shell. Keep
    // its admin settings routes visible and on the light menu surface.
    await page.getByRole("button", { name: "打开账户菜单" }).click();
    await expect(page.getByText("账户与个性化", { exact: true })).toBeVisible();
    await expect(page.getByText("组织设置", { exact: true })).toBeVisible();
    await expect(
      page.getByText("集成、模型与 Webhook", { exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath("agent-workspace-account-menu.png"),
      fullPage: true,
    });
  }

  await page.screenshot({
    path: testInfo.outputPath(`agent-workspace-${testInfo.project.name}.png`),
    fullPage: true,
  });
});

test("opens a structured canvas action beside the current Agent conversation", async ({
  page,
}, testInfo) => {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_token", "visual-test-token");
    localStorage.setItem("bidpilot_lang", "en");
    localStorage.setItem("theme", "light");
    localStorage.setItem("bidpilot_last_assistant_conversation_id", "canvas-conversation");
  });

  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "visual-user",
        email: "visual@example.com",
        display_name: "Visual User",
        role: "admin",
        plan: "free",
        email_verified: true,
        org_id: "visual-org",
        org_slug: "visual-org",
      }),
    });
  });
  await page.route("**/auth/me/providers", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ data: [] }) });
  });
  await page.route("**/chat/conversations**", async (route) => {
    const url = route.request().url();
    if (url.includes("/canvas-conversation/messages")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          total: 2,
          items: [
            {
              id: "message-user",
              role: "user",
              content: "打开当前项目的任务编排画布",
              created_at: "2026-08-15T12:00:00Z",
            },
            {
              id: "message-assistant",
              role: "assistant",
              content: "已准备好当前项目的任务编排。",
              runtime_run_id: "canvas-run",
              created_at: "2026-08-15T12:00:01Z",
            },
          ],
        }),
      });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "canvas-conversation",
          project_id: "project-1",
          title: "查看项目画布",
          is_pinned: false,
          created_at: "2026-08-15T12:00:00Z",
        },
      ]),
    });
  });
  await page.route("**/runtime/runs?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "canvas-run",
          kind: "assistant_turn",
          status: "completed",
          project_id: "project-1",
          project_name: "示例投标项目",
          engine: "harness",
          created_at: "2026-08-15T12:00:00Z",
          started_at: "2026-08-15T12:00:00Z",
          finished_at: "2026-08-15T12:00:01Z",
          latest_event_summary: "任务编排画布已准备好。",
        },
      ]),
    });
  });
  await page.route("**/runtime/runs/canvas-run/events?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            event_id: "canvas-action-event",
            run_id: "canvas-run",
            parent_event_id: null,
            sequence: 1,
            type: "capability.succeeded",
            public_summary: "任务编排画布已准备好。",
            payload: {
              capability: "open_page",
              turn_id: "canvas-turn",
              title: "打开任务编排画布",
              route: "/projects/project-1?surface=workflow",
              ui_action: {
                type: "canvas",
                label: "打开任务编排画布",
                route: "/projects/project-1?surface=workflow",
              },
            },
            schema_version: "1.0",
            timestamp: "2026-08-15T12:00:01Z",
          },
        ],
      }),
    });
  });
  await page.route("**/notifications", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });

  await page.goto("/agent?conversation=canvas-conversation&project_id=project-1");
  await expect(page.getByText("已准备好当前项目的任务编排。", { exact: true })).toBeVisible();
  // Replayed runtime traces render as a nested turn, so this transcript has
  // no outer collapsible activity group. Open the turn, then its real tool.
  await page.getByRole("button", { name: /Turn 1 Open page/ }).click();
  await page.getByRole("button", { name: /Show Open page details/i }).click();
  await page.getByRole("button", { name: "打开任务编排画布" }).click();

  await expect(page.getByRole("complementary", { name: "任务编排画布" })).toBeVisible();
  await expect(page.getByTestId("bidpilot-workflow-canvas")).toBeVisible();
  await expect(page.getByRole("button", { name: "关闭任务编排画布" })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath(`agent-workspace-${testInfo.project.name}-canvas.png`),
    fullPage: true,
  });
});
