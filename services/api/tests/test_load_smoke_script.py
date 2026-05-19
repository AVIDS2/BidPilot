import importlib.util
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "load_smoke.py"
_SPEC = importlib.util.spec_from_file_location("load_smoke", _SCRIPT_PATH)
assert _SPEC is not None
load_smoke = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(load_smoke)


def test_summarize_results_computes_error_rate_and_p95_latency() -> None:
    samples = [
        load_smoke.Sample(endpoint="/health", status_code=200, elapsed_ms=10.0, error=None),
        load_smoke.Sample(endpoint="/health", status_code=200, elapsed_ms=20.0, error=None),
        load_smoke.Sample(endpoint="/openapi.json", status_code=500, elapsed_ms=30.0, error=None),
        load_smoke.Sample(endpoint="/openapi.json", status_code=None, elapsed_ms=40.0, error="timeout"),
    ]

    summary = load_smoke.summarize_results(samples)

    assert summary.total == 4
    assert summary.failures == 2
    assert summary.error_rate == 0.5
    assert summary.p95_ms == 40.0


def test_check_thresholds_reports_error_rate_and_latency_failures() -> None:
    summary = load_smoke.LoadSummary(total=10, failures=2, error_rate=0.2, avg_ms=50.0, p95_ms=250.0)

    failures = load_smoke.check_thresholds(summary, max_error_rate=0.1, max_p95_ms=200.0)

    assert failures == [
        "error_rate 20.00% exceeded threshold 10.00%",
        "p95_ms 250.00 exceeded threshold 200.00",
    ]
