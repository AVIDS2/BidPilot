# BidPilot Frontend V2 重构需求与验收规范

> 状态：前端重构交接基线
>
> 本次工作是替换式企业工作台重构，不是给旧页面换肤，也不是继续给旧 Agent
> 面板叠加卡片。当前 `main` 上的 V1 前端必须保留，作为可回退版本。

## 1. 先读这些文件

- `AGENTS.md`
- `docs/superpowers/specs/2026-04-18-docpilot-design.md`
- `docs/product/roadmap.md`
- `docs/adr/0001-core-technology-stack.md`
- `docs/dev-log/progress.txt`
- `docs/design/frontend-v2/DESIGN.md`

## 2. 产品与重构目标

### 产品定位

BidPilot 是服务投标经理、售前工程师、方案架构师和交付负责人的**投标执行
工作台**。资料进入项目后，系统应帮助团队提取要求和证据、建立执行计划、起草、
审查、导出，并让每一次人和 AI 的动作可追溯。

它不是“上传文件后聊天”的壳。用户在每一个页面都应能判断：

1. 当前在哪个项目和组织空间；
2. 项目有什么资料、要求、证据、产物与待办；
3. 智能体正在做什么、进度在哪、下一步是什么；
4. 哪些行为需要人工确认；
5. 某个结论或草稿来自哪些来源、由谁在何时批准。

### 必须消灭的现状

- 站内跳转全屏白屏、整页刷新或路由重挂载；
- 侧栏、会话栏、输入框、浮层互相覆盖，窄屏/移动端溢出；
- Agent 运行态是堆叠卡片、原始 JSON、内部 tool 名或服务器异常；
- 发送、停止、队列、审批、失败、重试、后台完成等状态不可信；
- 历史会话改名、删除、切换等操作不完整或延迟明显；
- 项目页将大量无关概念平铺为同级 tab，无法表达真实执行流程；
- 仪表盘空态只剩大片空白和一个按钮；
- 荧光绿、彩色左描边、常驻光晕、无意义动画、嵌套卡片和营销风元素侵入工作台；
- 用户可见区域出现 `search_projects`、`tool_call_id`、请求参数、JSON、SQL/Python
  stack trace 或“假成功”。

## 3. 分支、范围与回退

### 分支规则

1. 从最新 `origin/master` 创建 `claude/frontend-v2-rebuild`。
2. 禁止直接在 `main` 重构、强推、重置或删除 V1 文件。
3. V2 放在独立 feature/route/flag 下，视觉和 E2E 验收完成后才替换默认入口。
4. 未经用户明确说“部署”，不得上公网；未经用户确认截图，不得合并 `main`。
5. 每个阶段单独提交，不能夹带无关格式化、依赖大升级或后端重构。

### 允许的改动

- 重建 React 页面组合、V2 App Shell、设计 token、前端状态层和测试；
- 新增 `opendesign/` 设计工作区、V2 组件来源台账、fixture 和视觉回归；
- 为既有 API 补充类型、TanStack Query 缓存、错误边界和适配层；
- 发现 API 缺口时新增明确的 `API gap` 文档和 mock fixture。

### 禁止的改动

- 在 UI 分支顺手改 Agent runtime、数据库 schema、模型密钥、生产环境变量；
- 为了构建通过而删除 V1；
- 将复杂执行状态藏进一段助手文案；
- 以“现在能用”为理由保留假删除、双消息、输入锁死、溢出或原始报错；
- 未验收就部署。

后端需求应放到独立分支，例如 `claude/agent-runtime-hardening`。V2 前端只定义和
消费稳定 Agent Run 契约；运行时、审批、后台任务、记忆和检索由后端分支完成。

## 4. 组件优先与来源可追溯

### 正确理解“不得手搓”

不是每个布局 `div` 都要来自第三方，而是：

- Button、Input、Select、Menu、Dialog、Drawer、Tabs、Popover、Tooltip、ScrollArea、
  Resizable、Toast、Markdown、上传、图表、流程画布等**基础交互原语**，必须使用
  成熟且可追溯的组件；
- 业务组件如 `RunTimeline`、`AttachmentTray`、`EvidencePanel` 可以自研，但只能由
  批准原语组合，不能重新发明焦点管理、键盘交互、菜单定位或滚动锁定；
- 自研 CSS 只负责 token、布局、业务组合与少量品牌表现；
- 不能粘贴来源不明的 snippet、博客整段代码、无许可证包、破解包或没有维护信号的
  新 Agent UI 包。

### 组件来源台账

第一个提交必须新增：

`docs/design/frontend-v2/COMPONENT_SOURCE_LEDGER.md`

每个重要组件记录：

| 字段 | 必填内容 |
| --- | --- |
| 场景 | 例如执行轨迹、附件、审批表单 |
| 组件/模式 | 实际使用的组件或组合 |
| 来源 | 官方文档 URL 与仓库 URL |
| 包和版本 | 固定版本，不能写“最新版” |
| 许可证 | 已核实的兼容性 |
| 选择原因 | 无障碍、维护状态、bundle、API 适配 |
| 采用方式 | 直接使用、受控封装、仅参考 |
| 验证 | 单测、Playwright、键盘和移动端检查 |

### 默认边界

| 能力 | 首选来源 | 约束 |
| --- | --- | --- |
| 无障碍原语 | `@base-ui/react` + 仓库已有 shadcn | 不重写底层焦点和弹层逻辑 |
| 查询/缓存 | `@tanstack/react-query` | 历史、项目列表和返回页可缓存 |
| 路由 | `react-router-dom` | 站内跳转必须 SPA |
| 表单 | shadcn + `zod` | loading/error/disabled/recovery 必须齐全 |
| 瞬态反馈 | `sonner` | 不用 toast 替代审批或永久错误 |
| Markdown | `streamdown` 或 `react-markdown` 择一验证 | GFM、代码、表格、数学公式、安全链接 |
| Agent UI | `assistant-ui` 只能隔离 POC | 不可覆盖真实 run 事件和领域状态 |
| 流程/图谱 | `@xyflow/react` | 只表示真实关系或运行状态 |
| 动效 | `motion` | 只服务状态与空间变化 |

一个能力只能有一个明确所有者。不要在同页混用 ReactBits、GSAP、assistant-ui、AI
Elements、CopilotKit 等多套所有权不清的方案。

## 5. OpenDesign 先行

OpenDesign 是本地设计工作区，不是 React 组件库。先在仓库维护：

```text
opendesign/
  index.html
  manifest.json
  design-systems/bidpilot-v2/
  mockups/frontend-v2/
```

至少先完成并提供本地预览以下高保真画板：

1. 全局 App Shell：展开/收起、窄桌面、移动端；
2. Agent Desk：空态、运行、审批、失败、后台完成、历史管理；
3. 项目工作台：资料、要求与证据、草稿、审查、交付物；
4. Dashboard：有项目与无项目；
5. 提供商设置：预设、模型拉取、错误态；
6. 工作流运行视图：运行、暂停、失败、人工检查点。

画板由用户确认后才翻译为 React 页面。不能“先写一大坨代码，再让用户猜效果”。

## 6. 统一视觉和布局

### 视觉方向

高密度、克制、可信的企业工作台，接近高质量开发工具或现代 B2B 软件，而不是营销
页、赛博终端或消费聊天应用。

- Light：冷白与蓝灰画布、炭黑文本、低对比结构线；
- Dark：石墨与深灰表面；
- 主操作：受控蓝色；Agent 运行与焦点：蓝紫；
- 绿色只表示成功/已验证，琥珀只表示注意/审批，红色只表示失败/危险；
- 使用 Geist variable；UI 标签稳定在 13-14px，不靠巨大标题制造层级；
- 统一 token、圆角、阴影、间距、边框和 focus ring；
- 长文本、ID、文件名、模型名必须截断或换行并提供 reveal，绝不撑破容器。

### 禁止项

- 荧光绿全局 accent、输入框常驻发光边框；
- 渐变光球、全屏雾化、装饰粒子、赛博网格、彩色左边框；
- 巨大圆角卡片堆、每个区块都玻璃拟态、嵌套浮卡；
- 无意义滚动 reveal、永久呼吸和页面级动画；
- 假客户、假数据、假认证、假“AI 思考”文案；
- 以绝对定位解决布局，导致收起栏遮住主内容。

### 全局 App Shell

顶级导航：概览、项目、智能体、知识资产、运行记录；团队/成员、模型提供商、账户
与账单、系统设置放到底部管理组。公开首页、定价、文档不和工作台混用。

- 桌面导航 232-264px；收起后 64-72px，主内容应真实扩展，不能被遮盖；
- 收起图标有 Tooltip 和键盘可达；
- 站内跳转用路由 lazy + 局部 skeleton，不许整页白屏刷新；
- 1024px 以下用可控折叠栏，768px 以下改成 Drawer；
- 页面主体有稳定 max width/gutter，单独的数据表可横滚，但浏览器不允许整体横滚。

### Dashboard

空态不能只有居中的“创建第一个项目”。应提供第一条可执行路径：新建/导入项目，
上传资料包，提取要求与计划，人工确认后开始起草。有项目时显示最近项目、待确认
事项、运行中任务、待审查交付物和最近活动；它们必须是工作入口，不是填空间的卡。

## 7. 项目工作台

项目详情的顶层区域固定为：

1. 项目概览与下一步；
2. 资料与来源包；
3. 要求与证据；
4. 草稿；
5. 审查；
6. 交付物；
7. 审计。

不要再把十二个无关概念平铺成同级 tab。次级操作放到当前区域的工具栏、菜单或项目
设置。

资料上传后必须如实展示上传中、已上传、解析中、可检索、解析失败、需要用户处理。
Agent 只有在文件真实可读取后才能说“已读取”。要求可追溯到来源；证据是领域对象；
草稿有版本/引用/diff/重新生成原因；审查使用左草稿/证据、右评论/决策的可调整分屏。

## 8. Agent Desk：最高优先级

### 页面结构

`/agent` 是完整的 Agent Desk；浮动助手只是其他页面的轻入口。

桌面布局：

```text
全局导航 | 会话历史（可收起） | 对话与执行轨迹主列 | 按需上下文/证据栏
```

- 会话历史 252-296px，独立滚动，可收起；
- 主对话列 640-900px 可读宽度；
- 右侧上下文 280-360px，只在项目、证据、审批、产物或运行有价值时显示；
- Composer 对齐主对话列，固定于主对话列底部，必须预留滚动 padding，永不遮住最后
  一行；
- 所有收起/展开都用真实 grid/resize，不允许 absolute 覆盖；
- 1024px 以下上下文变 Sheet，768px 以下历史变 Drawer；390px 可单面切换，不能将
  三栏挤成几条竖线。

### 会话历史

必须真实支持新建、首条有效意图自动命名、双击/菜单改名、搜索、按时间分组、删除
确认与失败回滚。切换使用 TanStack Query 缓存和局部 skeleton，不能整页白屏。运行中
或待确认会话仅显示小 spinner/状态点，不要永久装饰动画。

### 消息、附件与 Markdown

- 用户消息使用克制中性表面，不使用高饱和绿色大气泡；
- 附件作为消息外的文件对象展示：类型/缩略图、文件名、大小、上传与解析状态、操作；
- 发送后附件仍可查看，不能被塞进文本气泡；
- Markdown 支持 GFM、标题、列表、表格、引用、代码、链接、数学公式；
- 代码/表格/公式在窄屏必须可读且不能撑开；
- 复制、重新执行、编辑、引用来源等动作只在 hover/focus 或消息尾部显示；
- 流式文本稳定增量插入，不能重复整段或抖动。

### Composer

必须支持附件、tray、多行、Enter 发送、Shift+Enter 换行、模型/提供商、推理强度和
权限模式。推理强度所有 locale 均固定为：`low`、`medium`、`high`、`extra`、`max`。

运行中发送按钮变成停止；点击后显示“正在取消”，直到收到确认。输入框不能锁死：
允许用户排队下一条或发送中断指令，但必须防止重复发送。权限说明只放菜单/Tooltip/
审批上下文，不能在输入框下长期占位。

## 9. Agent Run / Execution Trace / HITL

### 用户可见术语

- Agent Run / 智能体运行：一次可持久化任务；
- Execution Trace / 执行轨迹：按时间排序、可展开的执行过程；
- Run Timeline / 运行时间线：执行轨迹的视觉呈现；
- Human-in-the-loop / 人工确认点：运行暂停等待决策；
- Artifact / 产物：计划、要求矩阵、草稿、导出文件等。

### Trace-first 规则

每一次运行的助手回复**第一项**必须是紧凑运行摘要，而不是先输出泛泛自然语言，
再把工具卡塞在最底部。摘要显示：当前阶段、进度、耗时、运行状态、展开/收起和停止。

展开后层级严格为：

1. Run summary；
2. Phase，例如“读取项目上下文”“提取资格要求”；
3. Action，例如“搜索项目”“读取资料包”“识别截止时间”；
4. 安全详情：精炼结果、来源、产物、可恢复错误。

运行中当前 action 使用一个安静 spinner 和克制蓝紫微脉冲；完成后静止；失败行默认
展开一次并给出重试/跳过/修复；完成后默认收成“已处理 3 个操作”。多步骤随着事件
插入同一次 run，不能全堆到聊天最底部。

用户界面不得显示内部 tool 名、`tool_call_id`、完整参数、JSON、SQL/Python stack
trace。必须做 i18n 映射，例如 `search_projects` -> “搜索项目”。开发者诊断模式如
存在，必须隔离、受权限保护、默认关闭。

### HITL

审批不是一段“你确定吗”的助手文案。它是 run 内显式中断，显示动作、影响对象、风险、
不可逆性、可编辑参数、确认/拒绝/稍后处理。确认结果必须写回同一条 trace。

删除项目、覆盖交付物、外部发送、产生显著成本等动作强制确认；读取/搜索/预览可按
权限模式自动执行，但必须留审计轨迹。

### 后台、取消与恢复

长任务可后台执行；离开页面后继续；返回后从 durable run 恢复。取消有请求中、已取消、
无法取消、已完成四种状态。失败支持从检查点重试，不能重复已完成步骤。单轮用户请求
的多轮自主执行表现为“计划 -> 多步骤 -> 检查点 -> 最终摘要”，而不是重复几条助手消息。

## 10. Agent Run 事件契约

前端先建 fixture state gallery，后续 SSE 必须消费稳定事件，不能自行发明字符串协议：

```ts
type AgentRunEvent = {
  run_id: string;
  event_id: string;
  sequence: number;
  timestamp: string;
  parent_id?: string;
  type:
    | "run.started"
    | "plan.updated"
    | "tool.started"
    | "tool.progress"
    | "tool.completed"
    | "tool.failed"
    | "approval.requested"
    | "approval.resolved"
    | "artifact.ready"
    | "message.delta"
    | "message.completed"
    | "run.cancelling"
    | "run.cancelled"
    | "run.completed";
  payload: unknown;
};
```

消费者必须按 `event_id` 去重、按 `sequence` 排序、支持断线补发与恢复、从同一个
`run_id` 重建时间线、将事件映射为用户语言，并防止重渲染/SSE 重连导致的双消息或双 run。

最少 fixture 状态：idle、planning、running/streaming、approval required、failed/retry、
cancelling/cancelled、background completed、restored session、多附件上传/解析失败、
长历史列表和窄屏。

## 11. 提供商与工作流可视化

- 提供商预设使用经过核对的官方名称和官方/许可明确的 logo；禁止随机 favicon 热链；
- 清楚表达 OpenAI-compatible、Anthropic Messages 和自定义端点的协议差异；
- “获取模型列表”有 loading、空结果、鉴权失败、协议不支持与成功态；
- key 永不回显、永不保存在前端、永不出现在 console；
- 工作流画布只展示真实运行状态，优先 `@xyflow/react`；节点状态应包括未开始、排队、
  运行、等待审批、完成、失败、取消；移动端提供线性阶段替代。

## 12. 交互、性能、可访问性、国际化

- 内部导航必须 SPA；加载使用局部 skeleton，不得白屏；
- 直接操作 140-220ms，面板变更 260-360ms；尊重 `prefers-reduced-motion`；
- 不同时运行 Canvas 粒子、GSAP ScrollTrigger 和多套持续动画；
- 大量历史/trace/文件使用虚拟化或分段加载；每个 token 流式更新不能重渲染整个 shell；
- 有键盘导航、visible focus、ARIA、44px 触控目标和足够对比度；
- 所有用户文本进入 i18n；中英文都需截图验收；推理强度除外，固定英文。

## 13. 实施顺序

1. OpenDesign 画板、设计 token、组件来源台账、Agent Run fixtures；
2. 用户确认视觉方向；
3. V2 App Shell + Agent Desk fixture；
4. Playwright 截图通过后接真实 API/SSE；
5. 项目工作台、知识、运行、设置、Dashboard；
6. 全量 E2E、视觉回归、性能与无障碍；
7. 用户确认后再切换默认入口和部署。

## 14. 不可合并/部署的阻断条件

- 1440x900、1024x768、768x1024、390x844 有遮盖、裁切、全页横滚或 composer 覆盖；
- 深浅主题存在不可读文本；
- 发送一次产生双消息/双 run；
- Agent 默认暴露内部数据、原始错误或虚假文件读取；
- 会话删除是假动作，审批/取消/失败/恢复没有真实状态；
- 内部路由仍整页刷新或明显白屏；
- 构建、关键 Playwright、console clean、组件来源台账任何一项未通过；
- 未获用户视觉确认。
