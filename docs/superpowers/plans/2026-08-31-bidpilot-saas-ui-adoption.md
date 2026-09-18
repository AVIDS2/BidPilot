# BidPilot SaaS UI 源码复用迁移计划

## 目标

将 BidPilot 的公共着陆页、认证体验、用户工作台、账户和团队管理页面，迁移到可验证的 SaaS 模板实现方式。优先评估 Open SaaS/Wasp 与 Kiranism/Next 的真实源码是否适合作为前端基座，同时保留 BidPilot 当前的 FastAPI、PostgreSQL、Pi Agent 和业务 API。基座选择必须经过实际启动、构建、认证/API 接入和 Agent 页面挂载验证。

本计划不是重新画一套相似皮肤，也不是把 Next.js/Wasp 应用强行嵌入当前项目。每个 UI 能力必须落到上游真实源码、现有 shadcn 组件、真实 API 状态和可执行的浏览器验收上。

## 已确认的复用来源

| 来源 | 许可 | 本项目使用范围 | 不复用 |
| --- | --- | --- | --- |
| [Kiranism/next-shadcn-dashboard-starter](https://github.com/Kiranism/next-shadcn-dashboard-starter) | MIT | 若选择前端基座：Sidebar、工作台壳层、页面容器、表格工具栏、筛选、表单组合、账户菜单、移动端交互；其 AI Chat 的消息渲染组件可作为参考 | Next App Router、Clerk 账号服务、演示数据、品牌资产；AI Chat 的 scripted transport |
| [ixartz/SaaS-Boilerplate](https://github.com/ixartz/SaaS-Boilerplate) | MIT | 着陆页区块组织、认证页面布局、多租户/团队页面的信息架构 | Clerk、Drizzle、Next.js 服务端实现、演示文案和图片 |
| [nextjs/saas-starter](https://github.com/nextjs/saas-starter) | MIT | 简洁的营销首屏、价格页、活动日志/账户信息层级参考 | Stripe、Next Server Actions、示例账号 |
| [wasp-lang/open-saas](https://github.com/wasp-lang/open-saas) | MIT | 若选择全栈基座：着陆页、认证/邮箱验证、管理后台、支付/文件上传/Jobs 的真实 Wasp 组织方式；AI function-calling 示例 | Wasp server 生成的认证/Prisma 数据层在未完成迁移前不能直接替代 FastAPI/Pi；AI demo 的业务模型和示例数据 |
| [shadcn/ui 官方组件](https://ui.shadcn.com/docs/components) | 组件源码生成模式 | 当前项目的 Base UI 组件、无障碍属性和组合规范 | 未验证的第三方 registry 代码 |

Midday 当前仓库标记为 AGPL-3.0，并且其官方说明要求商业部署联系授权；本迁移不复制 Midday 代码或组件。所有直接移植的 MIT 源码保留版权和许可证声明，记录在仓库根目录的 `THIRD_PARTY_NOTICES.md`。

## 架构边界

- 基座选择在兼容性验证完成前保持 pending；当前已有 Vite + React Router 实现作为可回退产品壳层。
- 如果采用 Kiranism，迁移范围是 Next 前端基座和页面源码，FastAPI/Pi 通过 typed API adapter 接入；Clerk 不自动进入生产。
- 如果采用 Open SaaS，必须明确是否迁移到 Wasp 的 Node/Prisma 控制面；仅复制页面不会获得其内置认证、数据库和 Jobs 的基础设施收益。
- FastAPI 继续负责认证、组织、权限、项目和运行数据；模板中的 Clerk 组件只作为视觉/交互来源，不能进入生产依赖。
- Pi Agent 的官方事件流、Handler、工具调用、暂停/恢复和错误终态不改造为 UI 关键词逻辑。
- 业务数据必须来自 TanStack Query/API；禁止用静态数量、假项目或延迟后替换默认 `0` 的占位行为。
- 所有新页面必须同时处理 loading、error、empty、success 和 mobile 状态。

## 任务清单

### A0. 基座兼容性验证

- [x] 核对 Open SaaS 当前仓库、Wasp 配置、AI 示例、认证和部署文档。
- [x] 核对 Kiranism 当前仓库、AI Chat 实现和 dashboard 页面结构。
- [ ] 在隔离目录分别实际启动/构建 Open SaaS 与 Kiranism 的最小页面，记录 Node/Wasp/Next/依赖和部署成本。
- [ ] 为当前 FastAPI/Pi API 写出基座接入矩阵：认证、会话、SSE、文件上传、支付、组织/团队、错误契约。
- [ ] 决定“全栈迁移 Open SaaS”或“只采用 Kiranism/Open SaaS 页面源码的前端基座”。

验收：有真实构建日志、关键页面截图/DOM、API 接入验证和可逆的基座选择结论；未完成前不切换生产前端。

### A. 基线与许可

- [x] 创建隔离分支 `codex/saas-ui-adoption`。
- [x] 用 shadcn CLI 确认项目为 Vite、Tailwind v4、`base-nova`、Base UI、Lucide。
- [x] 核对 Kiranism、ixartz、官方 starter 和 Midday 的许可证及当前源码结构。
- [x] 增加 `THIRD_PARTY_NOTICES.md`，登记实际复制/计划复制的 MIT 来源和排除的 AGPL 来源。

验收：分支可独立构建；许可证来源、复制范围和外部服务依赖可追溯。

### B. SaaS 应用壳层

- [ ] 用现有官方 shadcn `SidebarProvider/Sidebar/SidebarMenu` 组合替换自定义工作台导航壳层。
- [ ] 保留桌面收起、Logo 展开、移动端 Sheet、Tooltip、键盘快捷键和路由预取。
- [ ] 统一 `PageContainer`、页面标题、面包屑、页级操作区、Skeleton、Empty、Alert 和 Toast。
- [ ] 用真实账户菜单连接账户、组织设置、集成设置和退出登录。

验收：桌面 1440/1024、移动 768/390 下导航、收展、路由和键盘焦点无重叠、无重复按钮、无控制台错误。

### C. 公共着陆页

- [ ] 按 ixartz 的真实区块组织重构 `/`：导航、Hero、产品能力、工作流、价格、FAQ、CTA、Footer。
- [ ] 保留 BidPilot 的真实产品定位、Logo、登录/注册路由和价格 API 语义。
- [ ] 删除当前 `StarBorder`、`ProductGlareCard`、影视画框标注和非业务装饰性伪效果。
- [ ] 移动端使用真实 Sheet/Dropdown 导航，CTA 与内容不溢出。

验收：未登录可直接浏览完整首屏和区块；登录/注册/价格链接可用；桌面和移动截图核对布局。

### D. 认证与账户

- [ ] 用 shadcn `Field/FieldGroup/Input/Alert/Button/Spinner` 重构登录、注册、找回密码和邮箱验证表单。
- [ ] 保留现有 JWT、Turnstile、邮箱验证、组织创建和邀请 token API。
- [ ] 用 Kiranism/ixartz 的认证布局组织方式，但不引入 Clerk。
- [ ] 重构账户资料、安全、提供商和 Webhook 页面，使其共享页面容器和表单状态。

验收：注册→邮箱验证→登录→账户资料修改完整跑通；失败、重复提交、网络错误均有真实反馈。

### E. 团队与数据页面

- [ ] 复用 Kiranism 的 Table、Toolbar、Command/Popover filter、Pagination、DropdownMenu 行操作组合。
- [ ] 迁移项目、成员、运行记录、知识库、交付物和管理页面的 loading/error/empty 处理。
- [ ] URL 保留筛选、分页和排序；TanStack Query 缓存旧数据，避免页面先闪 `0`。
- [ ] 团队邀请、角色和危险操作使用 Dialog/AlertDialog，不使用 `window.confirm`。

验收：真实 API 数据、筛选、分页、CRUD、权限和移动端列表均有 Playwright 覆盖。

### F. Agent 专项适配

- [ ] 将 `apps/web/src/features/agent` 的聊天 UI 入口、消息/工具/思考渲染、composer 和事件状态适配器整理为稳定的 `AgentSurface` 边界，保证可在不同 SaaS 壳层挂载。
- [ ] 为 Agent Surface 明确 router、auth、API、Pi event feed 和 cancellation adapter，不让新基座直接复制关键词/伪造状态逻辑。
- [ ] 只统一 Agent 页面外围壳层和 shadcn 交互，不替换 Pi Handler 或事件协议。
- [ ] 工具执行完成后保留可展开明细；思考状态只由真实事件状态驱动。
- [ ] 暂停、取消、重试、恢复和错误终态分别验证，不使用“安全停止”泛化真实错误。

验收：真实 Pi 流式对话至少覆盖普通问候、工具调用、工具完成、暂停/取消、失败和恢复；桌面/移动无滚动跳动。

### G. 发布门禁

- [ ] TypeScript、单元测试、生产构建通过。
- [ ] Playwright 桌面和移动通过；记录截图、控制台和网络错误。
- [ ] API focused tests、Pi tests 和 worker tests 通过；已知依赖外部 MinIO 的测试单独标记。
- [ ] 先部署预览或低风险环境，确认后再部署生产。

## 动态记录

### 2026-08-31

- 创建隔离分支 `codex/saas-ui-adoption`。
- 完成上游仓库许可证、源码结构和官方 shadcn 组件文档核对。
- 确认当前项目已有完整 Base UI 组件集合；现阶段不创建第二套 UI 基础层。
- 完成 Open SaaS/Wasp 与 Kiranism/Next 的官方仓库和文档核对：Open SaaS 的 AI 是 OpenAI function-calling 日程示例，Kiranism 的 AI Chat 是本地 scripted `useChat` demo，均不是现成 Pi Agent 后端。
- 重新将下一步设为 A0 基座兼容性验证和 F 批次 Agent Surface 封装；在基座结论前暂停继续扩大 Vite 页面迁移范围。
