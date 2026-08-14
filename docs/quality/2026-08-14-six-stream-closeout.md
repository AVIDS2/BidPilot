# BidPilot 六项收口验收（2026-08-14）

这份记录把“功能已经能被用户看见”和“仍需要真实部署条件”分开，避免把代码存在误报成生产可用。

## 六项任务矩阵

| 任务 | 本轮交付 | 验证方式 | 状态 |
| --- | --- | --- | --- |
| 1. 部署、配置、演示数据 | OpenCode Go 配置、生产 readiness gate、可重复 seed；已向 `leho@bidpilot.local` 注入 3 个演示项目、资料/要求/证据、运行记录和 9 条雷达信号 | seed 幂等执行；Compose 配置；迁移到 head | 已完成本地收口 |
| 2. 招标雷达与资料 | 雷达来源/订阅/轮询/入库/转项目；远程材料受 SSRF、超时、大小、HTML 和 403 保护；本地 companion 支持用户选目录下载并回传校验 | 雷达 API/前端；远程导入测试；403 现场样例 | 已完成产品链路，受外站权限约束 |
| 3. Trace、运行、评估 | RuntimeRun/Event/Trace、节点状态、人工审批、取消/恢复、Harness 和 LangGraph golden path 证据 | OpenCode golden 10/10；Harness 27 事件/2 工具；API/Worker/Web 回归 | 已完成 |
| 4. 通知、协作、Webhook | Account > 通知偏好；审核通知按渠道/业务分类；业务 Webhook HMAC、重试、退避、租约；项目概览展示成员、待分配、逾期、待确认、活跃工作流 | API 通知测试 8/8；Web build/lint；Webhook 现有测试 | 已完成核心；Resend 最终回执待公开回调 |
| 5. Agent 体验与异常态 | 当前项目 Agent 入口、运行状态、事件时间线、失败原因、审批暂停；UI 使用中文层级和可追溯状态，不把错误伪装成成功 | 浏览器 Harness 运行证据；失败/重试测试 | 已完成核心验收 |
| 6. 开源交付 | README、部署 runbook、研究/架构/限制文档、local companion、确定性评估工件 | `git diff --check`、构建、测试、readiness 文档 | 已完成文档与本地交付 |

## 真实用户黄金链路

```text
雷达发现机会
  -> 建立项目
  -> 上传本地资料或确认远程附件
  -> 解析 / 建索引
  -> 要求矩阵与证据
  -> LangGraph 响应工作流
  -> 人工审批 / 退回返工
  -> 章节审核
  -> DOCX/PDF 交付
```

每一步都有 PostgreSQL 业务事实和 RuntimeEvent；浏览器刷新或 Agent 连接中断不会让任务只存在于上下文。

## 远程下载的边界

服务器不是用户的浏览器。对公开、无需登录的 HTTP(S) 二进制附件，服务端可以用 bounded streaming 下载并入 MinIO；对政府采购站点的 403、会话 Cookie、验证码、浏览器挑战，服务端不应不断 curl 猜 URL。此时使用 `bidpilot-local-companion` 在用户自己的网络和权限下下载到选定目录，随后通过资料页上传，服务器只负责校验、持久化和解析。

因此，现场 URL 返回 403 时显示“远程站点拒绝访问，请使用本地 companion 或手动上传”是正确的安全失败，不是下载网页的替代方案。

## 尚未宣称生产完成的条件

- 没有执行真实 VPS 发布、密钥轮换、备份恢复演练或外部站点授权；这些需要部署窗口和运维凭据。
- Resend 的 delivered/bounced/complained 最终状态需要公开 HTTPS webhook、签名校验、事件幂等和保留策略；当前只保证业务动作提交后通知 best-effort，不阻塞业务事实。
- 质量数字仍是合成评估集和本地 golden path 证据，不能外推成“97% 准确率”或“90% 交付率”。

## 最终本地验收记录

2026-08-14 的最终回归以**串行**方式运行，避免 API 与 Worker 的测试清理同一个
`docpilot_test` 数据库而制造并发假失败：

| 检查 | 结果 |
| --- | --- |
| API 全量测试 | `889 passed`（25 条 SQLAlchemy 测试清理警告，无失败） |
| Worker 全量测试 | `190 passed` |
| Web Vitest | `34 files passed`, `139 tests passed` |
| Web lint | 0 error；5 条既有 Hook dependency warning |
| Web production build | 通过；`AIAssistantPanel` 压缩后约 561 KB，列为后续代码拆分优化项 |
| Compose 配置 | `docker compose -f docker-compose.production.yml config --quiet` 通过（仅空 Turnstile site key 提示） |
| 真实浏览器冒烟 | Vite `http://127.0.0.1:5175` 首页和 `/agent` 返回 200；Chromium 快照渲染正常、控制台 0 error |

浏览器快照保存在本地 `.playwright-cli/`，不纳入版本库；此前的认证态关键页面截图仍保留在
`output/playwright/` 作为验收工件。

## 复验命令

```powershell
$env:DOCPILOT_DATABASE_URL='postgresql+psycopg://.../docpilot_test'
$env:DOCPILOT_TEST_DATABASE_URL=$env:DOCPILOT_DATABASE_URL
uv run --directory services/api alembic upgrade head
uv run --directory services/api pytest -q
pnpm --dir apps/web run lint
pnpm --dir apps/web run build
python scripts/production_readiness.py --target production
```
