# BidPilot 整改 Sprint 追踪

## Sprint 1: LangGraph Graph Foundation ✅
**状态：** 完成
**时间：** 2026-06-07

### 产出文件
- `services/worker/app/graph/__init__.py`
- `services/worker/app/graph/state.py` — BidPilotState TypedDict
- `services/worker/app/graph/builder.py` — StateGraph 组装
- `services/worker/app/graph/nodes/__init__.py`
- `services/worker/app/graph/nodes/supervisor.py` — 确定性路由
- `services/worker/app/graph/nodes/rfp_parser.py` — RFP 解析
- `services/worker/app/graph/nodes/knowledge_retriever.py` — 知识检索
- `services/worker/app/graph/nodes/section_drafter.py` — 章节撰写
- `services/worker/app/graph/nodes/quality_reviewer.py` — 质量评审
- `services/worker/app/graph/nodes/persist_result.py` — 持久化
- `services/worker/app/tasks.py` — USE_LANGGRAPH feature flag
- `services/worker/pyproject.toml` — langgraph 依赖

### 验证
- ✅ USE_LANGGRAPH feature flag
- ✅ langgraph 依赖
- ✅ BidPilotState 15+ 字段
- ✅ StateGraph + 6 节点 + 条件边
- ✅ tenacity 重试
- ✅ quality reviewer

---

## Sprint 2: HITL + Streaming + Agent Status UI ✅
**状态：** 完成
**时间：** 2026-06-07

### 产出文件
- `services/worker/app/graph/nodes/human_approval.py` — interrupt/resume 节点
- `services/worker/app/graph/state.py` — 添加 human_decision, review_feedback
- `services/worker/app/graph/nodes/supervisor.py` — 添加 HITL 路由
- `services/worker/app/graph/builder.py` — PostgresSaver + interrupt_before + resume_graph()
- `services/worker/app/tasks.py` — resume_draft task
- `services/api/app/drafting/schemas.py` — ResumeRunRequest
- `services/api/app/drafting/router.py` — POST /resume + GET /stream
- `services/api/app/drafting/service.py` — resume_run_command()
- `services/api/app/drafting/streaming.py` — SSE streaming generator
- `services/api/pyproject.toml` — sse-starlette
- `apps/web/src/components/agent-progress.tsx` — Agent 进度可视化
- `apps/web/src/components/agent-status-stream.tsx` — SSE 客户端 hook
- `apps/web/src/features/projects/project-detail-page.tsx` — Agent tab

### 验证
- ✅ human_approval interrupt 节点（7 个 interrupt 引用）
- ✅ /resume API 端点
- ✅ PostgresSaver + resume_graph()
- ✅ SSE streaming 端点（12KB streaming.py）
- ✅ Agent progress 组件（7.7KB）
- ✅ Agent status stream hook（7.2KB）
- ✅ Agent tab 集成（12 个 agent 引用）

---

## Sprint 3: Dashboard + Command Palette + Notification + Landing ✅
**状态：** 完成
**时间：** 2026-06-07

### 产出文件
- `apps/web/src/features/dashboard/dashboard-page.tsx` — Dashboard 页面（403 行）
- `apps/web/src/components/command-palette.tsx` — Cmd+K 命令面板（177 行）
- `apps/web/src/hooks/use-command-palette.ts` — Cmd+K hook
- `apps/web/src/components/notification-bell.tsx` — 通知组件（134 行）
- `apps/web/src/hooks/use-notifications.ts` — 通知 hook
- `apps/web/src/features/landing/landing-page.tsx` — 首页重设计（248 行，taste-skill）
- `apps/web/src/app.tsx` — Dashboard route + CommandPalette 集成
- `apps/web/src/components/site-header.tsx` — NotificationBell 集成
- `apps/web/src/lib/i18n.ts` — dashboard namespace
- `apps/web/public/locales/en/dashboard.json` + `zh-CN/dashboard.json` — 翻译
- `apps/web/package.json` — cmdk 依赖

### 验证
- ✅ Dashboard 页面（stat cards + activity feed + quick actions）
- ✅ Cmd+K 全局触发（Navigation + Actions 搜索）
- ✅ Notification bell + dropdown + 30s 轮询
- ✅ Landing page 重设计（bento grid + left-aligned hero）

---

## Sprint 4: 测试 + 文档 + 报告 ✅
**状态：** 完成
**时间：** 2026-06-07

### 产出文件
- `services/worker/tests/test_graph_state.py` — State 字段验证
- `services/worker/tests/test_supervisor.py` — 路由测试
- `services/worker/tests/test_graph_integration.py` — 集成测试
- `docs/plans/overhaul-final-report.md` — 最终报告

### 文档
- `docs/architecture/langgraph-agent.md`
- `docs/architecture/frontend-overhaul.md`
- `docs/plans/bidpilot-overhaul.md`
- `docs/plans/sprint-tracking.md`
- `docs/plans/taste-preflight-check.md`
- `docs/plans/overhaul-final-report.md`

---

## Sprint 4: Testing + Cleanup ⏳
**状态：** 待开始

### 任务
- [ ] 节点单元测试
- [ ] 路由测试
- [ ] 集成测试
- [ ] API 测试
- [ ] 死代码清理
- [ ] taste-skill Pre-Flight Check
