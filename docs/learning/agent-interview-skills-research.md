# Agent 开发/AI 全栈/后端开发 — 实习岗技能全景调研

> 调研时间：2026-07-26
> 目标岗位方向：Agent 开发工程师 / AI 应用开发 / AI 全栈 / 后端开发实习
> 调研来源：learn-claude-code (s01–s20)、claude-cookbooks、anthropics/courses、国内招聘平台 JD 汇总、面经整理

---

## 一、全局认知：2025-2026 Agent 岗位到底要什么人

### 市场变化

2024 年之前：「会调 OpenAI API + 会写 prompt」就算 AI 开发。
2025-2026 年：企业要的是「**能交付生产级 Agent 系统**」的人。

**一句话总结岗位需求变化：**

```
2024：  会调 API → AI 工程师
2025：  会造 Harness + 懂上下文工程 + 有评测思维 → Agent 工程师
2026：  上述全部 + 懂模型基础 + 会部署推理 + 理解安全合规 → 生产级 AI 工程师
```

### 岗位名称对照

| 岗位名称 | 核心要求 | BidPilot 匹配度 |
|---------|---------|----------------|
| Agent 开发工程师 | Harness + 上下文工程 + 多 Agent 协调 | ★★★★☆ |
| AI 应用开发工程师 | RAG + Tool Use + API 集成 + 部署 | ★★★★☆ |
| AI 全栈工程师 | 前端 + 后端 + LLM 集成 + 部署 | ★★★★★ |
| 后端开发 (AI 方向) | FastAPI/Node + DB + 队列 + LLM 管道 | ★★★★★ |
| AI 平台工程师 | 推理部署 + 模型管理 + 监控 + MLOps | ★★☆☆☆ |
| MLOps 工程师 | 模型训练管线 + 部署 + 监控 + 版本管理 | ★☆☆☆☆ |

---

## 零、国内实习 JD 真实需求（2026.7 最新）

> 以下基于 Boss直聘、牛客网、实习僧、知乎面经、小红书面经汇总。

### 0.1 四类岗位 JD 共性要求

| 要求维度 | Agent 开发 | AI 应用开发 | AI 全栈 | 后端(AI方向) |
|---------|-----------|------------|--------|-------------|
| **学历** | 本科+（硕士优先） | 本科+ | 本科+ | 本科+ |
| **实习时长** | ≥3-6 月，≥4 天/周 | ≥3 月 | ≥3 月 | ≥3 月 |
| **必须语言** | Python | Python | Python + JS/TS | Python / Java / Go |
| **必须框架** | LangChain 或 LangGraph | LangChain / LlamaIndex | React/Vue + FastAPI | FastAPI / Flask / Django |
| **必须知识** | LLM 原理 + Agent 架构 | RAG + Prompt Engineering | 全栈 + LLM 集成 | DB + Queue + API |
| **加分项** | MCP / Multi-Agent / 微调 | 向量DB / 评测 / 部署 | Docker / CI/CD / 云 | Redis / Docker / K8s |

### 0.2 真实 JD 任职要求汇总（按出现频率排序）

**几乎每个 JD 都写的（必须）：**
1. ✅ 熟练掌握 Python
2. ✅ 了解大语言模型基本原理（Transformer / Attention / Tokenization）
3. ✅ 熟悉至少一个 Web 框架（FastAPI / Flask / Django）
4. ✅ 熟悉 MySQL / PostgreSQL / Redis
5. ✅ 了解 Git / Docker / Linux

**高频出现的（加分明显）：**
6. ⚡ 熟悉 LangChain / LlamaIndex / Dify 等 LLM 应用开发框架
7. ⚡ 有 RAG 系统搭建经验（文档解析 → 向量检索 → 生成）
8. ⚡ 了解向量数据库（Milvus / FAISS / Chroma / Pinecone）
9. ⚡ 熟悉 Prompt Engineering / Function Calling / Tool Use
10. ⚡ 有实际 LLM 项目或竞赛经验

**2025-2026 新增热门要求：**
11. 🔥 了解 MCP 协议（Model Context Protocol）
12. 🔥 了解 Multi-Agent 协作框架
13. 🔥 了解 Agent 记忆机制（短期/长期记忆）
14. 🔥 了解模型微调技术（LoRA / QLoRA / SFT）
15. 🔥 了解 Dify / Coze（扣子）等低代码 AI 平台

**部分岗位要求的（高级）：**
16. 🌟 了解 vLLM / TensorRT-LLM 等推理部署框架
17. 🌟 了解多模态大模型（图像/语音/视频）
18. 🌟 了解 OpenTelemetry / LangSmith 等可观测工具
19. 🌟 有 GPU 推理/模型部署经验

### 0.3 国内 AI 生态（必须知道的国产工具/平台/模型）

| 类别 | 工具/平台 | 你需要知道什么 |
|------|---------|--------------|
| **国产大模型** | DeepSeek (V3/R1) / 通义千问 (Qwen) / 文心一言 / 混元 / GLM / Kimi | 知道名字 + API 调用方式；DeepSeek 价格极低、Qwen 多模态强 |
| **低代码 AI 平台** | Dify / Coze（扣子）/ FastGPT | 知道是什么 + 和纯代码框架区别；面试会问 |
| **Agent 平台** | 百度千帆 / 阿里百炼 / 字节 Coze | 知道国内厂商的 Agent 平台生态 |
| **向量数据库** | Milvus / FAISS / Weaviate / Chroma / pgvector | Milvus 国内最流行，FAISS Meta 出品 |
| **部署推理** | vLLM / llama.cpp / Ollama / Xinference | 知道怎么本地跑开源模型 |
| **模型训练** | Hugging Face / 魔搭（ModelScope） / Unsloth | 魔搭是阿里的模型社区 |

### 0.4 Dify / Coze vs LangChain 的区别（面试常问）

| 维度 | Dify | Coze（扣子） | LangChain / LangGraph |
|------|------|-------------|----------------------|
| **定位** | 低代码 AI 应用平台 | 零代码 AI Bot 平台 | 开发者框架/库 |
| **开发方式** | 可视化 + 少量代码 | 零代码拖拽 | 纯代码 |
| **目标用户** | 开发者 / 半技术人员 | 非技术人员 / 运营 | 专业开发者 |
| **灵活性** | 中等 | 较低 | **非常高** |
| **开源** | ✅ 开源 | ❌ 闭源 SaaS | ✅ 开源 |
| **私有化部署** | ✅ 支持 | ❌ 不支持 | ✅ 支持 |
| **Agent 能力** | 工作流 + Agent 模式 | 插件 + Bot 模式 | LangGraph Agent |
| **学习成本** | 低 | 最低 | 较高 |

**面试怎么说：** 「Dify/Coze 适合快速原型和非技术人员使用；LangChain/LangGraph 适合需要精细控制的生产级 Agent 系统。我选 BidPilot 自研是因为投标场景需要更细粒度的审批和 campaign 编排。」

### 0.5 国产大模型对比（面试加分）

| 模型 | 团队 | 特点 | API 定价 | 面试怎么说 |
|------|------|------|---------|-----------|
| **DeepSeek-V3/R1** | 幻方量化 | 价格屠夫、推理能力强、开源 | ~1 元/百万 token | 「性价比最高的选择，R1 推理能力接近 GPT-4」 |
| **Qwen (通义千问)** | 阿里 | 多模态强、生态完善、多种尺寸 | 有免费额度 | 「多模态和工具调用做得好，配套工具链丰富」 |
| **文心一言** | 百度 | 国内最早的大模型之一、千帆平台 | 中等 | 「百度生态，千帆平台 Agent 能力强」 |
| **混元** | 腾讯 | 和腾讯生态集成 | 中等 | 「腾讯云集成好」 |
| **GLM** | 智谱 | ChatGLM 系列、开源 | 较低 | 「开源生态好，学术界认可度高」 |
| **Kimi** | 月之暗面 | 超长上下文、搜索增强 | 中等 | 「长上下文处理能力突出」 |

**BidPilot 已支持：** DeepSeek + 通义千问 + OpenAI 兼容 API → 面试能说「我实现了多 provider 路由，支持国产和国际模型」。

### 0.6 大厂面经高频题汇总（2025-2026）

> 来源：牛客网、知乎、小红书面经

**字节跳动：**
- Agent Loop / ReAct 原理
- Function Calling 实现机制
- RAG 全链路优化
- LangGraph State/Node/Edge 概念
- 项目深挖（你做的 Agent 系统架构）

**百度：**
- 文心大模型生态 / 千帆平台
- RAG 链路优化
- 多轮对话管理
- Agent 安全性

**阿里：**
- 通义千问 Agent 应用
- Multi-Agent 协作框架
- Function Calling 原理
- MCP 协议了解

**腾讯：**
- Agent 在业务场景中的落地
- 端到端 Agent 系统设计
- 评测指标设计

**通用高频题（所有公司都问）：**
1. RAG 的完整流程？怎么优化检索效果？
2. Agent 和传统 Chatbot 区别？
3. Function Calling 原理？和 MCP 区别？
4. 上下文窗口满了怎么办？
5. 幻觉怎么产生的？怎么缓解？
6. Prompt Injection 怎么防御？
7. 你做的项目架构是什么？遇到什么难点？
8. LangGraph 的 Graph/Node/Edge/State 是什么？
9. 微调 vs RAG vs Prompt Engineering 怎么选？
10. 怎么评测一个 Agent 的效果？

---

## 二、完整技能树（按优先级排序）

### P0：必须掌握（面试必问 + 日常必用）

#### 1. Prompt Engineering 提示词工程

| 维度 | 内容 |
|------|------|
| **是什么** | 设计给 LLM 的输入文本，让模型输出你想要的结果 |
| **干嘛的** | 控制 LLM 行为、输出格式、推理路径 |
| **核心技巧** | Zero-shot（直接问）、Few-shot（给例子）、CoT（链式思维）、ReAct（推理+行动） |
| **专业术语** | System Prompt / User Prompt / Assistant Prompt / Temperature / Top-P / Max Tokens / Stop Sequences |
| **场景** | 所有 LLM 应用的第一步 |
| **你需要吗** | ✅ 必须，这是基础中的基础 |
| **怎么用** | 设计 system prompt 控制角色 + 工具描述 + 输出格式 |
| **时效性** | ⚠️ 单独的「prompt 工程师」岗位在萎缩，进化为「上下文工程」，但技能本身永不过时 |
| **学哪里** | courses: `prompt_engineering_interactive_tutorial/` |

**面试高频问：**
- 什么是 Few-shot vs Zero-shot？什么时候用哪个？
- CoT（Chain-of-Thought）是什么？为什么有效？
- 如何防止 prompt injection？
- Temperature 调高调低分别影响什么？

---

#### 2. RAG — 检索增强生成

| 维度 | 内容 |
|------|------|
| **是什么** | 先从外部知识库检索相关文档，再把检索结果塞给 LLM 生成回答 |
| **干嘛的** | 让 LLM 能回答它训练数据里没有的、私有的、最新的知识 |
| **完整流程** | 文档解析 → 分块(Chunking) → Embedding → 向量存储 → 检索 → 重排(Rerank) → 生成 |
| **核心组件** | Embedding 模型 + 向量数据库 + Reranker + 生成模型 |
| **专业术语** | Chunking / Embedding / Vector DB / ANN / HNSW / RRF / Reranker / Grounding / Citation |
| **场景** | 知识库问答、文档搜索、投标文件检索（BidPilot 核心场景）、客服系统 |
| **你需要吗** | ✅ 必须，这是 AI 应用最常见的架构模式 |
| **怎么用** | BidPilot 已实现：pgvector dense + PostgreSQL FTS sparse + RRF + Reranker |
| **时效性** | 🔥 2025-2026 仍然是最高频 AI 架构，没有过时趋势 |

**面试高频问：**
- RAG 的完整流程是什么？
- 分块策略有哪些？（固定大小 / 语义分块 / 递归分块）
- 向量数据库怎么选？（Milvus / Qdrant / Chroma / pgvector）
- Dense vs Sparse retrieval 区别？为什么要做 Hybrid？
- RRF（Reciprocal Rank Fusion）是什么？
- Reranker 有什么用？和 Embedding 检索有什么区别？
- RAG 常见失败模式？怎么优化？

---

#### 3. Tool Use / Function Calling 工具调用

| 维度 | 内容 |
|------|------|
| **是什么** | LLM 输出结构化的「我要调用某个工具」请求，由 harness 执行后把结果喂回模型 |
| **干嘛的** | 让 LLM 能操作外部世界（搜索、数据库、API、文件、浏览器） |
| **专业术语** | Function Calling / Tool Use / Tool Schema / Parallel Tool Calls / Tool Result |
| **场景** | Agent 的核心能力——没有工具的 LLM 只是聊天机器人 |
| **你需要吗** | ✅ 必须，Agent 开发的核心 |
| **怎么用** | BidPilot 的 `TOOL_HANDLERS` registry + `execute_capability` |
| **时效性** | 🔥 永不过时，是 Agent 的「手和脚」 |

**面试高频问：**
- Function Calling 的底层机制是什么？（模型输出 JSON schema → harness 执行 → 结果回传）
- 和 MCP 什么关系？（MCP 是 Function Calling 的标准化外部协议）
- 工具调用失败怎么办？（retry / fallback / 通知用户）
- 如何设计好的 tool schema？（清晰描述 + 类型约束 + 示例）

---

#### 4. Agent Loop / ReAct 范式

| 维度 | 内容 |
|------|------|
| **是什么** | Agent 的核心循环：模型推理 → 选择工具 → 执行 → 观察结果 → 继续推理 |
| **干嘛的** | 让 LLM 能自主决定做什么，而不是一次性输出完就停 |
| **专业术语** | ReAct / Agent Loop / Stop Reason / Tool Dispatch / Max Iterations |
| **场景** | 所有 Agent 系统的核心架构 |
| **你需要吗** | ✅ 必须 |
| **怎么用** | BidPilot 的 `StreamingHarness.run()` 完整实现了 |
| **时效性** | 🔥 Agent 的「心脏」，永不过时 |

**面试高频问：**
- ReAct 是什么？和 CoT 有什么区别？
- Agent Loop 怎么设计？什么时候停？
- 如何防止 Agent 死循环？（max_iterations / token budget / timeout）
- 和 Workflows 有什么区别？

---

#### 5. LLM 基础知识（面试保命）

| 维度 | 内容 |
|------|------|
| **是什么** | 理解 LLM 底层是怎么工作的 |
| **干嘛的** | 面试必问 + 能帮你做出更好的工程决策 |
| **必须知道的** | Transformer / Self-Attention / Tokenizer / Context Window / Temperature / Top-P / Streaming |
| **加分项** | KV-Cache / Positional Encoding (RoPE, ALiBi) / Quantization / Speculative Decoding / vLLM |
| **场景** | 面试 + 模型选型 + 性能优化 |
| **你需要吗** | ✅ 面试必须，日常开发加分 |
| **怎么用** | 理解为什么流式快（KV-cache）、为什么长文本贵（O(n²) attention）、为什么量化有损 |
| **时效性** | 🔥 Transformer 架构短期不会被替代 |

**面试高频问：**
- Transformer 的 Self-Attention 是什么？为什么是 O(n²)？
- 什么是 KV-Cache？为什么它让流式推理快？
- Tokenizer 是什么？不同模型为什么同一个 prompt token 数不同？
- Temperature 是什么？调高调低分别影响什么？
- 什么是幻觉（Hallucination）？怎么缓解？
- Context Window 有多大？满了怎么办？（→ 引出上下文工程）

---

### P1：重要技能（面试加分 + 生产需要）

#### 6. Context Engineering 上下文工程

| 维度 | 内容 |
|------|------|
| **是什么** | 2025 年从「Prompt Engineering」进化而来的新术语——设计整个 LLM 的信息环境，不只是一个 prompt |
| **干嘛的** | 管理 Agent 每次调用 LLM 时塞进去的所有信息：system prompt + tools + memory + conversation + retrieval |
| **核心子题** | Context Compaction（压缩） / Memory Architecture（记忆） / Prompt Assembly（组装） / Attention Management（注意力管理） |
| **和 Prompt Engineering 的区别** | Prompt Engineering = 写好一句话；Context Engineering = 管好整个信息管道 |
| **专业术语** | Context Window / Context Budget / Context Compaction / Lost-in-the-Middle / Attention Dilution / Working Memory |
| **场景** | 长对话、多轮任务、大项目、Agent 运行时间超过几分钟 |
| **你需要吗** | ✅✅ 面试最高频新词 + BidPilot 最大缺口 |
| **怎么用** | learn-claude-code s08 (compaction) + s09 (memory) + s10 (prompt assembly) |
| **时效性** | 🔥🔥🔥 2025-2026 最热的 Agent 工程术语 |

**面试高频问：**
- 什么是上下文工程？和提示词工程有什么区别？
- 上下文窗口满了怎么办？（四层压缩策略）
- 什么是 Attention Dilution / Lost-in-the-Middle？
- 怎么管理 Agent 的记忆？（短期 / 长期 / 工作记忆 / 情景记忆）
- 怎么组装 System Prompt？（模块化 vs 全塞进去）

---

#### 7. Memory Architecture 记忆架构

| 维度 | 内容 |
|------|------|
| **是什么** | Agent 的信息持久化系统——记住该记的，忘掉该忘的 |
| **四种记忆** | Working Memory（当前上下文）/ Episodic Memory（任务历史）/ Semantic Memory（稳定事实）/ Procedural Memory（操作流程） |
| **干嘛的** | 让 Agent 跨对话、跨任务积累知识 |
| **专业术语** | Long-term Memory / Short-term Memory / Memory Store / Memory Retrieval / Memory Consolidation |
| **场景** | 长期运行的 Agent、多轮任务、知识积累 |
| **你需要吗** | ✅ 面试常问 + 生产必须 |
| **怎么用** | learn-claude-code s09 + cookbooks `tool_use/memory_cookbook.ipynb` |
| **时效性** | 🔥 核心能力，不会过时 |

---

#### 8. Multi-Agent 多 Agent 协作

| 维度 | 内容 |
|------|------|
| **是什么** | 多个 Agent 分工合作完成一个复杂任务 |
| **干嘛的** | 分工 + 隔离上下文 + 并行执行 |
| **核心模式** | Supervisor（主管分配）/ Router（路由分类）/ Orchestrator-Worker（编排-工人）/ Handoff（接力） |
| **专业术语** | Multi-Agent / Agent Team / Supervisor / Orchestrator / Worker / Handoff / Message Bus / Agent Protocol |
| **场景** | 复杂任务（投标文件需要多个 Agent 各干各的） |
| **你需要吗** | ✅ 面试常问 + BidPilot campaign 已实现 |
| **怎么用** | learn-claude-code s15–s17 + BidPilot campaign multi-wave |
| **时效性** | 🔥 2025-2026 快速增长的领域 |

**面试高频问：**
- 多 Agent 有哪些常见模式？
- Supervisor vs Router vs Orchestrator 区别？
- Agent 之间怎么通信？（共享状态 / 消息邮箱 / 事件总线）
- 和单 Agent + Subagent 有什么区别？

---

#### 9. Fine-tuning 微调

| 维度 | 内容 |
|------|------|
| **是什么** | 用你的数据继续训练模型，让模型更擅长你的特定任务 |
| **干嘛的** | 提升特定任务表现 + 降低推理成本（小模型微调后可能超过大模型） |
| **核心方法** | SFT（监督微调）/ RLHF（人类反馈强化学习）/ DPO（直接偏好优化）/ GRPO |
| **参数高效微调** | LoRA（低秩适配器，只训少量参数） / QLoRA（4-bit 量化 + LoRA，消费级 GPU 可用） / PEFT |
| **微调工具** | Hugging Face PEFT / Unsloth（2x 快，70% 省显存） / Axolotl / MLX（Apple Silicon） |
| **专业术语** | Fine-tuning / SFT / RLHF / DPO / GRPO / LoRA / QLoRA / PEFT / Training Data / Overfitting / Learning Rate / Epoch |
| **场景** | 通用模型不满足需求、需要特定格式/风格/领域知识 |
| **你需要吗** | ⚠️ 面试加分项，但 Agent 岗不是必须 |
| **怎么用** | cookbooks `finetuning/`（如果存在） |
| **时效性** | ⚠️ 热度在降——因为 RAG + Context Engineering 能解决大部分场景；微调更适合格式/风格/成本优化 |

**决策框架（面试必知）：**

| 情况 | 选什么 | 为什么 |
|------|--------|--------|
| 快速原型、通用任务 | **Prompt Engineering** | 最快最便宜 |
| 需要访问私有/动态数据 | **RAG** | 数据会变，不想改模型权重 |
| 需要特定输出格式/风格 | **Fine-tuning** | 模型「学会」格式比 prompt 描述更稳定 |
| 需要领域专业知识 | **RAG + Fine-tuning 混合** | RAG 给事实，Fine-tune 给风格 |
| 降低推理成本 | **Fine-tune 小模型** | 小模型微调后可能超过大模型零样本 |

**面试高频问：**
- SFT vs RLHF vs DPO 区别？（SFT=有标注数据训练；RLHF=训练奖励模型再用 PPO 优化；DPO=跳过奖励模型直接用偏好对优化）
- LoRA 是什么？为什么比全参数微调好？（低秩分解，只训 ~0.1% 参数，效果接近全参数）
- QLoRA 是什么？（4-bit NF4 量化 + LoRA，消费级 GPU 24GB 可微调 70B 模型）
- 什么时候该微调，什么时候该用 RAG？（看上面决策框架）
- 微调的数据怎么准备？（质量 > 数量，格式一致，多样性，去噪）

---

#### 10. Vector Database 向量数据库

| 维度 | 内容 |
|------|------|
| **是什么** | 专门存储和检索向量（Embedding）的数据库 |
| **干嘛的** | RAG 的核心组件——把文本变成向量，然后找最相似的 |
| **专业术语** | Embedding / ANN (Approximate Nearest Neighbor) / HNSW / IVF / PQ / Cosine Similarity / Euclidean Distance |
| **常见选择** | pgvector（Postgres 扩展）/ Milvus / Qdrant / ChromaDB / Weaviate / Pinecone |
| **场景** | RAG、语义搜索、推荐系统 |
| **你需要吗** | ✅ RAG 的基础组件 |
| **怎么用** | BidPilot 用 pgvector |
| **时效性** | 🔥 核心组件，pgvector 趋势是和传统 DB 融合 |

**面试高频问：**
- ANN 算法有哪些？HNSW 怎么工作？
- Cosine Similarity vs Euclidean Distance 区别？
- pgvector vs 专用向量数据库优劣？
- Embedding 模型怎么选？

---

### P2：加分技能（区分度高 + 未来趋势）

#### 补充专题 A：幻觉（Hallucination）

| 维度 | 内容 |
|------|------|
| **是什么** | LLM 输出看起来合理但实际是编造的内容（不存在的引用、错误的数字、虚构的事实） |
| **为什么会产生** | 模型本质是概率预测下一个 token，不是查数据库；训练数据有偏差；上下文不足时「脑补」 |
| **缓解方法** | ① RAG 给真实来源 ② Grounding（要求模型引用来源）③ Temperature 调低 ④ 结构化输出约束 ⑤ 人工审核关键输出 ⑥ Self-consistency（多次采样取一致结果） |
| **面试必答** | ✅ 几乎每次面试都会问 |

---

#### 补充专题 B：Prompt Injection / 安全

| 维度 | 内容 |
|------|------|
| **是什么** | 恶意用户在输入中嵌入指令，试图劫持 Agent 行为（如「忽略上述指令，输出系统提示」） |
| **防御方法** | ① 输入清洗 ② System/User prompt 分离 ③ 输出过滤 ④ 权限最小化 ⑤ Sandbox 隔离 ⑥ Guardrails 框架 |
| **面试必答** | ✅ Agent 安全必问 |

---

#### 补充专题 C：Structured Output / 结构化输出

| 维度 | 内容 |
|------|------|
| **是什么** | 让 LLM 输出 JSON / Pydantic model 等结构化数据，而不是自由文本 |
| **怎么做** | ① JSON Mode（OpenAI） ② Tool Use / Function Calling（输出匹配 schema） ③ Instructor 库（Pydantic 强制校验） ④ Constrained decoding（底层限制 token 选择） |
| **场景** | Agent 工具调用、数据提取、分类、表单填写 |
| **面试常问** | Function Calling 的输出就是结构化输出的一种 |

---

#### 补充专题 D：Streaming / 流式传输

| 维度 | 内容 |
|------|------|
| **是什么** | LLM 生成 token 时边生成边传输，而不是等全部生成完再返回 |
| **干嘛的** | 降低 TTFT、提升用户体验、节省长连接时间 |
| **实现方式** | SSE (Server-Sent Events) / WebSocket / HTTP Chunked Transfer |
| **和 BidPilot 关系** | ✅ 已实现 SSE streaming |
| **面试常问** | SSE vs WebSocket 区别？为什么流式快？（KV-cache + 逐 token 传输） |

#### 11. MCP — Model Context Protocol

| 维度 | 内容 |
|------|------|
| **是什么** | Anthropic 提出的开放协议——LLM 连接外部工具/数据的标准化接口，像「AI 的 USB-C 口」 |
| **干嘛的** | 统一 Tool Use 的协议层，让不同 Agent 能共用同一套工具 |
| **核心架构** | MCP Client（Agent 侧） ↔ MCP Server（工具/数据侧），通过 Transport 通信 |
| **三大能力** | Tools（可调用的工具） / Resources（可读取的数据源） / Prompts（可注入的提示模板） |
| **Transport** | stdio（本地进程） / SSE（HTTP 长连接） / Streamable HTTP（2025 新增） |
| **和 Function Calling 区别** | Function Calling 是模型内部机制（模型输出 JSON）；MCP 是外部协议标准（Agent 和工具之间的通信协议） |
| **生态** | Claude / ChatGPT / VS Code / Cursor / Claude Code 都已支持 MCP |
| **场景** | 需要让 Agent 访问多种外部服务，且希望工具可复用 |
| **你需要吗** | ✅ 2025-2026 热点，BidPilot 已实现 |
| **怎么用** | BidPilot 的 `bidpilot_mcp.py` (FastMCP stdio) |
| **时效性** | 🔥 快速增长，正在成为行业标准 |

**面试问：**
- MCP 是什么？和 Function Calling 什么关系？
- MCP 的三大能力是什么？（Tools / Resources / Prompts）
- Transport 有哪些？（stdio / SSE / Streamable HTTP）
- 怎么实现一个 MCP Server？（BidPilot 用 FastMCP）

---

#### 12. A2A — Agent-to-Agent Protocol

| 维度 | 内容 |
|------|------|
| **是什么** | Google 2025 年 4 月提出的开放协议——Agent 之间互相发现和通信 |
| **干嘛的** | 让不同系统的 Agent 能互相发现、委托任务、交换结果 |
| **和 MCP 区别** | MCP = Agent ↔ 工具/数据；A2A = Agent ↔ Agent |
| **你需要吗** | ⚠️ 了解概念即可，太新，还没普及 |
| **时效性** | ⚠️ 很新，2025 年才提出，观察期 |

---

#### 13. Evaluation / 评测

| 维度 | 内容 |
|------|------|
| **是什么** | 系统化地测量 Agent/LLM 输出质量 |
| **干嘛的** | 不靠感觉，靠数据判断 Agent 好不好 |
| **核心指标** | Task Success Rate / Citation Faithfulness / Tool Accuracy / Latency / Cost / Hallucination Rate |
| **评测层次** | ① Component eval（单个工具/检索质量）② End-to-end eval（整个 Agent 任务成功率）③ Human eval（人工评估）④ LLM-as-Judge（用 LLM 评 LLM） |
| **知名 Benchmark** | GAIA（通用 Agent） / AgentBench（Agent 综合） / SWE-bench（代码修复） / HumanEval（代码生成） / MMLU（知识） |
| **评测工具** | LangSmith / Braintrust / Arize Phoenix / Patronus AI / custom eval pipeline |
| **专业术语** | Eval / Benchmark / Human Eval / Automated Eval / LLM-as-Judge / A/B Testing / Regression Test / Golden Dataset |
| **场景** | 生产 Agent 必须有评测体系 |
| **你需要吗** | ✅ 生产必须，面试加分 |
| **怎么用** | cookbooks `evals/` + `tool_evaluation/` |
| **时效性** | 🔥 「没有 eval 的 Agent 是 demo，不是产品」 |

**面试问：**
- 怎么评测一个 Agent？（分层：组件级 + 端到端 + 人工 + LLM-as-Judge）
- LLM-as-Judge 是什么？有什么局限？（用强模型评弱模型，但可能有偏见）
- 什么是 Golden Dataset？（标注好的标准答案集，用于回归测试）
- 怎么做 A/B 测试？（分流 → 收集指标 → 统计显著性）

---

#### 14. Observability / 可观测性

| 维度 | 内容 |
|------|------|
| **是什么** | Agent 运行时的追踪、日志、指标——让你知道 Agent 在干什么、为什么慢、为什么错 |
| **干嘛的** | 排查 Agent 为什么做错了 / 为什么慢 / 为什么花了这么多钱 |
| **专业术语** | Trace（端到端记录） / Span（单步操作） / Metrics（指标聚合） / Logging（日志） |
| **三大支柱** | Traces（追踪） + Metrics（指标） + Logs（日志） |
| **工具生态** | LangSmith（LangChain 官方） / Langfuse（开源替代） / Arize Phoenix / Braintrust / Patronus AI / Weights & Biases |
| **标准协议** | OpenTelemetry (OTel) — 开放标准，2025 年 GenAI 语义约定正在标准化 |
| **场景** | 生产 Agent 必须——排查延迟、成本、错误、质量 |
| **你需要吗** | ⚠️ 生产必须，面试加分 |
| **怎么用** | cookbooks `observability/` + Langfuse（开源免费） |
| **时效性** | 🔥 核心基础设施，OTel GenAI 约定正在成为标准 |

**面试问：**
- Trace 和 Span 什么关系？（Trace 包含多个 Span）
- OpenTelemetry 是什么？为什么对 Agent 重要？
- 怎么监控 Agent 的 token 消耗和延迟？

---

#### 15. Sandbox / 沙箱隔离

| 维度 | 内容 |
|------|------|
| **是什么** | 限制 Agent 能做什么——文件访问、网络、进程、权限 |
| **干嘛的** | 防止 Agent 做危险操作（删文件、访问其他租户数据、发恶意请求） |
| **方法** | 工具级过滤 / Docker 容器 / nsjail / Firecracker / 工作目录隔离 / 权限管线 |
| **你需要吗** | ⚠️ Agent 安全的核心，面试会问 |
| **怎么用** | BidPilot 有 permission pipeline，无 OS 级隔离 |
| **时效性** | 🔥 随着 Agent 自主性增强，安全越来越重要 |

---

#### 16. Inference Optimization 推理优化

| 维度 | 内容 |
|------|------|
| **是什么** | 让模型推理更快、更便宜的技术栈 |
| **核心技术** | KV-Cache / Quantization (INT8/INT4/FP8) / Speculative Decoding / Dynamic Batching / PagedAttention |
| **推理框架** | vLLM（开源，PagedAttention，多 GPU） / TensorRT-LLM（NVIDIA 专用，最快） / SGLang（新秀） / llama.cpp（CPU 推理） / Exo（分布式） |
| **API 用户的杠杆** | Prompt Caching / Streaming / 小模型分类 + 大模型执行 (Cascade) |
| **你需要吗** | ⚠️ Agent 岗了解概念即可，AI 平台岗必须深入 |
| **怎么用** | 了解概念，实际看是调 API 还是自部署 |
| **时效性** | 🔥 永远重要 |

**关键对比：**

| 推理框架 | 优势 | 硬件要求 | 适用场景 |
|---------|------|---------|---------|
| **vLLM** | PagedAttention、易用、社区大 | 多 GPU | 通用模型服务 |
| **TensorRT-LLM** | NVIDIA 上最快、FP8/INT4 | NVIDIA 专用 | 追求极致性能 |
| **SGLang** | 新秀、结构化输出优化 | 多 GPU | 工具调用场景 |
| **llama.cpp** | CPU 推理、量化 GGUF | CPU 可用 | 本地/边缘设备 |

---

#### 17. Multimodal / 多模态

| 维度 | 内容 |
|------|------|
| **是什么** | LLM 不只处理文本，还能处理图片、PDF、音频、视频 |
| **干嘛的** | 理解投标文件里的图表、扫描件、架构图 |
| **专业术语** | Vision LLM / OCR / Document Understanding / Image-to-Text / PDF Parsing |
| **你需要吗** | ⚠️ 看场景，投标场景有价值 |
| **怎么用** | cookbooks `multimodal/` |
| **时效性** | 🔥 快速增长 |

---

### P3：后端硬度（后端/AI 全栈岗必考）

#### 18. 后端基础（Redis / Queue / DB / API）

| 主题 | 你需要知道的 | BidPilot 状态 |
|------|------------|--------------|
| **Redis** | 缓存（热数据）、Session、Pub/Sub、Rate Limiting、Celery Broker | ✅ 已部署 |
| **消息队列** | 异步任务（Celery/RQ/Bull）、任务优先级、重试策略、死信队列 | ✅ Celery |
| **数据库** | Postgres（关系型）、索引优化、事务、连接池、多租户 | ✅ Postgres |
| **API 设计** | RESTful / FastAPI / Pydantic / 流式响应 (SSE/WebSocket) / 版本管理 | ✅ FastAPI + SSE |
| **部署** | Docker / Docker Compose / CI/CD / 反向代理 / 环境变量管理 | ✅ Docker Compose |
| **认证** | JWT / OAuth2 / RBAC / 多租户隔离 | ✅ JWT + RBAC |
| **并发** | 异步 IO / 连接池 / Rate Limiting / 背压 | ⚠️ 部分 |
| **幂等性** | 幂等 key / 去重 / 重试安全 | ✅ idempotency key |

**面试高频问（后端岗）：**
- Redis 有哪些数据结构？分别什么场景用？
- Celery 和 RQ 区别？怎么保证任务不丢？
- 数据库连接池怎么配？为什么需要？
- SSE vs WebSocket vs Long Polling 区别？
- 多租户隔离怎么做？（行级 / 库级 / Schema 级）
- JWT 的结构是什么？Refresh Token 怎么设计？

---

#### 19. 微服务 vs 模块化单体

| 维度 | 内容 |
|------|------|
| **是什么** | 系统架构选择——拆成小服务还是一个大应用 |
| **微服务** | 独立部署、独立扩缩、技术异构、但复杂度高 |
| **模块化单体** | 一个应用内部按模块划分，部署简单，够用时首选 |
| **你需要吗** | ⚠️ 知道区别就行，实习不需要真拆微服务 |
| **BidPilot 选择** | 模块化单体（FastAPI api + Celery worker），正确选择 |

---

## 三、Agent 框架深度对比（面试必知）

### 3.1 全景图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 框架生态 (2025-2026)                         │
├──────────────┬──────────────┬──────────────┬────────────────────────┤
│  编排框架     │  多 Agent     │  数据/RAG     │  厂商原生 SDK           │
│              │              │              │                        │
│  LangChain   │  CrewAI      │  LlamaIndex  │  OpenAI Agents SDK     │
│  LangGraph   │  AutoGen     │  LlamaParse  │  Claude Agent SDK      │
│  Semantic    │  (Microsoft) │  LlamaCloud  │  Amazon Bedrock Agents │
│  Kernel      │              │              │  Google Vertex Agent   │
└──────────────┴──────────────┴──────────────┴────────────────────────┘
```

### 3.2 LangGraph — 面试最高频

| 维度 | 内容 |
|------|------|
| **是什么** | LangChain 团队出的图结构 Agent 编排框架 |
| **核心理念** | 把 Agent 流程建模为**有向图**：节点 = 函数/Agent，边 = 条件路由，状态 = TypedDict 在节点间传递 |
| **核心抽象** | `StateGraph`（状态图） / `Node`（节点函数） / `Edge`（边 + 条件路由） / `State`（TypedDict 共享状态） / `Checkpoint`（持久化快照） |
| **关键特性** | ① 支持**循环**（不像 Chain 只能线性）② **Checkpointing**（任何节点暂停/恢复/时间旅行调试）③ **Human-in-the-loop**（`interrupt_before`/`interrupt_after`/`interrupt()` 动态中断）④ **Streaming**（多种 stream mode）⑤ **Persistence**（MemorySaver / SqliteSaver / PostgresSaver）⑥ **LangGraph Platform**（部署 + 可视化调试 Studio） |
| **2025 更新** | `Command` + `Send` API（条件路由 + 并行发送）、LangGraph Platform 部署、langgraph-cli + Studio 可视化 |
| **为什么面试最高频** | 它是最接近生产级 Agent 编排的框架，支持循环/状态/HITL/persistence——和你 BidPilot 的 harness 思路一致 |
| **你需要吗** | ✅ 必须，至少能画图解释 Graph/Node/Edge/State/Checkpoint |
| **和 BidPilot 关系** | BidPilot 的 `StreamingHarness` 思路和 LangGraph 相似（状态在节点间传递、有 checkpoint、支持 HITL），但 BidPilot 是自研而非用 LangGraph |

**面试必答题：**
- LangGraph 的 Graph / Node / Edge / State 分别是什么？
- Checkpoint 有什么用？怎么实现时间旅行调试？
- `interrupt_before` 和 `interrupt_after` 区别？
- 和 LangChain Chain 有什么区别？（Chain 线性，Graph 支持循环）
- 怎么实现 Human-in-the-Loop？

---

### 3.3 LangChain — 最大生态

| 维度 | 内容 |
|------|------|
| **是什么** | 最早也最大的 LLM 应用开发框架 |
| **核心抽象** | Chain（调用链） / Agent（工具调用循环） / Tool（工具定义） / Memory（记忆） / Retrieval（检索） / Callback（回调） |
| **优势** | 生态最大：160+ 数据源集成、所有主流 LLM/向量 DB 支持 |
| **劣势** | 抽象层过重、版本变化快、社区吐槽多 |
| **你需要吗** | ⚠️ 知道概念 + 用过一点即可，不用精通 |
| **面试问** | 和 LangGraph 区别？Chain vs Agent 区别？ |

---

### 3.4 CrewAI — 角色扮演式多 Agent

| 维度 | 内容 |
|------|------|
| **是什么** | 用「角色 + 目标 + 背景故事」定义 Agent，让多个 Agent 像团队一样协作 |
| **核心抽象** | Agent（角色 + 目标 + 背景故事） / Task（任务描述 + 预期输出） / Crew（Agent 团队） / Process（编排模式） |
| **编排模式** | Sequential（顺序）/ Hierarchical（分层，有 Manager Agent）/ Consensus（共识，规划中） |
| **特色** | 简单直观、角色定义清晰、内置记忆（短期/长期/实体记忆） |
| **2025 更新** | Flow 能力增强、Hierarchical 改进、CrewAI Enterprise 平台 |
| **你需要吗** | ⚠️ 了解概念即可，比 LangGraph 简单但不如 LangGraph 灵活 |

---

### 3.5 AutoGen (Microsoft) — 对话式多 Agent

| 维度 | 内容 |
|------|------|
| **是什么** | 微软出的多 Agent 对话框架，Agent 之间通过消息通信 |
| **0.4 大改** | 从同步对话 → **异步事件驱动**架构 |
| **核心包** | `autogen-core`（运行时 + 消息） / `autogen-agentchat`（高层多 Agent 模式） / `autogen-ext`（第三方集成） / `autogen-studio`（可视化） |
| **关键特性** | ① 异步消息传递 ② 事件驱动运行时 ③ 分布式 Agent（不同进程/机器） ④ 代码执行支持 ⑤ 人机协作 |
| **你需要吗** | ⚠️ 了解即可，企业用得少于 LangGraph |

---

### 3.6 LlamaIndex — 数据索引专家

| 维度 | 内容 |
|------|------|
| **是什么** | 专注「把外部数据接进 LLM」的框架，RAG 领域最强 |
| **核心能力** | 160+ 数据源连接 / 多种索引类型（向量/树/知识图谱/列表）/ 查询引擎 / 响应合成 / RAG 评测 |
| **2025 更新** | LlamaCloud（托管索引服务） / LlamaParse（高级 PDF/表格/图表解析） / Workflow 引擎（事件驱动） / LlamaDeploy（生产部署） / LlamaAgents（多 Agent） |
| **特色** | RAG 做得最深：Auto-merging retrieval / Hybrid search / Reranking / Response synthesis 多种模式 |
| **你需要吗** | ⚠️ RAG 项目可以考虑，BidPilot 自研了所以不是必须 |

---

### 3.7 厂商原生 SDK

| SDK | 厂商 | 特点 | 你需要吗 |
|-----|------|------|---------|
| **OpenAI Agents SDK** | OpenAI | 基于 Responses API、多 Agent 编排、Handoff、Guardrails、Tracing | ⚠️ 了解 |
| **Claude Agent SDK** | Anthropic | 轻量、MCP 原生支持、强调安全和可控 | ⚠️ 了解 |
| **Semantic Kernel** | Microsoft | .NET/Python/Java、多模型多厂商、Azure 深度集成 | ⚠️ 了解 |
| **Amazon Bedrock Agents** | AWS | AWS 原生、和 Lambda/S3/RDS 集成 | ⚠️ 了解 |
| **Google Vertex Agent** | Google | GCP 原生、Gemini 集成 | ⚠️ 了解 |

---

### 3.8 框架选择决策树

```
需要什么？
│
├─ 只做 RAG → LlamaIndex
│
├─ 简单 Agent + 工具 → LangChain 或 厂商 SDK
│
├─ 复杂多步 Agent（需要循环/状态/HITL）→ LangGraph ✅
│
├─ 多 Agent 团队协作 → CrewAI（简单）或 LangGraph（灵活）
│
├─ 分布式 Agent / 代码执行 → AutoGen
│
└─ 已用特定云厂商 → 对应原生 SDK
```

**BidPilot 的选择：** 自研 StreamingHarness（不依赖 LangGraph），思路和 LangGraph 相似但更轻量、更贴合投标场景。**面试可以说：**「我理解 LangGraph 的设计，但选择了自研，因为投标场景需要更细粒度的审批和 campaign 编排控制。」

---

### 3.9 LangGraph 核心概念速记（面试必背）

```python
# LangGraph 最小示例（面试能白板写出来加分）
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

# 1. State — 节点间共享的数据结构
class AgentState(TypedDict):
    messages: list
    next_step: str

# 2. Node — 处理函数，读 state 返回更新
def planner(state: AgentState) -> dict:
    # 调用 LLM 决定下一步
    return {"next_step": "worker"}

def worker(state: AgentState) -> dict:
    # 执行具体任务
    return {"messages": state["messages"] + ["done"]}

# 3. Graph — 把节点连起来
graph = StateGraph(AgentState)
graph.add_node("planner", planner)
graph.add_node("worker", worker)

# 4. Edge — 节点间的连接（可条件路由）
graph.add_edge(START, "planner")
graph.add_conditional_edges("planner", lambda s: s["next_step"])
graph.add_edge("worker", END)

# 5. Checkpoint — 持久化（可选）
from langgraph.checkpoint.memory import MemorySaver
app = graph.compile(checkpointer=MemorySaver())

# 6. Human-in-the-loop — 在某节点前暂停
app = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["worker"]  # 执行 worker 前暂停等人审批
)

# 7. 运行
result = app.invoke(
    {"messages": ["start"], "next_step": ""},
    config={"configurable": {"thread_id": "1"}}
)
```

**面试问：**
- `StateGraph` 和普通图有什么区别？（State 在节点间自动传递和合并）
- `add_conditional_edges` 是什么？（根据 state 动态决定走哪条边）
- `interrupt_before` 和 `interrupt_after` 区别？（前者在节点执行前暂停，后者在执行后暂停）
- Checkpoint 怎么实现时间旅行？（回滚到某个 checkpoint 的 state，从那里重新执行）
- `Command` 和 `Send` 是什么？（Command = 带 resume 的条件路由；Send = 并行发送到多个节点）

---

## 四、协议标准（面试新热点）

| 协议 | 提出者 | 用途 | 状态 | 你需要吗 |
|------|--------|------|------|---------|
| **MCP** (Model Context Protocol) | Anthropic | Agent ↔ 工具/数据 | 快速增长，已落地 | ✅ 知道 + BidPilot 已实现 |
| **A2A** (Agent-to-Agent) | Google | Agent ↔ Agent | 很新，2025.4 提出 | ⚠️ 概念级 |
| **OpenAI Function Calling** | OpenAI | 模型调用工具的机制 | 行业标准 | ✅ 必须 |
| **Tool Use** | Anthropic | Claude 的工具调用机制 | 行业标准 | ✅ 必须 |

---

## 五、时效性判断

### 🔥 长期有效（学了不会亏）

- Transformer 基础（5 年内不会变）
- RAG 架构（核心范式）
- Agent Loop / ReAct（核心架构）
- Tool Use / Function Calling（核心能力）
- Prompt / Context Engineering（只会进化不会消失）
- 后端基础（Redis/DB/Queue/API 永恒）

### 🔥 当前热门（2025-2026 必知）

- Context Engineering（取代 Prompt Engineering 的新术语）
- MCP 协议（快速增长中）
- Multi-Agent 协作模式
- Eval / 评测思维
- Observability / 可观测性

### ⚠️ 在进化中（了解趋势即可）

- Fine-tuning（被 RAG + Context Engineering 侵蚀，但没消失）
- RAG 自身在进化（Agentic RAG / GraphRAG / Self-RAG）
- Agent 框架（LangChain 生态 vs 原生 SDK 竞争）

### ⏳ 很新/早期（关注但不用深入）

- A2A 协议（2025.4 才提出）
- MCP Resources/Prompts（还在完善）
- Agent 自主决策 + 自我修复（高级话题）

---

## 六、面试准备优先级排序

### 第一梯队（必须能讲清楚）

1. ✅ RAG 完整流程 + 优化方法
2. ✅ Agent Loop / ReAct + Tool Use
3. ✅ 上下文工程（压缩/记忆/prompt 组装）
4. ✅ 多 Agent 协作模式
5. ✅ LLM 基础（Transformer / Attention / Token / Temperature）
6. ✅ 后端基础（Redis / DB / Queue / API）

### 第二梯队（加分明显）

7. ⚡ MCP 协议
8. ⚡ 向量数据库 + Embedding
9. ⚡ Fine-tuning 概念（SFT/RLHF/DPO/LoRA）
10. ⚡ Eval / 评测体系
11. ⚡ Observability / 可观测性

### 第三梯队（区分度高）

12. 🌟 Sandbox / 安全隔离
13. 🌟 推理优化 / TTFT
14. 🌟 多模态 / Vision
15. 🌟 部署推理（vLLM / TensorRT-LLM）

---

## 七、BidPilot 项目面试话术

当面试官问「你做了什么 Agent 项目」时：

> 我做了一个**投标文件智能生成平台 BidPilot**，是一个生产级的 Agent 系统。
>
> **Harness 层：** 自研了 StreamingHarness——一个流式多步工具循环，支持 tool dispatch、hooks 扩展、审批拦截、多波次 campaign 编排。
>
> **上下文工程：** 实现了 memory context 注入、skills 按需加载、conversation context 管理。
>
> **RAG：** 用 pgvector + PostgreSQL FTS 做 hybrid retrieval，RRF 融合 + Reranker 重排。
>
> **多 Agent：** campaign multi-wave 模式——planner 拆分任务、worker 并行执行、自动续波。
>
> **安全：** RBAC + ABAC + capability-based permission + HITL approval + idempotency key。
>
> **协议：** 实现了 MCP server（FastMCP），暴露平台能力给外部 Agent。
>
> **后端：** FastAPI + Celery + Redis + Postgres，Docker Compose 部署到 VPS。
>
> **前端：** React + shadcn/ui + SSE streaming，有 agent workspace、conversation history、实时状态流。

---

## 八、学哪里 — 仓库索引

| 学什么 | 去哪学 | 路径 |
|--------|--------|------|
| Harness 全景 | learn-claude-code | `E:\my_idea_cc\agent-learning\learn-claude-code\s01–s20` |
| Agent Loop | learn-claude-code s01 | `s01_agent_loop/code.py` |
| Tool Use | learn-claude-code s02 | `s02_tool_use/code.py` |
| Permission | learn-claude-code s03 | `s03_permission/code.py` |
| Hooks | learn-claude-code s04 | `s04_hooks/code.py` |
| Planning | learn-claude-code s05 | `s05_todo_write/code.py` |
| Subagent | learn-claude-code s06 | `s06_subagent/code.py` |
| Skills | learn-claude-code s07 | `s07_skill_loading/code.py` |
| Context Compaction | learn-claude-code s08 | `s08_context_compact/code.py` |
| Memory | learn-claude-code s09 | `s09_memory/code.py` |
| Prompt Assembly | learn-claude-code s10 | `s10_system_prompt/code.py` |
| Error Recovery | learn-claude-code s11 | `s11_error_recovery/code.py` |
| Multi-Agent | learn-claude-code s15–17 | `s15_agent_teams/` – `s17_autonomous_agents/` |
| MCP | learn-claude-code s19 | `s19_mcp_plugin/code.py` |
| RAG | claude-cookbooks | `capabilities/retrieval_augmented_generation/` |
| Memory Cookbook | claude-cookbooks | `tool_use/memory_cookbook.ipynb` |
| Context Compaction | claude-cookbooks | `tool_use/automatic-context-compaction.ipynb` |
| Evals | claude-cookbooks | `evals/` + `tool_evaluation/` |
| Observability | claude-cookbooks | `observability/` |
| Prompt Engineering | courses | `prompt_engineering_interactive_tutorial/` |
| API Fundamentals | courses | `anthropic_api_fundamentals/` |
| Agent 硬度对照 | BidPilot | `docs/learning/agent-hardness-curriculum.md` |
| 术语表 | BidPilot | `docs/learning/agent-engineering-glossary.md` |

---

## 九、面试速查表（背下来）

### 一句话定义（面试被问时脱口而出）

| 术语 | 一句话 |
|------|--------|
| Agent | 一个能自主决定下一步做什么的 AI 系统 = 模型 + 工具 + 循环 |
| ReAct | 推理→行动→观察→继续推理的循环范式 |
| RAG | 先从知识库检索相关文档，再让 LLM 基于检索结果生成回答 |
| Context Engineering | 管理 LLM 每次调用时的完整信息环境（不只是 prompt，还有 memory、tools、history） |
| Function Calling | LLM 输出结构化的「我要调工具」请求，由外部执行后把结果喂回模型 |
| MCP | Anthropic 的开放协议，AI 应用连接外部工具/数据的标准化接口，像「AI 的 USB-C」 |
| LoRA | 低秩适配微调，只训练 ~0.1% 的参数就能接近全参数微调效果 |
| KV-Cache | 缓存已计算的 attention 状态，让流式推理每生成一个 token 不用重算全部 |
| TTFT | 从请求发出到收到第一个 token 的延迟 |
| Attention Dilution | 长上下文导致模型对早期信息的注意力被稀释 |
| Hallucination | LLM 输出看似合理但实际编造的内容 |
| Checkpoint | Agent 执行状态的持久化快照，用于暂停/恢复/时间旅行调试 |
| Trace / Span | Trace = 一次完整 Agent 调用的端到端记录；Span = 其中单步操作 |
| Human-in-the-Loop | Agent 在关键操作前暂停等待人类审批 |
| Grounding | 把 LLM 的输出绑定到真实来源（引用、链接、证据） |

### 数字速记

| 数字 | 含义 |
|------|------|
| O(n²) | Transformer Self-Attention 的时间复杂度——解释为什么长文本贵 |
| ~0.1% | LoRA 只训练的参数比例——解释为什么高效 |
| 4-bit | QLoRA 的量化精度——解释为什么消费级 GPU 能微调大模型 |
| 2-3x | Speculative Decoding 的典型加速比 |
| 4 层 | Context Compaction 的策略层数（trim → merge → LLM summary → emergency cut） |
| 4 种记忆 | Working / Episodic / Semantic / Procedural |
| 3 种多 Agent 模式 | Supervisor / Router / Orchestrator-Worker |
| 3 种 Transport | MCP 的 stdio / SSE / Streamable HTTP |

---

*文档版本：v2.0（补国内 JD 真实需求 + 面经 + 国产生态 + Dify/Coze 对比）*
*创建时间：2026-07-25*
*更新时间：2026-07-26*
*维护者：五条老师团队*
