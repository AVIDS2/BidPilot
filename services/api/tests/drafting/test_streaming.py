"""Public drafting stream contract tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.drafting.streaming import _map_runtime_event


def _event(event_type: str, payload: dict, public_summary: str = "工作流步骤未能完成。"):
    return SimpleNamespace(
        event_type=event_type,
        payload_json=payload,
        public_summary=public_summary,
        created_at=None,
    )


def test_drafting_stream_exposes_safe_provider_retry_metadata() -> None:
    mapped = _map_runtime_event(
        _event(
            "capability.progressed",
            {
                "capability": "section_drafter",
                "node": "section_drafter",
                "phase": "provider_retry",
                "error_code": "provider_rate_limited",
                "next_attempt": 2,
                "max_attempts": 3,
            },
        ),
        SimpleNamespace(status="running", result_json={}),
    )

    assert mapped[0]["event"] == "provider_retry"
    payload = json.loads(mapped[0]["data"])
    assert payload["node_name"] == "section_drafter"
    assert payload["error_code"] == "provider_rate_limited"
    assert payload["attempt"] == 2
    assert payload["max_attempts"] == 3
    assert isinstance(payload["timestamp"], str)


def test_drafting_stream_exposes_error_code_without_internal_message() -> None:
    mapped = _map_runtime_event(
        _event(
            "capability.failed",
            {
                "capability": "section_drafter",
                "node": "section_drafter",
                "error_code": "provider_auth_failed",
            },
        ),
        SimpleNamespace(status="failed", result_json={}),
    )

    assert mapped[0]["event"] == "graph_error"
    payload = json.loads(mapped[0]["data"])
    assert payload["error_message"] == "工作流步骤未能完成。"
    assert payload["error_code"] == "provider_auth_failed"
    assert payload["node_name"] == "section_drafter"
