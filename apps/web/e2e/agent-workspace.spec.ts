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
    if (route.request().url().includes("/messages")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ total: 0, items: [] }),
      });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        { id: "visual-project-chat", project_id: "visual-project", title: "常州机会筛选", is_pinned: false, created_at: "2026-08-25T12:00:00Z" },
        { id: "visual-personal-chat", project_id: null, title: "临时问题", is_pinned: false, created_at: "2026-08-25T11:00:00Z" },
      ]),
    });
  });
  await page.route("**/projects", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "visual-project",
          slug: "visual-project",
          name: "常州招标响应",
          scenario_package: "招标响应",
          status: "active",
        },
      ]),
    });
  });
  await page.route("**/notifications", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
  await page.route("**/auth/me/providers/runtime", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        data: {
          version: "1",
          sandbox: {
            profile: "governed_cloud",
            hostTools: "disabled",
            network: "bridge_only",
            maxToolInputBytes: 131072,
            maxToolObservationBytes: 524288,
          },
          extensions: ["bidpilot-governance", "bidpilot-skills", "bidpilot-subagents"],
          skills: [{ name: "deep-research", description: "Research", version: "1.1.0", resources: ["references/source-quality.md"] }],
          tool_count: 44,
          parallel_tool_count: 21,
          mcp_servers: [],
        },
      }),
    });
  });
  await page.route("**/runtime/runs?**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
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
    await expect(page.locator(".agent-environment-panel")).toBeVisible();
    await expect(page.getByText("工作概览", { exact: true })).toBeVisible();
    await expect(page.getByText("项目工作区", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Chat history" }).click();
    await expect(page.locator(".bp-linear-history").getByText("常州招标响应", { exact: true })).toBeVisible();
    await expect(page.locator(".bp-linear-history").getByText("个人会话", { exact: true })).toBeVisible();
    await page.locator(".bp-linear-history").getByRole("button", { name: "会话操作" }).first().click();
    await expect(page.getByRole("menuitem", { name: "置顶会话" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "重命名会话" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "删除会话" })).toBeVisible();
    await page.keyboard.press("Escape");

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
  // Replay is a flat execution timeline: open the actual turn, then its tool.
  await page.getByRole("button", { name: /^Open page/ }).click();
  await page.getByRole("button", { name: /Show Open page details/i }).click();
  await page.getByRole("button", { name: "打开任务编排画布" }).click();

  if (testInfo.project.name === "mobile-chromium") {
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("heading", { name: "响应工作流" })).toBeVisible();
  } else {
    await expect(page.getByRole("complementary", { name: "任务编排画布" })).toBeVisible();
    await expect(page.getByRole("button", { name: "关闭任务编排画布" })).toBeVisible();
  }
  await expect(page.getByTestId("bidpilot-workflow-canvas")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath(`agent-workspace-${testInfo.project.name}-canvas.png`),
    fullPage: true,
  });
});

test("restores parallel subagents as a paged execution view", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_token", "visual-test-token");
    localStorage.setItem("bidpilot_lang", "zh");
    localStorage.setItem("theme", "light");
    localStorage.setItem("bidpilot_last_assistant_conversation_id", "subagent-conversation");
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
  await page.route("**/notifications", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/chat/conversations**", async (route) => {
    if (route.request().url().includes("/subagent-conversation/messages")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          total: 2,
          items: [
            {
              id: "subagent-user-message",
              role: "user",
              content: "并行核验三个公开来源",
              created_at: "2026-08-19T06:00:00Z",
            },
            {
              id: "subagent-assistant-message",
              role: "assistant",
              content: "三个核验任务已经汇总。",
              runtime_run_id: "parent-run",
              created_at: "2026-08-19T06:00:01Z",
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
          id: "subagent-conversation",
          project_id: null,
          title: "并行来源核验",
          is_pinned: false,
          created_at: "2026-08-19T06:00:00Z",
        },
      ]),
    });
  });
  await page.route("**/runtime/runs/parent-run/children?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(["researcher", "reviewer", "analyst"].map((profile, index) => ({
        id: `child-${index + 1}`,
        parent_run_id: "parent-run",
        kind: "assistant_subagent",
        status: "completed",
        profile,
        mode: "read_only",
        created_at: `2026-08-19T06:00:0${index + 2}Z`,
        started_at: `2026-08-19T06:00:0${index + 2}Z`,
        finished_at: `2026-08-19T06:00:0${index + 3}Z`,
        latest_event_summary: `${profile} 已完成核验。`,
      }))),
    });
  });
  await page.route("**/runtime/runs/parent-run/events?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            event_id: "parent-start",
            run_id: "parent-run",
            sequence: 1,
            type: "capability.started",
            public_summary: "正在委派三项独立核验。",
            payload: {
              capability: "spawn_subagents",
              tool_call_id: "spawn-call",
              turn_id: "parent-turn",
              title: "并行核验公开来源",
            },
            schema_version: "1.0",
            timestamp: "2026-08-19T06:00:01Z",
          },
          {
            event_id: "parent-complete",
            run_id: "parent-run",
            sequence: 2,
            type: "capability.succeeded",
            public_summary: "三个子 Agent 已完成核验。",
            payload: {
              capability: "spawn_subagents",
              tool_call_id: "spawn-call",
              turn_id: "parent-turn",
              title: "并行核验公开来源",
            },
            schema_version: "1.0",
            timestamp: "2026-08-19T06:00:05Z",
          },
          {
            event_id: "parent-run-complete",
            run_id: "parent-run",
            sequence: 3,
            type: "run.completed",
            public_summary: "并行核验完成。",
            payload: {},
            schema_version: "1.0",
            timestamp: "2026-08-19T06:00:06Z",
          },
        ],
      }),
    });
  });
  await page.route("**/runtime/runs/child-*/events?**", async (route) => {
    const pathParts = new URL(route.request().url()).pathname.split("/");
    const childId = pathParts[pathParts.length - 2] ?? "child-1";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            event_id: `${childId}-tool-start`,
            run_id: childId,
            sequence: 1,
            type: "capability.started",
            public_summary: "正在核验公开来源。",
            payload: {
              capability: "web_search",
              tool_call_id: `${childId}-search`,
              turn_id: `${childId}-turn`,
              title: "核验公开来源",
            },
            schema_version: "1.0",
            timestamp: "2026-08-19T06:00:03Z",
          },
          {
            event_id: `${childId}-tool-complete`,
            run_id: childId,
            sequence: 2,
            type: "capability.succeeded",
            public_summary: "公开来源核验完成。",
            payload: {
              capability: "web_search",
              tool_call_id: `${childId}-search`,
              turn_id: `${childId}-turn`,
              title: "核验公开来源",
            },
            schema_version: "1.0",
            timestamp: "2026-08-19T06:00:04Z",
          },
          {
            event_id: `${childId}-complete`,
            run_id: childId,
            sequence: 3,
            type: "run.completed",
            public_summary: "子 Agent 已完成核验。",
            payload: {},
            schema_version: "1.0",
            timestamp: "2026-08-19T06:00:05Z",
          },
        ],
      }),
    });
  });
  await page.route("**/runtime/runs?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "parent-run",
          kind: "assistant_turn",
          status: "completed",
          project_id: null,
          project_name: null,
          engine: "pi",
          created_at: "2026-08-19T06:00:01Z",
          started_at: "2026-08-19T06:00:01Z",
          finished_at: "2026-08-19T06:00:06Z",
          latest_event_summary: "并行核验完成。",
        },
      ]),
    });
  });

  await page.goto("/agent?conversation=subagent-conversation");
  await expect(page.getByText("三个核验任务已经汇总。", { exact: true })).toBeVisible();

  const parentGroup = page.locator(".cr-task-turn").first();
  await expect(parentGroup.locator(":scope > .cr-command-grid")).not.toHaveClass(/is-open/);
  await parentGroup.locator(":scope > .cr-task-turn-summary").click();

  const viewer = page.getByRole("region", { name: "子 Agent 执行记录" });
  await expect(viewer).toBeVisible();
  await expect(viewer.getByText("1 / 3", { exact: true })).toBeVisible();
  await expect(viewer.getByText("researcher 子 Agent", { exact: true }).first()).toBeVisible();
  await expect(viewer.getByText("reviewer 子 Agent", { exact: true })).toHaveCount(0);

  await viewer.getByRole("button", { name: "查看下一个子 Agent" }).click();
  await expect(viewer.getByText("2 / 3", { exact: true })).toBeVisible();
  await expect(viewer.getByText("reviewer 子 Agent", { exact: true }).first()).toBeVisible();

  const viewerBox = await viewer.boundingBox();
  expect(viewerBox).not.toBeNull();
  expect(viewerBox!.x).toBeGreaterThanOrEqual(0);
  expect(viewerBox!.x + viewerBox!.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);

  await page.screenshot({
    path: testInfo.outputPath(`agent-workspace-${testInfo.project.name}-subagents.png`),
    fullPage: true,
  });
});

test("projects deep research as one specialized runtime", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_token", "visual-test-token");
    localStorage.setItem("bidpilot_lang", "zh");
    localStorage.setItem("theme", "light");
    localStorage.setItem("bidpilot_last_assistant_conversation_id", "research-conversation");
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
  await page.route("**/notifications", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/chat/conversations**", async (route) => {
    if (route.request().url().includes("/research-conversation/messages")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          total: 2,
          items: [
            {
              id: "research-user-message",
              role: "user",
              content: "调研常州近期的医疗信息化招标机会",
              created_at: "2026-08-19T07:00:00Z",
            },
            {
              id: "research-assistant-message",
              role: "assistant",
              content: "已完成候选机会筛选，并保留可追溯来源。",
              runtime_run_id: "research-run",
              created_at: "2026-08-19T07:00:05Z",
            },
          ],
        }),
      });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{
        id: "research-conversation",
        project_id: null,
        title: "常州招标机会调研",
        is_pinned: false,
        created_at: "2026-08-19T07:00:00Z",
      }]),
    });
  });
  await page.route("**/runtime/runs/research-run/children?**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/runtime/runs/research-run/events?**", async (route) => {
    const presentation = {
      presentation_kind: "deep_research",
      presentation_session_id: "research-session",
      presentation_title: "招标机会深度调研",
    };
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            event_id: "research-start",
            run_id: "research-run",
            sequence: 1,
            type: "plan.updated",
            public_summary: "正在核对公开来源。",
            payload: {
              stage: "task_started",
              title: "招标机会深度调研",
              skill_name: "opportunity-deep-research",
              ...presentation,
            },
            schema_version: "1.0",
            timestamp: "2026-08-19T07:00:01Z",
          },
          ...[1, 2, 3].flatMap((index) => ([
            {
              event_id: `search-${index}-start`,
              run_id: "research-run",
              sequence: index * 2,
              type: "capability.started",
              public_summary: "正在核对公开来源。",
              payload: {
                capability: "web_search",
                tool_call_id: `search-${index}`,
                title: "联网搜索",
                ...presentation,
              },
              schema_version: "1.0",
              timestamp: `2026-08-19T07:00:0${index + 1}Z`,
            },
            {
              event_id: `search-${index}-complete`,
              run_id: "research-run",
              sequence: index * 2 + 1,
              type: "capability.succeeded",
              public_summary: "公开来源核对完成。",
              payload: {
                capability: "web_search",
                tool_call_id: `search-${index}`,
                title: "联网搜索",
                items: [{
                  title: `公开来源 ${index}`,
                  url: `https://example.test/source-${index}`,
                  snippet: "可追溯的公开公告摘要。",
                }],
                ...presentation,
              },
              schema_version: "1.0",
              timestamp: `2026-08-19T07:00:0${index + 2}Z`,
            },
          ])),
          {
            event_id: "research-complete",
            run_id: "research-run",
            sequence: 8,
            type: "run.completed",
            public_summary: "候选机会调研完成。",
            payload: {},
            schema_version: "1.0",
            timestamp: "2026-08-19T07:00:06Z",
          },
        ],
      }),
    });
  });
  await page.route("**/runtime/runs?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{
        id: "research-run",
        kind: "assistant_turn",
        status: "completed",
        project_id: null,
        project_name: null,
        engine: "pi",
        created_at: "2026-08-19T07:00:01Z",
        started_at: "2026-08-19T07:00:01Z",
        finished_at: "2026-08-19T07:00:06Z",
        latest_event_summary: "候选机会调研完成。",
      }]),
    });
  });

  await page.goto("/agent?conversation=research-conversation");
  await expect(page.getByText("已完成候选机会筛选，并保留可追溯来源。", { exact: true })).toBeVisible();
  await expect(page.getByText("招标机会深度调研", { exact: true })).toHaveCount(1);

  const parentGroup = page.locator(".cr-task-turn").first();
  await parentGroup.locator(":scope > .cr-task-turn-summary").click();
  await expect(page.getByLabel("深度调研运行状态")).toBeVisible();
  await expect(parentGroup.locator(".cr-deep-research-process > summary")).toContainText("查看调研过程");
  await expect(page.getByText("3 个来源", { exact: true })).toBeVisible();
  await expect(parentGroup.locator(".cr-tool-step")).toHaveCount(0);

  await page.screenshot({
    path: testInfo.outputPath(`agent-workspace-${testInfo.project.name}-deep-research.png`),
    fullPage: true,
  });
});
