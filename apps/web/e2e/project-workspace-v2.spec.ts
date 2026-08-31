import { expect, test, type Page } from "@playwright/test";

const projectId = "project-workspace-demo";

async function prepareProjectWorkspace(page: Page) {
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem("bidpilot_token", "project-workspace-visual-token");
    localStorage.setItem("bidpilot_lang", "zh-CN");
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
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ data: [] }) });
  });
  await page.route("**/notifications**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route(`**/projects/${projectId}`, async (route) => {
    if (route.request().resourceType() !== "fetch") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ id: projectId, name: "城市智慧交通平台投标", scenario_package: "bidpilot", status: "active" }),
    });
  });
  let bundleReingested = false;
  let bundleReindexed = false;
  await page.route("**/bundles**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{ id: "bundle-rfp", project_id: projectId, label: "招标文件与附件", source_type: "rfp", ingest_status: bundleReingested ? "parsed" : "failed" }]),
    });
  });
  await page.route(`**/bundles/${"bundle-rfp"}/reingest`, async (route) => {
    bundleReingested = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ id: "bundle-rfp", project_id: projectId, label: "招标文件与附件", source_type: "rfp", ingest_status: "queued" }),
    });
  });
  await page.route(`**/bundles/${"bundle-rfp"}/reindex`, async (route) => {
    bundleReindexed = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ id: "bundle-rfp", project_id: projectId, label: "招标文件与附件", source_type: "rfp", ingest_status: "parsed" }),
    });
  });
  await page.route("**/documents**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          { id: "document-rfp", bundle_id: "bundle-rfp", storage_key: "rfp.pdf", mime_type: "application/pdf", original_filename: "城市智慧交通平台招标文件.pdf", parse_status: "parsed", parse_attempt_count: 1, parser_name: "pdf", parser_version: "1", parse_error_code: null, parse_error_detail: null, parse_retryable: false, index_status: "indexed", index_error_code: null, version_number: 1, supersedes_document_id: null },
          { id: "document-appendix", bundle_id: "bundle-rfp", storage_key: "appendix.docx", mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", original_filename: "技术规范附件.docx", parse_status: bundleReingested ? "parsed" : "failed", parse_attempt_count: bundleReingested ? 2 : 1, parser_name: bundleReingested ? "docx" : null, parser_version: bundleReingested ? "1" : null, parse_error_code: bundleReingested ? null : "parser_timeout", parse_error_detail: bundleReingested ? null : "解析超时：附件未能在规定时间内完成文本提取。", parse_retryable: !bundleReingested, index_status: bundleReindexed ? "indexed" : "pending", index_error_code: null, version_number: 1, supersedes_document_id: null },
        ],
        total: 2,
        page: 1,
        page_size: 50,
        pages: 1,
      }),
    });
  });
  await page.route("**/parsed-assets**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{ id: "asset-rfp", source_document_id: "document-rfp", parser_name: "pdf", parser_version: "1", content_json: { text: "解析后的招标正文预览：\n第一章 项目概况\n第二章 技术要求" }, layout_json: null }]),
    });
  });
  await page.route("**/requirements**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        { id: "requirement-mandatory", project_id: projectId, section_key: "1", requirement_text: "提供项目经理近三年类似项目经验证明", original_text: null, source_document_id: "document-rfp", source_document_name: "城市智慧交通平台招标文件.pdf", source_locator_json: null, priority: "high", status: "draft", owner_user_id: null, reviewer_user_id: null, due_at: null, verification_status: "pending", extraction_confidence: 0.94, lock_version: 1, updated_at: "2026-08-07T00:00:00Z", bid_profile: null },
        { id: "requirement-evidence", project_id: projectId, section_key: "2", requirement_text: "说明平台高峰期并发能力及对应测试依据", original_text: null, source_document_id: "document-rfp", source_document_name: "城市智慧交通平台招标文件.pdf", source_locator_json: null, priority: "high", status: "active", owner_user_id: "visual-user", reviewer_user_id: null, due_at: null, verification_status: "pending", extraction_confidence: 0.91, lock_version: 1, updated_at: "2026-08-07T00:00:00Z", bid_profile: null },
        { id: "requirement-covered", project_id: projectId, section_key: "3", requirement_text: "提交项目实施计划与风险管理方案", original_text: null, source_document_id: "document-rfp", source_document_name: "城市智慧交通平台招标文件.pdf", source_locator_json: null, priority: "medium", status: "active", owner_user_id: "visual-user", reviewer_user_id: "visual-user", due_at: null, verification_status: "verified", extraction_confidence: 0.88, lock_version: 1, updated_at: "2026-08-07T00:00:00Z", bid_profile: null },
      ]),
    });
  });
  let requirementVerified = false;
  let evidenceVerified = false;
  let claimVerified = false;
  await page.route(`**/requirements/requirement-evidence`, async (route) => {
    const detail = {
      id: "requirement-evidence",
      project_id: projectId,
      section_key: "2",
      requirement_text: "说明平台高峰期并发能力及对应测试依据",
      original_text: "投标人应说明平台高峰期并发能力，并提供相应测试依据。",
      source_document_id: "document-rfp",
      source_document_name: "城市智慧交通平台招标文件.pdf",
      source_locator_json: { page: 18, section: "3.2.1" },
      priority: "high",
      status: "active",
      owner_user_id: "visual-user",
      reviewer_user_id: null,
      due_at: null,
      verification_status: requirementVerified ? "verified" : "pending",
      extraction_confidence: 0.91,
      lock_version: requirementVerified ? 2 : 1,
      updated_at: "2026-08-07T00:00:00Z",
      bid_profile: {
        id: "profile-evidence",
        requirement_id: "requirement-evidence",
        bid_category: "technical",
        is_mandatory: false,
        score_weight: 15,
        risk_level: "high",
        coverage_status: "partial",
        evidence_status: evidenceVerified ? "verified" : "missing",
        deadline_at: null,
        submission_metadata_json: null,
        updated_at: "2026-08-07T00:00:00Z",
      },
      evidence_links: [{
        id: "evidence-link-1",
        requirement_id: "requirement-evidence",
        evidence_id: "evidence-1",
        relation_type: "supports",
        verification_status: evidenceVerified ? "verified" : "pending",
        quote_text: "投标人应说明平台高峰期并发能力，并提供相应测试依据。",
        source_document_id: "document-rfp",
        source_document_name: "城市智慧交通平台招标文件.pdf",
        locator_json: { page: 18, section: "3.2.1" },
        confidence: 0.95,
        created_at: "2026-08-07T00:00:00Z",
      }],
      claims: [{
        id: "claim-1",
        project_id: projectId,
        requirement_id: "requirement-evidence",
        claim_text: "平台支持高峰期 10,000 并发请求。",
        claim_type: "factual",
        status: claimVerified ? "verified" : "draft",
        coverage_role: "direct",
        section_version_id: null,
        generation_run_id: null,
        created_by_actor: "ai",
        created_by_user_id: null,
        evidence_ids: ["evidence-1"],
        created_at: "2026-08-07T00:00:00Z",
        updated_at: "2026-08-07T00:00:00Z",
      }],
      decisions: [],
    };
    if (route.request().method() === "PATCH") {
      requirementVerified = true;
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(detail) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(detail) });
  });
  await page.route(`**/requirements/requirement-evidence/evidence/evidence-link-1`, async (route) => {
    evidenceVerified = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ id: "evidence-link-1", requirement_id: "requirement-evidence", evidence_id: "evidence-1", relation_type: "supports", verification_status: "verified", quote_text: "投标人应说明平台高峰期并发能力，并提供相应测试依据。", source_document_id: "document-rfp", source_document_name: "城市智慧交通平台招标文件.pdf", locator_json: { page: 18, section: "3.2.1" }, confidence: 0.95, created_at: "2026-08-07T00:00:00Z" }),
    });
  });
  await page.route(`**/requirements/requirement-evidence/claims/claim-1/verify`, async (route) => {
    claimVerified = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ id: "claim-1", project_id: projectId, requirement_id: "requirement-evidence", claim_text: "平台支持高峰期 10,000 并发请求。", claim_type: "factual", status: "verified", coverage_role: "direct", section_version_id: null, generation_run_id: null, created_by_actor: "ai", created_by_user_id: null, evidence_ids: ["evidence-1"], created_at: "2026-08-07T00:00:00Z", updated_at: "2026-08-07T00:00:00Z" }),
    });
  });
  await page.route(`**/readiness/projects/${projectId}`, async (route) => {
    const mandatoryGap = { id: "requirement-mandatory", section_key: "1", requirement_text: "提供项目经理近三年类似项目经验证明", bid_category: "qualification", is_mandatory: true, score_weight: 20, risk_level: "high", coverage_status: "uncovered", evidence_status: "missing", verification_status: "pending", owner_user_id: null, reviewer_user_id: null, due_at: null, source_locator_json: null };
    const evidenceGap = { id: "requirement-evidence", section_key: "2", requirement_text: "说明平台高峰期并发能力及对应测试依据", bid_category: "technical", is_mandatory: false, score_weight: 15, risk_level: "high", coverage_status: "partial", evidence_status: "missing", verification_status: "pending", owner_user_id: "visual-user", reviewer_user_id: null, due_at: null, source_locator_json: null };
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        formula_version: "v1", project_id: projectId, project_name: "城市智慧交通平台投标", generated_at: "2026-08-07T00:00:00Z", source_fingerprint: "visual", score_label: "需要补齐", readiness_score: 46,
        counts: { total: 3, mandatory: 1, scored: 2, covered: 1, partial: 1, uncovered: 1, disputed: 0, not_applicable: 0, accepted_risk: 0, verified: 1, assigned: 2 },
        scores: { mandatory_closure: 0, scored_coverage: 0.5, verification: 0.33, assignment: 0.67 },
        requirements: [mandatoryGap, evidenceGap], mandatory_gaps: [mandatoryGap], evidence_gaps: [evidenceGap], contradictions: [], overdue: [], qualifications: [], workload: { unassigned: 1, by_owner: { "visual-user": 2 } },
      }),
    });
  });
  await page.route("**/evidence**", async (route) => {
    if (route.request().url().includes("/requirements/")) {
      await route.fallback();
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: "evidence-1", project_id: projectId, source_document_id: "document-rfp", quote_text: "项目实施计划与风险管理方案应作为响应附件提交。", confidence: 0.95 }]) });
  });
  await page.route("**/deliverables**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/execution/runs**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{
        id: "execution-run-1",
        project_id: projectId,
        run_type: "draft_section",
        status: "succeeded",
        parent_execution_run_id: null,
        attempt_number: 1,
        runtime_run_id: "runtime-run-1",
        input_json: { section_key: "technical-approach" },
        output_json: { section_version_id: "version-1" },
      }]),
    });
  });
  await page.route("**/runtime/runs/runtime-run-1/events**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ items: [
        { event_id: "event-1", run_id: "runtime-run-1", parent_event_id: null, sequence: 1, type: "capability.succeeded", public_summary: "已识别 3 条招标需求。", payload: { node: "rfp_parser", capability: "rfp_parser", requirement_count: 3 }, schema_version: "1.2", timestamp: "2026-08-07T10:00:00Z" },
        { event_id: "event-2", run_id: "runtime-run-1", parent_event_id: null, sequence: 2, type: "capability.succeeded", public_summary: "已检索到 4 条相关证据。", payload: { node: "knowledge_retriever", capability: "knowledge_retriever", evidence_count: 4 }, schema_version: "1.2", timestamp: "2026-08-07T10:01:00Z" },
        { event_id: "event-3", run_id: "runtime-run-1", parent_event_id: null, sequence: 3, type: "capability.succeeded", public_summary: "内容计划已生成：4 个要点，1 个表格建议。", payload: { node: "content_plan", capability: "content_plan" }, schema_version: "1.2", timestamp: "2026-08-07T10:02:00Z" },
        { event_id: "event-4", run_id: "runtime-run-1", parent_event_id: null, sequence: 4, type: "capability.succeeded", public_summary: "章节草稿已生成。", payload: { node: "section_drafter", capability: "section_drafter" }, schema_version: "1.2", timestamp: "2026-08-07T10:03:00Z" },
        { event_id: "event-5", run_id: "runtime-run-1", parent_event_id: null, sequence: 5, type: "capability.succeeded", public_summary: "质量审核已通过。", payload: { node: "quality_reviewer", capability: "quality_reviewer", passed: true }, schema_version: "1.2", timestamp: "2026-08-07T10:04:00Z" },
        { event_id: "event-6", run_id: "runtime-run-1", parent_event_id: null, sequence: 6, type: "approval.resolved", public_summary: "人工审核已处理。", payload: { node: "human_approval", capability: "human_approval", decision: "approve" }, schema_version: "1.2", timestamp: "2026-08-07T10:05:00Z" },
        { event_id: "event-7", run_id: "runtime-run-1", parent_event_id: null, sequence: 7, type: "capability.succeeded", public_summary: "草稿和证据已保存。", payload: { node: "persist_result", capability: "persist_result" }, schema_version: "1.2", timestamp: "2026-08-07T10:06:00Z" },
      ] }),
    });
  });
  await page.route("**/response-plans**", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
  });
}

test("项目工作台展示真实就绪度并将缺口带入要求矩阵", async ({ page }, testInfo) => {
  await prepareProjectWorkspace(page);
  await page.goto(`/projects/${projectId}`);

  await expect(page.getByRole("heading", { name: "城市智慧交通平台投标" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "投标就绪度" })).toBeVisible();
  await expect(page.getByText("补齐强制项缺口", { exact: true })).toBeVisible();
  await expect(page.getByText("说明平台高峰期并发能力及对应测试依据", { exact: true })).not.toBeVisible();

  if (testInfo.project.name === "chromium") {
    const collapseButton = page.getByRole("button", { name: "收起侧栏" });
    await expect(collapseButton).toBeVisible();
    await collapseButton.click();
    await expect(page.locator(".workbench.is-sidebar-collapsed .wb-workspace-actions")).toBeHidden();
    const logoButton = page.getByRole("button", { name: "展开侧栏" });
    await expect(logoButton).toHaveCount(1);
    await expect(logoButton.locator(".wb-workspace-mark")).toBeVisible();
    await logoButton.click();
    await expect(page.getByRole("button", { name: "收起侧栏" })).toBeVisible();
  }
  await page.screenshot({ path: testInfo.outputPath(`project-workspace-${testInfo.project.name}.png`), fullPage: true });

  await page.getByRole("button", { name: /补齐强制项缺口/ }).click();
  await expect(page.getByRole("heading", { name: "要求与合规" })).toBeVisible();
  await expect(page.getByText("提供项目经理近三年类似项目经验证明", { exact: true })).toBeVisible();
  await expect(page.getByText("说明平台高峰期并发能力及对应测试依据", { exact: true })).not.toBeVisible();

  await page.getByRole("tab", { name: /证据缺口/ }).click();
  await expect(page.getByText("说明平台高峰期并发能力及对应测试依据", { exact: true })).toBeVisible();
  await page.getByText("说明平台高峰期并发能力及对应测试依据", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "要求详情" })).toBeVisible();
  await expect(page.locator("blockquote").filter({ hasText: "投标人应说明平台高峰期并发能力，并提供相应测试依据。" })).toBeVisible();
  await expect(page.locator(".wb-requirement-inspector__section").first().getByText("第18页 · 章节 3.2.1", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "确认要求已核验" }).click();
  await expect(page.getByText("要求已更新", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "核验证据" }).click();
  await expect(page.getByText("证据已核验", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "核验主张" }).click();
  await expect(page.getByText("响应主张已核验", { exact: true })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "要求详情" })).not.toBeVisible();
  await page.getByRole("button", { name: "资料", exact: true }).click();
  await expect(page.getByRole("heading", { name: "资料", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "处理健康" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath(`project-materials-${testInfo.project.name}.png`), fullPage: true });
  await expect(page.getByRole("button", { name: "重新解析" })).toBeVisible();
  await page.getByRole("button", { name: "重新解析" }).click();
  await expect(page.getByText("资料包已重新进入解析队列", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "重建索引" })).toBeVisible();
  await page.getByRole("button", { name: "重建索引" }).click();
  await expect(page.getByText("资料包已重新进入索引队列", { exact: true })).toBeVisible();
  await page.getByText("城市智慧交通平台招标文件.pdf", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "文档详情" })).toBeVisible();
  await expect(page.locator(".wb-document-inspector")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(page.getByRole("heading", { name: "解析预览" })).toBeVisible();
  await expect(page.getByText("解析后的招标正文预览", { exact: false })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath(`project-document-sheet-${testInfo.project.name}.png`), fullPage: true });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "概览" }).click();
  await page.getByRole("button", { name: "响应工作流" }).click();
  await expect(page.getByRole("heading", { name: "响应工作流" })).toBeVisible();
  await expect(page.getByText("章节 technical-approach", { exact: true })).toBeVisible();
  await expect(page.getByLabel("响应阶段").getByText("资料解析", { exact: true })).toBeVisible();
  await expect(page.getByLabel("响应阶段").getByText("已识别 3 条招标需求。", { exact: true })).toBeVisible();
  await expect(page.getByText("阶段完成度", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "概览", exact: true }).click();
  await page.getByRole("button", { name: "上传资料" }).first().click();
  await expect(page.getByRole("heading", { name: "上传项目资料" })).toBeVisible();
});
