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
