<p align="center">
  <img src="assets/readme-hero.svg" alt="BidPilot" width="720">
</p>

<h1 align="center">BidPilot</h1>

<p align="center">
  <strong>面向投标响应团队的项目优先 AI 工作台。</strong><br>
  从招标资料、要求和证据，到审核与最终交付，围绕同一个项目推进。
</p>

<p align="center">
  <a href="https://bidpilot.rglens.com/"><img src="https://img.shields.io/badge/online-demo-16a085?style=for-the-badge" alt="online demo"></a>
  <a href="https://github.com/AVIDS2/BidPilot/actions/workflows/ci.yml?query=branch%3Amaster"><img src="https://img.shields.io/github/actions/workflow/status/AVIDS2/BidPilot/ci.yml?branch=master&style=for-the-badge&label=CI&logo=github" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2563eb?style=for-the-badge" alt="license"></a>
  <a href="https://github.com/AVIDS2/BidPilot"><img src="https://img.shields.io/github/stars/AVIDS2/BidPilot?style=for-the-badge&logo=github&color=facc15" alt="stars"></a>
  <img src="https://img.shields.io/badge/Next.js-16-111827.svg?style=for-the-badge" alt="Next.js 16">
  <img src="https://img.shields.io/badge/FastAPI-0.136-009688.svg?style=for-the-badge" alt="FastAPI">
</p>

<p align="center">
  <a href="https://bidpilot.rglens.com/">打开公网演示</a>
  <br>
  <a href="docs/product/interview-demo-script.md">面试演示脚本</a>
</p>

<p align="center">
  <strong>项目工作区</strong> | <strong>资料解析</strong> | <strong>证据链</strong> | <strong>Copilot</strong> | <strong>人工审核</strong> | <strong>DOCX / PDF</strong>
</p>

<p align="center">
  <a href="#开始使用">开始使用</a> |
  <a href="#产品能力">产品能力</a> |
  <a href="#支持你的团队">工作入口</a> |
  <a href="#快速开始">快速开始</a> |
  <a href="#记忆模型">记忆模型</a> |
  <a href="#copilot-与工作流">Copilot</a> |
  <a href="docs/README.md">文档</a>
</p>

---

> 当前公网版本是个人面试展示版和 controlled pilot reference implementation。
> 它证明一条真实可运行的 AI 文档执行链路，但不把演示环境包装成已经完成企业商业 GA 的 SaaS。

<h2 id="bidpilot-是什么"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-overview.svg"><img src="assets/tags/section-overview.svg" alt="BidPilot" height="32" /></picture></h2>

BidPilot 把投标响应从一个孤立的聊天框，拉回一条可以核对、协作和交付的项目路径。招标文件、企业资料、要求、证据、响应章节、审核决定和最终文件，都属于同一个项目。

投标团队可以先判断机会，再整理资料；先看清要求和缺口，再起草响应；先由人确认版本，再导出真正要交付的文件。Copilot 负责理解和推进，项目数据与审核决定仍由系统持久化保存。

**什么时候该用 BidPilot：** 当资料散落在 Word、PDF、表格和历史案例里，团队需要反复确认同一件事，AI 输出必须有依据，最后还要交给客户或评审一份可下载、可追溯的方案时。

| 真实问题 | BidPilot 提供什么 |
| --- | --- |
| 招标文件和企业资料分散，没人知道先看什么 | 项目工作区、资料包、解析状态和明确的下一步 |
| 需求藏在长文档里，漏掉一条就可能影响投标 | 结构化要求清单、优先级、验证状态和缺口视图 |
| AI 写出了内容，但无法解释依据 | 要求、证据和响应内容之间的来源链 |
| 团队意见散落在聊天和文件名里 | 项目成员、审核决定、版本记录和审计事件 |
| 起草结果不能直接交付 | 只有审核通过的版本才能进入 DOCX/PDF 导出 |
| 长任务遇到断线、失败或刷新后无法恢复 | Pi 交互会话、Celery + LangGraph 持久化工作流和可恢复进度 |
| 用户每次都要重复解释项目背景 | 当前工作上下文、工作记录、项目知识和团队方法的分层记忆 |

BidPilot 的界面优先服务真实投标工作。项目页面负责项目业务，Copilot 是辅助入口；不会把所有侧栏入口都粗暴地跳回一个 Agent 页面，也不会用关键词触发脚本来猜用户意图。

### 产品能力

BidPilot 不是只生成一段文字。它把资料处理、证据检索、AI 协作、人工治理和文件交付连成一条可复核的业务链。

| 能力 | 用户实际得到什么 | 产品保证 |
| --- | --- | --- |
| 项目工作区 | 项目概览、资料、要求、响应、审核、交付和项目知识 | 项目是业务范围边界，入口保持当前项目上下文 |
| 资料处理 | 招标文件、企业资料、补充材料分包上传和处理 | 原始文件保留在私有对象存储，状态持久化 |
| 要求与证据 | 结构化要求、来源定位、覆盖状态和缺口 | 检索按组织和项目授权执行，没有依据就是缺口 |
| Copilot | 读取项目事实、发起受控动作、观察工作进度 | 原生 Pi Agent 会话，服务端能力授权和审计 |
| 人工审核 | 退回、反馈重做、确认项目知识、批准响应版本 | 模型不能自我批准，审核决定进入数据库和审计记录 |
| 可交付文件 | 审核后的 DOCX/PDF 文件和导出记录 | 导出读取批准版本快照，不导出草稿或退回版本 |
| 项目知识 | 带来源的项目事实、决定、风险和流程 | 提案先审核，支持编辑、退回、替代和有效期 |
| 个人偏好 | 可关闭、可单条删除、可全部清理的工作偏好 | 偏好不升级为招标事实，不越过项目边界 |
| 我的工作 | 按用户真正要处理的事项聚合提醒和下一步 | 不直接暴露原始运行日志和内部消息队列 |

<h2 id="项目工作区"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-workspace.svg"><img src="assets/tags/section-workspace.svg" alt="Project workspace" height="32" /></picture></h2>

一次投标响应的业务路径是：

```mermaid
flowchart LR
    A[机会判断] --> P[项目工作区]
    B[招标文件] --> P
    C[企业资料] --> P
    P --> I[解析与索引]
    I --> R[要求清单]
    R --> E[项目证据集]
    E --> D[响应章节候选]
    D --> H[人工审核]
    H -->|退回| D
    H -->|批准| X[批准版本快照]
    X --> O[DOCX / PDF 交付物]
```

项目页面不是一个装饰性 Dashboard。它是实际业务的主入口：

- `项目概览` 说明当前准备度、资料数量、交付状态和下一步；
- `资料` 管理招标文件、企业资料和补充材料，并展示解析/索引状态；
- `要求` 展示抽取出的要求、优先级、验证和证据覆盖；
- `响应` 以章节为单位起草、查看候选版本并进入审核；
- `评审` 处理团队确认和版本决定；
- `交付` 只展示可交付版本和真实导出入口；
- `项目知识` 管理带来源的项目事实，提案不会未经确认直接影响后续工作。

<h2 id="支持你的团队"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-agents.svg"><img src="assets/tags/section-agents.svg" alt="Works with your team" height="32" /></picture></h2>

BidPilot 的入口围绕责任设计，而不是把内部服务名称直接摆给用户。每个角色看到的是自己要推进的工作，所有入口仍回到同一个项目事实集。

<table>
<tr>
<td align="center" width="16.6%"><strong>投标负责人</strong><br><sub>项目全局 + 进度</sub></td>
<td align="center" width="16.6%"><strong>方案工程师</strong><br><sub>要求 + 证据</sub></td>
<td align="center" width="16.6%"><strong>评审负责人</strong><br><sub>审核 + 版本</sub></td>
<td align="center" width="16.6%"><strong>交付负责人</strong><br><sub>文件 + 留痕</sub></td>
<td align="center" width="16.6%"><strong>项目协作者</strong><br><sub>资料 + 讨论</sub></td>
<td align="center" width="16.6%"><strong>Copilot</strong><br><sub>自然语言协作</sub></td>
</tr>
<tr>
<td align="center"><a href="https://bidpilot.rglens.com/projects">项目</a></td>
<td align="center"><a href="https://bidpilot.rglens.com/requirements">要求清单</a></td>
<td align="center"><a href="https://bidpilot.rglens.com/reviews">评审</a></td>
<td align="center"><a href="https://bidpilot.rglens.com/deliverables">交付物</a></td>
<td align="center"><a href="https://bidpilot.rglens.com/projects">资料包</a></td>
<td align="center"><a href="https://bidpilot.rglens.com/agent">助手工作台</a></td>
</tr>
</table>

<p align="center">
  <sub>从项目、资料、要求到交付，每个入口都保持项目上下文，不把业务页面伪装成开发者调试台。</sub>
</p>

| 工作入口 | 作用 | 用户看到的结果 |
| --- | --- | --- |
| 项目 | 创建项目、查看准备度、进入项目工作区 | 当前项目的资料、状态和下一步 |
| 资料 | 上传并处理三类项目材料 | 文件状态、解析结果和索引进度 |
| 要求清单 | 确认要求、优先级、验证与来源 | 可追溯要求和明确缺口 |
| Copilot | 询问项目、推进动作、观察任务 | 有上下文的对话和真实工作进展 |
| 评审 | 分配、评论、退回和批准 | 人工决定与版本留痕 |
| 交付物 | 查看版本、导出最终文件 | 可下载、可复核的 DOCX/PDF |

<h2 id="开始使用"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-install.svg"><img src="assets/tags/section-install.svg" alt="Start" height="32" /></picture></h2>

### 公网体验

直接打开 [BidPilot 公网演示](https://bidpilot.rglens.com/)，或进入 [登录页](https://bidpilot.rglens.com/auth/sign-in)。公开演示使用合成的智慧社区项目资料，不要上传真实投标文件、个人信息或生产密钥。

### 本地前置条件

- Node.js 22+
- pnpm 11.19+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- UI/API 合同验证可以使用 SQLite；真实资料解析、向量索引和长流程需要 PostgreSQL + pgvector、Redis、MinIO/S3

当前 Windows 开发基线默认使用直接启动的 Node/Python 进程。Docker Compose 保留给已批准的基础设施环境和公网 VPS；完整约束见 [`docs/development/local-environment-baseline.md`](docs/development/local-environment-baseline.md)。

<h2 id="快速开始"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-quick-start.svg"><img src="assets/tags/section-quick-start.svg" alt="Quick start" height="32" /></picture></h2>

### 启动本地 UI/API 合同验证

在仓库根目录执行：

```powershell
corepack enable
pnpm install
uv sync --all-packages --locked

New-Item -ItemType Directory -Force .tmp | Out-Null
$localDbFile = (Join-Path (Resolve-Path .tmp) "bidpilot-local.sqlite3").Replace("\\", "/")
$env:DOCPILOT_ENV = "local"
$env:DOCPILOT_DATABASE_URL = "sqlite:///$localDbFile"
$env:DOCPILOT_APP_URL = "http://127.0.0.1:3300"
$env:DOCPILOT_API_URL = "http://127.0.0.1:8000"
$env:DOCPILOT_CORS_ORIGINS = "http://127.0.0.1:3300"
$env:DOCPILOT_AUTH_REQUIRED = "false"
$env:DOCPILOT_LANGGRAPH_CHECKPOINTER = "memory"
$env:DOCPILOT_AGENT_CHECKPOINTER = "memory"
$env:DOCPILOT_ASSISTANT_ENGINE = "pi"
$env:DOCPILOT_PI_AGENT_URL = "http://127.0.0.1:8787"
$env:DOCPILOT_PI_TOOL_BRIDGE_URL = "http://127.0.0.1:8000/internal/pi/tools/execute"

uv run --directory services/api python -c "from contracts.db import Base; import app.models; from app.db import engine; Base.metadata.create_all(engine)"
```

然后分别启动：

```powershell
# Terminal 1: FastAPI
uv run --directory services/api uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Pi sidecar
pnpm --filter @docpilot/pi-agent dev

# Terminal 3: Next.js
pnpm --filter @docpilot/web dev -- --port 3300
```

访问 [http://127.0.0.1:3300](http://127.0.0.1:3300)。SQLite profile 用于页面、认证和 REST/SSE 合同验证；它不虚构 Redis、对象存储或 Celery 能力。真实上传、索引和长流程请按 [`docs/development/local-environment-baseline.md`](docs/development/local-environment-baseline.md) 准备隔离基础设施。

### 一次完整的产品路径

1. 创建一个项目；
2. 上传招标文件、企业资料和补充材料；
3. 查看解析状态，确认要求清单和证据覆盖；
4. 在响应工作区起草一个章节；
5. 退回一次并带反馈重新起草，或直接审核批准；
6. 在交付物页面导出批准内容的 DOCX/PDF；
7. 回看版本、项目知识、审核决定和错误恢复边界。

### 模型连接

模型 key 只放在被忽略的本地环境或服务端 secret store 中。当前生产配置使用 MiMo 作为平台助手和工作流模型，OpenRouter 作为向量模型；代码通过 adapter 保留其它 OpenAI-compatible、Anthropic-compatible 和用户 BYOK 配置。

```text
DOCPILOT_ASSISTANT_ENGINE=pi
DOCPILOT_ASSISTANT_MODEL=mimo-v2.5-pro
DOCPILOT_PROVIDER_DOMESTIC_BASE_URL=https://api.xiaomimimo.com/v1
DOCPILOT_PROVIDER_DOMESTIC_API_KEY=<your-mimo-api-key>
DOCPILOT_PROVIDER_DOMESTIC_MODEL=mimo-v2.5-pro
OPENROUTER_API_KEY=<your-openrouter-api-key>
OPENROUTER_EMBEDDING_MODEL=qwen/qwen3-embedding-8b
OPENROUTER_EMBEDDING_DIMENSIONS=1536
```

MiMo 的 thinking、`max_completion_tokens` 和模型列表接口约束见 [`docs/development/provider-integrations.md`](docs/development/provider-integrations.md)。不要把 API key 填入聊天内容、README、截图、测试输出或 `VITE_*` 变量。

<h2 id="记忆模型"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-memory-model.svg"><img src="assets/tags/section-memory-model.svg" alt="Memory model" height="32" /></picture></h2>

BidPilot 不把四种记忆做成四个技术菜单。它们是决定什么可以保存、谁能读取、什么时候参与检索的产品边界。

| 记忆层 | 存什么 | 适合回答 | 权威来源 |
| --- | --- | --- | --- |
| 当前工作上下文 | 当前项目、会话、附件、待确认事项和正在进行的任务 | “我们现在做到哪一步？” | conversation / runtime state |
| 工作记录 | 已完成任务、审核决定、失败原因、修订过程和项目复盘 | “之前发生过什么？” | ChatMessage、RuntimeRun/Event、review/audit |
| 项目知识 | 已确认的项目事实、要求、风险、决定和术语，均带来源 | “这个项目确定了什么？” | PostgreSQL MemoryRecord + evidence links |
| 团队方法 | 模板、写作规范、审批规则、组织流程和可复用操作方式 | “团队通常怎么做？” | published org/project knowledge and skills |

`用户偏好` 是独立的个性化范围，不是第五种业务事实。它可以保存语言、响应格式、沟通风格和明确确认的工作习惯；可由用户关闭、单条删除或全部清理。Mem0 只服务这一范围，绝不保存或升级招标事实、截止时间、价格、资质、文件和证据。

项目知识遵循审核门：系统或用户先生成提案，审核人可以编辑、确认纳入、退回、调整有效期或创建替代版本。只有 `active` 的带来源记录会进入新的项目上下文；旧版本仍保留在历史中，便于复核而不会继续参与检索。

<h2 id="copilot-与工作流"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-memcode.svg"><img src="assets/tags/section-memcode.svg" alt="Copilot" height="32" /></picture></h2>

BidPilot 的交互 Agent 和长流程工作流各自承担适合自己的职责：

- **Pi Agent** 面向交互式 Copilot：原生会话、流式输出、provider-native tool call、取消、上下文压缩和系统 wake 属于 Pi 的运行时语义；
- **FastAPI 控制面** 负责身份、项目成员、能力授权、配额、幂等、审批、审计和业务写入；
- **Celery + LangGraph** 面向资料解析、混合检索、章节起草、验证、人工审核等待、恢复和导出等持久化工作流；
- **PostgreSQL** 保存项目事实、版本、审核和导出记录；LangGraph checkpoint 只帮助恢复执行，不能成为业务真相；
- **没有关键词触发**：用户意图不通过“出现某个词就运行一个脚本”来判断，动作来自模型原生 tool call 和显式服务端 contract；
- **没有模拟用户确认**：危险或有成本的动作由真实的人在回路确认，系统不会自动发送一条“确认执行”文本来伪造用户行为。

```mermaid
flowchart TB
    U[浏览器] --> N[Next.js 产品界面 + 同源 BFF]
    N --> API[FastAPI 控制面]
    API --> DB[(PostgreSQL + pgvector)]
    API --> OBJ[(私有 MinIO / S3)]
    API <--> PI[Pi Agent sidecar]
    API --> Q[(Redis + outbox)]
    Q --> W[Celery Worker]
    W --> LG[LangGraph 持久化工作流]
    LG --> DB
    W --> M[MiMo / provider adapters]
    W --> V[OpenRouter embeddings]
```

| 层 | 责任 | 不负责什么 |
| --- | --- | --- |
| `apps/web` | Next.js 产品界面、同源 BFF、REST/SSE 投影和响应式工作区 | 不持有 provider key，不直接访问数据库、Worker 或 Pi |
| `services/api` | 认证、组织与项目授权、能力注册、审批、幂等、审计、业务 API 和 Pi 签名桥 | 不承担重解析和长时间起草 |
| `services/pi-agent` | Pi `AgentSession`、原生工具循环、流式生命周期和可信扩展 | 不直接连接 PostgreSQL、Redis、MinIO，不直接写业务事实 |
| `services/worker` | Celery 消费、解析、检索、记忆、起草、审核恢复和导出 | 不成为浏览器交互入口，不取代 API 授权 |
| `packages/contracts` | 跨服务 ID、状态、事件和文档合同 | 不承载业务路由和隐式副作用 |
| PostgreSQL | 项目、资料、要求、证据、版本、审核、运行事件和审计 | 不只是 Agent checkpoint 的附属数据库 |
| Redis | 任务投递、outbox 和短期协调状态 | 不保存唯一业务事实 |
| MinIO / S3 | 私有源文件和导出制品 | 不把对象 URL 暴露给未授权用户 |

<h2 id="工作模式"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-runtime.svg"><img src="assets/tags/section-runtime.svg" alt="Work modes" height="32" /></picture></h2>

| 你想做什么 | 产品入口或运行方式 |
| --- | --- |
| 创建一个新的响应项目 | Web `项目` -> `新建项目` |
| 上传招标和企业资料 | 项目 -> `资料` -> `上传资料` |
| 查看要求和证据覆盖 | 项目 -> `要求`，或侧栏 `需求清单` |
| 让 Copilot 读取当前项目 | 进入 `助手`，带上项目上下文 |
| 起草响应章节 | 项目 -> `响应` -> 选择章节 |
| 处理团队审核 | 项目 -> `评审`，或 `我的工作` |
| 查看项目知识 | 项目 -> `项目知识`，管理提案与历史版本 |
| 导出交付文件 | 项目 -> `交付` -> 导出批准版本 |
| 查看异常或恢复任务 | 从 `我的工作` 的失败事项进入任务详情；运行记录只作为管理员/恢复入口 |

业务页面优先呈现用户要完成的工作；内部运行事件、队列、checkpoint 和原始 provider payload 只留在服务端与受控恢复路径中。

<h2 id="配置"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-configuration.svg"><img src="assets/tags/section-configuration.svg" alt="Configuration" height="32" /></picture></h2>

最小本地模型配置示例：

```text
DOCPILOT_ENV=local
DOCPILOT_APP_URL=http://127.0.0.1:3300
DOCPILOT_API_URL=http://127.0.0.1:8000
DOCPILOT_DATABASE_URL=postgresql://docpilot:docpilot@localhost:5433/docpilot
DOCPILOT_REDIS_URL=redis://localhost:6379/0

DOCPILOT_ASSISTANT_ENGINE=pi
DOCPILOT_ASSISTANT_MODEL=mimo-v2.5-pro
MIMO_API_KEY=<your-mimo-api-key>
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro

OPENROUTER_API_KEY=<your-openrouter-api-key>
OPENROUTER_EMBEDDING_MODEL=qwen/qwen3-embedding-8b
OPENROUTER_EMBEDDING_DIMENSIONS=1536
DOCPILOT_SECRETS_KEY=<generated-fernet-key>
```

服务端会对用户保存的 provider key 做加密处理；浏览器只收到规范化后的模型列表和状态，不会收到原始密钥。MiMo、OpenRouter 和其它 provider 的地址规则、模型优先级与 key alias 见 [`docs/development/configuration-and-secrets.md`](docs/development/configuration-and-secrets.md) 和 [`docs/development/provider-integrations.md`](docs/development/provider-integrations.md)。

<h2 id="部署"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-docker.svg"><img src="assets/tags/section-docker.svg" alt="Deployment" height="32" /></picture></h2>

本地开发和公网部署是两种边界：

- 本地默认使用直接启动的 Next、FastAPI 和 Pi 进程，SQLite 只用于 UI/API 合同验证；
- 公网使用单节点 Docker Compose，PostgreSQL、Redis、MinIO 只绑定本机或容器网络；
- Web 和 API 通过 HTTPS 反向代理暴露，数据库、Redis、对象存储和管理端口不公开；
- `deploy.sh` 按 Pi、API、Worker、Worker Beat、Web 的顺序构建，在低内存 VPS 上避免并发构建导致服务被杀；
- 发布前运行 readiness、migration、LangGraph checkpoint 初始化和健康检查，失败时恢复旧应用容器。

参考开发拓扑：

```bash
docker compose up --build -d
```

公网发布使用服务器布局下的 `/app/bidpilot/repo` 和 `/app/bidpilot/.env`，不要把生产 Compose 文件当成普通本地开发文件直接执行。部署、备份、回滚、反向代理和健康检查见 [`docs/ops/deployment-and-runbook.md`](docs/ops/deployment-and-runbook.md) 与 [`docs/ops/vps-pilot-deployment.md`](docs/ops/vps-pilot-deployment.md)。

当前公网入口：

- [BidPilot Web](https://bidpilot.rglens.com/)
- [API liveness](https://bidpilot-api.rglens.com/health)
- [API readiness](https://bidpilot-api.rglens.com/health/ready)

<h2 id="API"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-sdk.svg"><img src="assets/tags/section-sdk.svg" alt="API" height="32" /></picture></h2>

BidPilot 的外部调用通过 REST/SSE contract 进入服务端。浏览器使用同源 BFF 和 HttpOnly session cookie；内部 Agent、Worker 和 provider 适配器不绕过控制面直接写业务数据。

健康检查示例：

```bash
curl https://bidpilot-api.rglens.com/health
curl https://bidpilot-api.rglens.com/health/ready
```

主要业务边界包括：

| API 范围 | 作用 |
| --- | --- |
| `/auth/*` | 登录、注册、刷新、验证和账户身份 |
| `/projects/*` | 项目创建、项目状态和成员边界 |
| `/bundles/*`、`/documents/*` | 资料包、原始文件和处理生命周期 |
| `/requirements/*`、`/retrieval/*` | 要求清单、证据检索和来源定位 |
| `/assistant/*`、`/internal/pi/*` | Copilot 交互、签名能力桥和流式事件 |
| `/memory/*` | 个人偏好、项目知识、审核和来源链 |
| `/reviews/*`、`/deliverables/*` | 人工审核、版本批准和 DOCX/PDF 导出 |

完整接口由 FastAPI 路由、Pydantic schema 和 [`packages/contracts`](packages/contracts) 共同定义；业务真相在 PostgreSQL，不靠 prompt、浏览器状态或临时 Agent 内存维持。

<h2 id="文档"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-docs.svg"><img src="assets/tags/section-docs.svg" alt="Docs" height="32" /></picture></h2>

| 从这里开始 | 适合场景 |
| --- | --- |
| [文档地图](docs/README.md) | 快速找到正确的产品、架构、开发和运维文档 |
| [面试演示脚本](docs/product/interview-demo-script.md) | 按 10-15 分钟路径展示 Agent、Harness、RAG、Memory 和导出 |
| [非开发者演示指南](docs/product/non-developer-demo-guide.md) | 以投标团队用户视角走完产品流程 |
| [产品路线图](docs/product/roadmap.md) | 查看当前阶段、范围和后续边界 |
| [领域术语](docs/product/domain-glossary.md) | 统一项目、资料、要求、证据、交付和记忆语言 |
| [本地环境基线](docs/development/local-environment-baseline.md) | Windows 直接进程、本地端口和测试数据库约束 |
| [模型连接](docs/development/provider-integrations.md) | MiMo、OpenRouter 和其它 provider 的接入规则 |
| [部署运行手册](docs/ops/deployment-and-runbook.md) | 公网部署、迁移、健康检查、回滚和资源清理 |
| [安全策略](SECURITY.md) | 密钥、漏洞报告、数据边界和公开发布审计 |
| [开发进展](docs/dev-log/progress.md) | 查看阶段完成情况和工程变更 |

长期有效的产品决策、架构边界和验收条件记录在 [`docs/`](docs/README.md)，而不是只写在 README 的一次性说明里。

<h2 id="开发"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-development.svg"><img src="assets/tags/section-development.svg" alt="Development" height="32" /></picture></h2>

```powershell
git clone https://github.com/AVIDS2/BidPilot.git
cd BidPilot
corepack enable
pnpm install
uv sync --all-packages --locked

# Frontend
pnpm --filter @docpilot/web typecheck
pnpm --filter @docpilot/web test
pnpm --filter @docpilot/web build

# Pi sidecar
pnpm --filter @docpilot/pi-agent build

# Python static checks
uv run --project services/api ruff check services/api/app services/api/tests
```

API 和 Worker 测试必须使用专用、名称以 `_test` 结尾的数据库。测试启动前会拒绝普通开发库和生产库；完整规则见 [`scripts/test_database_safety.py`](scripts/test_database_safety.py) 与 [`docs/quality/testing-strategy.md`](docs/quality/testing-strategy.md)。

UI 变更使用 Playwright 做桌面和移动浏览器验收，重点检查真实导航、加载/错误状态、流式交互、中文显示、导出入口和控制台错误。最近一次本地前端回归为 `120 passed`，生产构建、类型检查和后端 Ruff 已通过；本机未运行 Docker 时，不把 SQLite UI 验证写成 PostgreSQL/Redis/MinIO 全链路通过。

<h2 id="安全"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-configuration.svg"><img src="assets/tags/section-configuration.svg" alt="Security" height="32" /></picture></h2>

BidPilot 的安全边界是产品的一部分：

- provider key、数据库 URL、Redis 密码、MinIO/S3 secret、JWT/Fernet secret、邮件和支付 secret 只在服务端环境或 secret store；
- 浏览器只使用同源 BFF 和 HttpOnly session cookie，不读取 bearer token 或 provider key；
- Pi sidecar 不持有业务数据库、对象存储或租户授权凭据，业务能力必须经过签名 API bridge；
- 项目访问、审核、导出和配额由 FastAPI/Worker 服务端裁决；
- 日志和用户界面展示稳定的公开错误类别，不回显原始 provider payload、密钥、数据库 DSN 或内部工具参数；
- 真实投标文件、客户个人信息和生产密钥不得进入公开样例、README、截图、测试 fixture 或 CI 日志。

公开发布前请阅读 [`SECURITY.md`](SECURITY.md)。任何出现在聊天、截图、录屏、终端或 CI 日志里的凭据，都应按已暴露处理并撤销、更换；代码扫描为零不能替代 provider 控制台轮换。

<h2 id="当前边界"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-runtime.svg"><img src="assets/tags/section-runtime.svg" alt="Boundaries" height="32" /></picture></h2>

诚实的边界说明：

- 这是个人面试展示版和公网 controlled pilot，目标是证明 Agent、Harness、RAG、Memory、全栈和基础设施链路，而不是声称已经完成商业容量与合规验证；
- 当前公网实例使用 VPS PostgreSQL/pgvector、Redis 和 MinIO。Supabase managed profile 已保留适配边界，但暂停项目恢复、连接凭据、备份迁移和对象校验尚未作为本版本的切换路径；
- 导出是批准门禁：如果交付物仍有未批准章节，系统只导出已批准内容，只有全部章节满足条件时才称为最终文件；
- 质量 benchmark 主要是开发控制 fixture，不等同于冻结数据集、真实用户评审和长期运营的商业质量证明；
- 尚未宣称企业 SSO/SCIM、水平扩展、完整支付运营、实时协同编辑或通用自主编程 Agent 已达到商业 GA 标准。

这些边界不是隐藏的遗留问题，而是项目定位的一部分。当前任务、证据和后续条件记录在 [`docs/development/current-execution-state.md`](docs/development/current-execution-state.md)、[`docs/product/known-limitations.md`](docs/product/known-limitations.md) 和 [`docs/dev-log/progress.md`](docs/dev-log/progress.md)。

<h2 id="鸣谢"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-acknowledgements.svg"><img src="assets/tags/section-acknowledgements.svg" alt="Acknowledgements" height="32" /></picture></h2>

BidPilot 的产品代码和业务边界由本仓库维护。前端工作台复用了 Kiranism/Base UI 的结构与 shadcn/Base UI 组件；部分营销结构参考 ixartz landing composition 与 Wasp Open SaaS 的公开组织方式，具体归属和许可证见 [`apps/web/THIRD_PARTY_NOTICES.md`](apps/web/THIRD_PARTY_NOTICES.md)。

本 README 的英雄图和图形化分节标题以 [AVIDS2/memorix](https://github.com/AVIDS2/memorix) README 的视觉资产为基准，并做了 BidPilot 文案与品牌适配；对应来源和许可说明见 [`NOTICE.md`](NOTICE.md)。Memorix 的产品能力、命令和运行时边界不属于 BidPilot，本 README 仅复刻其信息编排和展示方式。

<h2 id="license"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/tags/light/section-license.svg"><img src="assets/tags/section-license.svg" alt="License" height="32" /></picture></h2>

[MIT License](LICENSE)

BidPilot 自身代码按 MIT 发布。第三方依赖、字体、模板、图形资产和复用组件仍受其各自许可证约束。

<h2 id="发布历史">发布历史</h2>

当前公开版本和可复现的发布证据见：

- [开发进展](docs/dev-log/progress.md)
- [公网部署运行手册](docs/ops/deployment-and-runbook.md)
- [当前执行状态](docs/development/current-execution-state.md)
- [GitHub Releases](https://github.com/AVIDS2/BidPilot/releases)

如果你准备把它用于面试，建议先按 [面试演示脚本](docs/product/interview-demo-script.md) 走一遍完整路径，再用 [非开发者演示指南](docs/product/non-developer-demo-guide.md) 讲产品价值。这样能同时展示产品判断和工程边界，而不是只展示一次模型输出。
