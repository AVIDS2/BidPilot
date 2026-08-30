from pathlib import Path

from app.runtime.pi_adapter import _pi_resources, _pi_sandbox


def test_pi_resources_only_expose_server_owned_extensions_and_skill_metadata() -> None:
    resources = _pi_resources()

    assert resources["extensions"] == ["bidpilot-governance", "bidpilot-skills", "bidpilot-subagents"]
    assert resources["skills"]
    assert all({"name", "description"} <= set(skill) for skill in resources["skills"])
    assert all(set(skill) <= {"name", "description", "version", "resources"} for skill in resources["skills"])
    assert all(isinstance(skill["resources"], list) for skill in resources["skills"])
    assert all("content" not in skill and "path" not in skill for skill in resources["skills"])


def test_pi_cloud_sandbox_never_maps_full_access_to_host_tools() -> None:
    sandbox = _pi_sandbox()

    assert sandbox == {
        "profile": "governed_cloud",
        "hostTools": "disabled",
        "network": "bridge_only",
        "maxToolInputBytes": 128 * 1024,
        "maxToolObservationBytes": 512 * 1024,
    }


def test_pi_production_path_has_no_lexical_router_or_retired_loop_dependency() -> None:
    app_root = Path(__file__).resolve().parents[2] / "app"
    runtime_root = app_root / "runtime"
    production_sources = [
        app_root / "assistant" / "router.py",
        runtime_root / "pi_adapter.py",
        runtime_root / "pi_bridge.py",
        runtime_root / "pi_config.py",
    ]
    forbidden = (
        "harness_loop import",
        "_is_confirmation_followup",
        "_is_cancellation_followup",
        "keyword_router",
        "intent_keywords",
        "_assistant_engine",
        "stream_runtime_assistant_response",
        "runtime.classify(payload.message",
    )

    for source_path in production_sources:
        source = source_path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"{source_path.name} contains retired routing marker {marker}"

    operator_source = (runtime_root / "operator_adapter.py").read_text(encoding="utf-8")
    public_turn_source = operator_source.split("async def _replay_existing_run", maxsplit=1)[0]
    for marker in forbidden:
        assert marker not in public_turn_source, f"operator public turn contains retired routing marker {marker}"
    assert 'engine="pi"' in public_turn_source
    # The public Pi path queues a durable run before returning SSE. The old
    # synchronous stream helper is intentionally absent from this boundary.
    assert "enqueue_assistant_run(" in public_turn_source


def test_skill_catalog_descriptions_are_semantic_scopes_not_phrase_triggers() -> None:
    resources = _pi_resources()
    descriptions = "\n".join(str(skill["description"]) for skill in resources["skills"])

    assert "关键词时触发" not in descriptions
    assert "提到投标" not in descriptions
    writer = next(skill for skill in resources["skills"] if skill["name"] == "bid-tender-writer")
    assert "Do not use for opportunity discovery" in writer["description"]


def test_agent_runtime_has_no_lexical_user_intent_routes() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    roots = (
        repo_root / "services" / "api" / "app" / "assistant",
        repo_root / "services" / "api" / "app" / "runtime",
        repo_root / "services" / "pi-agent" / "src",
    )
    forbidden = (
        "intent_keywords",
        "route_keywords",
        "trigger_phrases",
        "confirmation_phrases",
        "cancellation_phrases",
        "_is_confirmation_followup",
        "_is_cancellation_followup",
        "_is_delegate_followup",
        "关键词时触发",
    )
    production_files = [
        path
        for root in roots
        for path in root.rglob("*")
        if path.suffix in {".py", ".ts", ".tsx"} and ".test." not in path.name
    ]

    for path in production_files:
        source = path.read_text(encoding="utf-8").casefold()
        for marker in forbidden:
            assert marker.casefold() not in source, f"{marker!r} reintroduced in {path}"
