# BidPilot 生产化与面试交付总 Spec

- 状态：提议，批准后作为唯一开发基线
- 日期：2026-07-27
- 产品：BidPilot（DocPilot 的招投标场景包）
- 目标：交付一条可重复验证的、证据驱动的投标响应闭环，并证明 AI 应用、Python 后端、Agent、RAG、异步任务与工程治理能力
- 关联短版发布门槛：[BidPilot 面试交付版 Agent 工程 Spec](2026-07-27-bidpilot-interview-release-spec.md)
- 关联架构：[系统总览](../architecture/overview.md)、[执行与工作流架构](../architecture/execution-and-workflow-architecture.md)、[Assistant Harness Runtime](../architecture/assistant-harness-runtime.md)、[质量门禁 ADR](../adr/0006-quality-evaluation-release-gates.md)

## 0. 这份文档解决什么问题

BidPilot 不能继续按“想到一个界面或 Agent 想法，再临时补一个接口”的方式生长。那会让数据模型、权限、任务状态、提示词、前端假状态和队列行为互相矛盾，最后无法证明系统能可靠处理真实投标资料。

本 Spec 固定以下工作原则：

1. **业务事实先于模型与页面。** 项目、资料、需求、证据、章节、审批、交付物和审计的真相只存在于 PostgreSQL 的可追溯业务记录中。
2. **后端契约先于前端。** 每个能力先定义领域规则、迁移、命令/查询、事件和回归测试；前端只消费这些契约，不维护另一套“看起来正确”的状态机。
3. **Agent 是受治理的执行入口，不是业务数据库。** 模型只能选择被授权的能力；能力通过领域服务写入真相；模型上下文、LangGraph checkpoint、Redis 和浏览器缓存都不是业务真相。
4. **一个产品问题，只有一个主运行时。** 对话执行由 Harness 负责；长运行投标流程由 Worker 内的 LangGraph 负责；不保留多个公开运行时互相兜底。
5. **先交付可重复的一个垂直闭环，再扩展平台。** 不用“多 Agent”“图谱”“企业级”等词替代可运行、可恢复、可评测的事实。

这是一份开发与验收文档，不是营销文案。未通过对应验收时，不得把功能写成“已生产可用”。

---

## 1. 产品定位、用户与边界

### 1.1 一句话定位

**BidPilot 是面向投标团队的、以证据和审批为中心的协同投标响应工作区。**

它帮助团队把一份 RFP/招标文件和企业资料，从接收、解析、需求拆解、证据检索、章节起草、多人审核到批准导出，变成可恢复、可解释、可审计的执行流程。

它不是：

- 政府或交易所的电子招投标提交门户；
- 泛化聊天机器人、通用 Agent Builder 或本地 Coding Agent；
- 替代法务、投标负责人或最终签章责任人的自动决策系统；
- 任何文件上传后即可承诺“零废标、零幻觉、中标”的系统。

### 1.2 首批目标用户

| 角色 | 真正要完成的工作 | BidPilot 的价值 |
| --- | --- | --- |
| 投标经理 / Proposal Manager | 判断是否参与、拆解 RFP、安排责任人、控制截止日期 | 有完整的项目、需求、状态与风险视图 |
| 售前 / 方案负责人 | 把公司能力组织为技术响应，并处理缺证据问题 | 从可定位证据起草，而不是从空白聊天框开始 |
| SME（技术、交付、法务、财务） | 回答被分派的要求、提供事实和材料 | 只看到自己负责的需求与可审核的上下文 |
| 审核人 / Approver | 审查承诺、风险、引用与输出版本 | 有评论、拒绝、批准、版本和审计链路 |
| 组织管理员 | 管理人员、项目边界、模型配置、保留策略与使用成本 | 有 RBAC、租户隔离、受控 BYOK、可查询运行记录 |

### 1.3 用户愿意使用而不是直接把文件扔给通用 AI 的原因

通用 Chat、Claude Code 或 Coding Agent 能写文本，但它们默认没有以下产品级约束：

1. **响应范围与责任人。** 一条要求是否必须响应、由谁负责、是否已经通过审核，不能藏在对话记录里。
2. **证据与版本。** 关键主张必须可以回到某份资料、具体版本和 locator；没有证据时必须明确暴露缺口。
3. **审批与风险。** 对外承诺、导出、删除、成本型任务需要可审计的审批，而不是一句自然语言“好的”。
4. **协作与恢复。** 人员、浏览器和后台 Worker 断开后，任务、评论、运行状态和产物仍然可恢复。
5. **组织数据边界。** 每个项目、资料、记忆、模型配置与交付物都有组织/项目/用户作用域。

因此 BidPilot 的竞争点不是“比通用模型更会写”，而是把模型放进一个**可管理的投标生产系统**。

### 1.4 市场参考与差异

公开调研表明，成熟 RFP/Proposal 软件普遍强调内容库、协作分工、审批与权限，而不只强调一次生成：

- Responsive 将 Proposal Management 生命周期描述为资格判断（Go/No-Go）、Kickoff、分工和响应管理，并强调 SME 协作。[来源](https://www.responsive.io/blog/what-is-proposal-management)
- Loopio 强调内容库作为响应的单一事实来源，并提供按问题分派的协作案例。[内容库来源](https://loopio.com/blog/optimizing-rfp-response-process-for-success)，[协作案例](https://loopio.com/case-study/powerschool)
- QorusDocs 公开描述了模板、审批流程、角色权限和内容发布控制。[来源](https://www.qorusdocs.com/blog/what-is-proposal-automation-software)
- [OpenBidKit_Yibiao](https://github.com/FB208/OpenBidKit_Yibiao) 是活跃的 AGPL-3.0 开源桌面工具，重点是本地工作区、文档解析、知识库、可恢复后台任务、标书检查以及 OpenCode/Pi Agent 运行时。

BidPilot 不复制 OpenBidKit 的 Electron 本地工作区或其实现。BidPilot 的可验证差异是：

| 维度 | OpenBidKit 公开定位 | BidPilot 必须做出的明确选择 |
| --- | --- | --- |
| 使用形态 | 本地桌面工具，文件与缓存以本机为中心 | 多租户 Web 工作区，服务器端控制平面是业务真相 |
| Agent | 可切换本地 OpenCode/Pi 运行时 | Web Harness 只能调用已授权的平台能力；不执行任意 Shell/网络 |
| 流程 | 本地生成、编辑、恢复任务 | 需求 -> 证据 -> 草稿 -> 审核 -> 批准 -> 导出，每步有审计 |
| 知识 | 本地知识库与素材复用 | 带组织/项目作用域、来源定位、版本、权限与审批的证据层 |
| 协作 | 不是其公开核心承诺 | 投标经理、SME、审核人、管理员的受控协作是 P1 核心 |

这不代表 BidPilot 现在已经更强。它意味着 BidPilot 的 P0 只能在上述 Web 协同、证据和治理闭环全部可验证后，才具备明确的产品叙事。

---

## 2. 发布目标与非目标

### 2.1 面试/演示发布目标

使用一份公开或脱敏的固定 RFP 资料包，任何演示者可以完成：

```text
创建投标项目
  -> 上传 RFP 与企业资料
  -> 等待解析和索引
  -> 审阅/修正需求矩阵
  -> 检索带 locator 的证据
  -> 由 Assistant 规划并启动某个章节工作流
  -> LangGraph Worker 完成起草与校验
  -> 审核人评论、拒绝重跑或批准版本
  -> 导出批准内容
  -> 回看 RuntimeRun、ExecutionRun、证据、审批和审计
```

这个流程必须可重复三次，不依赖手工改库、浏览器本地假数据、未记录模型对话或某一条偶然成功的上游响应。

### 2.2 生产试运行目标

在发布候选后，系统可供一个受控组织处理脱敏或明确授权的真实资料，满足：

- 租户、项目、文档和记忆的访问边界可测试；
- 上传、解析、索引、起草、审核、导出和失败恢复存在持久记录；
- 外部模型、解析器、对象存储、邮件等均被 adapter 与配置边界隔离；
- 秘钥不进入浏览器、SSE payload、日志、仓库或可下载导出物；
- 有备份、迁移、回滚和故障排查 Runbook；
- 有明确的试用额度、速率限制和人工介入边界。

这仍不是“无条件商业 GA”。GA 需要持续使用数据、支持流程、数据合规评估、可用性目标和客户合同边界；这些是 P2/商业化阶段的工作。

### 2.3 当前明确冻结的事项

以下项目不允许抢占 P0 交付资源：

- 泛化的工作流搭建器、自治 Agent 团队或无限循环的“自我进化”系统；
- 3D 知识图谱、未评测的图数据库、自动用户画像；
- 为了“企业级”名义拆分微服务、上 Kubernetes 或引入多套队列；
- 将 WeKnora、Pi SDK、A2A、MCP Server、vLLM、微调或本地 GPU 推理同时塞进主链路；
- 在后端契约不稳定时做大面积 UI 重构或新增营销页面。

WeKnora 可在 P2 作为知识平台替换/集成候选评估；其价值不等于应立刻替换当前已存在的 PostgreSQL/pgvector 证据层。

### 2.4 当前唯一关键路径：先投标闭环，后 Agent 接管

**当前最重要的不是泛化 Agent，也不是邀请页、品牌、端口、计费、图谱或 UI 动效。**

BidPilot 的第一产品价值是“把真实 RFP 和企业资料变成经审核的投标响应”。如果这个闭环不能稳定运行，Agent 只是一个会调用几个接口的聊天壳；反过来，只有业务能力而没有受控 Agent，也无法证明 Agent 工程能力。因此优先级必须严格如下：

| 优先级 | 唯一目标 | 允许做什么 | 明确不做什么 |
| --- | --- | --- | --- |
| P0-Blocker | 让一条真实黄金流程可运行 | 只修阻止迁移、模型调用、队列消费、幂等或运行恢复的根因，并补回归测试 | 不做“顺手清理”、端口/样式优化、无关配置重构 |
| P0-Core | 建成 AI 投标业务引擎 | RFP 资料 -> 需求/合规 -> 证据 -> 章节草稿 -> 审核/批准 -> 导出 | 不扩展泛化助手、邀请、套餐、图谱、CRM、营销页面 |
| P0-Agent | 让 Harness 接管已验证的业务引擎 | 用 7-9 个受治理 capability 编排核心流程，完成多步、缺参、审批、后台 bridge、重放 | 不做任意工具、本地 Shell、子 Agent 团队或“全能助手” |
| P0-Proof | 证明它可靠 | 固定数据集、E2E、eval、trace、部署演练和面试脚本 | 不先做视觉翻新或更多功能页 |

这里的顺序不是四条可并行的大路线，而是必须依次解锁的临界路径：

```text
可运行 blocker
  -> 一个可审计的投标业务闭环
  -> Harness 驱动该闭环
  -> 评测、演示和生产试运行证据
```

P0-Blocker 只能以一个明确的失败现象进入，例如“缺 migration 导致 `assistant_action_audit` 插入失败”或“已配置 provider 仍无法完成一次结构化模型调用”。每个 blocker 必须有：复现、根因、最小修复、回归测试和完成证据。它不是一个可以消耗数天的“平台优化阶段”。

为 P0-Agent 预留的最小 capability 集合是：

1. 查询项目与资料状态；
2. 查询/筛选需求与合规缺口；
3. 检索项目证据；
4. 创建或更新响应计划；
5. 启动指定章节起草；
6. 查询/恢复/取消后台 Run；
7. 请求审核、读取审核状态；
8. 在已批准条件满足时请求导出。

这些能力必须先由 API/Worker 的黄金路径独立验证，再接给 Harness。Invitation、成员管理 UI、通知、套餐、复杂权限管理、图谱、第三方连接器和视觉重构都不在当前关键路径上。

---

## 3. 领域语言与真实业务生命周期

### 3.1 统一领域词汇

| 词汇 | 定义 | 当前状态 |
| --- | --- | --- |
| Organization | 一个租户/公司，拥有成员、项目、配置与数据保留边界 | 已有基础 |
| Membership / Role | 用户在组织内的身份与权限 | 已有基础，需补权限矩阵测试 |
| Bid Project | 一次投标响应的工作容器；当前数据库/API 中的 `Project` 在 P0 保持兼容 | 已有 |
| Opportunity / Intake | RFP 到来后的立项、截止日期、客户、机会/Go-No-Go 信息 | P1 新领域能力 |
| Bundle | 为项目上传的一组资料 | 已有 |
| Source Document / Version | 原始文件与其不可变版本、解析产物、状态和 locator | 部分已有，需规范版本语义 |
| Requirement Item | 从 RFP 提取、人工可编辑的响应义务/评分点/限制/交付要求 | 已有基础 |
| Compliance Item | 需求对应的责任人、状态、证据、风险和最终响应覆盖情况 | P0 补齐 read model / P1 扩展 |
| Evidence | 可用于支持主张的、具来源和 locator 的片段 | 已有基础 |
| Content Library Entry | 组织级、审批后可复用的答案、案例、能力或模板 | P1 |
| Response Plan | 章节、需求、责任人、截止日期和起草策略的结构化计划 | P0 需显式化 |
| Section / Section Version | 章节和不可变草稿/批准版本 | 已有基础 |
| Review Thread / Decision | 评论、变更请求、拒绝和批准的持久记录 | 已有基础，需完整闭环 |
| Deliverable | 从已批准版本生成的 DOCX/PDF/提交包及其版本 | 已有部分，需发布门禁 |
| Runtime Run | 一个 Assistant 交互回合和其工具/审批事件的持久运行记录 | 已有 |
| Execution Run | 一个后台解析、索引、草拟、验证、导出等流程的持久运行记录 | 已有 |
| Audit Event | 对业务、权限、审批和交付具有追溯意义的不可变摘要 | 已有基础，需覆盖不变量 |

### 3.2 核心业务状态机

```mermaid
stateDiagram-v2
    [*] --> Intake
    Intake --> Qualified: Go
    Intake --> Closed: No-Go / withdrawn
    Qualified --> Preparing: project + source bundle created
    Preparing --> ReadyForDraft: parsing/indexing/requirements ready
    ReadyForDraft --> Drafting: response plan accepted
    Drafting --> InReview: section version submitted
    InReview --> Drafting: changes requested
    InReview --> Approved: reviewer approves
    Approved --> Exported: approved versions rendered
    Exported --> Submitted: optional external submission record
    Submitted --> Closed
```

当前 P0 必须可靠交付 `Preparing -> ReadyForDraft -> Drafting -> InReview -> Approved -> Exported`。`Intake`、Go/No-Go 和 `Submitted` 可以先作为 P1 实体/状态，但不得在 UI 中伪装成已实现。

### 3.3 投标响应的最小业务闭环

每一次可展示的投标必须满足以下不变量：

1. 每个生成章节属于一个 `Bid Project`、一个 `Response Plan` 和一个明确的版本。
2. 每条关键要求都有状态：`untriaged`、`assigned`、`in_progress`、`covered`、`at_risk`、`waived` 或 `not_applicable`，并有责任说明。
3. 每条引用必须指向一个被授权的 `Source Document Version` 与 locator；没有证据时只能标记 `missing_evidence`，不得捏造出处。
4. 只有已批准章节版本可以进入正式 `Deliverable`。
5. 删除、导出、审批、外部模型调用和高成本流程都在审计中可追溯到用户/运行/请求 ID。
6. 任何任务重试都不能重复创建项目、章节版本、审批或交付物。

### 3.4 P0 审核恢复的实现约束（2026-07-27）

为避免“审核页找不到版本”或“重试覆盖已批准内容”，P0 的章节审核必须遵守以下顺序：

```text
质量审核通过
  -> 持久化 immutable SectionVersion candidate
  -> 创建 / 复用 ReviewThread(section_version_id)
  -> ExecutionRun = awaiting_human + LangGraph interrupt
  -> 人工 approve / reject 写入审核与审计事务
  -> 同一事务创建 sequenced worker.resume_draft outbox
  -> Worker 以相同 LangGraph checkpoint 恢复
```

- 重试同一 `(section, execution run, iteration)` 只能回放同一个候选版本。
- 人工拒绝不能覆盖旧的 `approved_version_id`；后续重起草产生新 iteration 的候选版本。
- 人工批准只允许把其明确的 `section_version_id` 设为批准快照。
- 任何审核决策先提交数据库事务，再请求异步投递；队列不是审核或版本的真相来源。

---

## 4. 目标后端架构

### 4.1 总体形态：模块化单体 + 异步 Worker

BidPilot 当前和近期都采用模块化单体，不为形式拆服务：

```mermaid
flowchart LR
  Web[Web / API client]
  API[FastAPI Control Plane]
  DB[(PostgreSQL + pgvector)]
  Obj[(MinIO / S3)]
  Queue[(Redis + Celery)]
  Worker[Worker Execution Plane]
  LG[LangGraph inside Worker]
  Models[Model / Parser / Reranker adapters]
  Obs[Audit + Runtime Events + Observability]

  Web -->|commands, queries, SSE| API
  API --> DB
  API --> Obj
  API --> Queue
  Queue --> Worker
  Worker --> LG
  Worker --> DB
  Worker --> Obj
  API --> Models
  Worker --> Models
  API --> Obs
  Worker --> Obs
```

模块化单体的边界：

| 平面 | 责任 | 禁止事项 |
| --- | --- | --- |
| Control Plane（API + DB） | 命令校验、权限、领域事务、读模型、运行初始化 | 把长模型调用、文档大解析或 Celery 轮询放在请求线程 |
| Execution Plane（Worker） | 解析、索引、起草、验证、导出、重试与恢复 | 直接信任队列 payload、绕过领域服务写业务状态 |
| Knowledge Plane | 文档版本、分块、向量、全文检索、重排、证据、记忆提案 | 让 embedding 或 graph 结果成为未经审核的业务事实 |
| Integration Plane | Provider、Parser、Storage、邮件、MCP 等适配器 | 在业务服务中散落 SDK/HTTP 调用和密钥读取 |
| Operations Plane | 配置、迁移、日志、指标、trace、备份、发布 Runbook | 把生产故障依赖人工 SSH 猜测解决 |

### 4.2 后端模块边界

建议按领域而非页面或模型名称组织 API 服务。每个领域模块有 `schemas`、`service`、`repository`（必要时）、`router` 和测试；Router 只负责 HTTP/Pydantic/依赖注入，不写业务规则。

| 模块 | 拥有的数据和规则 | 对外命令/查询示例 |
| --- | --- | --- |
| `auth` / `organizations` | 用户、组织、成员、角色、会话 | invite member, change role, resolve actor scope |
| `projects` / `opportunities` | Bid Project、机会、状态、团队、截止日期 | create project, archive project, go/no-go |
| `bundles` / `documents` | 上传、对象、文档版本、解析/索引状态 | upload bundle, retry parsing, document status |
| `requirements` / `compliance` | Requirement、归属、覆盖与风险 | extract, assign, waive, mark at risk |
| `retrieval` / `evidence` | 索引、检索、locator、evidence set | search evidence, build evidence set |
| `planning` / `drafting` | response plan、章节、版本、草拟 | create plan, start draft, redraft section |
| `reviews` / `approvals` | 评论、审核决策、发布门禁 | request review, approve version, reject version |
| `deliverables` / `exports` | 批准快照、渲染产物、下载权限 | create export, get export status |
| `runtime` / `assistant` | RuntimeRun、事件、审批、capabilities | submit assistant turn, cancel, replay events |
| `memory` | proposal、批准、可见范围、context pack | propose, approve, compile context |
| `providers` / `usage` | 服务端模型配置、BYOK 密文、额度/成本 | resolve model, record usage, enforce quota |
| `audit` / `operations` | 不可变审计摘要、运行检索、操作诊断 | query audit, run health/release report |

**禁止的依赖方向：** `router -> ORM` 直写、`LangGraph node -> HTTP router` 回调、`provider adapter -> 业务表` 直写、前端把模型/解析状态当作真相。模块之间通过领域服务、显式 DTO 或受控 repository 协作。

### 4.3 事务、队列与幂等

异步任务必须接受“至少一次投递”，而不是假设 Celery 只会运行一次。

P0 规则：

1. API 在同一个事务内创建领域命令状态和 `ExecutionRun` / `RuntimeRun`。
2. 事务提交成功后才允许投递任务；任务使用 `run_id` 读取数据库，不携带可被伪造的完整业务对象。
3. Worker 每次开始、成功、失败、取消和恢复都持久化状态；写入版本、审批、导出物时使用唯一约束或 idempotency key。
4. 所有浏览器 Assistant 提交必须带 `client_request_id`，它在用户作用域内唯一；普通网络重试只能回放既有 Run，不得再次调用模型或工具。
5. P0 收口时为“数据库已提交但投递失败”的双写问题选定方案：轻量 `OutboxEvent + dispatcher`，或明确且测试过的事务后投递补偿任务。不能继续依赖偶然成功。

不把 Redis/Celery 的运行状态当用户可见真相；它们只是调度机制。

### 4.4 数据隔离与数据库约束

每个可读取/写入的业务对象必须至少携带：

- `org_id`；
- 如果属于项目，则 `project_id`；
- `created_by` / `updated_by` 或等价审计 actor；
- 状态、版本、创建/更新时间；
- 对带来源内容的对象，`source_document_version_id` 与 locator/evidence reference。

服务层要求：

- 每次查询从已认证 actor 的组织范围开始，而不是从浏览器传来的 ID 开始；
- 读取、工具执行、Worker 恢复和导出都重复检查组织/项目边界；
- 外键、唯一约束、check constraint 是不变量的第二层防线；
- 迁移按版本发布，`alembic upgrade head` 是部署硬门禁；
- 迁移须在专用测试数据库和 staging 路径验证，不能由公网运行时首次暴露缺表。

数据库 Row-Level Security 是否引入，属于 P2 设计决策；P0 先将所有 repository/service 的组织边界测试做成 100% 结构性门禁。引入 RLS 前必须评估 SQLAlchemy、迁移、后台 Worker 和管理员查询的可操作性。

---

## 5. Agent 运行时的唯一边界

### 5.1 运行时分工

| 场景 | 主运行时 | 例子 | 业务真相 |
| --- | --- | --- | --- |
| 交互式产品操作 | `StreamingHarness` | “查看这个项目资料状态，再启动第三章起草” | `RuntimeRun`、领域记录、`RuntimeEvent` |
| 长运行投标流程 | Celery Worker + LangGraph | 解析 -> 检索 -> 规划 -> 起草 -> 校验 -> HITL -> 落库 | `ExecutionRun`、章节版本、审核/审批、审计 |
| 外部工具入口 | MCP adapter（受同一 capability policy 管控） | 通过兼容客户端查询项目或启动允许的动作 | 同上 |
| 本地 Coding Agent | 不属于 BidPilot 公网主路径 | Pi/OpenCode 的本地文件工具模式 | 不适用 |

LangGraph 的价值是持久化图状态、条件分支、循环和人工中断。官方文档将其定位为可控制复杂任务的 Agent 框架，并通过 checkpoint/store 提供短期与长期状态机制。[概览](https://docs.langchain.com/oss/python/langgraph/overview)，[持久化](https://docs.langchain.com/oss/python/langgraph/persistence)

这不意味着所有 Agent 都要用 LangGraph。浏览器 Assistant 的一轮工具循环更适合一个小而可审计的 Harness；把它强行包装成另一个公开 LangGraph 会导致重复事件、重复消息和不清晰的恢复语义。

### 5.2 Harness 规范

`StreamingHarness` 是唯一公开 Assistant 路径，职责是：

```text
assemble authorized context
  -> model decides one capability
  -> validate capability arguments and policy
  -> execute domain capability
  -> persist public trace
  -> feed redacted result back to model
  -> continue / ask missing input / request approval / bridge workflow / finish
```

必须满足：

- 每次能力调用使用显式 schema；模型不能写 SQL、Shell、任意 HTTP 或跨项目读取数据；
- 读取、写入、高成本、删除能力有风险等级和授权策略；
- 每个能力通过领域服务，而不是绕过服务直接访问 ORM；
- 单轮最大迭代、最大工具错误次数、超时和取消策略是配置化且有测试的；
- 工具结果分为内部诊断与面向用户的 `public_summary`，默认不显示 JSON、内部工具名、ID、provider 原始报错；
- 模型错误走红脱敏错误和终态 Run 事件，不能把上游原始错误丢给用户；
- 同一 `client_request_id` 的 retry 必须 replay，不得生成两条用户消息或重复执行工具。

### 5.3 LangGraph 投标工作流规范

当前 Worker 已存在的核心图节点包括 supervisor、RFP parser、memory context、knowledge retriever、content plan、section drafter、quality reviewer、human approval、persist result 和 memory proposals。P0 不重写成另一套图，而是把它收敛到以下输入/输出约束：

```mermaid
flowchart LR
  A[ExecutionRun created] --> B[Load immutable project/document/version inputs]
  B --> C[Retrieve scoped evidence]
  C --> D[Build response plan]
  D --> E[Draft section version]
  E --> F[Validate: coverage, citations, policy]
  F -->|needs human| G[LangGraph interrupt + durable approval/review]
  G -->|approved| H[Persist immutable version + audit]
  G -->|changes requested| C
  F -->|passes automatic rules| H
  H --> I[Optional reviewed memory proposal]
```

规范：

1. 图输入只包含稳定 ID、版本、授权 scope 和配置快照；不要将整份原文或浏览器状态作为唯一输入。
2. 每个节点输入/输出应有 Pydantic/TypedDict 契约，并可离线单测。
3. 图节点不得直接暴露成 API，也不得绕过 `ExecutionRun` / 领域审核服务。
4. `interrupt()` 只暂停执行；批准、评论、拒绝和恢复必须同时写入独立业务记录。
5. Checkpoint 用于恢复执行，不替代项目、版本、审批或审计的关系型真相。
6. 任何模型生成都先成为候选版本，不能直接修改已批准版本或导出物。

### 5.4 现有重复运行时的收口任务

仓库中历史上同时存在 `StreamingHarness`、`runtime/operator_graph.py`、`runtime/operator_adapter.py` 与 `agent/graph.py` 等路径。P0 必须完成 runtime inventory：

1. 标明每个入口是否仍有生产调用；
2. 对公开 Assistant 保留一个入口和一套事件协议；
3. 兼容别名只能在配置解析层存在，不能再分叉业务流程；
4. 无调用的旧图必须删除，或移动到明确标记的 migration/compatibility 模块并设删除日期；
5. 用回归测试证明普通重试不会重复模型调用、消息或工具。

---

## 6. 文档、检索、证据与记忆架构

### 6.1 文档处理管线

```text
upload -> object storage -> file validation -> parser/OCR -> normalized document version
       -> structural blocks/tables/pages -> chunks -> embedding + full-text index
       -> retrieval candidates -> rerank -> evidence links -> draft/review/export
```

每一步均有状态与失败原因：

| 阶段 | 必须持久化的内容 | 失败处理 |
| --- | --- | --- |
| 上传 | 文件元数据、hash、对象地址、提交人、项目范围 | 文件类型/体积/恶意文件拒绝，保留安全审计 |
| 解析 | parser 版本、文档版本、页/块/表格 locator、状态 | 可重试，不覆盖旧成功版本 |
| 索引 | chunk、embedding 模型版本、全文索引版本 | 允许重新索引，保留版本关联 |
| 检索 | query scope、候选、重排、降级原因 | 无证据时显式返回 `missing_evidence` |
| 生成 | evidence set、prompt/context policy、输出候选版本 | 不能用未授权或无 locator 的内容做引用 |

P0 文件安全最低要求：允许类型白名单、大小/页数限制、对象存储私有访问、解析器超时、路径净化、上传文件不直接作为系统指令。后续生产试运行再评估恶意文件扫描和隔离 parser worker。

### 6.2 RAG 设计

当前 pgvector + 全文检索 + RRF + reranker 的方向正确，P0 不替换向量库。要补的是可证明性：

1. 所有召回先按 `org_id`、`project_id`、文档可见性和版本过滤，再做 dense/sparse 检索。
2. RRF 合并后进行 rerank；每个 evidence candidate 保留分数、来源、locator、文档版本和被选中原因。
3. Draft 前生成有上限的 `EvidenceSet`，并记录未满足的 Requirement；模型不能凭“相似内容”伪造出处。
4. 引用校验应检查 locator 是否存在、document version 是否仍有效、证据是否属于当前授权范围。
5. 检索服务必须给出降级状态（例如 embedding provider 不可用时的关键词 fallback），而非暗中改变回答可信度。

评测必须覆盖：Recall@K、locator 有效率、跨项目拒绝、必要证据命中、无证据降级和 rerank 对比。

### 6.3 组织内容库与复用

成熟投标产品的内容库不是“把所有历史文件都塞给模型”。P1 要建立 `ContentLibraryEntry`：

- 组织范围但有分类、行业/场景标签、所有者、有效期、审核状态；
- 可复用答案、案例、能力说明、模板和附件；
- 每条内容记录来源和版本，允许被废弃、替换与审核；
- 被用于某个 Bid Project 时记录引用，便于追踪“哪些投标用了哪条企业承诺”；
- 允许内容所有者/SME 批准后发布，不允许模型把草稿自动提升为组织事实。

### 6.4 记忆与 LLM Wiki

BidPilot 当前的正确方向是“source-bound proposal -> reviewer approval -> authorized retrieval”，而非自动建立用户画像或让 Agent 把对话当事实。

采用四层记忆：

| 层 | 内容 | 写入规则 | 读取规则 |
| --- | --- | --- | --- |
| Working | 当前 Run 的目标、已选择项目、未完成审批 | 当前运行时 | 当前 Run |
| Episodic | 已完成 Run 的简要结果、失败/恢复原因 | 自动摘要但带 Run/来源 | 受组织/项目范围限制 |
| Semantic | 已审核的组织能力、项目事实、历史经验 | proposal + evidence + approval | 只召回 active 且授权内容 |
| Procedural | 经审核的操作流程/Skill | 人工维护版本 | 与 capability policy 一起注入 |

Prompt 组装顺序固定为：

```text
system policy
-> actor / org / project authorization
-> selected procedural skill
-> unresolved task state and approval state
-> compact conversation summary + recent turns
-> staged attachment metadata
-> scoped evidence and approved long-term memory
-> current user request
```

超过 context budget 时必须保留未完成任务、项目绑定、审批和来源，生成/更新可追溯摘要；禁止静默截断使模型忘记审批或项目范围。

知识图谱继续遵守 [ADR 0009](../adr/0009-reviewed-memory-graph-projection.md)：当前只做可审核的 proposal ledger，不建立 3D 可视化，不把 graph row 当事实。WeKnora、图谱或 Agentic RAG 只能在独立 benchmark 证明其提升 evidence coverage 且不降低隔离/引用可靠性后，引入 adapter 评审。

---

## 7. 核心业务能力清单

### 7.1 P0：必须完成的投标响应能力

| 能力 | 后端定义 | 验收证据 |
| --- | --- | --- |
| 项目立项 | 创建项目、团队、场景、基本元数据 | 项目有组织范围、审计和幂等创建 |
| 资料包 | 上传、版本化、解析、索引与重试 | 每份文件可见 parse/index 状态与失败原因 |
| RFP 需求矩阵 | 提取、人工校正、分配、覆盖状态 | 至少一组需求可追溯到文档 locator |
| 证据检索 | 混合检索、重排、受范围约束的 EvidenceSet | 有效 locator 或明确 `missing_evidence` |
| 响应规划 | 章节与 requirement/evidence/owner 的映射 | 计划可保存、修改、审计 |
| 章节起草 | Worker 异步起草候选版本 | 版本、输入 evidence、Run、模型配置快照可追溯 |
| 质量校验 | 覆盖/引用/结构/风险检查 | 校验结果是结构化记录，不只是模型文本 |
| 审核与批准 | 评论、拒绝重跑、批准 | 导出只接受批准版本 |
| 交付物 | DOCX/PDF 或至少一种稳定格式的批准快照导出 | 交付物哈希、版本、权限、审计可查 |
| Assistant 入口 | 受控多步工具能力与 Workflow bridge | 同轮可完成读取+规划+启动，带审批和 replay |

### 7.2 P1：让产品接近真实团队使用的能力

| 能力 | 用户问题 | 后端优先实现 |
| --- | --- | --- |
| Go/No-Go | 这个机会值不值得投入？ | Opportunity、评分维度、风险/能力缺口、决策审计 |
| 团队与 SME 协作 | 谁回答哪条要求？何时逾期？ | requirement assignment、任务、提及、状态、通知事件 |
| 截止日期与计划 | 哪些章节拖慢整体交付？ | milestone、SLA、依赖、风险 read model |
| 组织内容库 | 如何复用已验证的答案而非重复找文件？ | ContentLibraryEntry、审核、生命周期、引用追踪 |
| 合规与废标风险 | 哪些硬性条款尚未覆盖？ | requirement type、mandatory flag、coverage/risk rules |
| 变更管理 | RFP 新版本改变了什么？ | DocumentVersion diff、requirement impact、重新审核任务 |
| Q&A / Clarifications | 客户澄清如何影响答案？ | clarification record、关联需求、变更审计 |
| 通知与订阅 | 谁该知道审批、失败和到期？ | domain event -> email/in-app adapter，避免直接在服务层发邮件 |

### 7.3 P2：商业化/规模化后再做

- SSO/SAML/SCIM、精细数据保留和企业审计导出；
- CRM、招标门户、SharePoint/Drive 等 connector；
- 组织级 Usage、计费、发票、套餐和自助升级；
- 客户自带模型的完整生命周期、模型评测和路由策略；
- 多区域/高可用/灾备、数据库 RLS、对象存储生命周期；
- 经 benchmark 批准的 WeKnora/Agentic RAG/知识图谱适配；
- 多语言、无障碍、完整移动端和行业模板市场。

---

## 8. API、事件与前端消费契约

### 8.1 API 先行流程

每个功能按以下顺序开发：

```text
领域规则与状态机
-> PostgreSQL schema / migration / constraints
-> command and query DTO
-> service + authorization + transaction
-> worker/capability integration
-> unit/integration/contract tests
-> OpenAPI/event fixture
-> frontend read model and interaction
```

没有完成前六步，不开始做“漂亮页面”。前端发现缺少状态时，应补充后端状态/事件契约，而不是用本地 boolean 猜测。

### 8.2 命令与查询原则

- 命令返回稳定资源或 `202 + run_id`；耗时操作不得伪装同步完成。
- 查询返回领域 read model，不返回 ORM 内部结构或 provider 原始 payload。
- 所有 mutation 支持 idempotency（浏览器 request ID、导入 hash、版本 fingerprint 等）。
- API 错误使用稳定 `code`、用户可见 `message`、关联 `run_id/request_id`，原始异常仅进安全日志。
- OpenAPI 是客户端/Agent/MCP 的公共契约，contract test 不能只靠手工网页验证。

### 8.3 Runtime 事件协议

Assistant 和后台 Workflow 都以持久化 Runtime Event 为源，SSE 是实时投影。每条事件至少有：

```json
{
  "schema_version": "1.1",
  "event_id": "uuid",
  "run_id": "uuid",
  "parent_event_id": "uuid-or-null",
  "sequence": 17,
  "occurred_at": "ISO-8601",
  "type": "capability.completed",
  "public_summary": "已检索项目资料",
  "payload": { "redacted": true }
}
```

最小事件集合：

- `run.started`、`plan.updated`；
- `capability.started`、`capability.progress`、`capability.completed`、`capability.failed`；
- `approval.requested`、`approval.resolved`；
- `workflow.linked`、`workflow.progress`；
- `message.delta`、`message.completed`；
- `run.cancelled`、`run.completed`、`run.failed`。

前端要求：按 `run_id + event_id/sequence` 去重，可从 REST 拉取事件后 reconnect SSE；不能因为 optimistic UI 再创建一条用户消息或伪造一个工具成功。完整 UI 形态（摘要、展开 trace、审批、取消、后台恢复）必须基于这些 fixture 开发。

---

## 9. 安全、权限、模型与成本治理

### 9.1 基础权限

角色至少区分：`org_admin`、`bid_manager`、`contributor`、`reviewer`、`viewer`。能力策略不是前端按钮显隐，而是服务端在每次调用时验证：

```text
actor -> organization -> project -> resource -> capability -> risk/approval policy
```

高风险/写入/成本型动作需要 `RuntimeApproval` 或等价业务审批。即使是 `full_access`，删除、外部发送、导出批准物和不可逆变更也可要求 typed confirmation。

### 9.2 文档与 Prompt Injection

RFP、附件、网页抓取内容和用户上传文本都是不可信数据，不是系统指令。OWASP 将 Prompt Injection 列为 LLM 应用的首要风险之一。[来源](https://genai.owasp.org/llmrisk/llm01-prompt-injection)

P0 防护：

- 系统策略、工具 schema、用户请求、检索证据分层放入 prompt；
- 检索文本以“引用材料”身份提供，不能覆盖工具权限或系统规则；
- capability allowlist、项目 scope 和结构化参数校验独立于模型输出；
- 未信任内容不能触发网络、Shell、删除、权限变更或自动记忆写入；
- 记录注入测试案例：要求模型忽略规则、跨项目取数、伪造引用、诱导导出/删除。

### 9.3 Provider 与 BYOK

- 平台 Key 只存在服务端环境变量或托管 Secret；浏览器永远不接触；
- 用户 BYOK 加密保存，只有 provider 调用瞬间解密；不进入事件、日志、错误消息或数据库调试 dump；
- provider adapter 显式声明协议（OpenAI Chat Completions、Anthropic Messages 等）、base URL、模型与能力；不得猜测模型名或 silently fallback；
- 模型调用记录 provider/model/policy/usage/cost 的红脱敏元数据；
- 平台试用额度、BYOK 额度和速率限制在服务器端按 user/org 生效，不能依赖前端计数；
- 上游 4xx/5xx 映射为稳定产品错误，保留可支持的关联 Run ID。

### 9.4 运行安全与数据保护

- 私有对象存储 bucket、签名下载 URL、短期访问；
- 备份 PostgreSQL 与对象存储元数据，定期恢复演练；
- 密码、会话、邮件验证、CORS、CSRF/Origin、rate limit 和登录审计走常规 Web 安全基线；
- 不宣称 SOC 2、ISO 27001 或任何法规合规，除非有真实控制与审计证据。

---

## 10. 质量、可观测性与测试策略

### 10.1 质量不是一个模型分数

质量门禁沿用 [ADR 0006](../adr/0006-quality-evaluation-release-gates.md)：`BidBench`、`RetrievalBench`、`MemoryBench`、`AssistantBench` 的来源、commit、数据集角色与阈值必须可追溯。

结构性不变量必须为 100%，不能被平均分掩盖：

- 跨组织/跨项目读取被拒绝；
- 无有效 locator 时不存在“带引用”的输出；
- 相同提交不重复执行；
- 未批准动作不能落为批准/导出状态；
- 公共错误、事件、日志和导出不含 secret；
- cancel/timeout/retry 不制造幽灵任务或重复交付物。

质量阈值（如 Recall@K、审核通过率）先由 20+ 条公开/脱敏固定案例建立 baseline，再写入版本化 policy；不得用好看的 demo 数据编造目标。

### 10.2 测试金字塔

| 层 | 目的 | 必须覆盖 |
| --- | --- | --- |
| Unit | 领域规则、策略、纯转换 | 状态迁移、RBAC、idempotency、citation validation、prompt assembly |
| Integration | DB/迁移/队列/adapter 边界 | 组织隔离、唯一约束、Worker 恢复、provider error redaction |
| Contract | OpenAPI/SSE/DTO 不漂移 | API 命令、事件 schema、replay、approval resolve |
| E2E | 固定投标资料的黄金路径 | upload -> draft -> review -> export -> audit |
| Eval/Security | AI 质量与越权防御 | retrieval、memory、assistant、prompt injection、model fallback |

CI P0 门禁：Ruff、类型检查、API/Worker/前端测试、迁移升级、contract fixtures、最小 eval 读取必须全部失败即阻断；不得使用 `|| true` 掩盖 lint/type 失败。

### 10.3 可观测性

P0 至少应能按 `run_id` 关联：

- 请求、用户/组织（脱敏 ID）、项目、模型、工具、Worker 任务；
- 运行状态、耗时、重试、取消、失败分类；
- token/成本、检索候选数量、证据命中、审批等待时间；
- 关联的 `RuntimeEvent`、`ExecutionRun`、Audit Event 与 deliverable。

用户可见 trace 与运维 trace 需要分层。前者只显示“搜索项目资料/生成章节草稿”；后者可在受权运维入口查看 provider 状态、异常栈标识和内部 diagnostics。P1 选择一个 OpenTelemetry 兼容 tracer（例如 Langfuse 或同类），但不得以安装 SDK 代替 trace 关联和告警实践。

---

## 11. 发布、运维与演示

### 11.1 环境矩阵

| 环境 | 用途 | 数据规则 |
| --- | --- | --- |
| local | 开发、快速单测、手工调试 | 仅 synthetic/脱敏资料；独立 `.env` |
| test | CI/integration/eval | 专用数据库名必须含 `_test`，不连接生产资源 |
| staging | 迁移、部署、端到端 rehearsal | 与生产形态一致的最小配置和 demo 数据 |
| production demo | 面试/受控试用 | 仅 demo 账户和脱敏资料，密钥经服务器 Secret 管理 |

### 11.2 部署硬门禁

发布前：

1. `git` commit、镜像 tag、migration revision、评测 artifact 与 Demo 数据版本明确；
2. 在 staging 执行 `alembic upgrade head`、服务健康检查、golden E2E；
3. 执行备份并验证恢复说明；
4. 通过 release quality gate；
5. 再由统一 `/app/bidpilot/repo/deploy.sh` 路径部署，Web/API 仅绑定 localhost，由 1Panel/OpenResty 反向代理；
6. 部署后验证 API health、Worker 心跳、对象存储、SSE replay、真实 demo run 与 export；
7. 记录回滚 commit 与上一份镜像/数据库 migration 策略。

迁移失败、缺表（例如审计表未创建）、provider 配置错误或 Worker 未消费队列，都属于发布失败，不能用前端默认文案掩盖。

### 11.3 面试演示材料

完成 P0 后，仓库必须有：

- `README`：本地启动、迁移、测试、demo seed、限制条件；
- 一张后端架构图与一张运行时边界图；
- 固定 RFP demo 数据的来源/许可/脱敏说明；
- 可逐步运行的 10 分钟 demo script；
- 一份 eval report 与 release gate artifact；
- 一份故障复盘：例如重复提交、provider 模型名错误、缺失 migration 或 citation 错误，说明根因、修复、测试；
- 简历表述和可能追问的设计取舍答案。

推荐的诚实简历描述：

> 设计并实现投标文档智能执行平台 BidPilot：使用 FastAPI、PostgreSQL/pgvector、Redis/Celery、LangGraph 和受控 Streaming Harness，完成资料解析、混合检索与引用、人工审批、可恢复异步工作流、SSE 执行追踪、受治理记忆和离线质量门禁；以固定脱敏 RFP 数据集验证端到端投标响应闭环。

---

## 12. 执行路线与 Definition of Done

### Phase P0-A：仅处理阻塞黄金流程的可信基线

**目的：只消除会阻止真实黄金流程运行、恢复或验证的根因。它不是无边界的“基础设施优化阶段”。**

| ID | 工作 | 完成条件 |
| --- | --- | --- |
| P0-A1 | 清理并拆分当前脏工作区 | 每项运行时/迁移/文档改动有明确 commit；不混入缓存、密钥、截图或临时文件 |
| P0-A2 | 迁移健康 | 新库从空状态可 `upgrade head`；既有库升级无缺表；降级/备份策略被记录 |
| P0-A3 | 本地/CI 测试环境 | 专用 `_test` Postgres、Redis、MinIO 可一键启动；API/Worker/前端测试可复跑 |
| P0-A4 | CI 硬门禁 | 移除 lint/type 的忽略；所有 failure 阻断；保留最小 smoke/eval job |
| P0-A5 | Runtime inventory | 只有一个公开 Harness 路径；旧 `operator`/graph 路径被删除或隔离并标记期限 |
| P0-A6 | 运行配置一致性 | production readiness、env example、adapter aliases 与实际 runtime 文档一致 |

### Phase P0-B：黄金投标闭环

**目的：证明不是单点聊天，而是完整领域流程。**

| ID | 工作 | 完成条件 |
| --- | --- | --- |
| P0-B1 | 固定 demo 数据集 | 至少 1 套脱敏 RFP + 企业资料，含许可证、hash、期望 requirements/evidence |
| P0-B2 | 文档 version 与 ingestion | 上传、解析、索引、重试、失败状态可在 API 查询；locator 稳定 |
| P0-B3 | Requirement/Compliance read model | 需求可人工修订、分配和查看覆盖/风险；无证据状态可见 |
| P0-B4 | EvidenceSet + citation validator | 草拟只使用授权 evidence；无效 locator 和跨项目 evidence 被拒绝 |
| P0-B5 | Response plan 和 Section Version | requirement/evidence/owner -> section 的映射持久化；草稿是不可变版本 |
| P0-B6 | Review/Approval/Export | 评论、拒绝重跑、批准、导出均有状态、审计与权限门禁 |

### Phase P0-C：Harness 与 LangGraph 可靠性

**目的：展示真正的 Agent 工程而不是工具调用 demo。**

| ID | 工作 | 完成条件 |
| --- | --- | --- |
| P0-C1 | 统一 Assistant request/replay | 一次提交一个用户消息/RuntimeRun；重复 request ID 只 replay |
| P0-C2 | 多步 capability loop | 单轮完成“解析意图 -> 查项目 -> 查资料/需求 -> 启动章节 workflow”；工具结果是业务摘要 |
| P0-C3 | 缺参/审批/取消 | `needs_input`、RuntimeApproval、typed destructive confirmation、cancel/timeout/reconnect 全部持久化 |
| P0-C4 | Workflow bridge | Assistant Run 与 ExecutionRun 一对多关联；后台进度可从 durable events 重放 |
| P0-C5 | Graph state correctness | Worker 图从稳定输入启动/恢复；HITL 与业务审核记录同步；重复 resume 不重复写版本 |
| P0-C6 | 失败治理 | provider、parser、tool 连续失败停止；错误脱敏、分类、可查 Run ID；无无限 retry |

### Phase P0-D：上下文、质量与生产试运行证据

| ID | 工作 | 完成条件 |
| --- | --- | --- |
| P0-D1 | Prompt Assembly / Compaction | 上下文顺序、预算、摘要、记忆选择有单测与 Trace 元数据 |
| P0-D2 | Memory authorization | proposal/approval/private/shared scope、过期和证据失效可回归验证 |
| P0-D3 | Eval baseline | 至少 20 个固定案例，输出 retrieval/memory/assistant/bid 报告并带 commit/model/dataset hash |
| P0-D4 | Security suite | tenant isolation、prompt injection、secret redaction、idempotency、unapproved export 全绿 |
| P0-D5 | Observability | 运行追踪、耗时、成本、错误分类可查；明确告警/诊断路径 |
| P0-D6 | Deployment rehearsal | staging -> production demo 三次可重复；备份/恢复/回滚 Runbook 可执行 |

### Phase P0-E：面试交付收口

| ID | 工作 | 完成条件 |
| --- | --- | --- |
| P0-E1 | Docs and diagrams | README、ADR、架构图、demo script、接口/事件文档相互一致 |
| P0-E2 | 可观测 demo | 在演示中能解释每个 API、run、节点、证据和审批为何存在 |
| P0-E3 | Failure narrative | 至少一个真实 bug 的根因/修复/回归测试完整记录 |
| P0-E4 | Public demo hygiene | 无真实客户资料、密钥或私密日志；角色、权限、额度、失败状态可体验 |

### P1/P2 开始条件

- 只有 P0-A 到 P0-E 全部通过后，才开始 P1 的协作、内容库、Go/No-Go、变更管理；
- 只有 P1 有真实使用数据和 benchmark 后，才考虑 P2 的 WeKnora、图谱、SSO、复杂计费、外部 connector；
- 任何需求若不能改善上述 DoD，进入 Backlog，不插队。

---

## 13. 当前基线与已知差距

### 13.1 已有、可复用的资产

| 资产 | 当前事实 | 后续动作 |
| --- | --- | --- |
| FastAPI + Pydantic + SQLAlchemy | 已有 API 领域模块和迁移体系 | 收敛服务边界、补 contract tests |
| PostgreSQL + pgvector | 已有业务真相与向量检索方向 | 增加 evidence/version/isolation 不变量 |
| Redis + Celery | 已有异步入口 | 做 idempotency、outbox/补偿和可恢复验证 |
| Worker LangGraph | 已有 drafting 图与 human approval 节点 | 收敛输入/输出、恢复、业务审批同步 |
| StreamingHarness | 已有受治理 Assistant 路径 | 消除旧入口、加强多步/replay/错误治理 |
| RuntimeRun/Event/Approval | 已有 durable trace 基础 | 固定 schema、lineage、SSE replay 和 UI fixture |
| 混合检索/重排 | 已有 dense + sparse/RRF + rerank 方向 | 以 citation validity 和 retrieval eval 验收 |
| 记忆 proposal/graph review | 已有受控提案方向 | 做 compaction、授权、评测，不急于图谱投影 |
| MCP | 已有受治理入口 | 仅作为 adapter，不让其绕过 policy |
| Eval/quality ADR | 已有 Bench/门禁设计 | 产出真实固定数据集与报告 |

### 13.2 必须修正的架构债

1. 当前历史运行时路径重叠，公开入口、兼容 alias、旧 LangGraph/adapter 的所有权不清。
2. 当前工作区存在未收口代码与迁移；在这一状态继续堆功能会让部署、回滚和评测不可重复。
3. lint/type 检查尚非可靠 release gate，测试依赖专用 `_test` 数据库但缺乏一键可复跑路径。
4. 公网曾出现缺 migration、provider 配置/模型名不一致、重复消息/重复工具执行等问题；这些必须靠后端约束和回归测试解决，不能靠前端隐藏。
5. 当前 graph/memory 设计文件明确禁止把 proposal 直接当事实，但产品叙事与前端仍需遵守这一边界。
6. UI 存在大量质量问题；它们在 P0 只消费稳定 API/事件，视觉重构在后端契约稳定后独立分支执行。

---

## 14. 开发工作协议

以后每一个任务卡至少包含：

```text
Problem: 用户/业务正在承担的真实成本
Domain rule: 不可违反的状态与权限规则
Data: 新增/修改的 schema、migration、索引、版本策略
API/Event: command/query 与版本化 runtime event
Execution: API/Harness/Worker/LangGraph 的唯一 owner
Security: scope、approval、input trust、secret/PII 影响
Tests: unit/integration/contract/e2e/eval 选择
Observability: run/audit/metric 关联方式
Frontend: 只列出需要消费的 contract 和用户状态
DoD: 可自动验证的完成条件
```

实施顺序：

1. 先读本 Spec、相关 ADR、现有模型和 migration；
2. 先写/更新 task card 与测试计划；
3. 先做数据库和服务层，再做 Worker/Harness；
4. 生成/更新 OpenAPI/SSE fixtures；
5. 前端按 fixture 做状态呈现，必要时再由 UI 团队美化；
6. 运行 focused tests -> integration -> golden flow；
7. 仅在通过门禁后部署。

禁止以下做法：

- 先看页面缺不缺按钮，再决定后端是否需要业务能力；
- 让模型文本承担审批、项目范围或版本状态；
- 为了演示成功吞掉异常、伪造工具结果、把失败变成“已完成”；
- 未经契约/测试就部署到公网试错；
- 以“加一个框架”“接一个 Agent UI 库”代替状态模型和事件合同。

---

## 15. 研究来源与使用限制

以下来源用于提炼能力与架构约束，不复制其代码或宣传文案：

1. [FB208/OpenBidKit_Yibiao](https://github.com/FB208/OpenBidKit_Yibiao)，2026-07-27 读取其公开 README、目录和 runtime registry。它是 AGPL-3.0；BidPilot 不复制其代码或将其作为闭源 SaaS 的嵌入依赖。
2. [Responsive: What Is Proposal Management?](https://www.responsive.io/blog/what-is-proposal-management)，用于验证 Go/No-Go、Kickoff、SME 协作是成熟 proposal workflow 的组成。
3. [Loopio: Improving the RFP response process](https://loopio.com/blog/optimizing-rfp-response-process-for-success)，用于验证内容库作为复用与一致性机制。
4. [Loopio PowerSchool case study](https://loopio.com/case-study/powerschool)，用于验证问题/需求的协作分派场景。
5. [QorusDocs: Proposal Automation Software](https://www.qorusdocs.com/blog/what-is-proposal-automation-software)，用于验证模板、审批流程和权限控制的产品需求。
6. [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) 与 [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)，用于确定 LangGraph 适合有状态、可恢复、可中断的 Worker 工作流，而不是强行统一所有交互。
7. [OWASP LLM01: Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection)，用于确定上传文档、网页和检索内容必须按不可信输入处理。

外部产品与框架会持续变化；实施时必须再次核查官方文档和许可证，不能仅依据本次调研快照。

---

## 16. 完成定义

这个项目只有同时满足以下条件，才可称为“可用于面试展示的工程化 AI 招投标应用”：

1. P0-A 到 P0-E 全部通过；
2. 固定 demo 资料在干净环境中连续三次跑通；
3. 所有结构性安全不变量和迁移/测试门禁通过；
4. 每次关键生成、审批、导出和失败都能由 Run、事件、审计、证据和版本解释；
5. 简历和演示只陈述已验证的能力与真实局限；
6. 前端以稳定后端/API/SSE 契约为基础，能展示而非伪造这些流程。

在此之前，BidPilot 是一个功能丰富但尚未收口的研发仓库；在此之后，它才是一个可以坦然向面试官展示架构、运行记录、质量证据和工程取舍的完整项目。
