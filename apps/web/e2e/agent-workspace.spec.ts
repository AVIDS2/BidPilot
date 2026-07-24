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
        role: "member",
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

  const conversationPane = page.getByTestId("assistant-conversation-pane");
  const composer = page.getByTestId("assistant-composer");
  const textarea = page.getByRole("textbox", { name: "Ask me anything..." });
  const sendButton = page.getByRole("button", { name: "Send" });
  await expect(conversationPane).toBeVisible();
  await expect(composer).toBeVisible();
  await expect(textarea).toBeVisible();
  await expect(sendButton).toBeVisible();

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

  if (testInfo.project.name === "mobile-chromium") {
    await expect(page.getByTestId("assistant-history-rail")).toBeHidden();
    await page.getByTestId("assistant-history-toggle").click();
    await expect(page.getByTestId("assistant-history-drawer")).toBeVisible();
  } else {
    await expect(page.getByTestId("assistant-history-rail")).toBeVisible();
  }

  await page.screenshot({
    path: testInfo.outputPath(`agent-workspace-${testInfo.project.name}.png`),
    fullPage: true,
  });
});
