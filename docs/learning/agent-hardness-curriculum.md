# Agent Hardness Curriculum — 从「调 API」到「生产级 Agent 工程师」

> 五条老师笔记原话：「我们之前太过聚焦于 harness 脚手架、loop，却忽略了大模型底层。」
> 这份文档就是补那块板的全景地图。

---

## 一、你刷到的名词 → 标准术语 → BidPilot 现状

| # | 你提到的 | 业界标准术语 | BidPilot 现状 | 学哪里 |
|---|---------|-------------|--------------|--------|
| 1 | 调 API 不叫 AI 工程 | **LLM API Integration** | ✅ 多 provider、BYOK、streaming | courses: `anthropic_api_fundamentals/` |
| 2 | harness 脚手架 | **Agent Harness / Agent Runtime** | ✅ `StreamingHarness` + hooks + registry | learn-claude-code: s01–s05 |
| 3 | 上下文治理 | **Context Engineering** | ⚠️ 有 memory_context_records 但无自动压缩 | learn-claude-code: **s08** + cookbooks: `tool_use/automatic-context-compaction.ipynb` |
| 4 | 提示词工程 | **Prompt Engineering** | ⚠️ system prompt 硬编码，无模板组装 | courses: `prompt_engineering_interactive_tutorial/` |
| 5 | 注意力稀释 | **Attention Dilution / Lost-in-the-Middle** | ⚠️ 长对话无摘要，靠 context pack 人工控制 | learn-claude-code: **s08**, **s10** |
| 6 | 首字响应延迟 | **TTFT (Time To First Token)** | ⚠️ 无 TTFT 监控/优化 | cookbooks: `extended_thinking/`, 需自建 |
| 7 | 长期记忆与短期记忆 | **Long-term Memory / Working Memory / Episodic Memory** | ⚠️ glossary 有定义，无自动提取层 | learn-claude-code: **s09** + cookbooks: `tool_use/memory_cookbook.ipynb` |
| 8 | Memory 设计 | **Memory Architecture** (筛选→提取→整理三子系统) | ⚠️ 只有 manual memory_context_records 注入 | learn-claude-code: **s09** |
| 9 | agent 架构优化 | **Multi-Agent Patterns** (supervisor/router/orchestrator/handoff) | ✅ campaign multi-wave + planner-worker | learn-claude-code: s15–s17 |
| 10 | 大小模型协同 | **Model Cascade / Cascade Routing / Speculative Execution** | ❌ 未实现（小模型分类 + 大模型执行） | cookbooks: patterns + 自建 |
| 11 | 模型推理加速 | **Inference Optimization** (KV-cache, quantization, speculative decoding, batch) | ❌ 调 API 不可控；自部署时需考虑 | cookbooks: `extended_thinking/`, WebSearch |
| 12 | 模型部署/微调 | **Model Deployment / Fine-tuning / RLHF / DPO** | ❌ 调 API，未自训 | courses: `finetuning/` (如果存在), cookbooks: `finetuning/` |
| 13 | Transformer 基础 | **Transformer Architecture** (attention, FFN, positional encoding) | ❌ 不阻塞 harness，但面试需要 | courses: 自行补充 |
| 14 | OCR 图片识别 | **Multimodal / Vision** (PDF OCR, image understanding) | ❌ 未实现 | cookbooks: `multimodal/` |
| 15 | Sandbox 沙箱设计 | **Sandbox Isolation** (Docker/nsjail/Firecracker/工作目录隔离) | ⚠️ 工具只读过滤，无 OS 级隔离 | learn-claude-code: s03 (permission) + s18 (worktree) |
| 16 | Checkpoint 机制 | **Execution Checkpoint / State Snapshot** | ✅ RuntimeRun + RuntimeEvent + after_sequence cursor | learn-claude-code: 无独立章节（s12 task 涉及），LangGraph 官方 |
| 17 | Redis 缓存/队列 | **Backend Infrastructure** (Redis cache, Celery queue, Postgres) | ✅ 已部署 Redis + Celery + Postgres | 常规后端知识 |
| 18 | 复杂微服务 | **Service Architecture** (API/Worker 分离) | ✅ api + worker 分离，非 microservice 但够用 | 常规后端知识 |
| 19 | HITL 审批 | **Human-in-the-Loop** (interrupt, approval gate, confirmation) | ✅ `resume_approval` + confirmation flow | learn-claude-code: s03 |
| 20 | Eval / 评测 | **Evaluation / Benchmarking** (task success, citation faithfulness, retrieval recall) | ⚠️ 有 stress smoke + AssistantBench 骨架，无自动 eval pipeline | learn-claude-code: 无独立章 + cookbooks: `evals/` |
| 21 | Observability / 可观测 | **Tracing / Spans / Metrics / Logging** | ⚠️ 有 RuntimeEvent 但无 span-level tracing | cookbooks: `observability/` |
| 22 | RAG 检索增强生成 | **RAG / Hybrid Retrieval / Reranker** | ✅ dense (pgvector) + sparse (FTS) + RRF | cookbooks: `capabilities/retrieval_augmented_generation/` |
| 23 | Skills 按需加载 | **Skill / Instruction Loading** | ✅ `docs/agent-skills/` + runtime skills.py | learn-claude-code: **s07** |
| 24 | 外部工具协议 | **MCP (Model Context Protocol)** | ✅ `bidpilot_mcp.py` FastMCP | learn-claude-code: **s19** |
| 25 | 权限治理 | **Permission Governance** (deny-list, allow-list, capability check) | ✅ `execute_capability` + RBAC/ABAC | learn-claude-code: **s03** |

---

## 二、「Agent 硬度」六层模型

你笔记里的「agent 硬度」和「后端硬度」，按面试/生产重要性排列：

```
┌─────────────────────────────────────────────────────────┐
│  Layer 6: 产品治理 (Product Governance)                    │
│  多租户 / RBAC / 审计 / 合规 / SLO / 成本追踪              │
├─────────────────────────────────────────────────────────┤
│  Layer 5: 可观测与评测 (Observability & Eval)               │
│  Trace / Span / Metrics / Eval pipeline / A/B            │
├─────────────────────────────────────────────────────────┤
│  Layer 4: Harness 工程 (Agent Runtime)                    │
│  Loop / Tools / Hooks / Skills / Campaign / HITL / MCP  │
├─────────────────────────────────────────────────────────┤
│  Layer 3: 上下文工程 (Context Engineering)                 │
│  Prompt assembly / Memory / Compression / Attention Mgmt │
├─────────────────────────────────────────────────────────┤
│  Layer 2: 模型交互工程 (Model Interaction)                  │
│  Streaming / TTFT / Provider routing / Cache / Cascade  │
├─────────────────────────────────────────────────────────┤
│  Layer 1: 模型基础 (Model Fundamentals)                    │
│  Transformer / Attention / Tokenization / Fine-tuning    │
│  Quantization / Inference / KV-cache                     │
└─────────────────────────────────────────────────────────┘
```

**BidPilot 现状：Layer 4 做得不错，Layer 1–3 和 5 有硬缺口。**

---

## 三、学习路线（12 周）

### Phase 0: 模型底子（2 周）— 面试保命

> 企业现在需要「看得懂模型参数的人」。

| 周 | 学什么 | 怎么学 | BidPilot 对照 |
|----|--------|--------|--------------|
| W1 | Transformer 原理：attention / FFN / positional encoding / tokenizer | Karpathy "Let's build GPT" 视频 + courses `anthropic_api_fundamentals/` 前半 | — |
| W2 | 推理概念：KV-cache / quantization / speculative decoding / batch / TTFT | cookbooks `extended_thinking/` + WebSearch「inference optimization 101」 | TTFT monitoring → 新增 |

**面试回报：** 能回答「为什么流式快？」「什么是 KV-cache？」「量化有什么 trade-off？」——这些是 AI 岗高频题。

### Phase 1: 上下文工程（3 周）— 核心竞争力

> 「上下文工程」是 2025-2026 agent 面试最高频新词。

| 周 | 学什么 | learn-claude-code | BidPilot 对照 |
|----|--------|-------------------|--------------|
| W3 | Context Compaction 四层策略 | **s08** 跑 `code.py` | 无自动压缩 → 需实现 |
| W4 | Memory 三子系统 + 短/长期记忆 | **s09** + cookbooks `tool_use/memory_cookbook.ipynb` | 只有手动注入 → 需自动提取层 |
| W5 | Prompt Assembly + System Prompt 组装 | **s10** + courses `prompt_engineering_interactive_tutorial/` | system prompt 硬编码 → 需模块化 |

**面试回报：** 能白板画「agent 的上下文怎么管」+ 说清「attention dilution 怎么解」= agent 岗核杀器。

### Phase 2: Harness 补全（3 周）— BidPilot 硬度

> 你已经有了很多，只缺几个关键件。

| 周 | 学什么 | learn-claude-code | BidPilot 动作 |
|----|--------|-------------------|--------------|
| W6 | Subagent + 上下文隔离 | **s06** | campaign 已有 worker，补 clean context per worker |
| W7 | Error Recovery + 长任务 | **s11** + **s13** (background) | harness_loop 有重试，补 exponential backoff + circuit breaker |
| W8 | Multi-agent 协调 + 自组织 | **s15** + **s16** + **s17** | campaign 已有，补 team protocol 通信格式 |

### Phase 3: 模型交互工程（2 周）— 生产硬度

> 从「调 API」升级到「管模型」。

| 周 | 学什么 | 来源 | BidPilot 动作 |
|----|--------|------|--------------|
| W9 | 大小模型协同 (Model Cascade) | cookbooks `patterns/agents/` + 自建 | 实现：小模型分类意图 → 大模型执行，省 token 40-60% |
| W10 | Provider routing + 降级 + 成本追踪 | 自建 + cookbooks `tool_use/tool_choice.ipynb` | 完善 BYOK fallback + 用量 dashboard |

### Phase 4: 可观测与评测（2 周）— 从 demo 到生产

> 「猴子拿枪」和「生产级」的区别就在这。

| 周 | 学什么 | 来源 | BidPilot 动作 |
|----|--------|------|--------------|
| W11 | Trace / Span / Metrics | cookbooks `observability/` | RuntimeEvent → OpenTelemetry span bridge |
| W12 | Eval pipeline + 回归测试 | cookbooks `evals/` + `tool_evaluation/` | AssistantBench 扩展 + 自动化 CI eval |

### 可选补充（按需）

| 主题 | 何时学 | 来源 |
|------|--------|------|
| 多模态 / OCR / Vision | 当投标文件需要 OCR 时 | cookbooks `multimodal/` |
| Fine-tuning / RLHF / DPO | 当需要定制模型行为时 | cookbooks `finetuning/` |
| Sandbox OS 级隔离 | 当需要执行用户上传代码时 | Docker/nsjail + learn-claude-code s18 |

---

## 四、企业面试高频考点对照

### AI Agent 岗

| 高频题 | 你答什么 | 考的硬度层 |
|--------|---------|-----------|
| 「agent 循环怎么设计？」 | ReAct loop + stop_reason + tool dispatch | Layer 4 |
| 「上下文窗口满了怎么办？」 | 四层压缩：trim → merge → LLM summary → emergency cut | Layer 3 |
| 「长任务怎么做？」 | Task system + checkpoint + background + wake | Layer 4 |
| 「多 agent 怎么协调？」 | Supervisor/Router/Orchestrator 模式 + 事件邮箱 | Layer 4 |
| 「工具调用安全怎么管？」 | Permission pipeline (deny → approve → allow) + capability check | Layer 6 |
| 「RAG 怎么做？」 | Dense (pgvector) + sparse (FTS) + RRF + reranker | Layer 3 |
| 「agent 评测怎么做？」 | Task success rate / citation faithfulness / tool accuracy / eval pipeline | Layer 5 |
| 「首字延迟怎么优化？」 | Streaming + KV-cache + speculative decoding + prompt cache | Layer 2 |
| 「怎么防止 attention 稀释？」 | Context compaction + todo reminder injection + subagent isolation | Layer 3 |
| 「大小模型怎么配合？」 | Cascade routing：小模型分类/摘要 → 大模型执行复杂推理 | Layer 2 |

### 后端/全栈岗补充

| 高频题 | BidPilot 答案 |
|--------|--------------|
| 「Redis 怎么用？」 | 缓存 + Celery broker + 未来 rate limiting |
| 「消息队列？」 | Celery + Redis，异步 draft/export/harvest |
| 「数据库设计？」 | Postgres + pgvector + 多租户 RBAC + idempotency key |
| 「API 设计？」 | FastAPI + Pydantic + SSE streaming + event replay cursor |
| 「部署？」 | Docker Compose + VPS + dual-mode deploy script |
| 「如何保证幂等？」 | `(run_id, action_key)` unique constraint |

---

## 五、你的日志 → 术语翻译

你之前的笔记原文，逐句翻译成标准术语：

| 你的原话 | 标准术语 | 在六层模型哪层 |
|---------|---------|--------------|
| 大模型基本的部署，微调 | Model Deployment + Fine-tuning (SFT / RLHF / DPO) | Layer 1 |
| 基础 transformer 知识 | Transformer Architecture (Attention, FFN, Tokenization) | Layer 1 |
| 大小模型协同设计 | Model Cascade / Cascade Routing | Layer 2 |
| 上下文治理 | Context Engineering | Layer 3 |
| memory 设计 | Memory Architecture (working / episodic / semantic / procedural) | Layer 3 |
| 长期记忆与短期记忆 | Long-term Memory (file/DB) vs Working Memory (in-context) | Layer 3 |
| OCR 图片识别模型 | Multimodal Vision / Document Understanding | Layer 1 (model) + Layer 4 (harness tool) |
| 非简单 API 调用 | Agent Harness + Tool Orchestration | Layer 4 |
| 首字响应延迟 | TTFT (Time To First Token) | Layer 2 |
| 提示词工程 | Prompt Engineering + Context Assembly | Layer 3 |
| 注意力稀释问题 | Attention Dilution / Lost-in-the-Middle Problem | Layer 3 |
| agent 架构优化 | Multi-Agent Patterns (Supervisor / Router / Orchestrator) | Layer 4 |
| 大模型推理加速 | Inference Optimization (KV-cache / Quant / Speculative Decoding) | Layer 1 |
| sandbox 沙箱设计 | Sandbox Isolation (Docker / nsjail / Firecracker / worktree) | Layer 4 |
| checkpoint 机制 | Execution Checkpoint / State Snapshot | Layer 4 |
| Redis 缓存，队列 | Backend Infra (Redis cache + Celery/RQ queue) | 后端通用 |
| 复杂微服务 | Service Architecture (API / Worker / Gateway separation) | 后端通用 |

---

## 六、learn-claude-code 章节 ↔ BidPilot 实现对照

| 章节 | 主题 | BidPilot 有对应吗 | 差距 |
|------|------|------------------|------|
| s01 | Agent Loop | ✅ `StreamingHarness.run()` | 完全对齐 |
| s02 | Tool Use / Dispatch | ✅ `TOOL_HANDLERS` registry | 完全对齐 |
| s03 | Permission | ✅ `execute_capability` + RBAC | 完全对齐 |
| s04 | Hooks | ✅ `hook_manager` + pre/post tool hooks | 完全对齐 |
| s05 | TodoWrite / Planning | ⚠️ campaign 有 step plan，无 todo reminder injection | 小补 |
| s06 | Subagent / Context Isolation | ⚠️ campaign workers 有，无 clean context per subagent | 中补 |
| s07 | Skill Loading | ✅ `docs/agent-skills/` + runtime skills.py | 完全对齐 |
| s08 | Context Compaction | ❌ 无自动压缩，只有手动 memory_context_records | **大缺** |
| s09 | Memory (筛选→提取→整理) | ❌ 无自动提取层 | **大缺** |
| s10 | System Prompt Assembly | ❌ 硬编码 prompt | 中缺 |
| s11 | Error Recovery | ⚠️ 有 retry，无 exponential backoff / circuit breaker | 中补 |
| s12 | Task System | ✅ RuntimeRun + RuntimeEvent | 对齐 |
| s13 | Background Tasks | ✅ Celery + agent wake | 对齐 |
| s14 | Cron Scheduler | ⚠️ 无 agent-level cron（Celery beat 有） | 小补 |
| s15 | Agent Teams / Mailbox | ❌ 无异步邮箱，campaign 是同步编排 | 中缺 |
| s16 | Team Protocols | ❌ 无固定通信格式 | 小缺 |
| s17 | Autonomous / Self-organize | ❌ 无自组织认领 | 低优先 |
| s18 | Worktree Isolation | ⚠️ 工具只读过滤，无 OS 级隔离 | 小补 |
| s19 | MCP | ✅ `bidpilot_mcp.py` | 对齐 |
| s20 | Comprehensive | — | — |

**最大缺口：s08 Context Compaction + s09 Memory Architecture + s10 System Prompt Assembly。**
**这三章恰恰是「上下文工程」的核心，也是面试最高频考点。**

---

## 七、下一步建议

### 立即可做（本周）

1. **跑 learn-claude-code s01–s05** — 你已经实现了，用来「对上暗号」确认理解
2. **开 s08 Context Compaction** — 这是 BidPilot 最大缺口，也是面试最值钱的技能

### 短期（2 周内）

3. 在 BidPilot 实现自动上下文压缩（TokenBudgetPreprocessor → MergePreprocessor → LLMCompact → EmergencyTrim）
4. 补 Memory 自动提取层（每轮结束提取用户偏好/关键事实）

### 中期（1 个月内）

5. 大小模型协同（小模型分类 → 大模型执行）
6. Eval pipeline 自动化
7. TTFT 监控

---

## 八、参考仓库路径

| 仓库 | 本地路径 | 重点看 |
|------|---------|--------|
| learn-claude-code | `E:\my_idea_cc\agent-learning\learn-claude-code\` | s08, s09, s10, s11, s15 |
| claude-cookbooks | `E:\my_idea_cc\agent-learning\claude-cookbooks\` | `tool_use/memory_cookbook.ipynb`, `tool_use/automatic-context-compaction.ipynb`, `evals/`, `observability/` |
| courses | `E:\my_idea_cc\agent-learning\courses\` | `anthropic_api_fundamentals/`, `prompt_engineering_interactive_tutorial/` |
| BidPilot | `E:\my_idea_cc\BidPilot\` | `services/api/app/runtime/harness_loop.py`, `docs/learning/agent-engineering-glossary.md` |

---

*文档版本：v1.0*
*创建时间：2026-07-25*
*维护者：五条老师团队*
