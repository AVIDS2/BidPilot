import { expect, test, type Page } from "@playwright/test";

/**
 * Browser-level regression for the user-visible stop -> send race.
 * The stream is controlled at the browser fetch boundary so the test covers
 * the real React shell, composer, AbortController and queue projection.
 */
async function prepareAssistantPage(page: Page) {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_token", "browser-soft-test-token");
    localStorage.setItem("bidpilot_lang", "en");
    localStorage.setItem("theme", "light");

    const testWindow = window as Window & {
      __assistantBrowserTest?: {
        requestCount: number;
        release: (() => void) | null;
      };
    };
    testWindow.__assistantBrowserTest = { requestCount: 0, release: null };
    const nativeFetch = window.fetch.bind(window);
    const encoder = new TextEncoder();

    window.fetch = async (input, init) => {
      const requestUrl =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      if (!requestUrl.includes("/assistant/stream")) {
        return nativeFetch(input, init);
      }

      const testState = testWindow.__assistantBrowserTest!;
      testState.requestCount += 1;
      const requestNumber = testState.requestCount;
      const runId = requestNumber === 1 ? "browser-run-old" : "browser-run-next";
      let released = false;
      let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          streamController = controller;
          controller.enqueue(
            encoder.encode(
              `event: assistant.start\ndata: {"conversation_id":"browser-conversation","runtime_run_id":"${runId}","state":"thinking"}\n\n`,
            ),
          );
          const release = () => {
            if (released || !streamController) return;
            released = true;
            streamController.enqueue(
              encoder.encode(
                [
                  `event: assistant.message\ndata: {"runtime_run_id":"${runId}","content":"${requestNumber === 1 ? "旧请求已停止。" : "第二条消息已送达。"}","state":"completed"}`,
                  `event: assistant.end\ndata: {"conversation_id":"browser-conversation","runtime_run_id":"${runId}","state":"${requestNumber === 1 ? "cancelled" : "completed"}"}`,
                ].join("\n\n") + "\n\n",
              ),
            );
            streamController.close();
          };
          testState.release = release;
          window.addEventListener("browser-soft-test-release", release, { once: true });
          init?.signal?.addEventListener("abort", () => {
            if (!released && streamController) {
              released = true;
              streamController.error(new DOMException("Aborted", "AbortError"));
            }
          }, { once: true });
        },
      });
      return new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    };
  });

  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "browser-soft-user",
        email: "browser-soft@example.test",
        display_name: "Browser Soft Test",
        role: "admin",
        plan: "free",
        email_verified: true,
        org_id: "browser-soft-org",
        org_slug: "browser-soft-org",
      }),
    });
  });
  await page.route("**/auth/me/providers**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ data: [] }) });
  });
  await page.route("**/chat/conversations**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/projects**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/notifications**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/runtime/runs?**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/runtime/runs/browser-run-old/cancel", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 150));
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "browser-run-old",
        kind: "assistant_turn",
        status: "cancelled",
        project_id: null,
        conversation_id: "browser-conversation",
        execution_run_id: null,
        engine: "pi",
        trace_id: "browser-soft-trace",
        parent_run_id: null,
      }),
    });
  });
}

test.describe("assistant stop and retry", () => {
  test("delivers a message submitted immediately after stop", async ({ page }, testInfo) => {
    const transportLog: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("assistant/stream") || request.url().includes("runtime/runs")) {
        transportLog.push(`${request.method()} ${request.url()}`);
      }
    });
    page.on("response", (response) => {
      if (response.url().includes("assistant/stream") || response.url().includes("runtime/runs")) {
        transportLog.push(`${response.status()} ${response.url()}`);
      }
    });
    await prepareAssistantPage(page);
    await page.goto("/agent");

    const input = page.getByRole("textbox", { name: "Ask me anything..." });
    await expect(input).toBeVisible();
    await input.fill("第一条长任务");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.getByRole("button", { name: "Stop generating" })).toBeVisible();

    await page.getByRole("button", { name: "Stop generating" }).click();
    await input.fill("第二条消息");
    await input.press("Enter");

    await expect(page.getByText("第二条消息", { exact: true })).toBeVisible();
    try {
      await expect.poll(async () => page.evaluate(() => {
        return (window as Window & { __assistantBrowserTest?: { requestCount: number } })
          .__assistantBrowserTest?.requestCount ?? 0;
      })).toBe(2);
    } catch (error) {
      console.log(`assistant transport log: ${JSON.stringify(transportLog)}`);
      throw error;
    }

    await page.evaluate(() => window.dispatchEvent(new Event("browser-soft-test-release")));
    await expect(page.getByText("第二条消息已送达。", { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("Aborted");

    await page.screenshot({
      path: testInfo.outputPath(`assistant-stop-retry-${testInfo.project.name}.png`),
      fullPage: true,
    });
  });
});
