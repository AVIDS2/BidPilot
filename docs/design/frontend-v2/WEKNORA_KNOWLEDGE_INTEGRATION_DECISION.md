# BidPilot x WeKnora 知识基础设施接入决策

> 状态：调研完成，待独立后端分支实施。
>
> 目标：用腾讯 WeKnora 替换 BidPilot 自研的文档解析、索引、检索、Wiki 与图谱能力，
> 但不让它取代 BidPilot 的业务控制面和 Agent 执行控制面。

## 1. 调研结论

WeKnora 不是一个前端组件库，也不只是向量数据库。它是一个可自托管的知识服务：

- 文档/FAQ/Wiki 知识库；
- 文档解析、分块、向量化、混合检索、重排和 GraphRAG；
- ReAct 知识问答、MCP、网页搜索、引用与检索进度；
- Agent 生成和维护 Markdown Wiki，并展示知识图谱；
- 工作区 RBAC、审计、异步任务队列、模型/存储适配、Langfuse 可观测性；
- REST API、CLI 和 MCP 服务。

官方 README 声明其 REST API 的基础路径为 `/api/v1`，使用 API Key 鉴权，支持 Docker
Compose 私有化部署，图谱、MinIO、Langfuse 等能力以 Compose Profile 按需开启。

来源：

- [Tencent/WeKnora](https://github.com/Tencent/WeKnora)
- [官方文档站](https://weknora.weixin.qq.com)
- [API 文档入口](https://github.com/Tencent/WeKnora/tree/main/docs/api)

## 2. 采用决策

### 决策

采用 **独立部署的 WeKnora 实例 + BidPilot Knowledge Gateway 适配器**。

不采用：

1. 将 WeKnora 的 Web UI iframe 到 BidPilot；
2. 让浏览器直接携带 WeKnora API Key；
3. 让 WeKnora 的内置 Agent 成为 BidPilot 项目工作流或审批的唯一控制者；
4. 一次性删除 BidPilot 的项目、资料包、证据、审查、交付物与审计模型。

### 为什么

BidPilot 的价值是“投标项目执行事实”：项目、资料包、要求、证据、草稿版本、评审、
交付物、审批和审计。它们必须仍由 BidPilot PostgreSQL 控制面持久化。

WeKnora 的价值是“可演进知识能力”：解析、索引、召回、重排、知识问答、Wiki、图谱、
数据源同步与知识质量评估。它应通过稳定 API 被 BidPilot 调用。

这避免出现两个系统同时声称拥有项目真相、两个 Agent 同时决定审批与执行的灾难。

## 3. 所有权边界

| 领域对象或能力 | 唯一所有者 | BidPilot 的用途 |
| --- | --- | --- |
| 组织、成员、项目、角色 | BidPilot | 业务隔离与产品访问控制 |
| 原始资料包与文件登记 | BidPilot | 项目输入、文件生命周期、审计 |
| 文件二进制的主存储 | BidPilot MinIO/S3 | 统一保留、权限与删除策略 |
| 解析、分块、向量索引、混合召回 | WeKnora | 知识检索与引用候选 |
| Wiki 页面、图谱节点和边 | WeKnora | 可浏览的知识衍生资产 |
| 要求矩阵、Evidence、草稿、评审、交付物 | BidPilot | 领域事实与可审计产物 |
| 检索命中、来源定位、置信/质量信号 | WeKnora 生成，BidPilot 引用 | 支撑 Evidence 与回答引用 |
| 项目工作流、审批、后台 Run、重试 | BidPilot + LangGraph | 执行控制面 |
| 知识问答中的检索/工具过程 | WeKnora | 作为受限的知识工具能力 |
| 用户面对的 Agent Desk | BidPilot | 统一会话、权限、审批与项目操作 |

## 4. 推荐映射模型

```text
BidPilot Organization
  -> WeKnora Workspace

BidPilot Organization shared knowledge library
  -> WeKnora organization knowledge base

BidPilot Project
  -> WeKnora project-scoped knowledge base

BidPilot Bundle / SourceDocument
  -> WeKnora document resource and parse/index task

BidPilot Evidence
  -> WeKnora retrieval hit / source locator snapshot
```

每次项目问答、起草或审查检索时，默认同时检索：

1. 当前项目知识库；
2. 当前组织共享知识库；
3. 用户明确允许的其他项目或外部来源。

界面必须显式展示来源范围。禁止让模型静默跨项目取数。

## 5. 服务拓扑与安全边界

```text
Browser
  -> BidPilot Web
  -> BidPilot API / Knowledge Gateway
  -> WeKnora REST API / MCP (private Docker network only)
  -> WeKnora workers, vector/index/graph storage
```

- WeKnora 不暴露给公网，不由浏览器直连；
- WeKnora 服务密钥只存在服务端 Secret/环境变量，不写入 Git、前端包、日志或错误响应；
- BidPilot API 将用户、组织、项目和权限翻译为受限的 WeKnora 服务调用；
- 每个跨服务请求都记录 `correlation_id`、BidPilot `org_id`、`project_id`、操作人和
  外部资源 ID；
- 文件由 BidPilot 控制上传授权。需要送入 WeKnora 时，通过内网流式上传或受控短期 URL；
  不公开 MinIO bucket；
- 删除、重建索引、修改同步连接、重新解析和跨知识库检索都必须进入审计与确认策略；
- WeKnora 自身账户/RBAC 是基础设施防线，不能替代 BidPilot 产品 RBAC。

## 6. 必须新增的 Gateway 契约

BidPilot 后端必须用 `KnowledgeProvider` / `WeKnoraKnowledgeProvider` 适配器隐藏第三方
API，禁止业务代码四处直接调用 WeKnora HTTP。

最小能力：

```text
ensure_workspace(org)
ensure_knowledge_base(scope)
upload_source_document(binding, file_stream, metadata)
get_ingestion_status(external_document_id)
retry_ingestion(external_document_id, process_config)
search(scope, query, retrieval_profile)
get_source_locator(hit)
generate_or_refresh_wiki(scope)
get_wiki_tree(scope)
get_graph(scope, filters)
delete_external_resource(binding)
```

BidPilot 还需要自己的 `knowledge_bindings` 持久映射，至少包含：

```text
id, org_id, project_id?, bundle_id?, source_document_id?,
provider, external_workspace_id, external_kb_id, external_resource_id,
sync_state, last_synced_at, correlation_id, created_at, updated_at
```

## 7. 分阶段迁移，而不是直接砍库

### Phase A: 隔离 POC

- 以单独 Docker Compose 栈启动 WeKnora；
- 使用一份脱敏投标资料，验证 PDF/DOCX/XLSX 解析、中文检索、重排、引用、Wiki 和图谱；
- 只读调用 WeKnora API，不切换生产用户路径；
- 记录延迟、失败率、索引成本、中文召回质量与引用可用性。

### Phase B: 双写与比对

- 新上传资料同时进入当前 BidPilot 管道与 WeKnora；
- 用固定问题集比较召回、引用定位、成本和时延；
- 任何一方失败不能影响原始文件、项目和审计记录。

### Phase C: 检索切换

- 将 Agent 和起草的 retrieval adapter 切到 WeKnora；
- 旧向量索引停止新增写入，但保留可回滚读取；
- Evidence 仍以 BidPilot 的领域模型保存，外部命中仅作为可复现的引用来源。

### Phase D: 删除旧索引实现

只有通过质量、性能、权限隔离、删除链路和恢复演练后，才能删除旧解析/索引代码。
不删除项目、SourceDocument、Evidence、Review、Deliverable、AuditEvent 表。

## 8. 评估门槛

上线前必须使用真实但脱敏的投标材料建立评估集，至少覆盖：

1. 从招标文件找到明确评分项；
2. 区分项目资料与组织共享案例；
3. 找到指定资质、合同或人员证明；
4. 检测资料之间的冲突或过期内容；
5. 从多个来源组织一段有引用的草稿；
6. 中文表格、扫描 PDF 和复杂 DOCX 的解析；
7. 撤销用户权限后不可检索旧项目；
8. 删除文档后召回、Wiki 与图谱不再暴露其内容。

验收指标应至少记录：Recall@K、引用可用率、人工事实正确率、端到端等待时间、每份资料
的索引成本、失败重试成功率和跨项目越权测试结果。

## 9. 对前端原型的约束

OpenDesign 需要为 WeKnora 接入设计“知识资产”体验，但不得把 WeKnora 的原始后台复制
进 BidPilot。用户看到的是 BidPilot 的项目工作台：

- 资料上传与解析状态；
- 项目知识库、组织共享知识库和允许范围；
- 搜索结果、引用、证据和资料定位；
- Wiki 树与真实图谱；
- 检索质量/同步/重解析等管理能力；
- Agent 使用了哪些来源、是否仍缺证据。

详细页面和状态要求见：
`docs/design/frontend-v2/OPENDESIGN_PLATFORM_MODULE_REQUIREMENTS.md`。

## 10. 非目标

- 不把 WeKnora 当作通用 CRM、项目管理或审批系统；
- 不在第一阶段启用全部 IM、网站嵌入、Chrome 插件、MCP OAuth、GraphRAG、Neo4j、
  Langfuse profile；
- 不为了“知识图谱”展示一个没有业务含义的 3D 关系球；
- 不允许 WeKnora 内置 Agent 绕开 BidPilot 的审计、权限或审批机制直接修改项目。
