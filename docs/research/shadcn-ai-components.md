# shadcn AI 组件研究报告

## 当前状态

BidPilot 已有 AI 组件：

| 组件 | 路径 | 用途 | 评价 |
|---|---|---|---|
| chat-container | `ui/chat-container.tsx` | 聊天容器（StickToBottom） | 基础功能，缺 streaming 渲染 |
| message | `ui/message.tsx` | 消息显示 + markdown | 能用，缺 streaming 逐字渲染 |
| prompt-input | `ui/prompt-input.tsx` | 输入框 | 基础功能 |
| prompt-suggestion | `ui/prompt-suggestion.tsx` | 快捷建议 | 基础 |
| markdown | `ui/markdown.tsx` | markdown 渲染 | 完整 |
| code-block | `ui/code-block.tsx` | 代码高亮（Shiki） | 完整 |
| source | `ui/source.tsx` | 引用来源卡片 | 基础 |
| agent-progress | `agent-progress.tsx` | Agent 进度可视化 | 新加 |
| agent-status-stream | `agent-status-stream.tsx` | SSE 客户端 | 新加 |

## 可用库

### 1. assistant-ui (`@assistant-ui/react` v0.14.14)
- **与 shadcn 兼容：** ✅ 基于 Radix UI + Tailwind，专门与 shadcn 配合
- **关键组件：**
  - `Thread` — 完整的聊天线程 UI
  - `ThreadViewport` — 自动滚动视口
  - `Composer` — 输入编辑器
  - `UserMessage` / `AssistantMessage` — 消息气泡
  - `BranchPicker` — 分支选择
  - `ThreadHistory` — 历史列表
- **优势：** 开箱即用、专为 AI chat 设计、streaming 原生支持
- **安装：** `npm install @assistant-ui/react @assistant-ui/react-ai-sdk`
- **缺点：** 新增依赖，可能和已有组件重叠

### 2. Vercel AI SDK (`ai` v6.0.197 + `@ai-sdk/react` v3.0.199)
- **关键功能：** `useChat()` hook — streaming chat、`useAssistant()` — OpenAI assistant
- **优势：** 生态最成熟、streaming 原生、多 provider
- **安装：** `npm install ai @ai-sdk/react`
- **缺点：** 主要是 hooks 层，UI 组件需要自己配

### 3. shadcn base-nova（已有）
- 已是最新版本（4.10.0），base-nova 风格
- 自带 chat-container, message, prompt-input 等基础组件
- 不需要额外安装

## 建议

### 应该做的（按优先级）
1. **添加 Vercel AI SDK** — 用 `useChat()` 替代手动轮询，实现真正的 streaming token 输出
2. **改进 chat-container** — 添加 streaming 逐字渲染支持
3. **保持现有 shadcn 组件** — 已有组件够用，不需要重复安装 assistant-ui

### 不应该做的
- ❌ 安装 assistant-ui — 跟已有组件重叠，会增加包体积
- ❌ 大规模替换现有组件 — 已有组件够用，只需增强 streaming

## 行动计划
1. `npm install ai @ai-sdk/react` → 添加 AI SDK 依赖
2. 修改 chat-container + message → 支持 streaming 渲染
3. 后端 SSE 端点已就绪（Sprint 2），前端 hook 用 useChat 重连
