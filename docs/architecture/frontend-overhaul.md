# BidPilot 前端整改方案

## Design Read

**Reading this as: B2B SaaS for technical buyers (procurement teams, bid managers), with a Linear-style minimalist language, leaning toward shadcn/ui + Tailwind v4 + Geist + restrained motion.**

### Dial Configuration
- DESIGN_VARIANCE: 5 (Offset — clean but not boring)
- MOTION_INTENSITY: 3 (Static — trust-first B2B)
- VISUAL_DENSITY: 5 (Daily App — data-dense but breathable)

## 设计系统确认

| 组件 | 状态 | 说明 |
|---|---|---|
| shadcn/ui base-nova | ✅ 已有 | 最新 shadcn 4 代 |
| Tailwind v4 | ✅ 已有 | CSS-based config |
| Geist Variable | ✅ 已有 | 主字体 |
| Lucide icons | ✅ 已有 | 图标库 |
| Dark mode | ✅ 已有 | next-themes |
| i18n | ✅ 已有 | i18next zh-CN/en |

## 新增组件

### 1. Agent Progress（agent-progress.tsx）
- 显示 agent 工作流当前节点
- 已完成节点带 checkmark
- 待执行节点灰色
- Review 分数显示
- Human approval 提示

### 2. Agent Status Stream Hook（agent-status-stream.tsx）
- useAgentStream(run_id) SSE 客户端
- 解析 SSE 事件更新状态
- 自动重连

### 3. Agent Tab（项目详情页）
- 新增 Agent tab
- 显示 agent 进度 + 审核界面

## taste-skill 规则应用

### 首页重设计
- **Hero:** Left-aligned headline + 右侧 product screenshot
- **Features:** Bento grid（不用 3 equal cards）
- **Social proof:** Logo wall under hero
- **How it works:** Zig-zag layout（max 2 consecutive image+text splits）
- **Pricing:** 3-column 优化间距

### Dashboard（新增）
- 项目概览卡片
- 最近活动 feed
- AI 使用量统计
- 快速操作入口

### Command Palette（新增）
- Cmd+K 命令面板
- 搜索项目、章节、需求
- 快速导航

### Notification（新增）
- 通知 bell icon + dropdown
- 通知类型：draft completed, review approved, export ready, HITL required

## Anti-Slop 检查清单

- [ ] ZERO em-dashes
- [ ] Hero fits viewport
- [ ] ≤ ceil(sectionCount/3) eyebrows
- [ ] No section-layout-repetition
- [ ] Color consistency lock
- [ ] Shape consistency lock
- [ ] No AI tells（no purple glow, no Inter, no three-equal cards）
- [ ] No div-based fake screenshots
- [ ] No fake-precise numbers
- [ ] No generic names（Jane Doe, Acme）
