import importlib.util
import json
from pathlib import Path

import pytest


_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "load_smoke.py"
_SPEC = importlib.util.spec_from_file_location("load_smoke", _SCRIPT_PATH)
assert _SPEC is not None
load_smoke = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(load_smoke)


def test_normalize_base_url_requires_safe_absolute_http_target() -> None:
    assert (
        load_smoke.normalize_base_url("https://api.example.com/", require_https=True)
        == "https://api.example.com"
    )

    with pytest.raises(ValueError, match="credentials"):
        load_smoke.normalize_base_url("https://user:password@api.example.com", require_https=True)
    with pytest.raises(ValueError, match="https"):
        load_smoke.normalize_base_url("http://api.example.com", require_https=True)
    with pytest.raises(ValueError, match="absolute"):
        load_smoke.normalize_base_url("/health", require_https=False)

    assert load_smoke.normalize_endpoint("/health") == "/health"
    with pytest.raises(ValueError, match="query"):
        load_smoke.normalize_endpoint("/health?token=secret")
    with pytest.raises(ValueError, match="absolute"):
        load_smoke.normalize_endpoint("https://api.example.com/health")


def test_evidence_artifact_is_redacted_and_retains_threshold_result(tmp_path: Path) -> None:
    samples = [
        load_smoke.Sample(endpoint="/health", status_code=200, elapsed_ms=12.5, error=None),
        load_smoke.Sample(endpoint="/openapi.json", status_code=503, elapsed_ms=20.0, error=None),
    ]
    summary = load_smoke.summarize_results(samples)
    failures = load_smoke.check_thresholds(summary, max_error_rate=0.0, max_p95_ms=1000.0)
    artifact = load_smoke.build_evidence_artifact(
        base_url="https://api.example.com",
        endpoints=["/health", "/openapi.json"],
        requests_per_endpoint=1,
        concurrency=1,
        timeout=5.0,
        max_error_rate=0.0,
        max_p95_ms=1000.0,
        samples=samples,
        summary=summary,
        failures=failures,
    )
    output_file = load_smoke.write_evidence_artifact(artifact, tmp_path / "evidence" / "load-smoke.json")

    saved = json.loads(output_file.read_text(encoding="utf-8"))
    assert saved["passed"] is False
    assert saved["summary"]["failures"] == 1
    assert saved["base_url"] == "https://api.example.com"
    assert "password" not in output_file.read_text(encoding="utf-8")


def test_load_smoke_identifies_itself_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, str] = {}

    class Response:
        status = 200

        def read(self) -> bytes:
            return b"ok"

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_urlopen(request: object, timeout: float) -> Response:
        observed["user_agent"] = request.get_header("User-agent")  # type: ignore[union-attr]
        observed["timeout"] = str(timeout)
        return Response()

    monkeypatch.setattr(load_smoke, "urlopen", fake_urlopen)

    sample = load_smoke.request_once("https://api.example.com", "/health", 3.0)

    assert sample.status_code == 200
    assert observed == {"user_agent": load_smoke.SMOKE_USER_AGENT, "timeout": "3.0"}
