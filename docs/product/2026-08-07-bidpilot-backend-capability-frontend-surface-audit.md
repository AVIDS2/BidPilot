# BidPilot 后端能力与前端工作面深度盘点

> 盘点日期：2026-08-07  
> 盘点范围：services/api、services/worker、packages/contracts、apps/web，以及 DocPilot 产品设计文档  
> 目的：先把后端已经具备的产品能力完整还原出来，再决定前端应该呈现什么。本文不等同于接口文档，也不代表所有能力已经在生产环境验证过。

## 一、先说结论

BidPilot 的后端并不是一个只有“项目列表、资料列表、聊天框”的半成品。它已经覆盖了一条相当完整的投标执行链：

机会评估 → 项目与成员 → 资料包 → 解析与索引 → 要求矩阵 → 证据与检索 → 响应方案 → 分节编写 → 审阅与人工决策 → 交付物版本 → 导出与审计。

另外还存在组织、团队、邀请、订阅、用量、Provider、通知、变更影响、项目记忆、知识库、运行时审批和运维诊断等支撑能力。

现在用户体感“功能很少”，主要不是后端没有能力，而是前端的呈现层发生了三类压缩：

1. 当前挂载的 Workbench V2 主要是读取项目投影，很多写入动作仍只存在于 API 或旧的 ProjectDetail 页面。
2. 后端的业务状态没有被翻译成用户可以执行的下一步。例如“未验证要求”“未分配责任人”“证据不足”“待审阅”没有形成统一的工作队列。
3. 内部执行能力和用户工作能力没有分层。解析任务、运行时事件、Provider 诊断、原始日志不应和机会、要求、交付物并列成为普通用户的主导航。

因此，下一步不应继续堆叠孤立的卡片或重复跳转按钮，而应把后端能力组织成一个可连续完成工作的产品表面。

## 二、盘点口径

本文对每项能力记录四个事实：

| 维度 | 含义 |
| --- | --- |
| 后端事实 | 路由、契约模型、Worker 或运行时注册表中已经能确认的能力 |
| 可调用性 | 是否有明确的 API 写入、异步任务、审批或导出动作 |
| 当前前端接入 | 当前挂载的 V2 页面是否有真实查询或操作，不把旧页面代码误算成已上线 |
| 应呈现方式 | 普通工作区、组织管理、内部运维，还是只作为上下文显示 |

“后端已有”不等于“业务已经完整可用”。例如路由存在但前端没有调用、只读投影没有写入动作、或底层任务没有真实数据，都需要在实现前继续验证。

## 三、产品边界：三个表面，不能混在一起

### 3.1 租户投标工作区

这是投标团队每天使用的主产品。应该围绕一份具体机会或一个项目组织：

- 机会判断与项目启动
- 资料上传、解析、版本和索引状态
- 要求矩阵、责任分配、截止时间和风险
- 证据、引用、检索和来源定位
- 响应方案和章节编写
- 人工审阅、评论、批准、返工
- 交付物、版本和导出
- 项目协作、通知和待办
- Agent 作为上述工作的入口和加速器

### 3.2 租户管理区

这是组织管理员配置工作环境的地方：

- 组织资料与成员
- 角色、团队和邀请
- 订阅、套餐、用量和预算
- AI Provider、模型和密钥
- 内容库、模板、批准规则和集成
- 个人账户、主题、语言、时区和会话

### 3.3 内部运维区

这是平台运营方使用的区，不应成为普通用户的主导航：

- 跨租户健康和服务状态
- 账单、用量、Webhook 回执
- Provider/MCP 治理
- 运行时诊断、队列、重试和死信
- 审计、发布、事故和评估

一个简单判断：用户想完成投标工作时需要的能力进入工作区；管理员为了让组织能工作而配置的能力进入管理区；只有研发或平台运营需要看的原始执行细节进入运维区。

## 四、真实的业务主链

### 4.1 从机会到交付的最短闭环

1. 创建或导入机会，形成机会评估和 go / no-go / conditional-go 决策。
2. 创建项目并邀请成员，确定 owner、manager、contributor、reviewer、viewer。
3. 创建资料包，上传招标文件、企业材料、历史案例等源文档。
4. 后端异步完成 ingest、parse、normalize、index，并保留解析器版本和文档血缘。
5. 从资料中提取要求，形成要求矩阵；为每条要求分配责任人、审核人、截止时间和优先级。
6. 通过证据集、知识块、检索和来源定位，为要求绑定可核验依据。
7. 生成 readiness summary，明确覆盖率、必选项闭合度、验证率、分配率和缺口。
8. 生成 response plan，把要求映射到响应章节和证据绑定。
9. 分章节生成草稿；每次生成形成 section version，并可进入人工审阅。
10. 审阅者批准、驳回或要求修改；评论和决策必须留痕。
11. 将批准的章节冻结为导出快照，生成 DOCX/PDF 等交付物，保留哈希和失败原因。

### 4.2 哪些状态必须让用户看见

用户不需要看到 Celery 任务名或 LangGraph 节点名，但必须知道：

- 资料是否已上传、解析、索引完成
- 某条要求是否已提取、分配、覆盖、验证
- 证据是否足够，引用能否回到原文
- 草稿是否正在生成、需要批准、已生成版本还是失败
- 哪些工作阻塞了交付
- 当前导出是否基于最新批准版本

## 四点一、当前前端实际接入与断层

### app.tsx 当前挂载的页面路由

当前 Web 应用已经挂载的入口包括：

- dashboard
- inbox
- my-work
- runs
- knowledge
- projects
- projects/:id
- reviews
- deliverables
- members
- administration
- account
- admin/users
- admin/teams
- admin/invitations
- settings/providers
- agent

这说明页面入口并不算少，但入口数量不能代表工作流完整。关键问题是这些入口之间没有全部共享同一套项目上下文、状态和下一步动作。

### Workbench V2 当前主导航

V2 主导航目前集中在：

- dashboard
- my work
- projects
- knowledge
- agent

项目工作区 V2 暴露的只读/半只读分区主要是：

- overview
- materials
- requirements
- plan
- sections
- review
- deliverables

它会查询项目、资料包、要求、readiness、证据、交付物、运行和响应方案，但目前没有把下面这些写入动作完整接上：

- 上传、重解析、重建索引
- 要求创建、批量分配、验证、决策
- 证据选择和引用回溯
- 章节生成、重写、版本比较
- 评论、审阅决策、返工
- 交付物创建、章节编辑、排序
- 导出、失败重试

### 旧 ProjectDetail 页面中的能力

旧的 project-detail-page.tsx 里仍可找到较多真实交互入口：

- bundles
- deliverables
- outline
- requirements
- knowledge
- drafting
- agent
- evidence
- search
- runs
- review
- export
- access
- audit
- ops

其中已经存在部分 reingest、创建交付物、要求更新/批量分配、证据/claim 验证、readiness pack、评论、审阅决策、项目成员等 API 调用。

旧页面未被当前 projects/:id 路由作为主页面挂载，所以“代码里有按钮”不能算“用户已经拥有能力”。后续应迁移业务动作，而不是恢复旧页面所有 tab。

### 断层结论

当前最需要做的是把 V2 的读取投影变成可操作的工作台：

资料状态 → 要求矩阵 → 缺口过滤 → 证据侧栏 → 章节生成 → 审阅决策 → 导出快照。

这条链完成后，页面自然会比现在丰富；继续增加独立菜单只会增加入口数量，不会增加有效功能密度。

## 五、后端能力分域盘点

## 5.1 机会评估与项目治理

### 已确认能力

机会评估模型包含：

- opportunity 的 draft、ready、decided、archived 生命周期
- scorecard、risk、rationale、history
- go、no_go、conditional_go 决策
- lock version，避免多人覆盖

项目模型包含：

- 创建、演示项目、列表、详情、更新、归档/删除
- scenario package
- 项目成员和角色管理
- 项目级审计、运行、资料包、交付物等关联

### 应呈现的工作面

机会详情不应只是一个项目名称。最少应有：

- 是否值得响应的结论
- 关键风险和待确认事项
- 评估依据和历史决策
- “转为项目”或“暂不响应”的明确动作

项目概览应回答三句话：

1. 这个项目当前处在哪个阶段？
2. 哪些要求或资料正在阻塞推进？
3. 下一步最值得做的动作是什么？

### 当前前端接入判断

当前 V2 项目页面能读取项目和部分 readiness 投影，但没有形成完整的机会评估工作流。机会评估 API 有模型和路由，当前代码检索未见它在 V2 中成为一等页面。

### 优先级

P0：项目阶段、项目 owner、成员、当前阻塞项。  
P1：机会 scorecard、风险历史、conditional-go 的后续条件。  
P2：跨项目机会漏斗和组织级转化趋势，前提是有可靠历史数据。

## 5.2 资料包、源文档与解析流水线

### 已确认能力

资料包 Bundle 支持：

- 创建和列表
- ingest 状态
- reingest
- reindex

源文档 SourceDocument 支持：

- 列表、上传、下载
- storage key、MIME、文件名、URL
- ingest queued、parse/index 状态
- attempts、parser、version、error、retry
- supersedes 文档血缘

ParsedAsset 保存：

- parser name/version
- content
- layout JSON

Worker 中有 ingest_bundle、reindex_bundle、死信记录和可恢复任务。

### 应呈现的工作面

资料页要按“能否继续工作”组织，而不是只显示文件名：

- 上传区：支持拖放、批量上传和来源类型
- 处理队列：等待解析、解析中、解析完成、需要重试、失败
- 文档详情：解析预览、页码/段落定位、解析器版本
- 版本关系：当前版本、被替代版本、影响了哪些要求和章节
- 明确的重新解析/重建索引动作

### 当前前端接入判断

V2 能读取 bundles、documents 和部分 parsed assets，但上传、重解析、重建索引在主工作流中不够明显。旧 ProjectDetail 有更多资料操作，不能算作当前 V2 已交付。

### 优先级

P0：上传、状态、失败重试、解析预览、版本血缘。  
P1：按资料包筛选和批量替换。  
P2：解析质量对比和自动异常诊断。

## 5.3 要求矩阵、责任分配与合规闭合

### 已确认能力

RequirementItem 支持：

- section_key、requirement_text、original_text
- source document、source locator
- priority、owner、reviewer、due_at
- extraction confidence
- bid profile
- status、verification、lock_version

要求相关动作包括：

- 创建、列表、筛选、详情
- 更新和批量分配
- 证据链接与更新
- 决策创建和批准
- claim 创建、验证
- requirement claim/evidence 关系
- review queue，包含待验证和被证据阻塞的数量

### 应呈现的工作面

要求页是系统的核心工作台，建议采用高密度但可扫描的矩阵：

| 主列 | 用户要回答的问题 |
| --- | --- |
| 要求 | 招标方到底要求什么 |
| 来源 | 原文在哪一页、哪一段 |
| 优先级 | 不满足会造成什么后果 |
| 覆盖 | 是否已有响应内容 |
| 证据 | 是否有可核验依据 |
| 责任人 | 谁负责补齐 |
| 审核人 | 谁负责确认 |
| 截止 | 是否已经逾期 |
| 状态 | 下一步是什么 |

一条要求点开后，应进入侧边详情，而不是跳到一个失去上下文的新页面。详情同时展示原文、证据引用、claim、章节绑定、决策记录和活动历史。

### 当前前端接入判断

V2 有要求列表和 readiness 读取，但要求分配、验证、决策、claim 审核等动作没有形成连续工作流。旧页面已有部分 API 调用，是可复用的业务入口。

### 优先级

P0：要求矩阵、筛选、责任分配、验证、缺口队列。  
P1：批量操作、锁版本冲突提示、按章节和风险分组。  
P2：跨项目要求模式和自动优先级建议。

## 5.4 证据、知识块与检索

### 已确认能力

后端有三种互相连接的事实来源：

- Evidence：可直接引用的证据记录
- KnowledgeChunk：文档切片和 embedding 状态
- EvidenceSet：供要求、章节和运行绑定的证据集合

相关能力包括：

- 证据列表和详情
- chunks 列表
- 语义检索
- evidence link
- quote_text、source locator、confidence
- evidence set 和章节版本绑定

Runtime capability registry 还注册了 semantic_search、search_bid_wiki、open_requirement_source 等能力。

### 应呈现的工作面

证据不是“AI 找到的一段文本”，而应该显示为可回溯的证明链：

要求 → 证据引用 → 文档 → 页码/段落 → 解析版本。

编写器中每个事实句都应该能展开引用；没有证据时应显示“待补证据”或“未核验”，不能用一段看似完整的生成文字掩盖缺口。

### 当前前端接入判断

V2 能读取 evidence 和 runs，但证据选择、引用回溯、证据不足提示没有成为写作和审阅中的常驻上下文。检索能力存在于 API 和运行时注册表中，未完全转化为可见的工作流。

### 优先级

P0：证据面板、来源定位、引用回溯、证据不足状态。  
P1：证据集管理、按项目/资料包/要求筛选。  
P2：检索质量评估和重复证据合并。

## 5.5 Readiness：真正有意义的项目健康图表

### 已确认能力

Readiness summary 已经有明确的指标契约：

- total、mandatory、scored
- covered、partial、uncovered
- disputed、not_applicable、accepted_risk
- verified、assigned
- mandatory_closure
- scored_coverage
- verification
- assignment
- unassigned、by_owner
- mandatory_gaps、evidence_gaps、contradictions、overdue、qualifications

Readiness pack 还包含：

- formula_version
- source fingerprint
- score 0–100
- 版本、状态
- 存储键
- 生成、读取和下载

### 图表应该回答什么

右侧或首屏的大矩形容器不应该放一个不能拖拽、不能解释的流程图。最有意义的内容是“项目交付健康”：

1. 顶部显示总体 readiness score 和公式版本。
2. 中部用四条可解释的进度条显示必选项闭合度、覆盖率、验证率、分配率。
3. 下方列出三类真正会阻塞交付的缺口：必选要求缺口、证据缺口、逾期/未分配。
4. 点击某一项直接过滤要求矩阵，不重复跳转。

若要使用趋势图，必须有多个 readiness snapshot 或历史时间点。当前只有一个实时汇总时，不应伪造折线趋势。可以使用：

- readiness 维度分解条形图
- 缺口按严重度的横向条形图
- 责任人工作量和逾期数
- 要求状态分布

这些图表都来自后端已有字段，不是为了填满空白而编造的装饰。

### 当前前端接入判断

V2 会读取 readiness，但现有可视化没有把 score、缺口、责任人和下一步动作组合起来。当前占位式流程图表达不了项目风险，也没有形成可操作的过滤入口。

### 优先级

P0：健康摘要、四项分解、缺口列表、点击过滤。  
P1：readiness pack 生成/下载、历史快照。  
P2：跨项目趋势和风险预测。

## 5.6 Response Plan、章节、版本与交付物

### 已确认能力

ResponsePlan 支持：

- plan version、status
- source fingerprint
- unmapped requirements
- sections
- section requirement bindings
- section evidence bindings
- evidence set、execution run、iteration
- unmet requirement IDs
- degraded reasons
- content plan

Deliverable 支持：

- 创建、列表
- section 创建、更新、删除、排序
- section status
- approved_version_id

SectionVersion 支持：

- 章节版本
- 内容
- actor
- execution run
- evidence set
- plan binding

### 应呈现的工作面

项目不能只有“生成全文”按钮。应该按章节显示：

- 章节目标和对应要求
- 已覆盖/未覆盖要求
- 已绑定证据和缺证据
- 当前草稿版本
- 审阅状态
- 负责人和下一步

章节列表要能快速识别：

- 哪些章节还没有草稿
- 哪些章节被要求或证据阻塞
- 哪些章节有待审阅版本
- 哪些章节已批准并可导出

### 当前前端接入判断

V2 能读取 response plans、sections、deliverables 和 section versions，但编写、重写、版本比较、排序和交付物编辑尚未形成完整主流程。旧页面包含更多入口，但未被当前路由挂载。

### 优先级

P0：章节状态、要求/证据绑定、版本、审阅入口。  
P1：版本对比、章节排序、批量生成和批量审阅。  
P2：组织模板和章节复用分析。

## 5.7 Drafting、Review、人工确认与运行时

### 已确认能力

Drafting 支持：

- draft section
- redraft section
- resume run
- SSE run stream
- connected、node started、node completed
- review result
- human approval required
- draft preview
- section version ID
- graph completed
- error、cancelled、heartbeat

Review 支持：

- 针对 section version 的 approve、reject、needs_revision
- 评论线程
- 评论列表
- 决策记录

ExecutionRun 和 RuntimeRun 支持：

- queued、running、completed、failed、cancelled、retry 等生命周期
- 父子运行和 attempt
- events、actions、approvals
- cancel、retry

### 应呈现的工作面

生成过程应是“可解释的进度”，不是一堆日志：

- 当前正在处理的章节
- 已完成的步骤
- 使用了哪些资料和证据
- 是否需要人工确认
- 失败后能否重试
- 取消后是否保留已有版本

人工确认要明确显示风险和影响。例如覆盖范围不足、引用冲突、使用成本较高、将要覆盖现有版本时，应先显示确认内容，再提供批准或拒绝。

### 当前前端接入判断

Agent 与运行 API 已存在，V2 有询问 Agent 的入口；但写作、审阅、批准、取消、重试没有被组织为一条可完成的路径。运行时原始事件应作为详情抽屉，而不是主导航。

### 优先级

P0：生成进度、人工批准、审阅决策、取消/重试。  
P1：版本差异和证据引用审阅。  
P2：运行质量评估、成本明细和模型对比。

## 5.8 导出与交付留痕

### 已确认能力

Export 支持：

- 创建导出
- 导出记录列表和详情
- artifact download
- DOCX/PDF 快捷导出
- 不可变导出快照
- 已批准章节快照
- 哈希
- 状态和失败原因

### 应呈现的工作面

交付页应该让用户知道：

- 当前导出包含哪些批准版本
- 是否有未批准章节
- 导出时间、发起人和格式
- 文件是否可下载
- 失败后能否重试
- 下载的文件对应哪个 readiness/response plan 版本

“导出”不是一个孤立按钮，而是批准版本的最终落点。

### 优先级

P0：导出前检查、导出历史、下载和失败重试。  
P1：导出快照详情、版本哈希和审计链接。  
P2：自定义模板和多格式批量导出。

## 5.9 文档变更与影响分析

### 已确认能力

DocumentChangeSet 支持：

- pending_parse、analyzed、accepted、dismissed
- 变更影响记录
- low、medium、high、critical 严重度
- open、acknowledged、resolved、dismissed
- 关联 requirement 或 section
- 摘要、定位、处理人和时间

### 应呈现的工作面

当新版本招标文件替换旧文件时，应出现“变更影响”：

- 哪些要求发生变化
- 哪些章节需要重写
- 哪些证据可能失效
- 谁需要确认
- 变更是否已处理

这是已有后端能力中非常有价值、但当前前端几乎看不见的一块。

### 优先级

P1：文档版本差异、影响清单、确认和关联跳转。  
P2：自动回归检查和历史变更趋势。

## 5.10 项目记忆、Bid Wiki 与内容库

### 项目记忆与知识图谱

MemoryRecord 支持：

- user_private、project_shared、org_shared 三种范围
- preference、fact、decision、procedure、risk、summary、entity_note
- proposed、active、superseded、rejected、deleted
- citations
- expiry
- 与 KnowledgeChunk、Requirement、Evidence、Chat、Audit、人为决策关联
- portfolio、evidence map、context、compile
- graph extraction、review decision、entity、relation、compilation run

这不是普通聊天历史，而是可审查、可引用、可废弃的长期项目知识。

### 内容库

ContentLibraryEntry / Version / Usage 支持：

- 标题、类型、分类、标签
- 内容、来源、生效日期、supersedes
- draft、published、archived
- review status draft、approved、rejected
- 发布、归档、使用记录

### 应呈现的工作面

知识资产页至少应分为：

- 项目资料和解析结果
- 组织批准内容
- 项目记忆和决策
- 可复用案例、模板、条款

用户需要看见来源、有效期、批准状态和使用位置，不能把所有东西混成一个“知识库列表”。

### 当前前端接入判断

V2 有 Knowledge 页面和部分 memory API，但 content library、memory graph、证据地图没有形成可发现的工作面。当前代码检索未见 changes、opportunities、content-library、collaboration 成为清晰的一等前端流。

### 优先级

P1：知识资产分层、来源、批准状态、复用。  
P2：图谱审阅、冲突合并、知识质量评分。

## 5.11 协作、我的工作与通知

### 已确认能力

Collaboration board 能聚合：

- 项目成员
- 要求 owner/reviewer/due
- overdue
- needs_assignment
- risk/coverage
- 未分配、逾期、待审阅、开放线程、运行中工作流数量

Notifications 支持：

- 列表
- 标记已读
- 全部标记已读
- SSE 实时流

Review threads/comments 和邀请、团队成员管理也已经有模型和路由。

### 应呈现的工作面

“我的工作”不应只是另一张表，而应是跨项目的行动队列：

- 今天到期
- 等我审核
- 等我补证据
- 被我认领
- 生成失败需要处理
- 新资料导致的变更
- Agent 等待我的批准

每一行都应能直接执行或进入带上下文的侧边详情。

### 优先级

P0：我的工作、项目通知、逾期和待批准队列。  
P1：团队工作量、筛选和批量认领。  
P2：提醒规则和外部通知渠道。

## 5.12 Agent、聊天、工具和审批

### 已确认能力

Assistant 支持：

- attachments
- stream
- answer、needs_input、tool_action、workflow_trigger
- request_approval、risky_only、full_access、custom
- project、conversation、provider、reasoning、locale、confirmation

Chat 支持：

- 持久化 conversation/history
- fork、pin、rename、delete
- message attachment
- SSE
- task state

Runtime capability registry 已注册以下可见业务能力：

- 搜索、创建项目、创建演示工作区
- 项目摘要、资料包、章节、要求、证据、交付物
- readiness 缺口
- 提交审阅决策
- 启动/继续/重写章节
- 运行状态、重试、取消
- 导出和 readiness pack
- semantic search、web search、URL 入库
- 上传文档、搜索 Bid Wiki
- 提议/遗忘记忆
- 打开页面、删除项目
- run section campaign

能力按 read、navigate、low risk write、costing、destructive 分级；高风险动作可要求审批或明确文字确认。

### 应呈现的工作面

Agent 不应独立成一个“什么都能聊”的空白页。它应该嵌入当前上下文：

- 在要求详情中：找证据、解释缺口、建议责任人
- 在章节编写中：生成、重写、检查引用
- 在 readiness 中：解释分数和下一步
- 在变更面板中：总结影响
- 在导出前：检查未批准内容

工具调用和审批应显示为用户可理解的动作卡：

- 动作是什么
- 会影响哪些对象
- 是否会产生费用或覆盖内容
- 批准、拒绝、取消、重试

### 当前前端接入判断

V2 有 Agent 入口，但主要呈现聊天，而不是把 Agent 能力嵌入项目主链。工具注册表的业务能力远多于当前可见按钮。

### 优先级

P0：上下文 Agent、审批卡、运行状态和错误恢复。  
P1：对话与项目对象的双向链接、任务历史。  
P2：组织级 Agent 策略和工具使用分析。

## 5.13 组织、账户、团队、订阅和 Provider

### 已确认能力

组织和账户后端包括：

- 组织创建、列表、当前成员、切换组织
- owner/admin/member 角色
- billing owner
- 成员移除
- 团队 CRUD 和成员角色
- 邀请创建、列表、删除
- 个人资料更新
- 邮箱验证、密码重置、刷新令牌
- 账号删除和个人数据导出

订阅和用量包括：

- subscription、billing summary
- checkout、portal、webhook
- official/byok token usage
- workflow/assistant/indexing quota
- organization budget
- platform ceiling
- quota/budget 读取和更新

Provider 包括：

- OpenAI/Anthropic 配置
- 加密和掩码密钥
- 配置测试
- 模型发现

### 应呈现的管理面

账户菜单不应只有“退出登录”。至少要有：

- 账户与个性化：头像、姓名、语言、时区、主题、通知
- 组织设置：名称、成员、角色、团队、邀请
- 套餐与用量：当前套餐、余额、预算、用量明细
- 集成与模型：Provider、模型、连接测试、默认策略
- 安全：邮箱、密码、会话、账号导出/删除

这些功能应该放在管理区，用清楚的分组和状态，不要和项目工作流混为一谈。

### 优先级

P0：账户、成员、邀请、角色。  
P1：套餐、用量、预算、Provider 测试。  
P2：组织策略、模型路由和成本优化。

## 5.14 审计、诊断、健康与安全

### 已确认能力

AuditEvent 支持事件列表；运行时诊断可汇总：

- timing、retries
- actions、approvals、events
- execution runs、worker tasks
- model usage
- retrieval
- audit
- deliverables
- alerts

Ops 还提供：

- runtime diagnostics
- runtime summary
- detailed health
- per-user billing usage
- webhook receipts

Worker 有 outbox、recover、dead letter、数据库备份等内部能力。

### 应呈现的层级

普通项目用户只需要看到：

- 当前项目的处理状态
- 失败原因的可读解释
- 重试/取消入口
- 与自己有关的审计活动

组织管理员可以看到：

- 成员操作历史
- 用量和 Provider 状态
- 项目导出与批准记录

平台运维才需要看到：

- 原始 runtime events
- worker task、队列、死信
- Webhook receipt
- 供应商诊断和跨租户告警

不要把内部诊断原样塞进主导航，也不要为了“功能密度”显示无意义的日志。

## 5.15 场景包与演示工作区

Scenarios 支持：

- 场景列表和详情
- 场景章节
- 模板
- 创建演示工作区

它应该用于：

- 新用户快速了解完整闭环
- 按行业/场景提供默认要求、章节和模板
- 在空项目中给出下一步

这比在首页放一排无意义的快捷按钮更有价值。

## 六、API 能力总表

下面是当前 API 路由按产品域的归类。它用于核对覆盖面，不意味着每个路由都要变成一个导航项。

| 产品域 | 主要路由能力 |
| --- | --- |
| 项目 | projects、members、bundles、documents、parsed-assets |
| 机会 | opportunities、assessment、decision |
| 要求 | requirements、assignment、evidence link、claim、decision |
| 证据 | evidence、chunks、retrieval、versions |
| 方案 | response-plans、sections、bindings |
| 编写 | drafting、redraft、resume、SSE |
| 审阅 | review decisions、threads、comments |
| 交付 | deliverables、export、artifact download |
| 运行 | execution、runtime、events、cancel、retry、approval |
| 变更 | changes、impact、acknowledge/resolve |
| 知识 | memory、content-library、graph、compilation |
| 协作 | collaboration board、notifications、invitations |
| Agent | assistant、chat、attachments、tool approval |
| 组织 | organizations、teams、members、invitations |
| 管理 | auth、billing、usage、providers |
| 平台运维 | audit、ops、health、webhook receipts |
| 场景 | scenarios、demo workspace |

## 六点一、实际 API 动作核对表

以下清单来自 services/api/app/main.py 注册的 router，以及各域 router.py 中的实际装饰器。路径中的项目 ID、用户 ID 等参数仅保留语义名称；完整公共前缀以 main.py 为准。清单的用途是证明后端能力覆盖面，不是要求把这些动作全部做成菜单。

### 项目、机会和资料

| 域 | 实际动作 |
| --- | --- |
| projects | POST 创建项目；POST demo 创建演示项目；GET 列表/详情；PATCH 项目；DELETE 项目；GET/POST/PATCH/DELETE 项目成员 |
| opportunities | GET 项目机会评估；PUT 更新评估；POST 记录机会决策 |
| bundles | POST/GET 资料包；POST reingest；POST reindex |
| documents | GET 分页列表；POST upload；GET download |
| parsed-assets | GET 解析资产列表；GET 单个解析资产 |
| changes | GET/POST 项目变更集；POST analyze；POST decision；PATCH 单条 impact |

### 要求、证据和检索

| 域 | 实际动作 |
| --- | --- |
| requirements | POST/GET 要求；POST bulk-assign；GET 详情；POST 证据链接；PATCH 证据链接；POST 要求决策；POST/GET claim review queue；POST claim；POST/PUT/PATCH 要求 |
| evidence | GET 证据；GET knowledge chunks |
| retrieval | POST semantic search |
| versions | GET section versions |
| readiness | GET 项目 readiness；POST 生成 readiness pack；GET pack artifact |

### 响应方案、编写、审阅和交付

| 域 | 实际动作 |
| --- | --- |
| response-plans | GET 方案列表；GET 方案详情 |
| drafting | POST draft section；POST redraft；POST resume run；GET SSE run stream |
| deliverables | POST/GET 交付物；POST/GET 交付物 sections；PATCH section；PUT reorder；DELETE section |
| review | POST decision；GET threads；POST comments；GET thread comments |
| export | POST export；GET deliverable exports；GET export record；GET artifact；GET DOCX；GET PDF |
| execution | GET run；GET runs；POST retry |
| runtime | GET runs；GET run；GET events；POST cancel；POST resolve approval |

### Agent、聊天、知识和协作

| 域 | 实际动作 |
| --- | --- |
| assistant | POST attachments；POST stream |
| chat | POST stream；GET conversations；GET messages；POST fork；PATCH conversation；DELETE conversation |
| memory | POST/GET memories；GET portfolio；GET evidence map；POST context；POST compile；POST graph extraction；POST graph review；GET compilation；POST approve；DELETE memory |
| content-library | GET/POST entries；GET entry；POST version；POST publish；POST archive；POST usage |
| collaboration | GET project board |
| notifications | GET list；PATCH read；PATCH read-all；GET SSE stream |

### 组织、账户、管理和平台

| 域 | 实际动作 |
| --- | --- |
| auth | register、login、refresh；GET/PATCH me；GET/PATCH subscription；GET billing summary；GET users；PATCH user/profile/role/status；password reset/confirm；verify/resend email；admin verify；DELETE me；GET me export |
| organizations | POST/GET organizations；GET current members；PATCH member；POST billing owner；DELETE member；GET entitlements；POST switch |
| teams | POST/GET team；GET/PATCH/DELETE team；POST/DELETE team member |
| invitations | POST/GET invitations；DELETE invitation |
| billing | POST checkout；POST portal；POST webhook |
| usage | GET quota；GET/PUT budget |
| providers | GET/POST/GET/PUT/DELETE provider config；POST test；POST models |
| audit | GET events |
| ops | GET runtime diagnostics/summary/health；GET user billing/usage/webhook receipts |
| health | GET /health 公共存活探针；GET /health/ready 依赖就绪探针 |
| scenarios | GET scenarios；GET scenario；GET scenario sections/template |

### 访问边界

main.py 当前把接口分成三类：

| 边界 | 典型能力 | 产品含义 |
| --- | --- | --- |
| 公共 | health、health/ready、auth、scenarios | 登录前、探活或演示入口；不得返回租户数据 |
| 登录用户 | projects、documents、requirements、drafting、review、export、memory、chat 等 | 租户工作区能力，必须按组织/项目权限过滤 |
| 管理员 | audit、ops，以及组织/账单/Provider 中的管理动作 | 组织管理或平台运维；不应混入普通项目导航 |

Providers、billing 等路由虽然在 router 注册层不一定统一附加 protected dependency，具体权限仍由各自依赖和服务逻辑决定；前端不应仅凭“路由存在”就把它们暴露给所有用户。

## 六点二、核心业务实体清单

这是 packages/contracts/models.py 中按领域整理的实体清单。实体本身不等于界面卡片；它们说明哪些业务事实已经有持久化边界。

### 组织与身份

- Organization
- OrganizationMembership
- OrganizationMembershipEvent
- Team
- TeamMember
- User
- Subscription
- OrganizationSubscription
- StripeWebhookEvent
- RefreshToken
- Invitation
- Notification

### 项目与资料

- Project
- ProjectMember
- Bundle
- SourceDocument
- AssistantAttachment
- ParsedAsset
- DocumentChangeSet
- DocumentChangeImpact

### 机会、知识与证据

- OpportunityAssessment
- OpportunityAssessmentDecision
- ContentLibraryEntry
- ContentLibraryVersion
- ContentLibraryUsage
- KnowledgeChunk
- EvidenceSet
- EvidenceSetItem
- Evidence

### 要求、声明与决策

- RequirementItem
- BidRequirementProfile
- RequirementEvidenceLink
- Claim
- RequirementClaimLink
- ClaimEvidenceLink
- RequirementDecision

### 方案、章节与交付

- ReadinessPack
- Deliverable
- DeliverableExport
- DeliverableSection
- ResponsePlan
- ResponsePlanSection
- ResponsePlanRequirement
- ResponsePlanEvidenceBinding
- SectionVersion

### 执行、审阅与审计

- ExecutionRun
- TaskOutboxEvent
- ReviewThread
- ReviewComment
- AuditEvent

### 用量、模型和 Agent 治理

- UsageEvent
- OrganizationUsageBudget
- OrganizationUsageBudgetEvent
- ModelUsageReservation
- ModelUsageRecord
- AssistantActionAudit
- AssistantApproval
- ProviderConfig

### Runtime 与聊天

- RuntimeRun
- RuntimeEvent
- RuntimeAction
- RuntimeApproval
- ChatConversation
- ChatMessage
- ChatMessageAttachment
- ChatTaskState

### 项目记忆与图谱

- MemoryRecord
- MemoryEvidenceLink
- MemoryEvent
- MemoryGraphReviewDecision
- MemoryEntity
- MemoryRelation
- MemoryCompilationRun

## 六点三、生命周期状态与用户语言

后端状态名不能直接原样露出给用户，建议统一翻译成下面的产品语言：

| 后端状态族 | 用户看到的语言 | 主要动作 |
| --- | --- | --- |
| project active / archived | 进行中 / 已归档 | 打开、归档、恢复 |
| bundle ingest queued / processing / ready / failed | 等待处理 / 处理中 / 可使用 / 处理失败 | 查看、重试、重建索引 |
| document parse/index status | 解析中 / 已解析 / 索引中 / 可检索 / 失败 | 预览、重试、替换版本 |
| opportunity draft / ready / decided / archived | 评估中 / 可决策 / 已决策 / 已归档 | 补评估、go/no-go |
| requirement uncovered / partial / covered | 未覆盖 / 部分覆盖 / 已覆盖 | 补内容、找证据 |
| verification pending / verified / disputed | 待核验 / 已核验 / 有争议 | 查看来源、确认、提出异议 |
| requirement decision pending / approved / rejected | 待决定 / 已接受 / 已拒绝 | 批准、退回 |
| execution queued / running / completed / failed / cancelled | 排队 / 运行中 / 已完成 / 失败 / 已取消 | 查看进度、重试、取消 |
| review open / resolved | 待审阅 / 已处理 | 评论、批准、要求修改 |
| section draft / in_review / approved / needs_revision | 草稿 / 审阅中 / 已批准 / 需修改 | 打开章节、提交决策 |
| export queued / running / completed / failed | 准备导出 / 导出中 / 可下载 / 导出失败 | 查看快照、重试 |
| memory proposed / active / superseded / rejected / deleted | 待确认 / 生效 / 已替代 / 已拒绝 / 已删除 | 批准、查看来源、废弃 |
| content draft / published / archived | 草稿 / 已发布 / 已归档 | 编辑、发布、归档 |

状态翻译的原则是：每个状态都应该告诉用户为什么会处于这里，以及下一步能做什么。只显示颜色和数字是不够的。

## 六点四、Worker 与异步执行核对表

services/worker/app/tasks.py 中的任务按用户意义分成三组：

### 用户直接感知的后台任务

| Worker 任务 | 用户应看到的结果 |
| --- | --- |
| worker.ingest_bundle | 资料包已接收、解析进度、失败原因 |
| worker.reindex_bundle | 文档现在是否可检索 |
| worker.draft_section | 章节生成进度、草稿版本、审阅中断 |
| worker.resume_draft | 人工批准后继续生成 |
| worker.compile_bid_wiki | 知识库编译状态和更新时间 |
| worker.index_memory_records | 记忆是否已进入检索 |
| worker.extract_memory_graph | 图谱抽取是否待审阅 |

### 用户需要间接感知的可靠性动作

| Worker 任务 | 前端呈现 |
| --- | --- |
| worker.dispatch_task_outbox_event | 活动是否已经可靠发送 |
| worker.recover_task_outbox_events | 不需要显示任务名，只在异常时提示“正在恢复” |
| worker.record_dead_letter | 仅显示可读错误和支持入口，不显示死信队列细节 |

### 纯内部任务

- worker.ping
- worker.cleanup_assistant_attachments
- worker.backup_database

内部任务不应增加普通用户的功能密度。可靠性通过状态、重试和清晰错误反馈体现。

## 七、为什么后端很多，前端却显得“没几个功能”

| 后端实际能力 | 当前用户看到的形态 | 造成的感受 |
| --- | --- | --- |
| 要求分配、验证、claim、决策 | 一个只读要求列表 | 看到了数据，却不知道怎么推进 |
| evidence、chunk、locator、confidence | 一个证据数量或空状态 | AI 的依据不可见，用户不信任 |
| readiness 四项分数和缺口 | 一个难解释的流程图 | 图很大，但不知道它解决什么问题 |
| drafting、review、approval、retry | 一个 Agent 入口 | 核心生产链被压成聊天 |
| section version、approved snapshot | 一个交付物列表 | 看不出哪个版本能交付 |
| changes 和 impact | 文件上传后没有影响提示 | 新资料的风险被隐藏 |
| collaboration board、notifications | 分散在各页的数字 | 用户没有统一待办 |
| org/team/quota/provider | 简单账户菜单 | 管理能力远少于后端实际能力 |
| runtime diagnostics | 没有用户级状态或直接显示原始日志 | 要么“什么都没有”，要么信息过载 |

根因不是“卡片数量不够”，而是没有把后端的状态转换成动作和决策。

## 八、建议的信息架构

### 8.1 租户主导航

建议控制在五个一级入口：

1. 工作台：我的工作、项目阻塞、待审阅、待批准、通知
2. 机会与项目：机会评估、项目列表、项目阶段
3. 知识资产：资料、内容库、项目记忆、Bid Wiki
4. 交付与审阅：跨项目章节、审阅队列、导出记录
5. Agent：跨项目搜索和任务历史

### 8.2 项目内导航

一个项目内建议采用同一套结构：

1. 概览
2. 资料
3. 要求
4. 响应方案
5. 编写
6. 审阅
7. 交付
8. 协作与设置

每个页面都应保留项目上下文；详情、证据和运行状态优先用侧边抽屉承载，避免重复跳转。

### 8.3 组织管理导航

建议分组为：

- 账户与个性化
- 组织、成员与团队
- 套餐、用量与预算
- 集成与模型
- 内容库与批准规则
- 安全与数据

### 8.4 内部运维导航

单独入口或单独应用：

- 租户与生命周期
- 服务健康与事故
- 运行和队列
- Provider/MCP
- 账单和 Webhook
- 审计与评估

## 九、图表与可视化原则

### 9.1 首屏图表的候选

| 图表 | 数据来源 | 用户得到的结论 | 点击后的动作 |
| --- | --- | --- | --- |
| Readiness 分解 | mandatory_closure、scored_coverage、verification、assignment | 项目为什么还不能交付 | 过滤对应缺口 |
| 缺口严重度 | mandatory_gaps、evidence_gaps、overdue、contradictions | 最大风险在哪里 | 打开要求详情 |
| 团队工作量 | by_owner、unassigned、overdue | 谁被压住，谁没有负责人 | 分配或认领 |
| 章节推进 | section status、approved_version_id | 哪些章节可审、可导出 | 打开编写/审阅 |
| 处理健康 | document parse/index status、retry/error | 资料是否已经可用 | 重试或查看解析 |
| 导出状态 | export status、approved snapshots | 交付是否可靠 | 查看快照/重试下载 |

### 9.2 不能做的图表

- 没有历史快照却画“过去七天趋势”
- 用随机或静态数字填充图形
- 用不能解释的节点关系替代 readiness 和缺口
- 图表没有点击后的筛选或行动
- 只展示总数，不展示总数背后的阻塞原因

### 9.3 关于“可拖拽”

拖拽只有在用户确实需要编排时才有意义：

- 章节排序
- 要求批量分配
- response plan 章节编排
- 内容块排序

为了让空白区域动起来而做一个可拖拽流程图，不属于有效交互。

## 十、信息层级与视觉实现方向

后端盘点最终要落成可读的界面层级：

- 页面标题和项目阶段是一级信息
- readiness、阻塞项、待处理数量是二级信息
- 资料名、要求文本、责任人和状态是主体信息
- 来源定位、运行事件、时间戳是展开后的上下文
- 内部 ID、解析器版本、原始事件只在详情或运维层显示

建议：

- 主体正文使用清晰的中文无衬线字体，避免过小字号
- 标题、数值、状态和辅助说明形成明显对比
- 次要信息用颜色和间距降级，不要大量半透明到不可读
- 用空间分组和少量圆角容器表达边界，不把整页包成浮空大卡片
- 表格行高应支持扫描和点击，移动端改为纵向摘要
- 空状态必须解释为什么为空以及下一步动作

字体选择应先以项目可稳定加载、中文字符覆盖完整为准，再决定视觉风格。可优先评估本地或自托管的 Noto Sans SC、思源黑体、HarmonyOS Sans SC 等方案，避免依赖不稳定的外部字体请求。字体包的引入属于实现决策，不能替代信息层级本身。

## 十一、实施优先级

### P0：让核心闭环真的能完成

- 工作台行动队列：待分配、待验证、待审阅、待批准、逾期、失败重试
- 项目概览：阶段、owner、readiness、阻塞项
- 资料上传和解析状态
- 要求矩阵：分配、验证、证据、缺口
- evidence 侧边面板和来源回溯
- response plan 和章节状态
- drafting、review、approve/reject、cancel/retry
- deliverable 编辑、版本和导出前检查
- 通知和活动历史
- 账户、成员、邀请和基本角色管理

### P1：把已有优势做成差异化

- opportunity scorecard 和 go/no-go
- 文档变更影响分析
- readiness pack 和历史快照
- 内容库、项目记忆、Bid Wiki
- 团队工作量和跨项目审阅
- Provider、用量和预算
- 版本差异和证据质量

### P2：平台规模化能力

- 跨项目趋势
- 自动回归检查
- 图谱冲突合并
- 组织级 Agent 策略
- 成本优化、模型路由和质量评估
- 内部运维控制台和事故流程

## 十二、明确不做的事情

- 不把每一个 API 路由都做成一级菜单
- 不把原始 Worker、LangGraph、Provider 日志当普通用户功能
- 不用假趋势、假数字或装饰性流程图填充页面
- 不重复放“查看全部、打开项目、去详情”这类同义按钮
- 不把租户工作区、组织管理和平台运维混在一个页面
- 不因为 Supabase 有某个组件，就机械复制它的结构
- 不以“卡片更多”作为功能密度的衡量标准
- 不把旧的十几个 tab 原样恢复为主导航

## 十三、建议的验收方式

下一轮前端实现不以“页面看起来丰富”为验收标准，而以以下闭环验收：

1. 用户可以从机会或项目进入资料上传。
2. 用户可以知道资料什么时候可用，失败时可以重试。
3. 用户可以从要求矩阵完成分配、补证据、验证和决策。
4. 用户可以看到 readiness 为什么不足，并直接进入对应缺口。
5. 用户可以生成章节、查看证据、提交审阅和处理返工。
6. 用户可以知道当前批准版本，并导出可追溯的交付物。
7. 用户可以在“我的工作”看到跨项目的下一步。
8. 管理员可以完成成员、权限、用量和模型配置。
9. 普通用户不会被原始运行日志和内部队列打断。

## 十四、主要源码依据

- services/api/app/main.py：API router 汇总和访问边界
- services/api/app/*/router.py：各产品域路由
- services/api/app/*/schemas.py：请求、响应和状态契约
- packages/contracts/models.py：业务实体、生命周期和关联
- services/api/app/runtime/registry.py：Agent/运行时可调用能力及风险等级
- services/worker/app/tasks.py：解析、索引、编写、记忆、outbox、重试和死信
- apps/web/src/app.tsx：当前实际挂载的页面路由
- apps/web/src/features/workbench-v2/workbench-v2-layout.tsx：V2 主导航和账户菜单
- apps/web/src/features/workbench-v2/project-workspace-page-v2.tsx：当前项目工作区读取范围
- apps/web/src/features/projects/project-detail-page.tsx：旧页面中尚未迁移的业务操作
- apps/web/src/lib/api.ts：前端 API 封装覆盖面
- docs/superpowers/specs/2026-04-18-docpilot-design.md：产品边界和四平面架构
- docs/product/roadmap.md：阶段目标
- docs/product/mvp-scope.md：MVP 闭环验收

## 实现回写（2026-08-08）

本节记录本轮已经落地的前端与运行时边界，避免把历史盘点误读为当前状态。

### 已落地的用户表面

- 项目工作区增加“响应工作流”视图。它把 LangGraph 的内部节点翻译成用户可理解的七个业务阶段：资料解析、上下文检索、响应计划、章节起草、质量检查、人工批准、结果入库。运行记录、阶段进度和公开事件来自真实 execution run/runtime event 查询，不展示模型思维或内部节点日志作为主内容。
- 没有关联 runtime event 流的历史运行仍然保留在列表中，并明确标注“暂无事件流”，不会被静默过滤。这样可以区分旧数据缺少观测链路与运行失败。
- 账户与个性化、组织设置、集成与模型共用设置导航和内容宽度，采用工作区的中文字体、空间分组和少量圆角容器；不再用整页浮空卡片或重复的“查看全部”按钮堆叠信息。
- 工作区与旧平台壳统一使用 BidPilot 自定义 SVG 标识；收起侧栏时标识和展开按钮使用独立网格行，避免覆盖。
- 知识资料文本文件可以在浅色 Sheet 中直接预览，二进制资料使用对象 URL，若后端返回可信 HTTP(S) 来源则显示来源链接。预览失败时仍提供下载原件和重新解析入口。

### 远程资料与研究语义

- `web_search` 只负责联网研究、摘要和引用，不会把搜索结果页面自动当成项目资料。
- `discover_remote_documents` 只在用户给定的公开页面上发现直接附件候选，不下载、不持久化；只接受明确的文档扩展名或“下载/附件/招标文件”等强信号，并排除“公告正文/详情”等普通页面链接。
- `fetch_url_to_project` 只把真实 PDF、DOCX、XLSX、TXT 等附件写入项目资料包，然后进入既有解析、索引和状态链路；网页证据必须显式声明 `import_mode=web_evidence`。该动作保留来源 URL，并遵守运行时审批边界。
- 这仍不是通用爬虫：当前发现范围是一页、明确附件、有限数量。跨页目录、登录态、验证码、批量站点适配需要单独的连接器和安全策略，不能由模型任意猜测。

### 尚未完成的表面

- 全局运行中心仍偏运维视角；项目内“响应工作流”是当前面向业务的主入口。后续可把全局运行记录按项目和业务阶段归类，并提供跳转到对应工作流。
- 资料中心目前支持上传和 Agent 入库，但尚未提供一个独立的“输入 URL → 发现附件 → 选择并入库”的直接 UI；现阶段该能力通过 Agent 工具调用完成。
- 账户、组织和模型设置的真实登录态端到端覆盖仍需测试夹具或测试租户；后端资料导入测试需要配置以 `_test` 结尾的 PostgreSQL 测试库。

本轮的验收原则是“后端事实可见、动作可追踪、失败可恢复”，而不是增加装饰性图表或菜单数量。

## 十五、给产品决策的两个问题

本文先不替产品做最终取舍，后续实现前需要确认两个边界：

### 问题一：P0 是否以“单项目完成交付”为唯一主线？

如果答案是是，首轮就应优先打通：

资料 → 要求 → 证据 → readiness → 章节 → 审阅 → 导出。

机会漏斗、跨项目分析和复杂知识图谱放到后续，不要抢占主工作区。

### 问题二：P1 是否把机会、变更和内容库作为差异化能力？

后端已经有 opportunity assessment、DocumentChangeSet、ContentLibrary、MemoryGraph 等基础。如果答案是是，它们应在信息架构上有明确入口，而不是继续藏在 API 和旧页面里。

## 最终判断

BidPilot 当前最需要的不是更多装饰组件，而是一次“后端能力到用户行动”的重新编排：

- 把状态变成下一步
- 把证据变成信任
- 把运行时变成可解释进度
- 把版本和审阅变成交付保证
- 把组织能力从账户菜单中补全
- 把内部运维从普通工作区隔离

这份盘点可以作为后续前端重构的范围基线。后续每实现一个页面，都应能在本文找到对应的后端事实、用户任务和验收闭环。
