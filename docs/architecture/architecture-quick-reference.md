# DocPilot 架构快速参考

## 核心架构图

```
浏览器 → React 19 + Vite + Tailwind CSS
                │
                │ HTTP/SSE
                ▼
        FastAPI + PostgreSQL
                │
                │ Celery
                ▼
        LangGraph Multi-Agent
        ┌─────────────────────┐
        │  supervisor          │
        └──────────┬──────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
    rfp_parser  knowledge  section
                retriever  drafter
        │          │          │
        └──────────┼──────────┘
                   │
                   ▼
            quality_reviewer
                   │
                   ▼
            human_approval (HITL)
                   │
                   ▼
            persist_result
                   │
                   ▼
            PostgreSQL + pgvector
```

## 核心技术栈

| 层次 | 技术 | 用途 |
|------|------|------|
| 前端 | React 19 + TypeScript + Vite | 用户界面 |
| 样式 | Tailwind CSS 4 + shadcn/ui | 设计系统 |
| 状态 | TanStack Query + Context API | 状态管理 |
| 后端 | FastAPI 0.111 | RESTful API |
| 数据库 | PostgreSQL 17 + pgvector | 数据存储 + 向量检索 |
| 队列 | Celery + Redis | 异步任务 |
| AI框架 | LangGraph 0.4 | 多Agent工作流 |
| 存储 | MinIO | 文档存储 |

## 核心数据模型

```
Organization
├── Team ──── TeamMember
│              └── User
├── Project
│   ├── Bundle
│   │   ├── SourceDocument
│   │   ├── ParsedAsset
│   │   ├── KnowledgeChunk (pgvector嵌入)
│   │   ├── RequirementItem
│   │   └── Evidence
│   ├── Deliverable
│   │   ├── DeliverableSection
│   │   └── SectionVersion
│   └── ExecutionRun
├── Subscription
├── ProviderConfig
└── AuditEvent
```

## 关键文件索引

### 后端核心
- `services/api/app/main.py` - FastAPI入口
- `services/api/app/models.py` - 数据模型(20+表)
- `services/worker/app/tasks.py` - Celery任务
- `services/worker/app/graph/builder.py` - LangGraph图
- `services/worker/app/graph/state.py` - 状态定义

### 前端核心
- `apps/web/src/app.tsx` - 应用根组件
- `apps/web/src/lib/auth.tsx` - 认证逻辑
- `apps/web/src/lib/api.ts` - API客户端
- `apps/web/src/features/projects/project-detail-page.tsx` - 项目详情

## 核心业务流程

### 文档摄入
```
用户上传 → POST /bundles
→ Celery: ingest_bundle
→ 解析器处理
→ 生成ParsedAsset + KnowledgeChunk
→ pgvector嵌入
→ 更新Bundle状态
```

### 章节起草（LangGraph路径）
```
POST /drafting/sections
→ Celery: draft_section
→ LangGraph: supervisor路由
→ rfp_parser (解析RFP)
→ knowledge_retriever (检索知识)
→ section_drafter (生成章节)
→ quality_reviewer (质量评审)
→ human_approval (HITL中断)
→ persist_result (持久化)
```

## API路由概览

### 公共路由
- `POST /auth/*` - 认证
- `GET /auth/verify-email` - 邮箱验证
- `POST /billing/webhook` - Stripe Webhook
- `GET /scenarios` - 场景列表

### 受保护路由（需认证）
- `/projects/*` - 项目管理
- `/bundles/*` - 文档包
- `/drafting/*` - 章节起草
- `/evidence/*` - 证据管理
- `/execution/*` - 执行任务
- `/providers/*` - AI提供商配置

### 管理员路由
- `/audit/*` - 审计日志
- `/ops/*` - 运维监控
- `PATCH /auth/subscription` - 计划升级

## 环境变量

```bash
# 数据库
DOCPILOT_DATABASE_URL=postgresql+psycopg://...

# Redis
DOCPILOT_REDIS_URL=redis://...

# MinIO
DOCPILOT_MINIO_ENDPOINT=...
DOCPILOT_MINIO_ACCESS_KEY=...
DOCPILOT_MINIO_SECRET_KEY=...

# 认证
DOCPILOT_JWT_SECRET=...
DOCPILOT_AUTH_REQUIRED=true

# LLM
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...

# Stripe
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...

# SMTP
DOCPILOT_SMTP_HOST=smtp.qq.com
DOCPILOT_SMTP_PORT=465
DOCPILOT_SMTP_USER=...
DOCPILOT_SMTP_PASSWORD=...

# LangGraph
USE_LANGGRAPH=1
```

## 常用命令

```bash
# 后端开发
cd services/api && python -m uvicorn app.main:app --reload

# 前端开发
cd apps/web && npm run dev

# Celery Worker
cd services/worker && celery -A app.celery_app worker --loglevel=info

# 数据库迁移
cd services/api && alembic upgrade head

# 测试
pytest                                    # 后端
cd apps/web && npm test                   # 前端
cd apps/web && npx playwright test        # E2E

# Docker
docker compose up -d                      # 启动
docker compose down                       # 停止
```

## LangGraph节点说明

1. **supervisor** - 智能路由，根据状态决定下一步
2. **rfp_parser** - 解析RFP文档，提取结构化需求
3. **knowledge_retriever** - pgvector检索相关知识块
4. **section_drafter** - LLM生成投标章节
5. **quality_reviewer** - LLM评审draft质量
6. **human_approval** - interrupt暂停，等待人工审核
7. **persist_result** - 持久化所有结果

## 部署架构

```
devlens.top (主站)
├── api.devlens.top → FastAPI
├── docs.devlens.top → 文档
└── pay.dwill.top → 支付

VPS: root@38.14.254.50
├── 1Panel (管理面板)
├── Docker Compose
├── Nginx
└── SSL (Let's Encrypt)
```

## 测试统计

- 后端API测试：141
- 前端测试：26
- Playwright E2E测试：15
- 总计：182个测试

## 技术债务

1. 传统drafting管道仍在维护（通过USE_LANGGRAPH切换）
2. 前端测试覆盖相对较少
3. 部分实现可能与文档不完全一致

## 快速故障排查

### LangGraph问题
```bash
# 检查LangGraph是否启用
echo $USE_LANGGRAPH

# 查看Worker日志
celery -A app.celery_app worker --loglevel=debug

# 查看PostgreSQL检查点
psql -d docpilot -c "SELECT * FROM checkpoint_blobs LIMIT 10;"
```

### 认证问题
```bash
# 检查用户验证状态
psql -d docpilot -c "SELECT email, email_verified FROM \"user\";"

# 手动验证邮箱
psql -d docpilot -c "UPDATE \"user\" SET email_verified=true WHERE email='...';"
```
