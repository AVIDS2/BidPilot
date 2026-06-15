# DocPilot 项目深度解析报告

## 项目概述

**DocPilot** 是一个企业级AI文档执行系统，专为复杂的文档工作流设计。该项目采用全栈架构，后端使用Python（FastAPI + Celery），前端使用React 19，集成LangGraph实现多Agent智能工作流。

---

## 一、系统架构全景

### 1.1 高层架构（Layer Model）

```
┌─────────────────────────────────────────────────────────────┐
│                    前端应用层 (Frontend)                      │
│  React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui    │
│  - 项目工作台                                                │
│  - 文档管理                                                  │
│  - 需求矩阵                                                  │
│  - 章节起草和审核                                              │
└─────────────────────────────────────────────────────────────┘
                            │ HTTP/SSE
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    API 应用层 (Backend)                       │
│  FastAPI + PostgreSQL + Redis + MinIO                        │
│  - 认证边界                                                  │
│  - 项目和文档 CRUD                                           │
│  - 执行调度端点                                               │
│  - 审核和批准 API                                            │
└─────────────────────────────────────────────────────────────┘
                            │ Celery
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Worker 执行层 (Async)                       │
│  Celery Worker + LangGraph Multi-Agent                       │
│  - 解析任务                                                  │
│  - 索引任务                                                  │
│  - 证据生成                                                  │
│  - 章节起草                                                  │
│  - 验证和导出                                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据层 (Data Services)                     │
│  - PostgreSQL：持久业务和审计状态                               │
│  - Redis：队列、临时状态和缓存                                  │
│  - MinIO/S3：原始和渲染的制品                                   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Plane 模型

| Plane | 职责 | 技术 |
|-------|------|------|
| **Control Plane** | 持久状态和命令 | PostgreSQL, FastAPI |
| **Execution Plane** | 长时间运行或异步操作 | Celery Worker, LangGraph |
| **Integration Plane** | 外部服务集成 | Adapters层 (LLM, Parsers, Vector) |
| **Operations Plane** | 部署、追踪、告警 | Docker, CI/CD, Monitoring |

---

## 二、后端架构深度分析

### 2.1 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| **Web框架** | FastAPI 0.111+ | RESTful API，支持异步和自动文档生成 |
| **数据库** | PostgreSQL 17 + pgvector | 持久存储 + 向量检索 |
| **ORM** | SQLAlchemy 2.0 + Alembic | 数据库抽象和迁移 |
| **任务队列** | Celery + Redis broker | 异步任务处理 |
| **Agent框架** | LangGraph 0.4+ | 多Agent工作流编排 |
| **认证** | JWT + bcrypt + email verification | 用户认证和授权 |
| **日志** | structlog | 结构化日志 |
| **速率限制** | slowapi | API速率限制 |

### 2.2 API 应用结构

```
services/api/app/
├── main.py                    # FastAPI应用入口，路由注册，中间件
├── db.py                      # 数据库会话管理
├── models.py                  # SQLAlchemy数据模型（20+表）
├── celery_client.py           # Celery任务调度客户端
├── logging.py                 # 结构化日志配置
│
├── auth/                      # 认证模块
│   ├── router.py              # /auth/* 路由
│   ├── service.py             # JWT、密码哈希、邮箱验证逻辑
│   ├── repository.py          # 用户数据访问
│   └── schemas.py             # 请求/响应模型
│
├── projects/                  # 项目管理模块
│   ├── router.py              # /projects/* 路由
│   ├── service.py             # 业务逻辑，包含plan限制检查
│   └── repository.py          # 数据持久化
│
├── bundles/                   # 文档包模块
├── documents/                 # 文档管理
├── drafting/                  # 章节起草
│   ├── router.py              # /drafting/* 路由
│   ├── service.py             # 起草任务调度
│   └── streaming.py           # SSE流式传输
│
├── execution/                 # 执行任务管理
├── requirements/              # 需求管理
├── evidence/                  # 证据管理
├── review/                    # 审核模块
├── deliverables/              # 交付物管理
├── billing/                   # 计费（Stripe集成）
├── teams/                     # 团队管理
├── organizations/             # 组织管理
├── providers/                 # AI提供商配置
├── invitations/               # 邀请管理
├── audit/                     # 审计日志
├── ops/                       # 运维监控
├── export/                    # 导出功能
├── adapters/                  # 外部集成适配器
│   ├── storage.py             # MinIO存储适配器
│   ├── stripe_adapter.py      # Stripe支付适配器
│   └── export.py              # 导出渲染适配器
│
└── scenarios/                 # 场景配置
```

**层级规则：**

1. **Router层**：HTTP请求/响应绑定、schema验证
2. **Service层**：业务规则、跨仓库编排、运行创建逻辑
3. **Repository层**：持久化访问、查询逻辑、行到域映射
4. **Adapter层**：提供者集成、解析器集成、检索器集成

### 2.3 数据模型（20+表）

**组织与用户域：**
- `Organization`：租户根实体
- `Team`：组织内的命名组
- `TeamMember`：多对多关系（用户-团队）
- `User`：组织成员，全局唯一email
- `Invitation`：待接受邀请

**项目与内容域：**
- `Project`：一个工作投入（提案、RFP响应等）
- `Bundle`：逻辑上传批次
- `SourceDocument`：原始上传文件
- `ParsedAsset`：解析器管道的规范化输出

**知识与检索域：**
- `KnowledgeChunk`：带pgvector嵌入的文本块
- `RequirementItem`：结构化需求
- `Evidence`：源支持的引用记录

**交付与审核域：**
- `Deliverable`：逻辑输出制品（如提案文档）
- `DeliverableSection`：交付物中的章节
- `SectionVersion`：章节内容的不可变快照
- `ReviewThread`：人工或AI审核对话
- `ReviewComment`：审核线程中的单个评论

**运维与审计域：**
- `ExecutionRun`：一次执行图调用
- `AuditEvent`：追加式事件日志

**订阅与计费域：**
- `Subscription`：用户计划和Stripe集成
- `ProviderConfig`：用户LLM提供商凭证
- `RefreshToken`：JWT刷新令牌

---

## 三、Worker执行层深度分析

### 3.1 Worker结构

```
services/worker/app/
├── celery_app.py              # Celery应用配置
├── tasks.py                   # 任务注册表
├── models.py                  # Worker专用数据模型
├── provider_registry.py       # AI提供商注册表
│
├── adapters/                  # 外部集成适配器
│   ├── llm.py                 # OpenAI适配器
│   ├── anthropic_llm.py       # Anthropic/Claude适配器
│   ├── parser.py              # 文档解析器
│   ├── embedding.py           # 向量嵌入适配器
│   ├── requirements.py        # 需求提取
│   ├── storage.py             # MinIO存储适配器
│   └── export.py              # 导出渲染
│
├── execution/                 # 执行管道
│   ├── ingest.py              # 文档摄入管道
│   └── drafting.py            # 传统起草管道（遗留）
│
└── graph/                     # LangGraph多Agent图
    ├── state.py               # BidPilotState类型定义
    ├── builder.py             # StateGraph组装和编译
    └── nodes/
        ├── supervisor.py      # 路由节点
        ├── rfp_parser.py      # RFP解析Agent
        ├── knowledge_retriever.py  # 知识检索Agent
        ├── section_drafter.py # 章节撰写Agent
        ├── quality_reviewer.py # 质量评审Agent
        ├── human_approval.py  # 人工审核节点（interrupt）
        └── persist_result.py  # 结果持久化节点
```

### 3.2 Celery任务

| 任务名 | 功能 | 描述 |
|--------|------|------|
| `worker.ping` | 健康检查 | 返回"pong" |
| `worker.ingest_bundle` | 文档摄入 | 解析文档、提取块、更新状态 |
| `worker.draft_section` | 章节起草 | 调用LLM生成投标章节 |
| `worker.resume_draft` | 恢复起草 | 人工审核后恢复LangGraph图 |
| `worker.record_dead_letter` | 死信记录 | 记录失败任务供后续检查 |
| `worker.backup_database` | 数据库备份 | 调用pg_dump进行备份 |

### 3.3 LangGraph多Agent工作流

**核心概念：** 使用有状态图（StateGraph）替代简单的RAG管道，支持draft-review循环和human-in-the-loop审核。

**图拓扑：**

```
__start__ → supervisor
  │
  ├─ 无requirements → rfp_parser → knowledge_retriever
  ├─ 无evidence → knowledge_retriever
  ├─ 无draft → section_drafter → quality_reviewer
  ├─ 有draft无review → quality_reviewer
  ├─ review通过 → human_approval (HITL中断)
  ├─ human approved → persist_result
  ├─ human rejected + iteration < max → section_drafter (带feedback)
  └─ iteration >= max → persist_result
```

**节点详解：**

1. **supervisor（路由节点）**
   - 根据状态决定下一步执行哪个Agent
   - 实现智能路由逻辑
   - 支持多轮迭代控制

2. **rfp_parser（RFP解析Agent）**
   - 查询ParsedAsset.content_json
   - 用LLM提取结构化需求
   - 降级：LLM失败时用正则模式匹配

3. **knowledge_retriever（知识检索Agent）**
   - pgvector cosine_distance检索相关知识块
   - 输出evidence_chunks（包含真实cosine distance分数）
   - 降级：ILIKE文本搜索 → 项目全量块

4. **section_drafter（章节撰写Agent）**
   - 调用LLM生成投标章节
   - 接收evidence_chunks, requirements, review_feedback, provider_config_id
   - 重试：tenacity 3次指数退避
   - 降级：LLM失败时返回stub draft

5. **quality_reviewer（质量评审Agent）**
   - LLM评审draft的完整性、合规性、证据使用
   - 输出review_result（passed/issues/suggestions/overall_score）
   - 降级：LLM失败时用确定性启发式检查

6. **human_approval（人工审核节点）**
   - interrupt()暂停图执行，等待用户审核
   - 输入draft_markdown, review_result
   - 输出human_decision, review_feedback
   - 机制：LangGraph interrupt + resume

7. **persist_result（持久化节点）**
   - 单DB session写入所有结果
   - 创建SectionVersion + Evidence记录 + 更新ExecutionRun
   - evidence confidence使用真实cosine_distance

**状态模型（BidPilotState）：**

```python
class BidPilotState(TypedDict):
    # 标识
    project_id: str
    section_key: str
    run_id: str
    provider_config_id: str | None
    review_feedback: str | None

    # RFP解析
    requirements: list[dict]
    requirements_parsed: bool

    # 知识检索
    evidence_chunks: list[dict]
    evidence_retrieved: bool

    # 章节撰写
    draft_markdown: str
    draft_model_used: str
    draft_created: bool

    # 质量评审
    review_result: dict | None
    review_passed: bool

    # 持久化
    section_version_id: str | None
    persisted: bool

    # 控制流
    human_decision: str | None
    iteration: int
    max_iterations: int
    error: str | None
```

---

## 四、前端架构深度分析

### 4.1 技术栈

| 组件 | 版本 | 用途 |
|------|------|------|
| **React** | 19.1 | UI框架，支持async actions和乐观更新 |
| **TypeScript** | 5.8 | 类型安全 |
| **Vite** | 7.0 | 快速开发环境和构建工具 |
| **Tailwind CSS** | 4.2 | CSS-first配置，token驱动设计系统 |
| **shadcn/ui** | 4.3 | 可访问、开放代码的构建块 |
| **TanStack Query** | 5.99 | 服务器状态管理、缓存、失效 |
| **React Router** | 7.14 | 类型安全路由、URL状态管理 |
| **TipTap** | 3.22 | 富文本编辑器 |
| **Recharts** | 3.8 | 图表可视化 |
| **Lucide React** | 1.9 | 图标库 |
| **Sonner** | 2.0 | Toast通知 |
| **next-themes** | 0.4 | 主题管理（亮/暗模式） |

### 4.2 项目结构

```
apps/web/src/
├── app.tsx                    # 应用根组件，路由定义，Provider树
├── main.tsx                   # 入口点
├── index.css                  # 全局样式和设计token
│
├── app/                       # 应用配置
│   └── app.test.tsx           # 根组件测试
│
├── components/                # 共享UI组件
│   ├── ui/                    # shadcn/ui基础组件（button, card, table等）
│   ├── app-sidebar.tsx        # 应用侧边栏
│   ├── site-header.tsx        # 站点头部
│   ├── login-form.tsx         # 登录表单
│   ├── signup-form.tsx        # 注册表单
│   ├── error-boundary.tsx     # 错误边界
│   ├── command-palette.tsx    # 命令面板
│   ├── notification-bell.tsx  # 通知铃铛
│   ├── section-editor.tsx     # 章节编辑器
│   ├── agent-progress.tsx     # Agent进度显示
│   └── agent-status-stream.tsx # Agent状态流
│
├── features/                  # 功能模块（按领域划分）
│   ├── auth/                  # 认证相关页面
│   │   ├── forgot-password-page.tsx
│   │   ├── reset-password-page.tsx
│   │   ├── verify-email-prompt-page.tsx
│   │   └── verify-email-page.tsx
│   │
│   ├── dashboard/             # 仪表板
│   │   └── dashboard-page.tsx
│   │
│   ├── projects/              # 项目管理
│   │   ├── project-list-page.tsx    # 项目列表
│   │   └── project-detail-page.tsx  # 项目详情
│   │
│   ├── drafting/              # 章节起草
│   ├── review/                # 审核
│   ├── admin/                 # 管理后台
│   │   ├── user-management-page.tsx
│   │   ├── team-management-page.tsx
│   │   └── invitation-management-page.tsx
│   │
│   ├── pricing/               # 定价页面
│   ├── landing/               # 落地页
│   ├── account/               # 账户设置
│   ├── settings/              # 设置（AI提供商配置）
│   ├── docs/                  # 文档页面
│   ├── scenarios/             # 场景配置
│   └── ops/                   # 运维监控
│
├── hooks/                     # 自定义React Hooks
│   ├── use-command-palette.ts
│   └── use-notifications.ts
│
└── lib/                       # 工具库
    ├── api.ts                 # API客户端
    ├── auth.tsx               # 认证Provider和Hook
    └── i18n.ts                # 国际化配置
```

### 4.3 状态管理策略

**服务器状态（TanStack Query）：**
- API数据获取
- 缓存和失效
- 乐观更新协调
- 后台刷新

**URL状态（React Router）：**
- 选中的项目上下文
- 过滤器
- 排序
- 面板状态（可分享时）

**本地UI状态（React useState）：**
- 临时表单交互
- 展开/折叠状态
- 临时编辑功能

**全局客户端状态（Context API）：**
- 认证状态（AuthProvider）
- 主题设置（ThemeProvider）

### 4.4 核心页面功能

**1. 仪表板（DashboardPage）**
- 项目统计概览
- 最近活动
- 快速操作

**2. 项目列表（ProjectListPage）**
- 创建新项目
- 项目卡片视图
- Plan限制显示（Starter: 3个项目限制）
- Onboarding向导（首次使用时）

**3. 项目详情（ProjectDetailPage）**
- Bundle管理（上传、解析状态）
- Deliverable管理（创建、章节编辑）
- 需求矩阵
- Evidence查看
- 执行任务监控
- 审核流程
- 审计日志（Admin）
- 系统状态（Admin）

**4. AI提供商设置（ProviderSettingsPage）**
- 添加/编辑/删除LLM提供商
- 测试连接
- 激活/停用
- 支持OpenAI兼容和Anthropic/Claude

**5. 定价页面（PricingPage）**
- 三个层级（Starter, Professional, Enterprise）
- Stripe结账集成
- 当前计划高亮显示

---

## 五、请求流深度分析

### 5.1 文档摄入流程

```
1. 用户上传Bundle
   ↓
2. POST /bundles → 创建Bundle记录
   ↓
3. Celery: worker.ingest_bundle 任务
   ↓
4. 解析器处理源文档
   ↓
5. 生成ParsedAsset和KnowledgeChunk
   ↓
6. pgvector生成嵌入（1536维）
   ↓
7. 更新Bundle状态为"ingested"
```

### 5.2 章节起草流程（LangGraph路径）

```
1. 用户触发POST /drafting/sections
   ↓
2. Celery: worker.draft_section 任务
   ↓
3. 检查USE_LANGGRAPH环境变量
   ↓
4. 启动LangGraph图执行
   ↓
5. supervisor → rfp_parser (解析RFP文档)
   ↓
6. rfp_parser → knowledge_retriever (检索相关知识)
   ↓
7. knowledge_retriever → section_drafter (生成章节)
   ↓
8. section_drafter → quality_reviewer (质量评审)
   ↓
9. quality_reviewer → human_approval (HITL中断)
   ↓
10. 人工审核（通过/拒绝+反馈）
    ↓
11. human_approval → persist_result
    ↓
12. 写入SectionVersion + Evidence + ExecutionRun
```

### 5.3 认证流程

```
1. 注册
   POST /auth/register
   → 创建User + Subscription(starter) + Invitation(如有)
   → 发送验证邮件
   → 导航到 /verify-email-prompt

2. 验证邮箱
   GET /auth/verify-email?token=xxx
   → 更新email_verified=True
   → 显示成功

3. 登录
   POST /auth/login
   → 验证密码哈希
   → 检查email_verified
   → 生成JWT access_token + refresh_token
   → 返回给前端存储

4. Token刷新
   POST /auth/refresh
   → 验证refresh_token
   → 生成新的access_token
```

---

## 六、数据流和集成

### 6.1 外部服务集成

**LLM提供商（通过Adapters层）：**
- OpenAI兼容API（GPT-4, GPT-3.5等）
- Anthropic/Claude API
- 用户自定义提供商（通过ProviderConfig）

**存储服务：**
- MinIO：文档存储、导出文件
- PostgreSQL：业务数据、向量嵌入

**支付服务：**
- Stripe：订阅管理、结账会话、Webhook处理

**邮件服务：**
- SMTP（QQ/Foxmail邮箱）
- 邮箱验证、密码重置

### 6.2 向量检索集成

```python
# KnowledgeChunk模型支持pgvector
embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

# 检索逻辑
cosine_distance(KnowledgeChunk.embedding, query_embedding)
```

---

## 七、安全架构

### 7.1 认证和授权

**JWT Token认证：**
- Access Token：短期（可配置过期时间）
- Refresh Token：长期，存储在数据库
- 密码哈希：bcrypt
- 邮箱验证：强制验证（生产环境）

**RBAC（角色基础访问控制）：**
- Admin：完全访问，可管理用户/团队/计划
- Member：受限访问，遵循Plan限制
- Dev User：开发环境下的默认管理员

**速率限制：**
- slowapi中间件
- 可配置限制（默认60请求/分钟）
- 邮箱重发限制（3次/小时）

### 7.2 数据安全

- 所有用户数据存储在PostgreSQL
- 敏感信息（密码哈希、API密钥）加密存储
- JWT Refresh Token数据库追踪
- AuditEvent记录所有关键操作

---

## 八、部署架构

### 8.1 Docker Compose（本地开发）

```yaml
services:
  postgres: pgvector/pgvector:pg17 (5433:5432)
  redis: redis:7.4-alpine (6379:6379)
  minio: minio/minio (9000:9000, 9001:9001)
```

### 8.2 生产部署（VPS）

```
bidpilot.rglens.com (主站)
├── api.bidpilot.rglens.com → API网关
├── docs.bidpilot.rglens.com → 文档站
└── pay.rglens.com → 支付

root@38.14.254.50 (VPS)
├── 1Panel v2.1.12 (管理面板)
├── Docker Compose
├── Nginx反向代理
└── Let's Encrypt SSL
```

### 8.3 CI/CD

**GitHub Actions：**
- api-test：运行API测试套件
- frontend-build：类型检查、单元测试、构建
- production-readiness：生产就绪检查
- release：发布流程

---

## 九、开发阶段总结

### Phase 0-4：基础设施和核心功能 ✅

- ✅ 仓库布局和根工具ing
- ✅ React工作台shell
- ✅ FastAPI服务和数据库骨架
- ✅ 本地基础设施（Docker Compose）
- ✅ 项目workspace CRUD
- ✅ Bundle上传和摄入调度
- ✅ Evidence支持的章节起草
- ✅ 审核工作流
- ✅ 审计和追踪关联
- ✅ 认证和RBAC基线
- ✅ 备份/恢复脚本
- ✅ 运维仪表板
- ✅ 场景包注册和模板绑定

### Deepening：持续深化 ✅

- ✅ 持久层扩展（20+表）
- ✅ Celery任务调度
- ✅ 新域模块（Deliverables, Execution, Documents等）
- ✅ Worker DB状态更新
- ✅ 前端集成（TanStack Query, React Router）
- ✅ 治理RBAC和Playwright E2E
- ✅ 负载烟雾测试
- ✅ 监控仪表板基线
- ✅ 生产就绪门禁
- ✅ 发布排练门禁
- ✅ 备份/恢复和Pilot就绪
- ✅ Bootstrap Admin
- ✅ CI和发布工作流硬化
- ✅ 商业包装（定价页、落地页）
- ✅ 订阅模型和Onboarding向导
- ✅ Plan限制执行和管理员升级
- ✅ Quota UI和管理员控制
- ✅ Stripe集成和结账流
- ✅ SMTP邮件基础设施
- ✅ 企业级邮箱验证
- ✅ 用户自定义AI API提供商

---

## 十、关键架构决策和权衡

### 10.1 为什么选择LangGraph？

**优势：**
- 有状态的多Agent工作流
- 支持条件路由和循环
- Human-in-the-loop支持
- Postgres检查点（持久化状态）
- 清晰的节点职责分离

**权衡：**
- 增加了系统复杂度
- 需要学习曲线
- 需要特征标志控制（USE_LANGGRAPH）

**决策：** 通过特征标志实现，可随时回滚到遗留路径

### 10.2 为什么选择D/DD和Clean Architecture？

**优势：**
- 清晰的职责边界
- 易于测试和维护
- 适应复杂业务逻辑
- 支持并行开发

**层级规则：**
- Router → Service → Repository → Model
- Adapter隔离外部依赖
- 队列机制不替代持久运行状态

### 10.3 为什么选择pgvector而不是专用向量数据库？

**优势：**
- 单一数据库（减少运维复杂度）
- 向量检索和业务数据在同一事务中
- HNSW索引支持高效检索

**权衡：**
- 大规模时可能需要专用向量数据库
- 嵌入维度固定（1536）

**决策：** 初期使用pgvector，后续可扩展到专用解决方案

---

## 十一、技术债务和改进机会

### 11.1 当前技术债务

1. **遗留代码路径：** 传统drafting管道仍在维护（通过特性标志切换）
2. **测试覆盖：** 前端测试相对较少（26个 vs 后端141个）
3. **文档同步：** 部分实现可能和文档不完全一致

### 11.2 改进机会

1. **前端测试：** 增加E2E测试覆盖
2. **API文档：** 完善OpenAPI规范和示例
3. **性能优化：** 数据库查询优化、缓存策略
4. **监控增强：** Prometheus指标、Grafana仪表板
5. **容器化：** Kubernetes部署配置

---

## 十二、项目统计

| 指标 | 数量 |
|------|------|
| 后端Python文件 | 100+ |
| 前端React组件 | 60+ |
| API测试 | 141 |
| 前端测试 | 26 |
| Playwright E2E测试 | 15 |
| 数据库表 | 20+ |
| API路由 | 100+ |
| LangGraph节点 | 7 |
| Docker服务 | 3 |

---

## 十三、总结

DocPilot是一个设计精良的企业级文档执行系统，具有以下特点：

1. **架构清晰：** D/DD分层，职责明确
2. **AI集成：** LangGraph多Agent工作流，支持复杂业务逻辑
3. **安全可靠：** JWT认证、RBAC、邮箱验证、审计日志
4. **可扩展：** 模块化设计，易于添加新功能
5. **生产就绪：** 完整的CI/CD、备份恢复、监控运维

该项目展示了现代全栈应用的最佳实践，特别是在AI驱动的文档处理领域。其LangGraph集成和Human-in-the-loop设计使其在复杂业务场景中具有显著优势。
