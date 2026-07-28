# Agent 工程师完全手册 — 面试 + 学习 + BidPilot 对照

> 更新时间：2026-07-26
> 目标：Agent 开发 / AI 应用开发 / AI 全栈 / 后端开发实习
> 一份文档覆盖：术语、技能树、JD 需求、框架对比、面经、学习路线、BidPilot 对照

---

# 目录

- **Part 1** — 市场认知：岗位要什么人
- **Part 2** — 国内 JD 真实需求
- **Part 3** — 完整技能树（19 项，按优先级）
- **Part 3B** — 后端 + AI 全栈认知地图
- **Part 4** — Agent 框架深度对比
- **Part 5** — 六层硬度模型 + 学习路线
- **Part 6** — 术语表（70+ 词条）
- **Part 7** — BidPilot 缺口 + learn-claude-code 章节对照
- **Part 8** — 面试速查表 + 面经高频题
- **Part 9** — 学习资源索引

---

# Part 1 — 市场认知

## 岗位需求变化

```
2024：  会调 API → AI 工程师
2025：  会造 Harness + 懂上下文工程 + 有评测思维 → Agent 工程师
2026：  上述全部 + 懂模型基础 + 会部署推理 + 理解安全合规 → 生产级 AI 工程师
```

## 岗位名称对照

| 岗位 | 核心要求 | BidPilot 匹配度 |
|------|---------|----------------|
| Agent 开发工程师 | Harness + 上下文工程 + 多 Agent | ★★★★☆ |
| AI 应用开发工程师 | RAG + Tool Use + API 集成 + 部署 | ★★★★☆ |
| AI 全栈工程师 | 前端 + 后端 + LLM 集成 + 部署 | ★★★★★ |
| 后端开发 (AI 方向) | FastAPI/Node + DB + 队列 + LLM 管道 | ★★★★★ |
| AI 平台工程师 | 推理部署 + 模型管理 + 监控 + MLOps | ★★☆☆☆ |

---

# Part 2 — 国内 JD 真实需求（2026.7 最新）

> 来源：Boss直聘、牛客、实习僧、知乎面经、小红书面经

## 四类岗位共性要求

| 要求 | Agent 开发 | AI 应用开发 | AI 全栈 | 后端(AI方向) |
|------|-----------|------------|--------|-------------|
| 学历 | 本科+(硕士优先) | 本科+ | 本科+ | 本科+ |
| 时长 | ≥3-6月，≥4天/周 | ≥3月 | ≥3月 | ≥3月 |
| 必须语言 | Python | Python | Python + JS/TS | Python/Java/Go |
| 必须框架 | LangChain 或 LangGraph | LangChain/LlamaIndex | React/Vue + FastAPI | FastAPI/Flask/Django |
| 必须知识 | LLM 原理 + Agent 架构 | RAG + Prompt Engineering | 全栈 + LLM 集成 | DB + Queue + API |
| 加分项 | MCP/Multi-Agent/微调 | 向量DB/评测/部署 | Docker/CI/CD/云 | Redis/Docker/K8s |

## JD 任职要求（按出现频率）

**几乎每个 JD 都写（必须）：**
1. 熟练掌握 Python
2. 了解大语言模型基本原理（Transformer / Attention / Tokenization）
3. 熟悉至少一个 Web 框架（FastAPI / Flask / Django）
4. 熟悉 MySQL / PostgreSQL / Redis
5. 了解 Git / Docker / Linux

**高频出现（加分明显）：**
6. 熟悉 LangChain / LlamaIndex / Dify 等 LLM 应用开发框架
7. 有 RAG 系统搭建经验
8. 了解向量数据库（Milvus / FAISS / Chroma / Pinecone）
9. 熟悉 Prompt Engineering / Function Calling / Tool Use
10. 有实际 LLM 项目或竞赛经验

**2025-2026 新增热门：**
11. 了解 MCP 协议
12. 了解 Multi-Agent 协作框架
13. 了解 Agent 记忆机制
14. 了解模型微调（LoRA / QLoRA / SFT）
15. 了解 Dify / Coze 等低代码 AI 平台

**部分岗位要求（高级）：**
16. 了解 vLLM / TensorRT-LLM 等推理部署框架
17. 了解多模态大模型
18. 了解 OpenTelemetry / LangSmith 等可观测工具
19. 有 GPU 推理/模型部署经验

## 国产 AI 生态（必须知道）

| 类别 | 工具 | 你需要知道 |
|------|------|-----------|
| 国产大模型 | DeepSeek / Qwen / 文心 / 混元 / GLM / Kimi | 知道名字 + API；DeepSeek 价格低、Qwen 多模态强 |
| 低代码 AI 平台 | Dify / Coze（扣子）/ FastGPT | 知道是什么 + 和纯代码框架区别 |
| Agent 平台 | 百度千帆 / 阿里百炼 / 字节 Coze | 知道国内厂商 Agent 平台生态 |
| 向量数据库 | Milvus / FAISS / Weaviate / Chroma / pgvector | Milvus 国内最流行 |
| 部署推理 | vLLM / llama.cpp / Ollama / Xinference | 知道怎么本地跑开源模型 |
| 模型训练 | Hugging Face / 魔搭（ModelScope）/ Unsloth | 魔搭是阿里的模型社区 |

## Dify/Coze vs LangChain 对比

| 维度 | Dify | Coze（扣子） | LangChain/LangGraph |
|------|------|-------------|---------------------|
| 定位 | 低代码 AI 应用平台 | 零代码 AI Bot 平台 | 开发者框架/库 |
| 开发方式 | 可视化 + 少量代码 | 零代码拖拽 | 纯代码 |
| 目标用户 | 开发者/半技术人员 | 非技术人员/运营 | 专业开发者 |
| 灵活性 | 中等 | 较低 | **非常高** |
| 开源 | ✅ | ❌ 闭源 SaaS | ✅ |
| 私有化部署 | ✅ | ❌ | ✅ |

## 国产大模型对比

| 模型 | 团队 | 特点 | 定价 |
|------|------|------|------|
| DeepSeek-V3/R1 | 幻方量化 | 价格屠夫、推理强、开源 | ~1元/百万token |
| Qwen (通义千问) | 阿里 | 多模态强、生态完善 | 有免费额度 |
| 文心一言 | 百度 | 千帆平台、Agent 能力 | 中等 |
| 混元 | 腾讯 | 腾讯云集成 | 中等 |
| GLM | 智谱 | 开源、学术认可度高 | 较低 |
| Kimi | 月之暗面 | 超长上下文、搜索增强 | 中等 |

## 实习薪资参考

- 一线城市本科：¥200-350/天
- 硕士：¥300-500/天
- 头部大厂/AI 公司硕士：¥400-800/天

## 招聘企业

| 类型 | 公司 |
|------|------|
| 大厂 | 字节跳动、阿里、腾讯、百度、美团、京东、华为、小米、网易 |
| AI 公司 | 智谱AI、月之暗面(Kimi)、百川智能、零一万物、MiniMax、DeepSeek |
| 独角兽 | 商汤科技、科大讯飞、第四范式 |
| 金融科技 | 蚂蚁集团、平安科技 |

---

# Part 3 — 完整技能树（19 项）

## P0：必须掌握（面试必问 + 日常必用）

### 1. Prompt Engineering 提示词工程

- **是什么：** 设计给 LLM 的输入文本，控制输出行为
- **核心技巧：** Zero-shot / Few-shot / CoT（链式思维）/ ReAct（推理+行动）
- **术语：** System Prompt / User Prompt / Temperature / Top-P / Max Tokens
- **场景：** 所有 LLM 应用的第一步
- **时效性：** ⚠️ 单独的「prompt 工程师」岗位萎缩，进化为「上下文工程」，但技能永不过时
- **学哪里：** courses: `prompt_engineering_interactive_tutorial/`

### 2. RAG — 检索增强生成

- **是什么：** 先从知识库检索相关文档，再让 LLM 基于结果生成回答
- **完整流程：** 文档解析 → 分块(Chunking) → Embedding → 向量存储 → 检索 → 重排(Rerank) → 生成
- **术语：** Chunking / Embedding / Vector DB / ANN / HNSW / RRF / Reranker / Grounding / Citation
- **场景：** 知识库问答、文档搜索、投标文件检索
- **时效性：** 🔥 最高频 AI 架构，没有过时趋势
- **BidPilot：** ✅ 已实现 pgvector dense + FTS sparse + RRF + Reranker

### 3. Tool Use / Function Calling

- **是什么：** LLM 输出结构化的「我要调工具」请求，由 harness 执行后结果喂回模型
- **术语：** Function Calling / Tool Use / Tool Schema / Parallel Tool Calls
- **场景：** Agent 的核心能力——没有工具的 LLM 只是聊天机器人
- **时效性：** 🔥 永不过时
- **BidPilot：** ✅ `TOOL_HANDLERS` registry + `execute_capability`

### 4. Agent Loop / ReAct 范式

- **是什么：** 模型推理 → 选择工具 → 执行 → 观察结果 → 继续推理
- **术语：** ReAct / Agent Loop / Stop Reason / Tool Dispatch / Max Iterations
- **时效性：** 🔥 Agent 的「心脏」
- **BidPilot：** ✅ `StreamingHarness.run()`

### 5. LLM 基础知识

- **必须知道：** Transformer / Self-Attention / Tokenizer / Context Window / Temperature / Streaming
- **加分项：** KV-Cache / Positional Encoding (RoPE, ALiBi) / Quantization / Speculative Decoding
- **时效性：** 🔥 Transformer 架构短期不会被替代

## P1：重要技能（面试加分 + 生产需要）

### 6. Context Engineering 上下文工程 ⭐ 2025-2026 最热新词

- **是什么：** 从「Prompt Engineering」进化而来——设计整个 LLM 的信息环境
- **核心子题：** Context Compaction（压缩）/ Memory Architecture（记忆）/ Prompt Assembly（组装）/ Attention Management
- **和 Prompt Engineering 区别：** Prompt = 写好一句话；Context = 管好整个信息管道
- **术语：** Context Window / Context Budget / Lost-in-the-Middle / Attention Dilution / Working Memory
- **时效性：** 🔥🔥🔥 最热的 Agent 工程术语
- **学哪里：** learn-claude-code s08 + s09 + s10

### 7. Memory Architecture 记忆架构

- **四种记忆：** Working（当前上下文）/ Episodic（任务历史）/ Semantic（稳定事实）/ Procedural（操作流程）
- **术语：** Long-term Memory / Short-term Memory / Memory Store / Memory Consolidation
- **时效性：** 🔥 核心能力
- **学哪里：** learn-claude-code s09 + cookbooks `tool_use/memory_cookbook.ipynb`

### 8. Multi-Agent 多 Agent 协作

- **核心模式：** Supervisor（主管分配）/ Router（路由分类）/ Orchestrator-Worker（编排-工人）/ Handoff（接力）
- **术语：** Agent Team / Supervisor / Orchestrator / Worker / Message Bus
- **时效性：** 🔥 快速增长
- **BidPilot：** ✅ campaign multi-wave

### 9. Fine-tuning 微调

- **核心方法：** SFT / RLHF / DPO / GRPO
- **参数高效：** LoRA（低秩适配）/ QLoRA（4-bit + LoRA）/ PEFT
- **工具：** Hugging Face PEFT / Unsloth（2x 快 70% 省显存）/ Axolotl
- **决策框架：**
  - 快速原型 → Prompt Engineering
  - 私有/动态数据 → RAG
  - 特定格式/风格 → Fine-tuning
  - 领域知识 → RAG + Fine-tuning 混合
  - 降成本 → Fine-tune 小模型
- **时效性：** ⚠️ 热度在降，被 RAG + Context Engineering 侵蚀

### 10. Vector Database 向量数据库

- **是什么：** 专门存储和检索向量（Embedding）的数据库
- **术语：** Embedding / ANN / HNSW / IVF / PQ / Cosine Similarity
- **选择：** pgvector / Milvus / Qdrant / ChromaDB / Weaviate / Pinecone
- **BidPilot：** ✅ pgvector

## P2：加分技能（区分度高 + 未来趋势）

### 11. MCP — Model Context Protocol

- **是什么：** Anthropic 的开放协议——AI 的 USB-C 口
- **三大能力：** Tools（可调用工具）/ Resources（可读取数据）/ Prompts（可注入提示）
- **Transport：** stdio / SSE / Streamable HTTP
- **和 Function Calling 区别：** FC 是模型内部机制；MCP 是外部协议标准
- **BidPilot：** ✅ `bidpilot_mcp.py` (FastMCP)

### 12. A2A — Agent-to-Agent Protocol

- **是什么：** Google 2025.4 提出——Agent 之间互相发现和通信
- **和 MCP 区别：** MCP = Agent↔工具；A2A = Agent↔Agent
- **时效性：** ⚠️ 很新，观察期

### 13. Evaluation / 评测

- **评测层次：** ① 组件级 ② 端到端 ③ 人工 ④ LLM-as-Judge
- **知名 Benchmark：** GAIA / AgentBench / SWE-bench / HumanEval / MMLU
- **工具：** LangSmith / Langfuse / Braintrust / Arize Phoenix
- **时效性：** 🔥 「没有 eval 的 Agent 是 demo，不是产品」

### 14. Observability / 可观测性

- **三大支柱：** Traces（追踪）+ Metrics（指标）+ Logs（日志）
- **术语：** Trace / Span / OpenTelemetry / LangSmith / Langfuse
- **时效性：** 🔥 OTel GenAI 约定正在成为标准

### 15. Sandbox / 沙箱隔离

- **方法：** 工具级过滤 / Docker / nsjail / Firecracker / 工作目录隔离
- **BidPilot：** ⚠️ 有 permission pipeline，无 OS 级隔离

### 16. Inference Optimization 推理优化

- **核心技术：** KV-Cache / Quantization / Speculative Decoding / PagedAttention / Dynamic Batching
- **推理框架：** vLLM（易用多GPU）/ TensorRT-LLM（NVIDIA最快）/ SGLang（新秀）/ llama.cpp（CPU）

### 17. Multimodal / 多模态

- **是什么：** LLM 处理图片、PDF、音频、视频
- **术语：** Vision LLM / OCR / Document Understanding

## 补充专题

### A. 幻觉（Hallucination）

- **是什么：** LLM 输出看似合理但实际编造的内容
- **缓解：** RAG 给真实来源 / Grounding 引用来源 / Temperature 调低 / 结构化输出约束 / 人工审核 / Self-consistency

### B. Prompt Injection

- **是什么：** 恶意输入嵌入指令，劫持 Agent 行为
- **防御：** 输入清洗 / System/User 分离 / 输出过滤 / 权限最小化 / Sandbox / Guardrails

### C. Structured Output

- **是什么：** 让 LLM 输出 JSON/Pydantic 等结构化数据
- **方法：** JSON Mode / Tool Use / Instructor 库 / Constrained decoding

### D. Streaming

- **是什么：** 边生成边传输，不等全部生成完
- **实现：** SSE / WebSocket / HTTP Chunked
- **BidPilot：** ✅ 已实现 SSE streaming

---

# Part 3B — 后端 + AI 全栈认知地图

> **定位：** 本节补足后端、全栈和 AI 应用之间的边界，帮助你读 JD、拆需求、让 AI 实现代码、审查结果和定位问题。它是认知地图，不要求为每个概念手写造轮子。

## 2026 JD 核验（2026-07-26）

> 下表是本次调研中能直接查看职位描述的样本，不把少数 JD 当成统计结论。招聘状态会变化，投递前以职位页为准。

| 样本 | 页面可见需求 | 对地图的结论 |
|------|--------------|--------------|
| [上海美因特 Python 后端实习](https://www.nowcoder.com/jobs/detail/431314) | Python、Git、FastAPI/Django、REST API、PostgreSQL/MongoDB、基础数据库设计 | AI 团队的后端实习首先仍是 API + 数据库 + 协作能力 |
| [天津蓝快 Java 开发实习](https://www.ncss.cn/student/jobs/WQTKQWpGdZrTgufVjhVcZ9/detail.html)（1-49 人） | Java/OOP、数据结构算法、JS 数据交互、MySQL/SQL/索引/事务、MyBatis、Spring Boot、单元测试 | 小团队也会同时看后端基础、数据层和前后端接口 |
| [上海那一科技前端实习](https://www.shixiseng.com/intern/inn_xzikduzg9kie) | React、TypeScript、数据结构算法、Git、英文文档 | 全栈前端侧不是“会画页面”，而是浏览器与工程化能力 |
| [商飞软件 AI 应用开发实习](https://www.shixiseng.com/intern/inn_whulhfzxfhvv) | Python/Java、FastAPI/Flask/Spring Boot、数据库/缓存/消息队列、Linux/Git、CI/CD、RAG/Agent | AI 应用是在常规工程底座上增加模型、检索和 Agent 能力 |
| [美图 AI Agent 研发实习](https://www.nowcoder.com/jobs/detail/445785) | 一门主流语言、算法与数据结构、Agent/RAG/Tool Calling、评测、可观测性 | Agent 平台岗位会进一步要求工程质量与 AI 效果闭环 |

## 三张地图如何拼起来

```text
用户 / 浏览器 / App
        |
前端：界面、状态、路由、交互、流式展示
        |
HTTP / WebSocket / SSE / 鉴权 / API Contract
        |
后端：业务规则、编排、权限、任务、稳定性
  |              |                 |
关系数据库      缓存 / 队列         LLM / RAG / Tools / MCP
  |              |                 |
数据模型        异步任务             Agent（Part 3）

横向贯穿：Git、测试、日志、Trace、监控、安全、部署、成本
```

- **后端**负责把能力做成可靠、可控、可维护的服务。
- **全栈**负责把前端体验、后端服务和部署闭环连起来。
- **AI 应用 / Agent**是在这个闭环中加入模型推理、检索、工具调用和效果评估，不替代底层工程。

## 后端认知地图

| 层 | 关键问题 | 需要认识的概念与典型技术 |
|----|----------|--------------------------|
| 1. 程序与计算机基础 | 代码、进程和网络请求为什么会这样运行？ | Python/Java/Go 任一主语言、类型/异常/OOP、数据结构算法、进程/线程/协程、内存、TCP/IP、DNS、HTTP/HTTPS |
| 2. Web 与 API | 客户端如何安全、稳定地调用服务？ | Request/Response、REST/RPC、JSON、状态码、OpenAPI、参数校验、认证、授权、CORS、限流、分页、版本化、SSE/WebSocket |
| 3. 业务与数据建模 | 业务状态和数据如何正确保存、演进？ | 表设计、SQL、Join、索引、事务、隔离级别、ORM、Migration、对象存储、幂等键、审计日志 |
| 4. 性能与异步任务 | 慢操作、并发和失败任务如何处理？ | Redis、缓存失效、缓存穿透、消息队列、Celery/Kafka/RabbitMQ、Cron、重试、退避、死信队列、分布式锁 |
| 5. 质量与安全 | 怎样证明服务正确，并避免把数据或权限交错？ | 单元/集成/API 测试、代码评审、日志、Metrics、Trace、RBAC/ABAC、密钥管理、输入校验、速率限制、数据隔离、备份恢复 |
| 6. 交付与运行 | 怎样让服务能重复部署、观察和回滚？ | Linux、环境变量、Docker/Compose、Nginx/反向代理、CI/CD、云服务、健康检查、灰度/回滚、可用性与成本 |

### 后端面试中常见的“表面词”

| 词 | 不能只停留在定义，还要能说明 |
|----|------------------------------|
| 数据库索引 | 为什么能加速、什么查询用不上、写入代价是什么 |
| 事务 | 原子性、并发下的问题、什么时候应拆成异步流程 |
| Redis | 缓存什么、何时失效、缓存与数据库不一致怎么办 |
| 消息队列 | 为什么要异步、重复消费怎么办、失败任务去哪了 |
| API 设计 | 输入输出契约、错误码、权限、分页、版本兼容 |
| 并发 | 同时请求会发生什么、共享状态如何避免竞态 |
| Docker | 解决什么环境问题、镜像/容器/卷/网络分别是什么 |

## 全栈认知地图

| 层 | 关键问题 | 需要认识的概念与典型技术 |
|----|----------|--------------------------|
| 1. Web 平台 | 页面和浏览器如何工作？ | HTML 语义、CSS 布局/响应式、DOM、事件、Fetch、Cookie/Storage、浏览器渲染、可访问性 |
| 2. JavaScript / TypeScript | 前端逻辑如何组织且不失控？ | ES Modules、Promise/async、类型系统、错误处理、数据结构、包管理、Lint/Format |
| 3. UI 框架 | 组件、状态和路由如何组成应用？ | React 或 Vue、组件生命周期、Props/State、Hooks/Composition API、Router、表单、状态管理 |
| 4. 前端工程化 | 怎样把多人开发的页面构建、测试和发布？ | Vite/Next.js/Nuxt、构建产物、环境变量、代码分割、单元/E2E 测试、性能监测、错误上报 |
| 5. 前后端协作 | API、登录和异常状态如何成为完整体验？ | API Contract、Loading/Error/Empty State、JWT/Session、CORS、文件上传、权限 UI、设计系统 |
| 6. AI 交互 | 大模型能力如何成为可用而非只会聊天的界面？ | Token Streaming/SSE、对话与会话状态、引用来源、Tool Call 状态、审批 UI、生成中断、反馈收集、成本提示 |

### AI 全栈的典型闭环

```text
用户输入 -> React/Vue 表单或聊天界面 -> API
       -> 后端鉴权、参数校验、业务编排
       -> RAG / LLM / Tool Calling / 后台任务
       -> SSE 事件流、引用、状态、错误码
       -> 前端展示、审批、反馈、可观测数据
```

其中“聊天窗口”只是一层 UI。真正的 AI 全栈还要处理会话持久化、流式断线重连、权限、引用、工具审批、失败提示和历史数据。

## 三种常见技术栈视角

| 目标岗位 | 一条常见主线 | 另一侧需要能读懂的内容 |
|----------|--------------|--------------------------|
| AI 应用 / Python 后端 | Python + FastAPI + Pydantic + PostgreSQL + Redis + Docker | TypeScript/React 基础、LLM API、RAG、SSE |
| AI 全栈 | TypeScript + React/Next.js + Python/FastAPI 或 Node.js/NestJS | 数据库、鉴权、部署、LLM/Agent 集成 |
| 传统后端 / AI 后端 | Java/Spring Boot 或 Go + MySQL/PostgreSQL + Redis + MQ | Python 脚本/LLM API、React/Vue 基础、分布式系统概念 |

不需要同时深耕三条主线。对每条主线要能识别职责、读懂架构与 AI 生成的代码；选择其中一条作为你能完成、调试和讲清楚的作品栈即可。

## Agent 地图与后端/全栈地图的对应关系

| Agent 概念（Part 3） | 后端 / 全栈中的落点 |
|--------------------|---------------------|
| Tool Calling | API Contract、参数校验、权限、超时、幂等、审计日志 |
| RAG | 文档入库、异步解析、向量/全文检索、元数据过滤、数据权限、引用展示 |
| Memory / Session | 会话模型、数据保留策略、Redis/数据库、隐私与用户删除 |
| Streaming | SSE/WebSocket、断线重连、前端状态机、取消与资源释放 |
| HITL / Approval | 权限模型、审批 UI、操作记录、可恢复状态 |
| Eval / Observability | 自动化测试、Trace/Span、指标、Bad Case 数据集、回归检查 |
| Multi-Agent / 长任务 | 队列、Worker、任务状态、重试、限流、成本与并发控制 |

## AI 编程时代的掌握标准

AI 可以生成实现，但你需要对结果负责。对地图里的每个核心概念，按下面四层理解即可：

| 层次 | 你应做到什么 |
|------|--------------|
| 了解 | 能说清它解决什么问题、与相邻概念的区别 |
| 能设计 | 能把业务需求翻译为数据、接口、状态和约束 |
| 能驱动 AI 实现 | 能给出技术栈、边界条件、验收标准、错误处理和安全要求 |
| 能验收与排障 | 能看测试/日志/Trace，判断 AI 生成的实现是否正确并提出修正方向 |

这比逐行手写所有框架更符合 AI 编程时代，也足以支撑项目深挖型面试；但“让 AI 写了”本身不能替代架构判断、验证和排错。

---

# Part 4 — Agent 框架深度对比

## 全景图

```
┌──────────────────────────────────────────────────────────────┐
│                    Agent 框架生态 (2025-2026)                   │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│  编排框架     │  多 Agent     │  数据/RAG     │  厂商原生 SDK    │
│  LangChain   │  CrewAI      │  LlamaIndex  │  OpenAI Agents  │
│  LangGraph   │  AutoGen     │  LlamaParse  │  Claude Agent   │
│  Semantic    │  (Microsoft) │  LlamaCloud  │  Bedrock Agent  │
│  Kernel      │              │              │  Vertex Agent   │
└──────────────┴──────────────┴──────────────┴─────────────────┘
```

## LangGraph（面试最高频）

- **核心理念：** 图结构编排 Agent——节点=函数，边=条件路由，状态=TypedDict
- **核心抽象：** StateGraph / Node / Edge / State / Checkpoint
- **关键特性：** 支持循环 / Checkpointing（暂停恢复+时间旅行）/ HITL（interrupt_before/after）/ Persistence / Streaming
- **2025 更新：** Command + Send API / LangGraph Platform / Studio 可视化

```python
# LangGraph 最小示例（面试能白板写出来加分）
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    next_step: str

def planner(state: AgentState) -> dict:
    return {"next_step": "worker"}

def worker(state: AgentState) -> dict:
    return {"messages": state["messages"] + ["done"]}

graph = StateGraph(AgentState)
graph.add_node("planner", planner)
graph.add_node("worker", worker)
graph.add_edge(START, "planner")
graph.add_conditional_edges("planner", lambda s: s["next_step"])
graph.add_edge("worker", END)

from langgraph.checkpoint.memory import MemorySaver
app = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["worker"]  # HITL
)
```

## LangChain

- **是什么：** 最大的 LLM 应用框架生态
- **核心：** Chain / Agent / Tool / Memory / Retrieval / Callback
- **劣势：** 抽象层过重、版本变化快
- **面试问：** 和 LangGraph 区别？（Chain 线性，Graph 支持循环）

## CrewAI

- **是什么：** 角色扮演式多 Agent——每个 Agent 有角色+目标+背景故事
- **编排：** Sequential / Hierarchical（Manager Agent）/ Consensus
- **特色：** 简单直观、内置记忆

## AutoGen (Microsoft)

- **0.4 大改：** 同步对话 → 异步事件驱动
- **核心包：** autogen-core / autogen-agentchat / autogen-ext / autogen-studio
- **特色：** 分布式 Agent、代码执行

## LlamaIndex

- **是什么：** RAG 领域最强——专注「把外部数据接进 LLM」
- **2025 更新：** LlamaCloud / LlamaParse（高级 PDF 解析）/ Workflow 引擎 / LlamaAgents
- **特色：** 160+ 数据源 / Auto-merging retrieval / Hybrid search

## 框架选择决策树

```
需要什么？
├─ 只做 RAG → LlamaIndex
├─ 简单 Agent + 工具 → LangChain 或 厂商 SDK
├─ 复杂多步 Agent（循环/状态/HITL）→ LangGraph ✅
├─ 多 Agent 团队 → CrewAI（简单）或 LangGraph（灵活）
├─ 分布式 Agent / 代码执行 → AutoGen
└─ 已用特定云厂商 → 对应原生 SDK
```

## 厂商原生 SDK

| SDK | 厂商 | 特点 |
|-----|------|------|
| OpenAI Agents SDK | OpenAI | Responses API + Handoff + Guardrails |
| Claude Agent SDK | Anthropic | 轻量 + MCP 原生 |
| Semantic Kernel | Microsoft | .NET/Python/Java + Azure 集成 |
| Amazon Bedrock Agents | AWS | AWS 原生 |
| Google Vertex Agent | Google | GCP 原生 + Gemini |

---

# Part 5 — 六层硬度模型 + 学习路线

## 六层模型

```
Layer 6  产品治理    多租户/RBAC/审计/SLO/成本追踪
Layer 5  可观测评测  Trace/Span/Metrics/Eval pipeline
Layer 4  Harness     Loop/Tools/Hooks/Skills/Campaign/HITL/MCP
Layer 3  上下文工程  Prompt assembly/Memory/Compression/Attention
Layer 2  模型交互    Streaming/TTFT/Provider routing/Cache/Cascade
Layer 1  模型基础    Transformer/Attention/Tokenization/Fine-tuning
```

**BidPilot：Layer 4+6 生产级，Layer 1-3+5 有硬缺口。**

## 12 周学习路线

| 周 | 内容 | 面试回报 |
|----|------|---------|
| W1-2 | 模型底子（Transformer/KV-cache/推理概念） | 面试保命 |
| W3 | s08 Context Compaction | ⭐ 核心竞争力 |
| W4 | s09 Memory Architecture | ⭐ 核心竞争力 |
| W5 | s10 Prompt Assembly | ⭐ 核心竞争力 |
| W6 | s06 Subagent + 上下文隔离 | BidPilot 硬度 |
| W7 | s11 Error Recovery + Circuit Breaker | BidPilot 硬度 |
| W8 | s15-17 Multi-Agent 协调 | BidPilot 硬度 |
| W9 | Model Cascade（大小模型协同） | 生产硬度 |
| W10 | Provider routing + 成本追踪 | 生产硬度 |
| W11 | Trace/Span/Metrics | demo→生产 |
| W12 | Eval pipeline + 回归测试 | demo→生产 |

---

# Part 6 — 术语表

## Agent 核心概念

| 术语 | 一句话 |
|------|--------|
| Agent | 能自主决定下一步做什么的 AI 系统 = 模型 + 工具 + 循环 |
| Harness | Agent 的运行环境 = 工具 + 知识 + 观察 + 动作接口 + 权限 |
| ReAct | 推理→行动→观察→继续推理的循环范式 |
| Workflow | 已知步骤的固定序列（vs Agent 动态决定） |
| Router | 一次性分类器，选择一条路径 |
| Orchestrator-Worker | 一个编排者分发任务给多个工人 |
| Supervisor | 主管 Agent 决定下一步交给谁 |
| Handoff | Agent 之间的任务交接 |

## 上下文与记忆

| 术语 | 一句话 |
|------|--------|
| Context Engineering | 管理 LLM 每次调用时的完整信息环境 |
| Context Compaction | 自动压缩 messages[] 防止上下文溢出 |
| Attention Dilution | 长上下文导致模型对早期信息注意力被稀释 |
| Lost-in-the-Middle | 模型对长上下文中间部分召回最差 |
| Working Memory | 当前上下文窗口中的信息——短期记忆 |
| Episodic Memory | 过去任务的记录：什么试过、什么有效、什么失败 |
| Semantic Memory | 稳定事实：公司能力、客户数据、标准 |
| Procedural Memory | 可复用的操作流程：怎么起草、怎么格式化 |
| Prompt Assembly | 从模块化片段组装最终 system prompt |
| Prompt Cache | 服务端缓存公共 prompt 前缀，跳过重复处理 |

## 检索与生成

| 术语 | 一句话 |
|------|--------|
| RAG | 先检索相关文档，再让 LLM 基于结果生成 |
| Embedding | 把文本变成向量（数字数组）用于相似度搜索 |
| Dense Retrieval | 通过向量相似度搜索 |
| Sparse Retrieval | 通过关键词/词法匹配搜索 |
| Hybrid Retrieval | 融合 dense + sparse |
| RRF | Reciprocal Rank Fusion——合并多个排序列表 |
| Reranker | 第二轮模型对 query-doc pair 重新打分 |
| Grounding | 把 LLM 输出绑定到真实来源 |
| Hallucination | LLM 输出看似合理但实际编造的内容 |
| GraphRAG | 用图结构作为额外索引的检索 |

## 工具与协议

| 术语 | 一句话 |
|------|--------|
| Function Calling | 模型输出结构化的工具调用请求 |
| Tool Use | 同 Function Calling（Anthropic 用语） |
| MCP | Model Context Protocol——AI 的 USB-C 口，标准化工具连接协议 |
| A2A | Agent-to-Agent Protocol——Agent 之间互相发现和通信 |
| HITL | Human-in-the-Loop——关键操作前暂停等人审批 |

## 模型与推理

| 术语 | 一句话 |
|------|--------|
| Transformer | 所有现代 LLM 的底层架构：Self-Attention + FFN |
| Self-Attention | 每个 token 对所有其他 token 计算相关性，O(n²) |
| Tokenization | 文本→整数 token ID，不同模型不同分词器 |
| KV-Cache | 缓存已计算的 attention 状态，流式推理每 token 不用重算全部 |
| TTFT | Time To First Token——从请求到首个 token 的延迟 |
| Quantization | 降低权重精度（FP32→INT8→INT4）省内存加速，有质量损失 |
| Speculative Decoding | 小模型猜 token + 大模型验证，加速 2-3x |
| Fine-tuning (SFT) | 监督微调——用标注数据继续训练 |
| RLHF | 人类反馈强化学习——训练奖励模型再用 PPO 优化 |
| DPO | 直接偏好优化——跳过奖励模型直接用偏好对优化 |
| LoRA | 低秩适配——只训练 ~0.1% 参数，接近全参数效果 |
| QLoRA | 4-bit 量化 + LoRA——消费级 GPU 可微调大模型 |
| Model Cascade | 小模型分类/摘要 → 大模型执行复杂推理 |

## 工程与运维

| 术语 | 一句话 |
|------|--------|
| Checkpoint | 执行状态的持久化快照，用于暂停/恢复/时间旅行 |
| Trace | 一次完整 Agent 调用的端到端记录 |
| Span | Trace 中的单步操作 |
| OpenTelemetry | 开放的可观测标准（traces/metrics/logs） |
| SLO | 可靠性目标：P95 延迟、完成率等 |
| Idempotency Key | 使重复请求安全的稳定标识符 |
| Event Replay Cursor | 客户端已处理的最高事件序列，用于断线重连 |
| Circuit Breaker | 连续失败 N 次后停止调用，防级联故障 |
| Exponential Backoff | 重试间隔递增（1s→2s→4s→8s） |
| Sandbox Isolation | 限制 Agent 的 OS 级能力：文件/网络/进程 |
| Cooperative Cancellation | 不硬杀进程，让当前节点到事务边界后安全停止 |

## 权限与安全

| 术语 | 一句话 |
|------|--------|
| RBAC | 基于角色的访问控制 |
| ABAC | 基于属性的访问控制（租户/项目/状态/时间） |
| Capability | 命名的权限单元（如 `requirements.review`） |
| IDOR | 不安全的直接对象引用——改 URL 访问别人的数据 |
| Prompt Injection | 恶意输入嵌入指令劫持 Agent 行为 |
| RLS | PostgreSQL 行级安全——数据库层面的租户隔离 |

## 评测

| 术语 | 一句话 |
|------|--------|
| Eval | 可重复的质量测量 |
| Benchmark | 标准化的评测集 |
| LLM-as-Judge | 用强模型评弱模型输出 |
| Golden Dataset | 标注好的标准答案集，用于回归测试 |

---

# Part 7 — BidPilot 缺口 + 章节对照

## learn-claude-code s01-s20 ↔ BidPilot

| 章节 | 主题 | BidPilot | 差距 |
|------|------|----------|------|
| s01 | Agent Loop | ✅ StreamingHarness | 对齐 |
| s02 | Tool Use | ✅ TOOL_HANDLERS | 对齐 |
| s03 | Permission | ✅ execute_capability + RBAC | 对齐 |
| s04 | Hooks | ✅ hook_manager | 对齐 |
| s05 | TodoWrite/Planning | ⚠️ campaign 有，无 reminder | 小补 |
| s06 | Subagent | ⚠️ workers 有，无 clean context | 中补 |
| s07 | Skill Loading | ✅ agent-skills + skills.py | 对齐 |
| **s08** | **Context Compaction** | **❌ 无自动压缩** | **大缺** |
| **s09** | **Memory Architecture** | **❌ 无自动提取** | **大缺** |
| **s10** | **Prompt Assembly** | **❌ 硬编码 prompt** | **中缺** |
| s11 | Error Recovery | ⚠️ 有 retry，无 backoff | 中补 |
| s12 | Task System | ✅ RuntimeRun + RuntimeEvent | 对齐 |
| s13 | Background Tasks | ✅ Celery + agent wake | 对齐 |
| s14 | Cron | ⚠️ Celery beat 有 | 小补 |
| s15 | Agent Teams | ❌ 无异步邮箱 | 中缺 |
| s16 | Team Protocols | ❌ 无固定通信格式 | 小缺 |
| s17 | Autonomous | ❌ 无自组织 | 低优先 |
| s18 | Worktree Isolation | ⚠️ 只有工具级过滤 | 小补 |
| s19 | MCP | ✅ bidpilot_mcp.py | 对齐 |
| s20 | Comprehensive | — | — |

**最大缺口：s08 + s09 + s10 = 上下文工程三件套 = 面试最高频考点**

## 你的日志 → 术语翻译

| 你的原话 | 标准术语 | 六层模型 |
|---------|---------|---------|
| 大模型部署/微调 | Model Deployment + Fine-tuning | Layer 1 |
| 基础 transformer 知识 | Transformer Architecture | Layer 1 |
| 大小模型协同设计 | Model Cascade | Layer 2 |
| 上下文治理 | Context Engineering | Layer 3 |
| memory 设计 | Memory Architecture | Layer 3 |
| 长期/短期记忆 | Long-term vs Working Memory | Layer 3 |
| OCR 图片识别 | Multimodal Vision | Layer 1+4 |
| 非简单 API 调用 | Agent Harness + Tool Orchestration | Layer 4 |
| 首字响应延迟 | TTFT | Layer 2 |
| 提示词工程 | Prompt Engineering + Context Assembly | Layer 3 |
| 注意力稀释 | Attention Dilution / Lost-in-the-Middle | Layer 3 |
| agent 架构优化 | Multi-Agent Patterns | Layer 4 |
| 大模型推理加速 | Inference Optimization | Layer 1 |
| sandbox 沙箱 | Sandbox Isolation | Layer 4 |
| checkpoint 机制 | Execution Checkpoint | Layer 4 |
| Redis/队列 | Backend Infra | 后端通用 |
| 微服务 | Service Architecture | 后端通用 |

---

# Part 8 — 面试速查表

## 一句话定义（脱口而出）

| 术语 | 一句话 |
|------|--------|
| Agent | 能自主决定下一步做什么的 AI = 模型 + 工具 + 循环 |
| ReAct | 推理→行动→观察→继续推理的循环 |
| RAG | 先检索相关文档，再让 LLM 基于结果生成回答 |
| Context Engineering | 管理 LLM 每次调用时的完整信息环境 |
| Function Calling | LLM 输出结构化的工具调用请求 |
| MCP | AI 的 USB-C 口——标准化工具连接协议 |
| LoRA | 低秩适配微调，只训 ~0.1% 参数接近全参数效果 |
| KV-Cache | 缓存 attention 状态，让流式推理每 token 不用重算全部 |
| TTFT | 从请求到首个 token 的延迟 |
| Hallucination | LLM 输出看似合理但实际编造的内容 |
| Checkpoint | 执行状态的持久化快照 |
| Trace/Span | Trace=端到端记录；Span=其中单步操作 |
| HITL | 关键操作前暂停等人审批 |
| Grounding | 把 LLM 输出绑定到真实来源 |

## 关键数字

| 数字 | 含义 |
|------|------|
| O(n²) | Self-Attention 时间复杂度——长文本贵的原因 |
| ~0.1% | LoRA 只训练的参数比例 |
| 4-bit | QLoRA 量化精度——消费级 GPU 能微调大模型 |
| 2-3x | Speculative Decoding 典型加速 |
| 4 层 | Context Compaction 策略（trim→merge→LLM summary→emergency cut） |
| 4 种记忆 | Working/Episodic/Semantic/Procedural |
| 3 种多 Agent | Supervisor/Router/Orchestrator-Worker |
| 3 种 Transport | MCP 的 stdio/SSE/Streamable HTTP |

## 大厂面经高频题（2025-2026）

**字节：** Agent Loop/ReAct + Function Calling 原理 + RAG 全链路优化 + LangGraph State/Node/Edge + 项目深挖

**百度：** 文心生态/千帆 + RAG 链路优化 + 多轮对话管理 + Agent 安全

**阿里：** 通义千问 Agent + Multi-Agent 框架 + Function Calling + MCP 协议

**腾讯：** Agent 业务落地 + 端到端系统设计 + 评测指标

**通用高频 Top 10：**
1. RAG 完整流程？怎么优化？
2. Agent 和传统 Chatbot 区别？
3. Function Calling 原理？和 MCP 区别？
4. 上下文窗口满了怎么办？
5. 幻觉怎么产生？怎么缓解？
6. Prompt Injection 怎么防御？
7. 你做的项目架构？遇到什么难点？
8. LangGraph 的 Graph/Node/Edge/State？
9. 微调 vs RAG vs Prompt Engineering 怎么选？
10. 怎么评测一个 Agent 的效果？

## BidPilot 面试话术

> 我做了一个**投标文件智能生成平台 BidPilot**，是生产级 Agent 系统。
>
> **Harness：** 自研 StreamingHarness——流式多步工具循环，支持 tool dispatch、hooks、审批拦截、多波次 campaign 编排。
>
> **上下文工程：** memory context 注入、skills 按需加载、conversation context 管理。
>
> **RAG：** pgvector + FTS hybrid retrieval，RRF 融合 + Reranker 重排。
>
> **多 Agent：** campaign multi-wave——planner 拆任务、worker 并行执行、自动续波。
>
> **安全：** RBAC + ABAC + capability permission + HITL approval + idempotency key。
>
> **协议：** MCP server (FastMCP) 暴露平台能力给外部 Agent。
>
> **后端：** FastAPI + Celery + Redis + Postgres，Docker Compose 部署。
>
> **前端：** React + shadcn/ui + SSE streaming，有 agent workspace、conversation history、实时状态流。
>
> **国产模型：** 支持 DeepSeek + 通义千问 + OpenAI 兼容 API，多 provider 路由。

---

# Part 9 — 学习资源索引

## 本地仓库

| 仓库 | 路径 | 用途 |
|------|------|------|
| learn-claude-code | `E:\my_idea_cc\agent-learning\learn-claude-code\` | 主课 s01-s20 |
| claude-cookbooks | `E:\my_idea_cc\agent-learning\claude-cookbooks\` | 菜谱 |
| courses | `E:\my_idea_cc\agent-learning\courses\` | 底课 |

## 按主题找资源

| 学什么 | 去哪学 |
|--------|--------|
| Agent Loop | learn-claude-code s01 `code.py` |
| Tool Use | learn-claude-code s02 |
| Permission | learn-claude-code s03 |
| Hooks | learn-claude-code s04 |
| Planning | learn-claude-code s05 |
| Subagent | learn-claude-code s06 |
| Skills | learn-claude-code s07 |
| **Context Compaction** | **learn-claude-code s08** |
| **Memory** | **learn-claude-code s09** + cookbooks `tool_use/memory_cookbook.ipynb` |
| **Prompt Assembly** | **learn-claude-code s10** |
| Error Recovery | learn-claude-code s11 |
| Multi-Agent | learn-claude-code s15-17 |
| MCP | learn-claude-code s19 |
| RAG | cookbooks `capabilities/retrieval_augmented_generation/` |
| Context Compaction 实例 | cookbooks `tool_use/automatic-context-compaction.ipynb` |
| Evals | cookbooks `evals/` + `tool_evaluation/` |
| Observability | cookbooks `observability/` |
| Prompt Engineering | courses `prompt_engineering_interactive_tutorial/` |
| API Fundamentals | courses `anthropic_api_fundamentals/` |
| BidPilot 硬度对照 | `docs/learning/agent-hardness-curriculum.md` |
| 术语表(详细版) | `docs/learning/agent-engineering-glossary.md` |

## 外部资源

| 资源 | 链接 | 用途 |
|------|------|------|
| LangGraph 文档 | docs.langchain.com | 框架概念 |
| MCP 官网 | modelcontextprotocol.io | 协议规范 |
| DeepSeek API | platform.deepseek.com | 国产模型 |
| 通义千问 API | bailian.console.aliyun.com | 国产模型 |
| 牛客网 | nowcoder.com | 面经 |
| 知乎/小红书 | 搜索「Agent 面经」 | 面经 |
| Karpathy "Let's build GPT" | YouTube | Transformer 基础 |
| Unsloth 文档 | docs.unsloth.ai | QLoRA 微调 |
| Langfuse | langfuse.com | 开源可观测 |

---

*文档版本：v2.0*
*创建时间：2026-07-25*
*更新时间：2026-07-26*
*维护者：五条老师团队*
