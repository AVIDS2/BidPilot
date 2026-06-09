# BidPilot 严格整改方案

> 从"先跑起来"到"企业级 agent 平台"

---

## Design Read

**Reading this as: B2B SaaS for technical buyers (procurement teams, bid managers), with a Linear-style minimalist language, leaning toward shadcn/ui + Tailwind v4 + Geist + restrained motion.**

### Dial Configuration
- DESIGN_VARIANCE: 5 (Offset — clean but not boring)
- MOTION_INTENSITY: 3 (Static — trust-first B2B, no playful animations)
- VISUAL_DENSITY: 5 (Daily App — data-dense but breathable)

---

## Part A: 后端 Agent 工作流整改（LangGraph）

### 现有问题（7 个）
1. retrieval service 和 worker 各自实现检索，架构重复
2. Evidence confidence 用排名启发式，不是真实 cosine similarity
3. Worker 单次运行开 4 个独立 DB session
4. llm.py 和 anthropic_llm.py 大量重复代码
5. DraftResult.evidence_ids 永远是空列表
6. drafting.py 里有死代码 stub
7. LLM 调用无重试，失败直接 fallback stub

### 架构设计：Supervisor + Human-in-the-Loop

```
START → supervisor → rfp_parser → supervisor
                   → knowledge_retriever → supervisor
                   → section_drafter → supervisor
                   → quality_reviewer → human_approval → supervisor → persist_result → END
                                                                  ↘ section_drafter (revision loop)
```

### 6 个 Agent 节点
| 节点 | 职责 | 输入 | 输出 |
|---|---|---|---|
| supervisor | 路由决策（LLM structured output） | 全状态 | next |
| rfp_parser | 解析 RFP → 提取需求 | project_id, section_key | requirements |
| knowledge_retriever | pgvector 检索 + cosine distance | project_id, requirements | evidence_chunks |
| section_drafter | LLM 生成章节（带 retry） | evidence_chunks, requirements, review_feedback | draft_markdown |
| quality_reviewer | LLM 评审（completeness/compliance） | draft_markdown, requirements | review_result |
| human_approval | interrupt() 暂停等用户审核 | draft_markdown, review_result | human_decision |
| persist_result | 写入 DB（单 session） | 所有最终数据 | - |

### State Schema
```python
class BidPilotState(TypedDict):
    project_id: str
    run_id: str
    section_key: str
    review_feedback: str | None
    provider_config_id: str | None
    requirements: list[dict]
    evidence_chunks: list[dict]
    draft_markdown: str | None
    model_used: str
    review_result: dict | None
    iteration: int
    max_iterations: int
    next: str
    human_decision: str | None
    error: str | None
```

### 实施阶段

#### Phase 1: Graph Foundation（3-4 天）
**创建文件：**
- `services/worker/app/graph/__init__.py`
- `services/worker/app/graph/state.py` — BidPilotState
- `services/worker/app/graph/nodes/__init__.py`
- `services/worker/app/graph/nodes/supervisor.py` — 确定性路由（Phase 1 不用 LLM）
- `services/worker/app/graph/nodes/knowledge_retriever.py` — 包装现有 _retrieve_evidence，修复 cosine distance
- `services/worker/app/graph/nodes/section_drafter.py` — 包装 LLM adapter + tenacity 重试
- `services/worker/app/graph/builder.py` — StateGraph 组装 + MemorySaver

**修改文件：**
- `services/worker/app/tasks.py` — graph.invoke() 替代 run_draft()
- `services/worker/pyproject.toml` — 添加 langgraph, langchain-core, tenacity

**验证：** 简化流程 supervisor → knowledge_retriever → section_drafter → FINISH 跑通

#### Phase 2: Quality Review + RFP Parser + Loop（4-5 天）
**创建文件：**
- `services/worker/app/graph/nodes/rfp_parser.py`
- `services/worker/app/graph/nodes/quality_reviewer.py`

**修改文件：**
- `services/worker/app/graph/nodes/supervisor.py` — 升级为 LLM structured output 路由
- `services/worker/app/graph/builder.py` — 添加节点 + 条件边

#### Phase 3: Persist + Evidence Fix（2-3 天）
**创建文件：**
- `services/worker/app/graph/nodes/persist_result.py` — 单 DB session 写入

**修复：**
- Evidence confidence 用真实 cosine_distance
- evidence_ids 不再为空
- DB session 合并为单个

#### Phase 4: Human-in-the-Loop（3-4 天）
**创建文件：**
- `services/worker/app/graph/nodes/human_approval.py` — interrupt()
- `services/api/app/drafting/router.py` — POST /drafting/runs/{run_id}/resume
- `services/api/app/drafting/schemas.py` — ResumeRunRequest

**修改：**
- MemorySaver → PostgresSaver
- 添加 human_approval 节点

#### Phase 5: Cleanup + Tests（3-4 天）
- 删除死代码（drafting.py stub）
- 8 个测试文件
- USE_LANGGRAPH feature flag 移除

### 依赖
```
langgraph>=0.4
langchain-core>=0.3
langchain-openai>=0.3
langchain-anthropic>=0.3
langgraph-checkpoint-postgres>=2.0
tenacity>=9.0
```

### 迁移策略
- USE_LANGGRAPH=1 环境变量切换新旧代码
- 新旧 API 并行，可即时回滚
- API 层完全不变（Phase 1-3），只改 Celery task 内部

---

## Part B: 前端整改（shadcn + taste-skill）

### Design System 确认
- shadcn/ui base-nova ✅（已有）
- Tailwind v4 ✅（已有）
- Geist Variable ✅（已有）
- Lucide icons ✅（已有，taste-skill 建议 Phosphor 但项目已锁定 Lucide，保持一致）
- Dark mode via next-themes ✅（已有）

### taste-skill Dial 应用
BidPilot 是 B2B SaaS，不是营销页。taste-skill 的 Landing Page 规则部分适用（首页），Dashboard/Product UI 部分参考 Section 2.A（shadcn 是正确选择）。

**关键 taste-skill 规则应用：**
1. **Anti-Center Bias** — 首页 hero 不用居中，用 left-aligned + 右侧 product preview
2. **No three-equal feature cards** — 用 bento grid 或 asymmetric layout
3. **No AI-purple gradients** — 用 neutral base + 单一 accent（建议 deep blue 或 emerald）
4. **Section-Layout-Repetition Ban** — 8 个 section 至少 4 种 layout family
5. **Hero fits viewport** — headline ≤ 2 lines, subtext ≤ 20 words
6. **No em-dashes** — 全面禁止
7. **Color Consistency Lock** — 一个 accent 贯穿全站
8. **Shape Consistency Lock** — 统一 corner-radius（shadcn 默认 0.625rem）

### 前端整改清单

#### 1. AI Chat 升级（核心）
**现状：** 有 chat-container + message + prompt-input，但无 streaming、无对话持久化

**整改：**
- [ ] 添加 SSE streaming 支持（EventSource / fetch ReadableStream）
- [ ] 对话历史持久化（Conversation + Message 模型）
- [ ] 消息支持 thumbs up/down 反馈
- [ ] "Regenerate with feedback" 功能
- [ ] Token 使用量显示

**组件来源：** shadcn 已有 chat-container, message, prompt-input, prompt-suggestion, source, markdown, code-block — 直接用

#### 2. Agent 状态可视化（新增）
**现状：** 无。用户看不到 agent 在干什么

**整改：**
- [ ] Agent 进度指示器（当前节点、已完成节点、待执行节点）
- [ ] 实时状态流（SSE 推送 supervisor 路由决策）
- [ ] Review 状态面板（quality_reviewer 的评分 + issues 展示）
- [ ] HITL 审核界面（approve/reject + 反馈输入）

**设计原则：**
- 用 shadcn 的 Progress + Badge + Card 组合
- 状态用 color-coded badges（running=blue, passed=green, failed=red）
- 不用 spinner，用 linear progress with step labels

#### 3. Dashboard 页面（新增）
**现状：** 无全局 dashboard

**整改：**
- [ ] 项目概览卡片（总数、进行中、已完成）
- [ ] 最近活动 feed（最近的 draft、review、export 事件）
- [ ] AI 使用量统计（token 消耗、API 调用次数）
- [ ] 快速操作入口（新建项目、查看待审核）

**布局：** shadcn Card grid，不用 bento（dashboard 是数据密集型，taste-skill 说 dashboard 用 Section 2.A 的设计系统）

#### 4. Command Palette（新增）
**现状：** 无全局搜索

**整改：**
- [ ] Cmd+K 命令面板
- [ ] 搜索项目、章节、需求
- [ ] 快速导航到任意页面
- [ ] 执行操作（新建项目、切换主题）

**组件：** shadcn 有 Dialog + Command 组件

#### 5. Notification System（新增）
**现状：** 占位符 "Coming soon"

**整改：**
- [ ] 通知 bell icon + dropdown
- [ ] 通知类型：draft completed, review approved, export ready, HITL required
- [ ] 已读/未读状态
- [ ] 通知偏好设置

#### 6. 项目详情页重构
**现状：** 11 个 tab，信息过载

**整改：**
- [ ] 合并相关 tab（Bundles + Deliverables → Content, Evidence + Search → Knowledge）
- [ ] 添加 Agent 控制面板 tab（启动 agent、查看进度、审核结果）
- [ ] Breadcrumb 导航优化
- [ ] 移动端 tab 改为 bottom navigation

#### 7. 首页重设计（应用 taste-skill）
**现状：** 基础 hero + 3 equal feature cards（taste-skill 禁止模式）

**整改方案：**
- **Hero:** Left-aligned headline + 右侧 product screenshot（非 div-based fake preview）
- **Features:** Bento grid（2+1 或 asymmetric），不用 3 equal cards
- **Social proof:** Logo wall under hero，用真实 SVG logos
- **How it works:** Sticky-stack 或 zig-zag（max 2 consecutive image+text splits）
- **Pricing:** 保持 3-column 但优化间距和 hierarchy
- **CTA:** 单一 intent，不重复

**taste-skill Pre-Flight Check 通过标准：**
- [ ] ZERO em-dashes
- [ ] Hero fits viewport
- [ ] ≤ ceil(sectionCount/3) eyebrows
- [ ] No section-layout-repetition
- [ ] Color consistency lock
- [ ] Shape consistency lock
- [ ] No AI tells（no purple glow, no Inter, no three-equal cards）

---

## Part C: Agent 方法论对标

### 对标企业级 Agent 平台的标准

| 维度 | 当前状态 | 企业级标准 | 差距 |
|---|---|---|---|
| **状态管理** | 无状态（每次调用独立） | LangGraph StateGraph + checkpoint | 需要重建 |
| **多 Agent 协作** | 单一 RAG 管道 | Supervisor + 专业化 subagents | 需要重建 |
| **Human-in-the-Loop** | 无 | interrupt/resume + 审核 UI | 需要新增 |
| **可观测性** | 日志 | LangSmith tracing + 状态可视化 | 需要新增 |
| **错误处理** | 直接 fallback stub | 重试 + 指数退避 + 降级策略 | 需要修复 |
| **评测** | 无 | 自动化质量评分 + A/B 测试 | 需要新增 |
| **Streaming** | 无 | SSE/WebSocket 实时推送 | 需要新增 |
| **对话记忆** | 无 | 上下文窗口管理 + 摘要 | 需要新增 |

### Agent 开发原则（来自 langgraph-agent-patterns）

1. **Clear Agent Responsibilities** — 每个 agent 职责不重叠
2. **Loop Prevention** — iteration counter + max_iterations
3. **Context Management** — 超长时摘要，只传必要信息
4. **Error Handling** — 验证路由决策，处理无效路由
5. **State Design** — TypedDict，每个字段有明确用途

---

## 执行顺序

### Sprint 1（后端核心，1 周）
Phase 1 + Phase 2：Graph skeleton + core nodes + quality reviewer + draft-review loop

### Sprint 2（后端完善 + 前端 AI，1 周）
Phase 3 + Phase 4：Persist + HITL + streaming + agent 状态可视化

### Sprint 3（前端产品化，1 周）
Dashboard + Command Palette + Notification + 首页重设计

### Sprint 4（测试 + 清理，3-4 天）
Phase 5 + 全面测试 + taste-skill Pre-Flight Check

---

## 依赖清单

### 后端新增
```
langgraph>=0.4
langchain-core>=0.3
langchain-openai>=0.3
langchain-anthropic>=0.3
langgraph-checkpoint-postgres>=2.0
tenacity>=9.0
```

### 前端新增
```
cmdk (command palette)
@radix-ui/react-notification (or sonner, already have)
```

前端基本不需要新增依赖，shadcn 已有的组件足够覆盖所有需求。
