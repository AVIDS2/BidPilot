# ReAct Harness、提示词与计划执行真实状态

> 日期：2026-08-10  
> 依据：[Pi 源码学习记录](../learning/2026-08-10-pi-agent-harness-source-study.md)、`temple/pi` 当前源码、[Agent 工程师完全手册](../learning/agent-engineering-complete-guide.md)。  
> 结论先行：BidPilot 已有可运行的 **ReAct** 工具循环和业务接入；尚未达到 Pi coding-agent 所展示的完整交互 harness，更没有完成一个可由用户审阅、确认、恢复的产品级 Plan-and-Execute。

## 1. 术语先纠正

这里是 **ReAct**，不是 React 前端设计模式：

```text
模型读取上下文 -> 选择工具 -> 服务端执行/暂停 -> 工具结果进入下一轮上下文 -> 模型继续或结束
```

Pi 的 `packages/agent/src/agent-loop.ts` 实现的正是这条循环。它没有内建的 `planner node -> executor node` 工作流；Pi 的 plan mode 位于 `examples/extensions/plan-mode/`，是可选扩展。

## 2. 当前实现核对

| 能力 | 代码事实 | 状态 | 说明 |
| --- | --- | --- | --- |
| ReAct 核心循环 | `services/api/app/runtime/harness_core.py` | 已实现 | 顺序工具调用、结果回写、失败预算、暂停、取消、步数上限、稳定 trace。|
| 受治理的业务工具 | `bidpilot_harness_adapter.py` + `service.py` | 已实现 | 业务事实仍在 PostgreSQL；写入先走参数校验、权限、审批、审计、幂等 action。|
| 模型适配和真实工具调用 | `harness_host.py` | 已实现 | DeepSeek V4 在“先确认、不要只解释”场景会切换非思考工具绑定，生成真正的受治理审批，而不是只输出口头确认。|
| 上下文工程 | `prompt_assembly.py` | 已实现 | 固定上下文顺序、预算、非可信资料边界、附件/记忆/通知 trace。|
| 运行事件 trace | `RuntimeRun` / `RuntimeAction` / `RuntimeEvent` | 已实现 | 关联 `turn_id`、`action_id`、父事件；可回放审批和工具生命周期。|
| 同一次运行内写入去重 | `bidpilot_harness_adapter.py` | 已实现 | 按 capability + 规范化参数缓存成功 mutation；底层仍由 action key 保证持久化幂等。|
| 通用 core steering/follow-up | `harness_core.py` | 内核已实现，产品未接通 | 内核可在工具边界接收 steering、在将结束时接收 follow-up；当前 Web/SSE Host 没有把用户新输入接入正在运行的同一个 active run。|
| Pi 式会话树、压缩后恢复 | Pi `session-manager.ts` / `agent-session.ts` 有；BidPilot 无同构实现 | 未完成 | BidPilot 有数据库事件和每轮确定性上下文裁剪，但没有 Pi JSONL 会话树、分支、一次 overflow 压缩后继续的完整语义。|
| 计划模式 / Plan-and-Execute | core 有 `HarnessPlanPolicy` 协议；Host 只发布回合状态 | 未完成 | 当前 `PLAN_UPDATED` 大多是“正在判断下一步”的运行状态，不是用户可确认、可逐步完成、可恢复的计划。|
| Loop engineer | 目前无独立实现 | 未完成 | 尚缺长任务自检、上下文压缩恢复、工具错误分类后的计划修订、可测试的任务级 stopping policy。|
| LangGraph 任务型编排 | 现有 workflow bridge | 部分完成 | 可由业务 capability 启动并回写事件；尚未与通用对话的计划模式统一成同一份可审阅执行计划。|

因此，不能称“harness、loop engineer、plan-and-execute 都完成了”。准确说法是：**ReAct 核心与受治理业务执行已可用；Pi 式产品级 harness 和 Plan-and-Execute 还在缺口清单中。**

## 3. Pi 的小提示词为什么能工作

Pi `packages/coding-agent/src/core/system-prompt.ts` 的默认提示词确实很短：角色、可见工具、少量 guideline、项目上下文入口。它不靠提示词单独实现 harness。可靠性主要来自代码：

1. `agent-loop.ts` 维护模型、工具和工具结果的循环；
2. 工具参数先 `prepareArguments` / schema 校验，截断输出中的工具调用不执行；
3. `beforeToolCall` / `afterToolCall` hook、AbortSignal、流式 progress 和规范化 tool result 都在运行时；
4. `AgentSession` 负责会话、压缩、恢复和扩展。

所以“提示词小”不是少写规则，而是把控制流、权限、失败和状态从提示词移到可验证代码。BidPilot 当前的业务 system policy 仍过长，虽已把上下文组装抽到 `prompt_assembly.py`，但还没有把计划/恢复等控制语义完全移出提示词。

## 4. AgentBook 本轮回读后的落点

本仓库的 [Agent 工程师完全手册](../learning/agent-engineering-complete-guide.md) 把 Prompt Engineering、Tool Use、ReAct、Context Engineering、Evaluation 和 Observability 视为同一工程链路。对应落点如下：

- Prompt Engineering：保留领域目标、工具何时使用、非可信上下文处理和用户语言；不要求模型泄露思维链。
- Context Engineering：固定优先级、预算、历史摘要、资料和记忆边界。当前已经实现且有 context trace。
- ReAct：模型只根据真实工具结果继续；写入通过服务端审批而非聊天假确认。当前已实现。
- Evaluation / Trace：合同测试、真实提供商回归和可回放 RuntimeEvent。当前已有基础，覆盖面仍不足以宣布所有能力完成。

## 5. 已完成验收证据

### 确定性和受治理路径

- `62 passed`：核心 loop、Host、适配器、动作/审批、战役预算、附件与相关运行时回归。
- `875` 个 API 测试已完成全量执行；本轮修复前为 `871 passed, 4 failed`，四项已定位并修复，仍需最后一次全量复跑作为最终 gate。

### 真实模型路径

`services/api/artifacts/evaluations/live-harness/live-harness-eval-0efb72e599.md`：

- DeepSeek `deepseek-v4-flash`；
- embedding `qwen3-embedding-8b`，1536 维；
- 普通问答、资料检查、交付物生成、准备度分析、审批暂停和批准恢复；
- 交付物只写入一次，trace 同时含 `capability.started` 与 `capability.succeeded`。

这不是全能力评分：未覆盖真实远程文件下载、本地 companion、所有 capability、OCR worker、前端 active-run steering、复杂 LangGraph graph 轨迹和长上下文压缩恢复。

## 6. 接下来的实现顺序

1. **产品级计划模式**：计划是持久化的 runtime 视图，计划阶段只开放只读能力；用户确认后才开放相应写入 capability；每一项由真实 action/workflow event 更新，不能由模型文本标记完成。
2. **active run 控制面**：一个 conversation 只有一个 active run；Web 新输入按 steering 或 follow-up 入队；取消、重连、审批恢复都保留同一 trace。
3. **loop engineer**：加入上下文长度/截断探测、一次压缩后恢复、结构化错误分类、允许的替代路径和 task-level stop policy；每条规则必须有 fixture。
4. **统一 trace 与评估**：将普通 harness、审批、LangGraph、远程导入和本地 companion 统一关联到同一 trace；为成功、暂停、取消、失败、重试、幂等各建立真实和确定性场景。

在上述四项未完成前，任何 UI 都不应宣称“自动规划并完整执行”。
