from __future__ import annotations

from typing import Any

from app.memory import mem0_provider


class FakeMem0Client:
    def __init__(self) -> None:
        self.add_calls: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []

    def add(self, messages, options=None, **kwargs):  # noqa: ANN001
        self.add_calls.append({"messages": messages, "options": options, **kwargs})
        return {"status": "PENDING", "event_id": "mem0-event-1"}

    def search(self, query, options=None, **kwargs):  # noqa: ANN001
        self.search_calls.append({"query": query, "options": options, **kwargs})
        return {
            "results": [
                {
                    "id": "memory-1",
                    "memory": "用户偏好中文、先给结论。",
                    "score": 0.91,
                    "categories": ["preferences"],
                }
            ]
        }

    def delete_all(self, **kwargs):  # noqa: ANN001
        self.delete_calls.append(kwargs)
        return {"message": "deleted"}


def test_mem0_profile_provider_uses_official_scoped_operations(monkeypatch) -> None:
    fake = FakeMem0Client()
    monkeypatch.setenv("DOCPILOT_MEM0_ENABLED", "true")
    monkeypatch.setenv("DOCPILOT_MEM0_API_KEY", "test-key")
    monkeypatch.setenv("DOCPILOT_MEM0_AGENT_ID", "bidpilot-assistant")
    monkeypatch.setattr(mem0_provider, "_client", lambda *_args: fake)

    queued = mem0_provider.capture_profile_memory(
        user_id="user-1",
        org_id="org-1",
        run_id="run-1",
        messages=[
            {"role": "user", "content": "请以后用中文并先给结论。"},
            {"role": "assistant", "content": "好的。"},
        ],
    )
    assert queued == {"status": "queued", "event_id": "mem0-event-1"}
    assert fake.add_calls[0]["user_id"] == "user-1"
    assert fake.add_calls[0]["agent_id"] == "bidpilot-assistant:user-1"
    assert fake.add_calls[0]["app_id"] == "org-1"
    assert fake.add_calls[0]["run_id"] == "run-1"
    assert fake.add_calls[0]["options"].custom_instructions

    memories = mem0_provider.search_profile_memory(
        user_id="user-1",
        org_id="org-1",
        query="应该用什么语言回答？",
    )
    assert memories[0].text == "用户偏好中文、先给结论。"
    filters = fake.search_calls[0]["options"].filters
    assert {"user_id": "user-1"} in filters["OR"]
    assert {"agent_id": "bidpilot-assistant:user-1"} in filters["OR"]
    assert filters["AND"] == [{"app_id": "org-1"}]

    deleted = mem0_provider.delete_profile_memory(user_id="user-1", org_id="org-1")
    assert deleted["status"] == "deleted"
    assert fake.delete_calls == [
        {"user_id": "user-1", "app_id": "org-1"},
        {"agent_id": "bidpilot-assistant:user-1", "app_id": "org-1"},
    ]


def test_mem0_profile_provider_fails_open_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("DOCPILOT_MEM0_ENABLED", "false")
    monkeypatch.delenv("DOCPILOT_MEM0_API_KEY", raising=False)
    assert mem0_provider.search_profile_memory(user_id="u", org_id="o", query="x") == []
    assert mem0_provider.capture_profile_memory(user_id="u", org_id="o", run_id="r", messages=[{"role": "user", "content": "x"}]) == {"status": "disabled"}


def test_mem0_profile_provider_omits_platform_app_scope_for_oss_hosts(monkeypatch) -> None:
    fake = FakeMem0Client()
    monkeypatch.setenv("DOCPILOT_MEM0_ENABLED", "true")
    monkeypatch.setenv("DOCPILOT_MEM0_API_KEY", "test-key")
    monkeypatch.setenv("DOCPILOT_MEM0_APP_SCOPE", "false")
    monkeypatch.setattr(mem0_provider, "_client", lambda *_args: fake)

    result = mem0_provider.capture_profile_memory(
        user_id="user-1",
        org_id="org-1",
        run_id="run-1",
        messages=[{"role": "user", "content": "请用中文回答。"}],
    )

    assert result["status"] == "queued"
    assert fake.add_calls[0]["user_id"] == "user-1"
    assert "app_id" not in fake.add_calls[0]
