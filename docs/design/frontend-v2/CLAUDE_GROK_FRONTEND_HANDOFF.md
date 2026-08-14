# 可直接复制给 Claude Code / Grok 的前端 V2 任务说明

```text
你现在接手 BidPilot 的前端 V2 重构。请把这视为一次替换式企业工作台工程，
不是修补旧聊天页面，也不是给现有 UI 换色。

仓库：E:\my_idea_cc\BidPilot

第一原则：当前 main 上的 V1 前端必须保留作为稳定回退。不要在 main 直接改，
不要删除 V1，不要强推，不要部署公网，除非用户明确说“部署”。

请从最新 origin/master 创建独立分支：
  claude/frontend-v2-rebuild

开始前必须阅读：
1. AGENTS.md
2. docs/superpowers/specs/2026-04-18-docpilot-design.md
3. docs/product/roadmap.md
4. docs/adr/0001-core-technology-stack.md
5. docs/dev-log/progress.txt
6. docs/design/frontend-v2/DESIGN.md
7. docs/design/frontend-v2/FRONTEND_V2_REBUILD_REQUIREMENTS.md

BidPilot 不是通用聊天机器人。它是投标经理、售前工程师、方案架构师、交付负责人的
投标执行工作台：资料进入项目后，系统提取要求和证据、建立执行计划、起草、审查、
导出，并让每一个 AI/工具动作可追溯。

技术边界：
- 保留 React 19 + Vite + TypeScript + React Router + TanStack Query；
- 复用现有 FastAPI API client、鉴权和领域边界；
- 基础 UI 优先 Base UI + 仓库已有 shadcn 组件；
- `assistant-ui`、AI Elements 等 Agent UI 库只能先做隔离 POC，不能因为 star 高就把
  demo 生搬到产品里；
- 动效优先 Motion，克制使用；不要堆 ReactBits、GSAP、Canvas 粒子；
- 不改后端 runtime、数据库、模型 key、生产环境变量。发现 API 缺口时写 API gap 和
  mock fixture，交给后端独立分支处理。

组件与来源要求：
- Button、Input、Select、Menu、Dialog、Drawer、Tabs、Popover、Tooltip、ScrollArea、
  Resizable、Toast、Markdown、上传、流程画布等基础交互必须用成熟、官方、可访问且
  来源清晰的组件，不能手搓脆弱基础设施；
- 业务组件可以自研，但只能由上述原语组合，不能重新发明焦点、键盘、弹层定位或
  sticky scroll；
- 首个提交新增 docs/design/frontend-v2/COMPONENT_SOURCE_LEDGER.md，记录每个重要
  组件的场景、来源 URL、仓库 URL、固定版本、许可证、选择原因、采用方式和验证；
- 禁止来源不明 snippet、博客整段复制、无许可证包、破解包、随机 favicon 热链和没有
  维护信号的新 Agent UI 包；
- 官方模型提供商 logo 必须来自官方品牌资产或许可明确来源，不准用临时字母伪造。

先设计，后实现：
- 使用 nexu-io/open-design 作为本地设计工作区，不把它当 React 组件库；
- 在仓库根目录维护 opendesign/，先做 V2 画板并给用户本地预览；
- 不要导入现有混乱 UI 后微调；只继承 BidPilot 的业务语义和必要品牌资产；
- 必须先做并让用户看见：App Shell、Agent Desk 六种状态、项目工作台、Dashboard
  有/无项目态、提供商设置、工作流运行视图；
- 画板确认后再翻译成 React。不要写完一大坨代码才让用户猜效果。

视觉方向：
- 高密度、克制、可信的企业工作台，像优秀开发工具/现代 B2B 软件，不像营销页、
  赛博终端或消费聊天应用；
- Light 用冷白/蓝灰，Dark 用石墨/深灰；主操作是受控蓝；蓝紫仅用于 Agent 运行、
  焦点和模型能力；
- 绿色仅成功，琥珀仅审批/注意，红色仅失败/危险；
- 使用 Geist；统一 token、间距、圆角、阴影和 focus ring；
- 禁止荧光绿常驻边框、渐变光球、赛博网格、彩色左边框、巨大圆角卡堆、每区块玻璃
  拟态、永久呼吸、假客户/假认证/假数据；
- 任何文本、文件名、模型名、消息、菜单都不得溢出、遮盖或撑破容器。

必须重做的信息架构：
全局导航：概览、项目、智能体、知识资产、运行记录；团队/成员、模型提供商、账户
与账单、系统设置放底部管理组。公开首页/定价/文档不混进工作台。

项目详情只保留：
1. 项目概览与下一步
2. 资料与来源包
3. 要求与证据
4. 草稿
5. 审查
6. 交付物
7. 审计
不要再把十二个无关概念平铺为 tab。

Agent Desk 是第一优先级，路由 /agent：
- Desktop：全局导航 | 可收起会话历史 | 可读宽度对话主列 | 按需上下文/证据栏；
- 输入框必须仅对齐对话主列，固定于其底部，并留出精确滚动空间，不得遮最后一条；
- 1024px 以下上下文改 Sheet，768px 以下历史改 Drawer，390px 仍可用；
- 收起栏必须真实改变 grid/resize，不能用 absolute 遮住内容或挤成竖条；
- 历史会话必须真实支持新建、首条有效意图自动命名、双击/菜单改名、搜索、按时间
  分组、删除确认/失败回滚、缓存切换；
- 内部路由和会话切换必须 SPA + 局部 skeleton，不能全屏白屏刷新。

聊天与附件：
- 用户消息是克制中性表面，不用饱和绿色大气泡；
- 附件是消息外的文件对象：缩略图/类型、文件名、大小、上传/解析状态和操作；
- 附件不能被塞进文本气泡；系统仅在真实上传并可解析后才能说“已读取”；
- 流式 Markdown 必须正确支持 GFM、代码、表格、数学公式、引用和安全链接；
- 代码/表格/公式在窄屏不能撑破宽度；
- 复制、重新执行、编辑、来源引用等动作 hover/focus 或消息尾部显示；
- 输入框支持附件、多行、Enter 发送、Shift+Enter 换行、模型、推理强度和权限菜单；
- 推理强度固定英文：low / medium / high / extra / max；
- 运行时发送按钮必须变停止，点击后显示“正在取消”直到收到确认；
- 运行时不能锁死输入框；允许排队或中断指令，但必须防止双重发送；
- 不要在 composer 下方永久放 Sandbox/权限解释文字。

最关键：Agent Execution Trace / Run Timeline：
- 一次请求开始后，助手回复的第一项必须是紧凑运行摘要，而不是先说空话再把工具卡
  堆到最底部；
- 摘要显示当前阶段、进度、耗时、状态、展开/收起和停止；
- 展开层级必须是 Run -> Phase -> Action -> 安全详情/产物；
- 用户只看见“搜索项目”“读取资料包”“提取资格要求”“建立执行计划”等领域语言；
  绝不能暴露 search_projects、tool_call_id、JSON、SQL/Python stack trace、原始参数；
- 运行中当前 action 使用一个安静 spinner 与蓝紫微脉冲；完成后静止；失败行展开并
  给出重试/跳过/修复；完成后默认收成“已处理 N 个操作”；
- 多步骤必须随着 SSE 事件插入同一次 run 内，不能全挤在聊天最底部；
- Approval/HITL 必须是显式中断组件：动作、影响范围、风险、可编辑参数、确认/拒绝/
  稍后处理，并把结果写回同一 trace；
- 支持后台运行、离开恢复、取消、从检查点重试；不能假装多轮执行。

Agent 事件契约：先建 fixture state gallery，再接 SSE。每条事件至少包含 run_id、
event_id、sequence、timestamp、optional parent_id。事件至少包括 run.started、
plan.updated、tool.started、tool.progress、tool.completed、tool.failed、
approval.requested、approval.resolved、artifact.ready、message.delta、
message.completed、run.cancelling、run.cancelled、run.completed。前端必须按 event_id 去重、
按 sequence 排序、支持重连补发与恢复，禁止重渲染/SSE 重连造成双消息或双 run。

先演示 fixture 状态：idle、planning、running/streaming、approval、failed/retry、
cancelling/cancelled、background completed、restored session、多附件上传/解析失败、
长历史列表和移动端。

项目工作台要求：
- 资料真实展示上传、解析、可检索、失败重试；
- 要求回链来源，证据是领域对象；
- 草稿有版本、来源、diff、重新生成原因；
- 审查用可调整分屏：左草稿/证据，右评论/决策；
- 工作流画布只展示真实状态，优先 @xyflow/react，移动端有线性替代；
- Dashboard 空态给出第一条执行路径，不是一大片空白。

验证与节奏：
1. 先提交设计计划、组件来源台账、状态矩阵和 OpenDesign 画板；
2. 用户确认视觉后实现 App Shell + Agent Desk fixture；
3. Playwright 截图通过后再接真实 API/SSE；
4. 再做项目工作台、知识、运行、设置与 Dashboard；
5. 最后做全量 E2E、视觉回归、性能和无障碍；
6. 用户确认前不部署。

每个阶段需用 Playwright 验证 1440x900、1024x768、768x1024、390x844：无横滚、
无文本遮盖、无 composer 覆盖、无 console error、无重复请求。运行
pnpm --filter @docpilot/web build 和关键 E2E 后再请求验收。不要使用 Codex 内置浏览器；
终端 Playwright 可以用。

不要告诉我“局部补丁足够”或“先做简单 MVP”。这次要求的是可回退、可验收的前端替换。
但也不要为重构引入第二个路由器、第二套 CSS 框架、第二个全局状态管理或一堆没有
明确所有权的动画库。每次改动前读代码，并按来源台账和设计稿实施。
```
