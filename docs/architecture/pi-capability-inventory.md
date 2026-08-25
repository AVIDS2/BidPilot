# Pi 能力清单与启用状态

> 审计日期：2026-08-25  
> 目的：把 Pi 收到的工具、Skills、MCP、扩展和沙箱边界分开记录，后续逐项做官方资料调研、能力评估和前端适配。  
> 结论不能把“代码支持”误写成“生产已启用”。

## 1. 先看结论

| 层 | 本地当前代码 `5ddbf1f` | 公网当前代码 `f3d445c` | 真实含义 |
| --- | --- | --- | --- |
| Pi 运行时 | 已接入 `@earendil-works/pi-agent-core` / `pi-ai` 的 Pi `AgentSession` | 已启用 | Pi 负责模型轮次、流式事件、工具生命周期、重试、压缩和终止信号 |
| 业务工具 | 42 个 API capability + `read_skill` | 旧版本能力目录，尚未含本地新增的通用深度调研运行 | 工具由 API 动态生成，Pi 不持有数据库或租户密钥 |
| Skills | 5 个本地 Skill 元数据 | 旧版本 4 个领域 Skill | 只发送元数据；模型显式调用 `read_skill` 后才加载正文 |
| MCP | 代码支持 stdio / Streamable HTTP 动态发现 | 生产白名单为空 | 当前没有任何 MCP 工具进入 Pi；`mcp_<server>_<tool>` 只是扩展协议，不代表已经配置 |
| Pi 扩展 | governance、skills、subagents 三个一方扩展 | 已启用治理和 Skills，子 Agent 以生产代码为准继续做健康检查 | 扩展是构建时信任列表，不接受租户随意注入 npm 包 |
| 云沙箱 | `governed_cloud` | `governed_cloud` | 主机工具关闭，网络只能走业务桥接；不是 bash/read/write 云端工作区 |
| 搜索 | 本地支持 Hikari Bearer / 官方 Tavily 两种协议 | `TAVILY_API_KEY` 已配置，Hikari base 未配置 | 公网当前实际走官方 Tavily endpoint；本地 Hikari 修复尚未发布 |
| Mem0 | 代码已接入 | `DOCPILOT_MEM0_ENABLED=true` | 只做低风险用户画像/偏好；项目事实、期限、证据仍在 PostgreSQL |

公网配置的只读核对结果：`DOCPILOT_ASSISTANT_ENGINE=pi`、`DOCPILOT_MEM0_ENABLED=true`、`DOCPILOT_MCP_SERVERS` 为空、`TAVILY_HIKARI_BASE_URL` 和 `TAVILY_API_BASE_URL` 为空、`TAVILY_API_KEY` 存在。

## 2. Pi 收到的工具

Pi 的基础目录由 `services/api/app/runtime/pi_config.py` 生成。当前本地是 42 个业务 capability，外加 1 个 `read_skill` 工具。只读 capability 默认 `executionMode=parallel`；写入、计费、破坏和导航操作默认 `sequential`。

### 项目与上下文

| 工具 | 风险 | 作用 |
| --- | --- | --- |
| `search_projects` | read | 查找当前用户可访问的项目 |
| `create_demo_workspace` | low-risk-write | 创建演示工作区 |
| `create_project` | low-risk-write | 创建投标项目 |
| `get_project_summary` | read | 读取项目概览 |
| `list_project_bundles` | read | 读取项目资料包 |
| `list_sections` | read | 读取章节列表 |
| `get_project_outline` | read | 读取响应大纲 |
| `list_pending_reviews` | read | 查找待审核章节 |
| `get_runtime_status` | read | 查询运行状态 |

### 需求、证据与交付

| 工具 | 风险 | 作用 |
| --- | --- | --- |
| `list_requirements` | read | 列出需求 |
| `list_claim_review_queue` | read | 列出待核验 AI 主张 |
| `get_readiness_summary` | read | 读取投标准备度 |
| `list_readiness_gaps` | read | 查找合规、证据和截止期缺口 |
| `open_requirement_source` | read | 打开需求来源定位 |
| `list_evidence` | read | 列出证据 |
| `list_deliverables` | read | 列出交付物 |
| `list_documents` | read | 列出资料 |
| `get_section_versions` | read | 读取章节版本 |
| `create_deliverable` | low-risk-write | 创建交付物记录 |
| `export_deliverable` | costing | 生成并导出交付文件 |
| `generate_readiness_pack` | low-risk-write | 生成投标准备度包 |

### 起草、审核与长期工作流

| 工具 | 风险 | 作用 |
| --- | --- | --- |
| `start_draft_section` | costing | 启动章节起草工作流 |
| `start_redraft_section` | costing | 启动章节重写工作流 |
| `write_section` | low-risk-write | 将内容写入章节版本 |
| `resume_draft_run` | low-risk-write | 根据审核决定恢复起草运行 |
| `retry_run` | costing | 重试已有工作流 |
| `run_section_campaign` | costing | 运行多章节起草战役 |
| `submit_review_decision` | low-risk-write | 提交人工审核决定 |
| `attach_uploaded_documents` | costing | 将附件加入资料包并投递解析 |
| `upload_document` | costing | 上传资料到项目 |

### 外部研究与远程资料

| 工具 | 风险 | 作用 |
| --- | --- | --- |
| `web_search` | read / parallel | 单次公开网页检索；不是深度调研运行 |
| `start_deep_research` | costing / sequential | 启动持久化的计划、并行检索、正文读取、主张核验和报告生成运行；本地已实现，公网尚未发布 |
| `discover_remote_documents` | read / parallel | 只读检查一个公开页面的直接附件链接 |
| `fetch_url_to_project` | costing | 经确认后下载并入库远程资料 |

### 知识与记忆

| 工具 | 风险 | 作用 |
| --- | --- | --- |
| `semantic_search` | read | 检索项目资料证据片段 |
| `search_bid_wiki` | read | 查询 Bid Wiki / 项目记忆 |
| `list_knowledge_portfolio` | read | 查看知识资产概览 |
| `propose_memory` | low-risk-write | 保存用户低风险工作偏好 |
| `forget_memory` | destructive | 删除一条用户记忆 |
| `propose_memory_graph` | costing | 从已验证知识生成待审核实体关系提案 |

### 导航与破坏性操作

| 工具 | 风险 | 作用 |
| --- | --- | --- |
| `open_page` | navigate | 返回一个需要用户点击的结构化页面入口 |
| `delete_project` | destructive | 删除项目，需要项目权限和完整名称确认 |

### Skill 入口

`read_skill(name)` 是 Pi 的第 43 个工具。它只接受 `AVAILABLE_SKILLS` 中的精确名称，不通过用户文本关键词路由。它的执行模式是 sequential，因为一次加载的流程正文会改变当前模型上下文。

## 3. 当前 Skills

| Skill | 当前用途 | 前端 presentation |
| --- | --- | --- |
| `bid-outline-first` | 写章节前先解析稳定的 `section_key` | 普通任务轨迹 |
| `bid-research` | 投标项目外部研究、附件发现、经确认后保存证据或资料 | 普通/研究任务 |
| `bid-tender-writer` | 已知项目的标书起草、续写、重写和合规审阅 | 普通/起草任务 |
| `deep-research` | 通用、有边界、来源可追溯的深度研究运行 | `deep_research` 专用运行面板 |
| `opportunity-deep-research` | 招标机会只读调研的领域包装；约束候选数量、官方来源和禁止动作 | `deep_research` 专用运行面板 |

Skills 的实际加载路径是：

1. API 扫描 `docs/agent-skills/*/SKILL.md` 的 frontmatter；
2. Pi 只收到名称和描述；
3. 模型调用 `read_skill`；
4. API 返回截断到约 1,200 字符的流程正文；
5. 网页、邮件、资料正文仍然是数据，不会因为 Skill 正文而获得指令权限。

## 4. MCP 能力

### 代码支持

`services/api/app/runtime/mcp_client.py` 支持：

- stdio MCP：`command + args + env`；
- Streamable HTTP MCP：`url`；
- 20 秒发现/调用超时；
- 每个进程按服务名复用连接，空闲 300 秒回收；
- 工具名统一暴露为 `mcp_<server>_<tool>`，避免和一方 capability 重名；
- 默认只读感知；只有服务名列入 `DOCPILOT_MCP_TRUSTED_MUTATIONS` 才允许被标记为受信变更服务；
- MCP 不可用时跳过发现，不阻塞普通 Pi 回合。

### 实际配置

本地和公网 `DOCPILOT_MCP_SERVERS` 都为空，因此目前 **没有 MCP server，也没有 MCP tool** 进入 Pi。代码和文档中曾出现 `tavily-mcp` 示例，但它不是当前生产配置；当前搜索入口是 API 自有 `web_search` capability。后续如果接入 MCP，必须先决定它是补充工具还是替代现有 Tavily，不能双路径重复暴露同一搜索能力。

## 5. Pi 扩展与子 Agent

当前一方扩展白名单：

- `bidpilot-governance`：在 Pi 原生 `tool_call` hook 再次校验 API 下发的工具集合、输入大小和主机工具禁用规则；
- `bidpilot-skills`：把 Skill 元数据拼入 Pi 的可用 Skill 区域，并要求 `read_skill` 存在；
- `bidpilot-subagents`：注册 `spawn_subagents` 原生 Pi 工具，任务通过 API bridge 进入持久化子运行。

`spawn_subagents` 的边界：

- `single`、`parallel`、`chain` 三种模式；
- 单次最多 8 个子任务；
- 每个子任务最多 32 个 child steps；
- `foreground` 默认等待子结果；`background` 只有用户明确要求异步时使用；
- 单次任务描述最多约 12 KB；观察结果受沙箱上限保护；
- 子运行由 PostgreSQL/Worker 持久化，不是仅存在于当前对话上下文。

## 6. 沙箱和模型边界

当前 Pi 云沙箱固定为：

```json
{
  "profile": "governed_cloud",
  "hostTools": "disabled",
  "network": "bridge_only",
  "maxToolInputBytes": 131072,
  "maxToolObservationBytes": 524288
}
```

因此 `bash`、`read`、`write`、`edit`、`grep`、`find`、`ls` 不是当前云端 Pi 工具。要实现用户本地终端操作，需要另一个隔离 workspace runner，不能把这些工具直接加进云端业务会话。

模型协议和 provider 由 API 运行时配置传给 Pi；Pi 使用 `pi-ai` 的 provider/model catalog，但租户密钥只在 API/Worker 侧解密，浏览器和 Pi sidecar 不持有数据库、对象存储或租户凭据。

## 7. 目前最值得逐项调研的缺口

这份清单只做盘点，不替代后续调研。建议按下面顺序逐项验证：

1. `web_search` 与 `start_deep_research`：官方 Tavily、Hikari 网关、正文抽取、来源评分、停止条件和前端运行态；
2. `read_skill`：渐进式披露长度、Skill 版本/依赖、Skill 资源和安全隔离；
3. MCP：官方 Tavily MCP、官方 GitHub MCP、Streamable HTTP 认证和 MCP 工具治理；
4. `spawn_subagents`：Pi/OpenCode/DeerFlow 的 foreground/background、child session、并行取消、子结果汇总和 UI 分栏；
5. 资料工具：远程下载、PDF/DOCX/XLSX 解析、SSRF、断点恢复、入库与交付物关联；
6. 业务工作流：`start_draft_section`、`run_section_campaign`、人工审批、LangGraph checkpoint 和交付导出；
7. 记忆：PostgreSQL 项目事实、Bid Wiki、Mem0 画像和跨会话唤醒如何保持边界；
8. UI：Pi 原生事件、Skill/MCP 运行事件、子 Agent 分栏、深度调研专用面板和恢复态如何映射到实时组件。

每一项调研必须分别产出：官方资料、当前实现差距、是否需要替换现有代码、前端呈现方案、测试场景和发布门槛。
