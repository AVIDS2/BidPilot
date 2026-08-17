"""Named, deterministic acceptance targets for the Pi-style harness."""

from __future__ import annotations

from dataclasses import dataclass

from .harness_metrics import HarnessDimension


@dataclass(frozen=True)
class HarnessEvaluationTarget:
    id: str
    dimension: HarnessDimension
    detail: str
    pytest_targets: tuple[str, ...]
    p0: bool = False


HARNESS_EVALUATION_TARGETS: tuple[HarnessEvaluationTarget, ...] = (
    HarnessEvaluationTarget(
        id="contract-preflight-before-side-effect",
        dimension="contracts",
        p0=True,
        detail="受治理工具在持久化预检后才允许副作用，并保持开始事件顺序。",
        pytest_targets=("tests/runtime/test_harness_core.py::test_preflight_runs_before_the_started_event_and_side_effect",),
    ),
    HarnessEvaluationTarget(
        id="contract-policy-block-before-routing",
        dimension="contracts",
        p0=True,
        detail="PreToolUse 策略在 MCP 和业务能力路由前阻止工具。",
        pytest_targets=("tests/runtime/test_bidpilot_harness_adapter.py::test_preflight_guard_blocks_before_mcp_or_capability_routing",),
    ),
    HarnessEvaluationTarget(
        id="contract-action-event-lifecycle",
        dimension="contracts",
        p0=True,
        detail="真实 PostgreSQL RuntimeAction 在执行前后具有可重放事件。",
        pytest_targets=("tests/runtime/test_bidpilot_harness_adapter.py::test_real_database_action_is_visible_before_and_after_execution",),
    ),
    HarnessEvaluationTarget(
        id="contract-approval-terminal-sse",
        dimension="contracts",
        p0=True,
        detail="审批暂停明确结束 SSE，不会让客户端永久等待。",
        pytest_targets=("tests/runtime/test_harness_host.py::test_core_host_emits_confirmation_end_for_approval_pause",),
    ),
    HarnessEvaluationTarget(
        id="loop-multi-tool-order",
        dimension="loop_recovery",
        detail="跨工具读写调用按模型顺序执行，结果完整写回下一回合。",
        pytest_targets=("tests/runtime/test_harness_core.py::test_generic_multi_tool_turn_preserves_model_order_and_result_context",),
    ),
    HarnessEvaluationTarget(
        id="loop-recovery-after-invalid-tool",
        dimension="loop_recovery",
        detail="首次失败作为结构化工具结果可见，模型可改正路径而非中断。",
        pytest_targets=("tests/runtime/test_harness_core.py::test_failed_tool_becomes_model_visible_and_the_model_can_correct_it",),
    ),
    HarnessEvaluationTarget(
        id="loop-cancellation-boundary",
        dimension="loop_recovery",
        p0=True,
        detail="取消在模型和工具边界生效，后续模型调用不会发生。",
        pytest_targets=("tests/runtime/test_harness_core.py::test_cancellation_stops_before_the_next_model_turn",),
    ),
    HarnessEvaluationTarget(
        id="loop-nonrecoverable-artifact-failure",
        dimension="loop_recovery",
        p0=True,
        detail="远程附件失败保留公开错误并停止自动重试。",
        pytest_targets=("tests/runtime/test_harness_core.py::test_nonrecoverable_failure_preserves_its_public_message_for_the_host",),
    ),
    HarnessEvaluationTarget(
        id="loop-failure-budget",
        dimension="loop_recovery",
        detail="重复失败到预算即终止，避免模型无限试错。",
        pytest_targets=("tests/runtime/test_harness_core.py::test_failure_budget_terminates_repeated_failures",),
    ),
    HarnessEvaluationTarget(
        id="cross-domain-plain-conversation",
        dimension="cross_domain",
        detail="不调用工具的普通对话不虚构执行结果。",
        pytest_targets=("tests/runtime/test_harness_core.py::test_plain_conversation_completes_without_a_tool",),
    ),
    HarnessEvaluationTarget(
        id="cross-domain-no-keyword-tool-forcing",
        dimension="cross_domain",
        p0=True,
        detail="自然语言中的动作词不会触发服务端工具路由或 required-tool 重试。",
        pytest_targets=("tests/runtime/test_harness_host.py::test_core_host_never_forces_a_tool_call_from_message_keywords",),
    ),
    HarnessEvaluationTarget(
        id="cross-turn-terminal-action-context",
        dimension="loop_recovery",
        detail="上一轮终止动作以可信、无参数的上下文进入下一轮，模型无需重放失败调用。",
        pytest_targets=("tests/runtime/test_actions_and_approvals.py::test_previous_terminal_action_context_is_scoped_and_argument_free",),
    ),
    HarnessEvaluationTarget(
        id="project-limit-is-terminal",
        dimension="loop_recovery",
        p0=True,
        detail="项目额度耗尽只报告一次明确终止错误，不伪装成参数错误或重复调用。",
        pytest_targets=("tests/runtime/test_harness_loop.py::test_streaming_harness_stops_after_one_project_limit_failure",),
    ),
    HarnessEvaluationTarget(
        id="cross-domain-steering",
        dimension="cross_domain",
        detail="用户转向输入在工具边界优先，不继续执行被放弃的后续调用。",
        pytest_targets=("tests/runtime/test_harness_core.py::test_steering_input_preempts_following_calls_at_a_tool_boundary",),
    ),
    HarnessEvaluationTarget(
        id="cross-domain-followup",
        dimension="cross_domain",
        detail="后续输入在回合边界进入同一循环，且不重放工具。",
        pytest_targets=("tests/runtime/test_harness_core.py::test_followup_input_runs_on_a_turn_boundary_without_replaying_tools",),
    ),
    HarnessEvaluationTarget(
        id="cross-domain-local-artifact",
        dimension="cross_domain",
        detail="用户本机 companion 仅流式下载确认文件，产生校验回执并拒绝网页。",
        pytest_targets=("tests/runtime/test_local_companion.py",),
    ),
    HarnessEvaluationTarget(
        id="bidpilot-host-tool-cycle",
        dimension="bidpilot",
        detail="生产 Host 真实走 core 的模型-工具-模型顺序和计划投影。",
        pytest_targets=("tests/runtime/test_harness_host.py::test_core_host_projects_a_governed_tool_turn_in_core_order",),
    ),
    HarnessEvaluationTarget(
        id="bidpilot-remote-import-no-guessing",
        dimension="bidpilot",
        p0=True,
        detail="确认后的远程导入失败不改写 URL、不自动重试。",
        pytest_targets=("tests/runtime/test_bidpilot_harness_adapter.py::test_remote_import_failure_is_not_automatically_retried",),
    ),
    HarnessEvaluationTarget(
        id="bidpilot-mcp-observable",
        dimension="bidpilot",
        detail="只读 MCP 感知工具也按统一成功/失败事件合同运行。",
        pytest_targets=("tests/runtime/test_bidpilot_harness_adapter.py::test_mcp_sensing_tool_uses_the_same_durable_tool_contract",),
    ),
    HarnessEvaluationTarget(
        id="bidpilot-missing-input",
        dimension="bidpilot",
        detail="业务缺参进入持久化 needs_input，不创建副作用动作。",
        pytest_targets=("tests/runtime/test_bidpilot_harness_adapter.py::test_missing_input_pauses_before_a_mutating_action",),
    ),
    HarnessEvaluationTarget(
        id="langgraph-safe-read-trajectory",
        dimension="langgraph",
        detail="LangGraph 安全只读路径的节点和 RuntimeEvent 轨迹稳定。",
        pytest_targets=("tests/runtime/test_operator_adapters.py::test_operator_graph_uses_runtime_boundary_for_safe_read",),
    ),
    HarnessEvaluationTarget(
        id="langgraph-approval-resume-once",
        dimension="langgraph",
        p0=True,
        detail="LangGraph 中断后批准只执行一次变更并完成可重放事件链。",
        pytest_targets=("tests/runtime/test_operator_adapters.py::test_operator_graph_interrupt_resume_executes_one_approved_mutation",),
    ),
)


__all__ = ["HARNESS_EVALUATION_TARGETS", "HarnessEvaluationTarget"]
