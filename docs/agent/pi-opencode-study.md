# BidPilot Agent Harness 学习与落地映射

本文只记录对仓库内 `temple/pi` 与 `temple/opencode` 源码的可验证观察，作为 BidPilot Agent 的实现约束，不把业务工具反向当成 Harness 核心。

## 1. Pi 的核心边界

Pi 的 Harness 由几层组成：模型循环、工具执行、事件 reducer、JSONL session、telemetry、compaction。模型输出不是最终 UI，而是事件流；宿主可以把同一事件流投影为终端、Web 或日志。

对应源码：

- `temple/pi/packages/agent/src/harness/agent-harness.ts`：回合循环与工具执行边界。
- `temple/pi/packages/agent/src/events.ts`：事件类型。
- `temple/pi/packages/agent/src/reducer.ts`：事件折叠为当前状态。
- `temple/pi/packages/agent/src/session/`：可恢复的会话记录。
- `temple/pi/packages/agent/src/telemetry.ts`：运行观测。

对 BidPilot 的约束：业务真相仍在 PostgreSQL；Harness 只负责决定下一步、等待工具结果、恢复和发出可重放事件。

## 2. OpenCode Web 的关键做法

`temple/opencode/packages/sdk/js/src/gen/types.gen.ts` 将一次 Agent 回合拆成细粒度事件：文本与推理 delta、工具输入开始/结束、工具调用、工具进度、成功、失败、重试、step 开始/结束/失败、压缩等。Web 端按事件类型渲染时间线，而不是收到一个“已完成”字段后自行猜状态。

这解释了 BidPilot 当前的两个问题：

1. 只发 `tool_succeeded` 或通用 `assistant.end` 会掩盖失败原因。
2. 把整段执行包成一个圆角卡片，会丢失“当前正在等待什么、工具拿到了什么、下一步依赖什么”的上下文。

## 3. BidPilot 的目标事件协议

每个事件至少携带 `runtime_run_id`、`turn_id`、`tool_call_id`（适用时）、公开摘要、脱敏参数、公开结果或错误码。前端状态只由事件推进：

`idle -> thinking -> executing_tool -> waiting/needs_confirmation -> executing_tool -> completed|failed`

工具详情必须能回答：调用了哪个工具、传入了什么、何时开始、进度是什么、返回了什么、失败在哪里、是否可重试。`assistant.end` 只能关闭流，不能把已确认的失败改写成成功。

## 4. 并行、等待和恢复

Harness 可以并行执行同一回合中互不依赖且明确标记 `parallel_safe` 的只读工具；涉及审批、数据库写入、共享 Session 或前置结果的工具保持顺序。等待审批、外部下载、异步工作流必须产生可恢复的暂停状态，并以 runtime event 作为唤醒游标，而不是依赖浏览器内存。

当前 BidPilot 产品适配器使用共享 SQLAlchemy Session，因此暂不打开业务工具并行；先保证协议具备并行能力，再逐项声明无副作用工具。

## 5. 结构化 UI

Agent 可以输出受限的 `ui_action` JSON（如 `canvas`、`link`、`download`、`form`），前端根据白名单渲染按钮、表单或画布入口。禁止让模型直接输出 HTML/JS。动作必须带明确标题和目标路由，导航类动作由用户点击确认，避免“用户问能否打开画布”却被模型误导到交付页。

## 6. 本轮验收标准

- 工具开始、进度、成功、失败均可见，失败详情不会被终态覆盖。
- “打开/查看任务编排画布”解析到当前项目的 `?surface=workflow`，并展示为用户可点击动作。
- 运行详情保留 trace、turn、tool call 标识和脱敏参数。
- 时间线采用扁平事件流，只有真实产物/预览保留容器。
- 非依赖工具的并行能力有核心层契约与测试；业务写工具默认串行。
