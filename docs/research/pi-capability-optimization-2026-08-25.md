# Pi 能力 1–8 调研与优化记录

> 研究时间：2026-08-25  
> 范围：搜索/深度调研、Skills、MCP、子 Agent、资料摄取、LangGraph、记忆、前端运行态。  
> 方法：官方文档优先，Tavily CLI 做当前资料检索，GitHub CLI 检查仓库活跃度、许可证和适配性。没有因为星数就直接引入第三方代码。

## 结论摘要

| 项 | 采用方向 | 本轮落地 |
| --- | --- | --- |
| 1 搜索/DR | 自有受治理 `start_deep_research` 运行；Tavily/Hikari 作为搜索适配器；证据和报告持久化 | 已落地：深度、主题、并发预算、取消检查、报告 validator |
| 2 Skills | 采用 Agent Skills 标准包：`SKILL.md` + `skill.json` + `scripts/`/`references/`/`assets/`；按需资源读取 | 已落地：`read_skill_resource`、资源路径白名单、标准校验 |
| 3 MCP | 保持 MCP 为可选外部感知边界；配置白名单、分页发现、结构化 output schema、注解不授予权限 | 已落地：`tools/list` cursor 分页、outputSchema/annotations 传递；生产仍未启用 MCP |
| 4 子 Agent | Pi 原生 `spawn_subagents`，API/Worker 持久化 child run；foreground 默认等待，background 明确选择 | 已落地：前端活动轮询、状态修复；后续补 child event cursor 与取消聚合 |
| 5 资料 | 远程地址只经 SSRF/大小/超时/重定向守卫；网页正文与二进制附件分离；Worker 负责大文件 | 已落地：`Content-Disposition` 文件名解析；现有下载/解析边界保留 |
| 6 LangGraph | 只用于长期业务工作流；Postgres checkpointer + 稳定 `thread_id` + `interrupt`/`Command(resume=...)` | 已核对并保留现有实现；不把 LangGraph 混回 Pi 聊天循环 |
| 7 记忆 | PostgreSQL 是项目事实；Mem0 只做低风险画像；user/assistant entity 必须隔离 | 已落地：assistant entity 改为 user-scoped，避免组织成员交叉污染 |
| 8 前端 | 根据真实 runtime event 渲染专用视图；MCP/Skill/子 Agent/DR 不平铺成普通搜索行 | 已落地：Pi 能力面板资源清单、子 Agent 活动轮询、DR 专用运行面板 |

## 1. 搜索与 Deep Research

### 调研结论

- Tavily 的官方 Agent 集成和 GPT Researcher 都强调“并行研究者/来源整理/报告合成”，不是无上限重复搜索。
- LangChain 的 Open Deep Research 展示了可替换搜索 API、MCP 和 LangGraph Studio 配置，但仓库状态与许可证/维护情况仍需单独审计，不能直接替换 BidPilot 控制面。
- `dzhng/deep-research` 是极简迭代研究循环，适合验证“计划 -> 搜索 -> 深挖 -> 合成”的最小闭环；`AnotiaWang/deep-research-web-ui` 适合参考专用研究运行 UI，不适合直接接入我们的租户和权限。
- Hikari 官方仓库的 HTTP cheat sheet 规定代理路径为 `/api/tavily/search`；配置中的 `TAVILY_API_BASE_URL` 应优先于根域名变量，调用端再补 `/search`。本轮真实请求曾因错误优先级命中根域名 `/search` 返回 404，现已修正并通过真实常州招标查询。

### 当前改造

`start_deep_research` 是 Pi 可选的结构化工具。它创建独立 `RuntimeRun(kind=deep_research)`，Worker 完成：

```text
scope -> plan -> parallel retrieve -> read HTML/PDF -> verify claims -> synthesize -> package
```

每个来源带 `source_id`，每条主张带 `source_ids` 和 `verification`；报告落在终态事件的红acted result 中，可在断线后恢复。`quick/standard/deep` 分别限制查询和来源预算。取消请求在阶段边界生效，不依靠前端断开连接。

## 2. Skills

### 官方标准

Agent Skills 规范要求每个包至少有 `SKILL.md`，推荐将可执行脚本放入 `scripts/`，延迟参考资料放入 `references/`，生成资产放入 `assets/`，并通过渐进式披露降低上下文污染。官方参考校验器会检查 frontmatter、命名和未完成脚手架。

### 当前改造

`deep-research` 现在包含：

- `SKILL.md`：路由和不可变业务边界；
- `skill.json`：版本、许可证、兼容性、presentation 和资源清单；
- `references/source-quality.md`：来源质量层级；
- `references/report-contract.json`：报告结构契约；
- `scripts/validate_report.py`：确定性报告校验器。

Pi 先拿元数据，再通过 `read_skill` 读取入口，需要时通过 `read_skill_resource` 读取已声明资源。资源读取不能访问 Skill 包外的路径，也不能读取宿主机任意文件。

`qodex-ai/ai-agent-skills@creative-generation-agent` 在 skills.sh 有 534 次安装，但源仓库只有 41 stars，且它解决的是创意生成而不是技能包工程；本轮没有把它当作核心依赖。技能包结构采用官方 `agentskills/agentskills` 和高活跃的 `obra/superpowers` / `addyosmani/agent-skills` 的可验证做法。

## 3. MCP

MCP 官方规范要求：

- `tools/list` 用不透明 cursor 分页；
- 工具可以声明 `outputSchema`；
- `annotations` 不能自动被当作可信权限；
- 工具调用应有清晰 UI 指示和必要人工确认；
- 工具自身错误应通过 `isError` 让模型看到，协议级找不到工具才用协议错误。

本轮让客户端最多消费 32 页工具列表，保留 output schema/annotations，并继续把所有 MCP 默认标成 sensing-only。公网没有配置 MCP server，因此不会出现“代码看起来支持、实际偷偷启用”的假象。

候选只进入后续评估：官方 GitHub MCP、Microsoft Playwright MCP、FastMCP。必须先做许可证、远程认证、租户隔离、工具输出契约和确认 UX 评估，不能直接把 `tavily-mcp` 与内置搜索双挂。

## 4. 子 Agent

Pi 扩展保留 `single/parallel/chain`，每次最多 8 个任务、深度最多 3、单任务最多 32 steps。API/Worker 持久化 child run，前端不再只在创建时读一次：父任务活动期间每 1.2 秒刷新子运行和选中 child 的事件；终态 child 不再轮询。状态文案同时识别 `succeeded/completed/failed/cancelled`。

后续必须补：child event cursor、父级取消聚合、foreground 超时后的明确“后台继续”状态，避免把长任务误认为失败。

## 5. 资料摄取

现有 `web_import` 已有公共 URL、SSRF、重定向、字节数、超时和网页/附件分流。补充了 `Content-Disposition` 的 RFC 5987/legacy 文件名解析，并继续使用 URL 名称作为回退。远程 ZIP、PDF 等大文件仍由 Worker 临时文件流式下载，不放在 Pi 请求内存里。

## 6. LangGraph

官方文档确认生产长流程需要 checkpointer 与稳定 `thread_id`；人工中断通过 `interrupt()`，后续以同一 `thread_id` 的 `Command(resume=...)` 继续。当前 BidPilot Worker 图已经使用 PostgresSaver、项目运行 ID作为默认 thread id 和审核恢复函数。本轮不把 LangGraph 引入 Pi 的即时对话层，保持两个运行时边界。

## 7. Mem0

官方文档明确区分 `user_id`、`agent_id`、`run_id`、`app_id`。本轮把原来的共享 assistant id 改为 `bidpilot-assistant:<user_id>`，并在搜索过滤器使用当前用户对应的 assistant entity。项目事实、招标期限、预算、证据和文件不进入 Mem0，仍由 PostgreSQL/BidPilot 知识域负责。

## 8. 前端

能力面板现在展示：工具总数、并行工具数、Skill 数量、Skill 版本/资源数量、MCP server 数量和 transport。运行态继续按照事件关系渲染：

- Skill：使用 Skill / 读取 Skill 资源；
- MCP：显示 provider 和外部工具名；
- Deep Research：显示阶段、来源、主张和报告；
- 子 Agent：显示分页 child、实时状态和 child 事件；
- 普通搜索：保留普通工具行，不冒充深度研究。

## 参考来源

- [Agent Skills specification](https://agentskills.io/specification)
- [MCP tools specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [MCP protocol repository](https://github.com/modelcontextprotocol/modelcontextprotocol)
- [LangGraph durable execution and interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Mem0 memory types and scopes](https://docs.mem0.ai/core-concepts/memory-types)
- [GPT Researcher](https://github.com/assafelovic/gpt-researcher)
- [Open Deep Research](https://github.com/langchain-ai/open_deep_research)
- [Deep Research Web UI](https://github.com/AnotiaWang/deep-research-web-ui)
- [Agent Skills reference repository](https://github.com/agentskills/agentskills)
- [Superpowers](https://github.com/obra/superpowers)
- [Pi/OpenCode-style skill package examples](https://github.com/addyosmani/agent-skills)
