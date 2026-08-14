# BidPilot 核心业务收口与验收报告

日期：2026-08-12  
范围：核心招标业务闭环、Pi 式 Harness、LangGraph 长任务、资料入库、人工审批、交付导出、招标雷达、Webhook 与浏览器可用性。

## 结论

核心交付黄金链路已在本地真实 API、Worker、PostgreSQL、Redis、对象存储、DeepSeek 模型配置和浏览器中跑通：**发现/创建项目 -> 上传并解析资料 -> Agent 查询 -> 创建交付物与章节 -> LangGraph 起草 -> 人工审核 -> DOCX 导出 -> 失败任务重试**。

这不等于“任何第三方网站附件都一定能下载”或“Agent 已拥有无限制本机 Shell 权限”。前者受远端站点的登录、反爬、协议与可用性影响；后者不应由 SaaS 后端替用户执行。系统对这两种边界均有明确、可恢复的状态与错误，而不是把网页误当附件后反复失败。

## 本轮实际验证

| 验收面 | 结果 | 证据 |
| --- | --- | --- |
| API + Worker 黄金链路 | 通过，10/10 | `artifacts/evaluations/bidpilot-golden-20260812/golden-path-closeout-20260812-164447.json` |
| 隔离账号浏览器注册 | 通过 | Playwright `live-product-chain.spec.ts`，2026-08-12 |
| 浏览器真实手动链路 | 通过，约 83 秒 | 创建项目、上传 TXT、等待解析/索引、向当前项目 Agent 查询、创建交付物/章节、起草、人工批准、DOCX 下载 |
| API 全量测试 | 877 passed | `services/api/tests` |
| Worker 全量测试 | 186 passed | `services/worker/tests` |
| Web 单元测试 | 139 passed / 34 files | `apps/web` Vitest |
| Web 构建 | 通过 | `pnpm build`，Vite 7.3.2 |
| 浏览器回归 | 28 passed，24 env-gated skipped | 桌面与移动：Agent、项目工作台、资料异常恢复、工作流图、雷达、设置/账户入口 |
| Harness 合同评估 | 19/19，100/100 | `services/api/artifacts/evaluations/harness-20260810-closeout/report.md` |
| 真实模型 Harness 评估 | 通过 | `services/api/artifacts/evaluations/live-harness/live-harness-eval-ec43ddf435.md`，DeepSeek + 1536 维向量 |

黄金链路产物中已验证：3 份资料真实解析和索引、32 条买方需求、候选稿拒绝后重起草、批准后仅导出已批准版本、受控失败运行经公开 API 与 Worker 重试成功。

## Agent 与长任务

### Harness

`services/api/app/runtime/harness_core.py`、`harness_host.py` 与 `harness_loop.py` 构成通用的观察 -> 规划/选工具 -> 服务端校验 -> 执行 -> 观察结果 -> 继续或结束循环。它支持：

- 多工具顺序执行、循环预算、失败分类、可恢复重试、取消、追问与用户中途转向；
- 服务端能力白名单、项目/组织作用域、结构化参数校验、幂等和审批边界；
- 持久化 `runtime_run`、SSE 事件、工具事件、Trace、诊断、重试与终态，客户端不会把“审批暂停”误判为卡死；
- 通用问答、项目资料检查、就绪度分析、创建交付物、审批请求/恢复均已在真实 DeepSeek 验收中跑过。

它采用 Pi 的 Harness/loop 思路，但不是把 Pi 的任意本机工具权限直接暴露给多租户后端。业务写操作仍由平台真相数据库、权限和人工审批控制；LangGraph 只是长任务执行器，不能替代控制面。

### LangGraph 编排与人工审批

`services/worker/app/graph` 把资料检索、内容计划、章节起草、质量审查、持久化与人工审批恢复拆为可追踪节点。任务出入队走 durable outbox，Worker 至少一次投递通过 lease 与幂等键防重。

本轮修正了一个高风险语义：模型供应商审查不可用或返回无效结构时，**不再自动判定通过**，而是标为 `degraded`、写入原因、产出候选稿并转入人工验证。拒绝会产生新的起草检查点，批准后才允许最终交付。

前端将运行状态投影为 React Flow 画布；节点、边、当前阶段、人工审批与重试来自运行事件，而不是静态装饰。画布的个人布局可调整，但不改变后端工作流事实。

### 模型与提示词兼容

通过 Context7 检索 DeepSeek 官方文档后，已将 DeepSeek V4 的结构化推理调用改为 `thinking` + `reasoning_effort` 的兼容组合；普通章节起草显式关闭 thinking，并在提示词要求只返回 Markdown 正文、不泄露推理轨迹。该处理避免按 OpenAI 参数习惯猜测模型行为。

## 资料导入与远程下载

远程资料路径不应依赖“联网搜索后下载网页”。当前流程是：搜索/公告页仅用于发现候选；用户确认后，系统仅对确认的 HTTP(S) **附件直链**执行导入。

- 服务端 Worker 使用流式下载至临时文件，不把 ZIP/PDF 整体塞进 Agent 上下文或内存；
- HTTP/HTTPS、公开地址、跳转次数、超时、512 MB 上限、内容长度、HTML 伪附件、校验和和临时文件清理均受控；
- 私网/本机目标和无效跳转会被拒绝；失败返回 `remote_not_artifact`、`remote_timeout`、`remote_protocol_error` 等可行动错误；
- 已提供窄化的本机 companion：`services/api/app/runtime/local_companion.py` 与 `services/api/scripts/bidpilot_local_companion.py`。它只能把用户确认的直链原子写入用户选定目录，可设主机白名单，不是远程 Shell。

这与 OWASP 的 SSRF 建议一致：对允许的协议、主机和重定向做正向校验，不以字符串黑名单替代网络边界。有关远端政府站点的登录、签名 URL、TLS 兼容、限速与反爬，系统应明确提示本地下载再上传，而不是无界重试。

## 招标雷达、Webhook 与业务界面

- 雷达：`/radar` 提供来源、机会、匹配理由、趋势、保存和转项目；Worker Beat 按计划轮询 RSS/JSON/webhook 来源。命中、保存、转项目均可产生业务 Webhook。
- Webhook：`/settings/webhooks` 提供组织管理员配置；投递记录经持久化队列、签名/公共 HTTP 地址校验、退避重试处理。Worker 每 30 秒恢复到期投递，避免仅靠内存队列。
- 资料与交付：项目工作台可见资料包、文档解析/索引状态、异常重试、需求/证据/主张、版本审核、交付导出和运行中心。
- 账户、组织、模型、Webhook 与雷达均已有前端路由和角色检查；“页面存在”之外，本轮已经将核心项目链路在真实浏览器执行。

## Trace 与异常体验

每一项长任务拥有运行 ID、Trace ID、事件序列、工具结果、审批状态与可恢复失败码。Agent 界面有 SSE 心跳、终态判定、断线恢复、审批恢复和任务重试显示。此前“助手连接结束但未报告终态”的表现已覆盖为可检测的失败状态，而非永久等待。

## 剩余收口项（不把它们伪装成已完成）

1. **外网来源验收**：针对典型政府采购站点分别建立可公开访问、需 Cookie、签名下载、反爬拒绝四类回归夹具。当前真实验收使用隔离本地资料，不把第三方稳定性归因给产品。
2. **本机 companion 产品化**：已有安全下载内核与脚本；还需要桌面安装/连接状态、用户选择目录、回传“已下载/待上传”收据的完整 UI 协议，才算用户可一键使用。
3. **生产角色浏览器验收**：管理员动作已有服务端与浏览器用例，但 24 条端到端用例被环境变量保护，生产预发需要专用组织、邮箱和测试 endpoint 后执行。
4. **前端性能与测试洁净度**：构建成功但 Agent/图表 chunk 超过 500 KB；Vitest 有 React `act` 提示，部分测试会探测默认 8000 端口并走 fallback；API 测试夹具还有 SQLAlchemy 循环 FK 清理 warning。这些不是本轮业务阻断，但应作为 P1 工程债处理。
5. **通知偏好与邮件投递面板**：按优先级被放在核心业务之后。业务通知、Resend 回执、退信/投诉 webhook、失败重试面板应建立在现有任务/审批终态之上，不能反过来替代核心闭环。

## 外部依据

- [DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion)
- [DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP Top 10: SSRF](https://owasp.org/Top10/2021/A10_2021-Server-Side_Request_Forgery_%28SSRF%29)

## 下一步的验收门槛

在进入通知偏好、邮件回执和后台运维面板前，先完成“外网资料四类夹具 + 本机 companion UI 协议 + 预发管理员 E2E”三个缺口。三个缺口都通过后，才把核心业务闭环标为生产级完成。
