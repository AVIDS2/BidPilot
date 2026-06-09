# BidPilot LangGraph Agent 工作流架构

## 概述

BidPilot 使用 LangGraph 实现有状态的多 agent 工作流，替代原有的简单 RAG 管道。核心是一个 StateGraph，包含 7 个节点（agent），通过 supervisor 路由实现自动编排，支持 draft-review 循环和 human-in-the-loop 审核。

## 架构图

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  supervisor │ ◄──────────────────────────┐
                    └──────┬──────┘                            │
                           │                                   │
              ┌────────────┼────────────┐                      │
              │            │            │                      │
     ┌────────▼───┐  ┌─────▼─────┐  ┌──▼──────────┐          │
     │ rfp_parser │  │knowledge_ │  │section_     │          │
     │            │  │retriever  │  │drafter      │          │
     └────────┬───┘  └─────┬─────┘  └──┬──────────┘          │
              │            │            │                      │
              └────────────┼────────────┘                      │
                           │                                   │
                    ┌──────▼──────┐                            │
                    │  quality_   │                            │
                    │  reviewer   │                            │
                    └──────┬──────┘                            │
                           │                                   │
                    ┌──────▼──────┐                            │
                    │   human_    │ (interrupt)                │
                    │  approval   │────────────────────────────┘
                    └──────┬──────┘    (rejected + feedback)
                           │
                           │ (approved)
                    ┌──────▼──────┐
                    │  persist_   │
                    │  result     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    END      │
                    └─────────────┘
```

## 节点说明

### supervisor（路由节点）
- **职责：** 根据状态决定下一步执行哪个 agent
- **路由逻辑：**
  - 无 requirements → rfp_parser
  - 无 evidence → knowledge_retriever
  - 无 draft → section_drafter
  - 有 draft 无 review → quality_reviewer
  - review 通过 → human_approval
  - human approved → persist_result
  - human rejected + iteration < max → section_drafter（带 feedback）
  - iteration >= max → persist_result（强制完成）

### rfp_parser（RFP 解析 agent）
- **职责：** 查询 ParsedAsset.content_json，用 LLM 提取结构化需求
- **输入：** project_id, section_key
- **输出：** requirements (list[dict])
- **降级：** LLM 失败时用正则模式匹配

### knowledge_retriever（知识检索 agent）
- **职责：** pgvector cosine_distance 检索相关知识块
- **输入：** project_id, section_key, requirements
- **输出：** evidence_chunks (list[dict])，包含真实 cosine distance 分数
- **降级：** ILIKE 文本搜索 → 项目全量块

### section_drafter（章节撰写 agent）
- **职责：** 调用 LLM 生成投标章节
- **输入：** evidence_chunks, requirements, review_feedback, provider_config_id
- **输出：** draft_markdown, draft_model_used
- **重试：** tenacity 3 次指数退避
- **降级：** LLM 失败时返回 stub draft

### quality_reviewer（质量评审 agent）
- **职责：** LLM 评审 draft 的完整性、合规性、证据使用
- **输入：** draft_markdown, requirements, evidence_chunks
- **输出：** review_result (passed/issues/suggestions/overall_score)
- **降级：** LLM 失败时用确定性启发式检查

### human_approval（人工审核节点）
- **职责：** interrupt() 暂停图执行，等待用户审核
- **输入：** draft_markdown, review_result
- **输出：** human_decision, review_feedback
- **机制：** LangGraph interrupt + resume

### persist_result（持久化节点）
- **职责：** 单 DB session 写入所有结果
- **操作：** 创建 SectionVersion + Evidence 记录 + 更新 ExecutionRun
- **修复：** evidence confidence 用真实 cosine_distance（不是排名启发式）

## 状态模型

```python
class BidPilotState(TypedDict):
    # 标识
    project_id: str
    section_key: str
    run_id: str
    provider_config_id: str | None
    review_feedback: str | None

    # RFP 解析
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
    iteration: int
    max_iterations: int
    error: str | None
```

## 集成方式

### Celery Task 集成
```python
# services/worker/app/tasks.py
_USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "0").lower() in ("1", "true", "yes")

@celery_app.task(name="worker.draft_section")
def draft_section(run_id, project_id, section_key, ...):
    if _USE_LANGGRAPH:
        from app.graph.builder import invoke_graph
        result = invoke_graph(project_id=project_id, section_key=section_key, run_id=run_id, ...)
    else:
        from app.execution.drafting import run_draft
        result = run_draft(run_id, project_id, section_key, ...)
```

### Feature Flag
- `USE_LANGGRAPH=1` 启用 LangGraph 路径
- 默认关闭，保持向后兼容
- 可即时回滚

## 依赖

```
langgraph>=0.4.0
langchain-core>=0.3.0
langchain-openai>=0.3.0
langchain-anthropic>=0.3.0
langgraph-checkpoint-postgres>=2.0.0
tenacity>=9.0.0
```

## 文件结构

```
services/worker/app/graph/
├── __init__.py
├── state.py          # BidPilotState TypedDict
├── builder.py        # StateGraph 组装 + 编译
└── nodes/
    ├── __init__.py
    ├── supervisor.py       # 路由节点
    ├── rfp_parser.py       # RFP 解析
    ├── knowledge_retriever.py  # 知识检索
    ├── section_drafter.py  # 章节撰写
    ├── quality_reviewer.py # 质量评审
    ├── human_approval.py   # 人工审核（interrupt）
    └── persist_result.py   # 持久化
```

## 测试策略

### Layer 1: 节点单元测试
- mock DB session 和 LLM adapter
- 验证每个节点读取正确的 state 字段并写入正确的输出

### Layer 2: 路由测试
- 验证 supervisor 在不同 state 配置下走正确的边
- 测试 draft-review 循环

### Layer 3: 集成测试
- 全图运行，所有节点 mock
- 验证 START → END 的完整状态转换

### Layer 4: API 测试
- /resume 端点测试
- SSE streaming 端点测试
