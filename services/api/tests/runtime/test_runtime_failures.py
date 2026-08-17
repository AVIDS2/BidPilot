from app.runtime.bidpilot_harness_adapter import BidPilotToolExecutor
from app.runtime.failures import classify_capability_failure


def test_project_plan_limit_has_a_specific_non_retryable_failure() -> None:
    failure = classify_capability_failure(
        ValueError("starter plan limit of 3 projects would be exceeded. Upgrade to create more.")
    )

    assert failure.error_code == "project_limit_exceeded"
    assert "项目数量上限" in failure.message
    assert BidPilotToolExecutor._is_auto_retry_safe("create_project", failure.error_code) is False
