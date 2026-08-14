# Pi 式 Harness Agent 实施计划

> 对应规格：[Pi 式 Harness Agent 规格](../architecture/2026-08-10-pi-style-harness-agent-spec.md)

## 阶段 0：基线与约束

- [x] 阅读现有 Runtime、能力注册、审批、LangGraph 边界和 Pi 源码学习记录。
- [x] 研究并筛选公开评估工具：AgentEvals、eval-view、ASSERT、AgentBench、Comet。
- [x] 固化本轮前的现有 Runtime 测试基线，记录失败而非掩盖。

**验收**：明确不会把 Pi 的本地 shell 直接暴露给多租户 API；业务事实仍在 PostgreSQL。

## 阶段 1：通用内核

- [x] 新增 `runtime/harness_core.py`：协议模型、模型步骤、工具结果、终态、取消、步数与连续失败预算。
- [x] 新增可替换 `ModelPort`、`ToolExecutor`、事件观察器和确定性 fake harness test kit。
- [x] 覆盖：无工具、单工具、多步、未知工具、参数无效、异常后自修复、暂停、取消、超限、结果顺序。

**验收**：内核源码不出现 BidPilot capability 名、project 字段或中文业务文案。

## 阶段 2：BidPilot Host 适配

- [x] 抽出 `BidPilotToolAdapter`，把 CAPABILITY_REGISTRY 和现有 prepare/execute/approval 转为通用 `ToolOutcome`。
- [x] 普通对话由 `CoreStreamingHarness` 驱动；旧 `StreamingHarness` 暂保留为审批恢复与兼容外壳。
- [x] 保持现有动作幂等、审批、附件与 workflow bridge 行为；移除循环控制所需的业务提示词规则。

**验收**：同一已有 assistant 请求回归通过；失败能以稳定 error code 回传下一模型回合。

## 阶段 3：计划、恢复与本地执行协议

- [ ] 产品 Host 接入可审阅的 `PlanPolicy` 和计划事件，不影响普通交互。内核协议已存在；当前产品事件主要是回合状态，不能称完整计划模式。
- [ ] 将 core steering/follow-up 队列接到 Web active run；resume cursor 的内核测试存在，但产品端未提供 Pi 同等的会话恢复语义。
- [x] 定义 Local Companion 执行协议、授权和 artifact 回传合同；不实现服务端任意 shell。

**验收**：审批、断线、取消和再次进入均不重复副作用；计划并不成为第二套业务真相。

## 阶段 4：评估和产品验收

- [x] 编写跨领域的评估集与规范化轨迹输出。
- [x] 实现 AgentEvals 对齐的 strict/unordered/subset trajectory matcher，生成 JSON 报告与快照。
- [ ] 增加 LangGraph workflow 图轨迹断言，并跑完整招标交付金链路与浏览器验收。已有局部覆盖，尚未形成最终全链路 gate。
- [ ] 运行完整测试、记录每类得分、P0 gate 与未覆盖风险。当前全量 API 已定位四项回归，修复后需重新全量执行。

**验收**：报告可由无模型密钥的确定性测试重跑；可选 LLM judge 只在明确配置时运行。

## 执行顺序

严格按阶段 1 -> 2 -> 3 -> 4。任一阶段的 P0 不通过时，先修复，不进入下一阶段。每阶段提交的变更均运行其直接单测，最终再运行 API、Worker、前端构建和浏览器金链路。

## 阶段性记录（2026-08-10）

- 确定性评估执行 19 个具名案例，覆盖通用轨迹合同、错误纠正/暂停/取消、跨领域工具、BidPilot 动作生命周期和 LangGraph 图轨迹；该集合的 P0 gate 通过，但不等于产品级 Plan-and-Execute 完成。
- API 金链路烟测已经改为显式传递 `section_id`。同名章节只传 `section_key` 被拒绝是有意的歧义保护，不再将它误判为起草失败。
- 本地 companion 是用户本机显式执行的受限 HTTP(S) 文件下载器。它不向服务端暴露 shell，也不会让网页静默控制用户设备；下载后的导入仍经既有上传和资料解析入口。
- 真实状态见：[ReAct Harness、提示词与计划执行真实状态](../architecture/2026-08-10-react-harness-prompt-status.md)。
