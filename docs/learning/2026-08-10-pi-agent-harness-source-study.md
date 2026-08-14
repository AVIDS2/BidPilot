# Pi Agent Harness 源码学习记录

> 目的：为 BidPilot 后续的智能体开发保留一份可追溯的 Pi 源码事实记录。
> 本文描述源码已经实现、明确未实现或作为示例提供的内容；不把示例扩展、路线图或本文推断写成 Pi 的既有能力。

## 1. 研究快照

| 项目 | 值 |
| --- | --- |
| 克隆目录 | `temple/pi` |
| 克隆来源 | `https://github.com/badlogic/pi-mono.git` |
| GitHub 当前仓库 | GitHub API 将该地址重定向为 `earendil-works/pi` |
| 源码提交 | `936aff00918de1187f085f123c2812d8f2d67745` |
| 提交时间 | `2026-08-09T02:11:00+02:00` |
| 本次阅读时间 | `2026-08-10` |
| 许可 | MIT，见仓库根目录 `README.md` |

仓库根 README 将 Pi 定义为 **Pi Agent Harness**，并列出三个核心包：统一模型 API `pi-ai`、具备工具调用与状态管理的 `pi-agent-core`、交互式 CLI `pi-coding-agent`。原始出处见 [根 README](../../temple/pi/README.md) 第 13-35 行。

### 关于“1500 行核心 harness”的核对

这个说法适合作为“概念上很小的 agent loop”的印象，但不符合当前源码快照的文件事实。运行时被拆成多个可组合模块，关键文件规模如下：

| 文件 | 行数 | 职责 |
| --- | ---: | --- |
| `packages/agent/src/agent-loop.ts` | 796 | 最小的 LLM-工具循环 |
| `packages/agent/src/agent.ts` | 592 | 有状态封装、队列、生命周期和事件订阅 |
| `packages/agent/src/harness/agent-harness.ts` | 508 | Harness V2 接口/占位实现 |
| `packages/coding-agent/src/core/tools/bash.ts` | 508 | 本机 shell 工具和流式输出 |
| `packages/coding-agent/src/core/session-manager.ts` | 1,714 | JSONL 会话树与分支持久化 |
| `packages/coding-agent/src/core/agent-session.ts` | 3,342 | CLI 层的会话编排、扩展、压缩和恢复 |

Pi 的“小”不等于把所有事情压在一个 1500 行文件里；它把 provider、loop、会话、TUI、工具和扩展分层，核心 loop 本身保持短小。

## 2. 代码结构：从模型到交互 CLI

```text
pi-ai
  统一多厂商模型协议、流式响应、工具参数校验
       |
pi-agent-core
  Agent 状态封装 + agentLoop + 事件 + tool hooks
       |
pi-coding-agent
  SessionManager(JSONL/会话树) + AgentSession + 内置工具 + TUI/CLI + Extensions
       |
终端中的本地用户进程 / 本地工作目录 / 可替换的工具执行器
```

这个层级来自 [根 README](../../temple/pi/README.md) 第 17-35 行和各包源文件。它说明 Pi 的可复用边界是 `pi-agent-core`，而交互式开发体验、会话文件、本机 bash 等位于 `pi-coding-agent`。

## 3. 当前可运行的 agent loop

### 3.1 循环不是“调用一次模型”

`packages/agent/src/agent-loop.ts` 的 `runLoop()`（第 155-275 行）是当前可运行的核心。它的实际顺序为：

1. 读取已排队的 steering 消息。
2. 进入内层循环，将 steering 写入上下文后请求并流式输出一条 assistant message。
3. 若模型返回 `error` 或 `aborted`，发出 `turn_end`、`agent_end` 并结束。
4. 从 assistant message 抽取 tool calls；若因 token 上限以 `length` 停止，则**拒绝执行整批工具调用**，避免执行参数被截断的命令。
5. 执行工具，将工具结果按原始调用顺序放回上下文，再结束该 turn。
6. 调用 `prepareNextTurn`，允许外层刷新上下文、模型或推理等级；随后检查停止条件和新的 steering。
7. 没有工具调用时，才读取 follow-up 队列；有 follow-up 则回到内层循环，没有才终止。

因此，Pi 区分两种“用户在过程中继续说话”的语义：

| 队列 | 注入时机 | 对应源码 |
| --- | --- | --- |
| `steer` | 当前 assistant turn 结束、下一次模型请求之前 | `agent.ts` 第 282-289 行；`agent-loop.ts` 第 181-190、259 行 |
| `followUp` | agent 本来将停止时 | `agent.ts` 第 287-289 行；`agent-loop.ts` 第 262-271 行 |

### 3.2 单活跃 run 与规范化失败

`Agent.prompt()` 和 `Agent.continue()` 在已有活跃 run 时直接拒绝，并提示调用者使用 `steer()` 或 `followUp()`（[agent.ts](../../temple/pi/packages/agent/src/agent.ts) 第 347-388 行）。每个 run 由一个 `AbortController` 关联；任何未捕获错误都会转成规范化的 assistant `error`/`aborted` 消息，仍然发出完整的 `message_start`、`message_end`、`turn_end`、`agent_end` 生命周期（第 486-535 行）。

订阅者按注册顺序被 `await`；即使 `agent_end` 已发出，直到订阅者完成，agent 才真正变为 idle（第 240-249、537-590 行）。这使“界面显示完成”和“会话/审计写入完成”可以由同一生命周期收口，而不是靠前端猜测。

## 4. 工具调用：校验、并发、流式进度与错误回写

`agent-loop.ts` 的工具调用管线不是简单 `try/catch`：

1. 找到工具；不存在时返回一条结构化错误工具结果。
2. 调用工具的 `prepareArguments`，再通过 `validateToolArguments` 校验。
3. 可执行 `beforeToolCall` hook；hook 可阻止调用并指定是否终止本批次。
4. 以 `AbortSignal` 和 `onUpdate` 调用工具；工具进度会变成 `tool_execution_update` 事件。
5. 经 `afterToolCall` hook 后，发出结束事件、构造 tool-result message，并让模型看到结果或错误。

出处为 [agent-loop.ts](../../temple/pi/packages/agent/src/agent-loop.ts) 第 600-758 行。

### 批处理并发的细节

- 全局配置或任一工具标注 `executionMode: "sequential"` 时，整批顺序执行。
- 否则 Pi 在预检查后用 `Promise.all` 并发执行。
- 并发的完成事件可以先后到达，但回写给模型的 tool-result message 仍按模型原始 tool-call 顺序排列。
- 只有一批工具**全部**将 `terminate` 设为 `true` 时，loop 才停止后续工具轮次。

出处为 `agent-loop.ts` 第 411-553、582-584 行。这里的“并发”是同一 agent turn 内的工具并发，不等于一个具备队列、租户隔离或故障恢复的后台工作系统。

## 5. 本地 shell / curl：Pi 实际做了什么

### 5.1 默认是运行 Pi 的本机进程

`packages/coding-agent/src/core/tools/bash.ts` 第 57-152 行定义了可替换的 `BashOperations`。默认 `createLocalBashOperations()`：

- 取得本机 shell 配置；
- 用 Node 的 `spawn()` 在 Pi 的 `cwd` 执行命令；
- 流式接收 stdout 和 stderr；
- 接受可选 timeout；超时或 `AbortSignal` 触发时调用 `killProcessTree()`；
- 支持替换 `operations.exec`，注释明确举例可委派给 SSH 等远端系统。

所以在 Pi 中让 agent 使用 `curl` 下载文件，实质是：**模型提出 bash 调用，当前启动 Pi 的用户进程在其本机/容器/远端执行器中运行 curl**。不是浏览器给网页临时授权，也不是 Pi 内置的“远程附件入库”协议。

### 5.2 输出处理，而非文件资料领域模型

`bash` 工具将持续输出通过 `onUpdate`（100ms 节流）回传 UI；默认只向模型返回有限行数/字节数，过长输出写到临时文件并在结果中提示路径。命令失败、超时、取消或非零退出码均转换成错误结果。见 `bash.ts` 第 321-457 行。

源码没有提供以下专用能力：

- 采购公告页解析、附件发现、HTML 与真实文件的判别；
- URL 下载断点续传、文件哈希、资料包归档、文件解析或业务去重；
- 将某次本机下载的文件可靠同步到一个多用户 Web 产品的对象存储；
- 用户身份、项目归属、人工审批、配额、审计或多租户授权。

这些不是 Pi 的缺陷，而是它把边界放在“可扩展的本地 coding harness”之后的结果。不能把 `bash` 的成功演示误称为上述业务能力已经由 Pi 提供。

### 5.3 权限事实

Pi 根 README 第 38-46 行明确写明：它**不内置**文件系统、进程、网络或凭据访问限制；默认继承启动 Pi 的用户与进程权限。其文档推荐的隔离方式是 Gondolin、Docker 或 OpenShell。`containerization.md` 进一步说明：可让工具运行在本地 micro-VM、将整个 Pi 放入 Docker，或放进由策略控制的 sandbox；后两者仍需调用者自行设置边界。

这项事实尤其重要：Pi 的本机 shell 模式可解释“使用用户本地 curl”这一交互方向，但源码本身没有把它变成可直接部署给任意 Web 用户的安全执行方案。

## 6. 会话、分支与上下文压缩

`pi-coding-agent` 的 `SessionManager` 使用 JSONL 保存会话：

- 新会话头包含版本、会话 ID、时间、cwd 与可选父会话；默认会话文件以时间和 ID 命名为 `.jsonl`。
- 每个 entry 有 `id` 和 `parentId`，内存索引维护当前 leaf，因此会话是树，不是不可回退的一条纯消息数组。
- 普通 message、模型/推理等级切换、压缩摘要、分支摘要、用户标签和扩展自定义 entry 都可附加到当前 leaf。
- 文件恢复会逐行读 JSONL，跳过损坏行，检查 header，并迁移旧 session 格式。

出处为 [session-manager.ts](../../temple/pi/packages/coding-agent/src/core/session-manager.ts) 第 870-1057、1096-1188、503-555 行。

上下文达到阈值或发生可恢复的 overflow/长度截断时，`AgentSession` 调用压缩：生成摘要、把摘要作为 `compaction` entry 持久化、重建 agent messages。对于可恢复错误，代码只做一次“压缩后重试”；达到阈值的正常响应只压缩，不自动继续。见 `agent-session.ts` 第 1951-2052、2058-2188 行。

这里保存的是 Pi 终端会话的历史与恢复资料，不是替代业务数据库。Pi 根本没有项目、材料、审批或交付物这些领域实体。

## 7. “Plan and Execute”与多智能体：当前源码的准确边界

### 7.1 它们不属于默认内核

`packages/coding-agent/README.md` 第 15-19 行明确说明：Pi 是一个最小终端 coding harness，默认跳过 sub agents 和 plan mode。`docs/usage.md` 第 303 行还列出默认不包含 MCP、子智能体、权限弹窗、计划模式、待办与 background bash。

因此当前可运行主 loop 是“模型 -> 工具 -> 结果 -> 下一轮模型”的反馈循环；它本身没有一个名为 planner node、executor node 的内建工作流图。

### 7.2 仓库确实有可读的实现示例，但它们是扩展

`packages/coding-agent/examples/extensions/plan-mode/` 是一个 TypeScript extension：

- 开启 `/plan` 时去掉 `edit`/`write`，并限制 bash 为只读命令白名单；
- 通过 prompt 要求模型输出 `Plan:` 下的编号步骤；
- 从 assistant 文本提取步骤，用户在 TUI 选择“执行/继续计划/细化”；
- 恢复工具后，将后续步骤作为 follow-up 发送；用 `[DONE:n]` 文本标记和 UI widget 跟踪进度；
- 状态通过 `pi.appendEntry("plan-mode", ...)` 写回 session。

出处为 [plan-mode/index.ts](../../temple/pi/packages/coding-agent/examples/extensions/plan-mode/index.ts) 第 1-25、116-215、250-325 行。

`examples/extensions/subagent/` 也是扩展示例：每个子智能体是独立 Pi 进程，支持单个、并行与链式调用；示例 workflow 例如 `scout -> planner -> worker`。它限定并行最多 8、同时 4，并对返回给父模型的结果设 50 KB 上限。见 [subagent README](../../temple/pi/packages/coding-agent/examples/extensions/subagent/README.md)。

结论：这些是可学习的扩展模式与源码样例，**不是安装 Pi 后默认自动获得的能力**。

## 8. Harness V2：设计文档与当前代码不能混为一谈

`packages/agent/docs/harness-v2.md` 与 `harness-v2-state-machine.md` 提出 durable harness 的目标：会话树、lane、操作记录、全局事实、单写入者、事件/副作用分离、手动或自动 drive、恢复和 checkpoint。

但同目录的当前 [agent-harness.ts](../../temple/pi/packages/agent/src/harness/agent-harness.ts) 不是完整的生产执行器：

- `AgentHarness.create()` 一旦发现已有 record 就抛出 `HarnessNotImplemented("create.restore")`（第 347-353 行）；
- `prompt`、`compact`、`resume`、`abort`、`steer`、`followUp`、`watch`、多 lane 等方法均通过 `unavailable()` 返回 `HarnessNotImplemented`（第 355-503 行）；
- 当前唯一已实装的是配置读取/替换与 `close()` 之类的表面状态。

所以 V2 文档应作为“Pi 正在明确设计的 durable harness 模型”阅读，不能据此称当前 Pi CLI 已经提供了 durable multi-lane execution。

## 9. 可供后续开发核对的源码要点

以下是本次源码已经存在、可以在今后比对实现时引用的机制，而非额外产品方案：

| 需要核对的能力 | Pi 中的对应事实 | 关键位置 |
| --- | --- | --- |
| 单个对话执行不重入 | 一个 active run；中途输入分为 steering/follow-up | `agent.ts` 第 282-388、486-535 行 |
| 前端实时看到执行 | assistant/tool 都有 start/update/end 事件 | `agent-loop.ts` 第 192-224、400-553 行 |
| 工具失败不让控制流失踪 | 参数校验/前后 hook/错误 tool-result 回写模型 | `agent-loop.ts` 第 600-758 行 |
| 同 turn 可并行工具但记录可复现 | `Promise.all` 执行，工具结果按源顺序回写 | `agent-loop.ts` 第 489-553 行 |
| 长文本不会无限塞回模型 | 上下文压缩为持久化 summary；overflow 只重试一次 | `agent-session.ts` 第 1951-2188 行 |
| 本地工具可被替换 | bash `operations.exec` 可替换为 SSH 等执行器 | `bash.ts` 第 57-79、191-202 行 |
| 计划与子智能体可扩展 | plan-mode/subagent 示例用 extension 做，不在内核 | `examples/extensions/` |
| 权限必须由宿主提供 | Pi 默认继承进程权限，隔离由 Docker/VM/sandbox 提供 | 根 README 第 38-46 行 |

## 10. 后续阅读入口

按阅读顺序建议直接从源码验证，而不是从二手描述判断：

1. [agent-loop.ts](../../temple/pi/packages/agent/src/agent-loop.ts)：loop 与工具批次。
2. [agent.ts](../../temple/pi/packages/agent/src/agent.ts)：生命周期、可中途插话和事件订阅。
3. [bash.ts](../../temple/pi/packages/coding-agent/src/core/tools/bash.ts)：本机 shell、取消、超时、流式输出和可替换执行器。
4. [session-manager.ts](../../temple/pi/packages/coding-agent/src/core/session-manager.ts)：JSONL、树和分支。
5. [agent-session.ts](../../temple/pi/packages/coding-agent/src/core/agent-session.ts)：CLI 如何把 loop、持久化、扩展和压缩接起来。
6. [plan-mode 示例](../../temple/pi/packages/coding-agent/examples/extensions/plan-mode/index.ts) 与 [subagent 示例](../../temple/pi/packages/coding-agent/examples/extensions/subagent/README.md)：计划/执行和多智能体如何作为 extension 构成。
7. [Harness V2 文档](../../temple/pi/packages/agent/docs/harness-v2.md) 与 [当前占位实现](../../temple/pi/packages/agent/src/harness/agent-harness.ts)：区分未来模型与今天可调用的 API。

## 11. 本次研究的结论

Pi 的可复用价值不在于“它已经替任何业务系统解决了远程资料、审批、工作流或交付”，而在于它已经把一条可靠的交互式 agent 反馈循环拆清楚：有明确生命周期、工具参数校验、流式工具进度、取消、队列语义、会话持久化、上下文压缩和扩展点。

同时，Pi 源码也清楚划出边界：本机 shell 继承宿主权限；计划模式/多智能体是扩展示例；Harness V2 仍在设计和占位实现阶段。后续引用 Pi 时应同时保留这两部分事实，避免把“源码中已有模式”“示例扩展”“未来设计”混成同一层能力。
