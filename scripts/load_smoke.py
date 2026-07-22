from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class Sample(NamedTuple):
    endpoint: str
    status_code: int | None
    elapsed_ms: float
    error: str | None


class LoadSummary(NamedTuple):
    total: int
    failures: int
    error_rate: float
    avg_ms: float
    p95_ms: float


def request_once(base_url: str, endpoint: str, timeout: float) -> Sample:
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    started_at = time.perf_counter()
    try:
        request = Request(url, method="GET")
        with urlopen(request, timeout=timeout) as response:
            response.read()
            status_code = response.status
            error = None
    except HTTPError as exc:
        status_code = exc.code
        error = None
    except URLError:
        status_code = None
        error = "network_error"
    except TimeoutError:
        status_code = None
        error = "timeout"
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    return Sample(endpoint=endpoint, status_code=status_code, elapsed_ms=elapsed_ms, error=error)


def summarize_results(samples: list[Sample]) -> LoadSummary:
    total = len(samples)
    if total == 0:
        return LoadSummary(total=0, failures=0, error_rate=0.0, avg_ms=0.0, p95_ms=0.0)

    failures = sum(1 for sample in samples if sample.error is not None or sample.status_code is None or not 200 <= sample.status_code < 300)
    latencies = sorted(sample.elapsed_ms for sample in samples)
    p95_index = max(0, math.ceil(total * 0.95) - 1)
    return LoadSummary(
        total=total,
        failures=failures,
        error_rate=failures / total,
        avg_ms=sum(latencies) / total,
        p95_ms=latencies[p95_index],
    )


def check_thresholds(summary: LoadSummary, max_error_rate: float, max_p95_ms: float) -> list[str]:
    failures = []
    if summary.error_rate > max_error_rate:
        failures.append(f"error_rate {summary.error_rate:.2%} exceeded threshold {max_error_rate:.2%}")
    if summary.p95_ms > max_p95_ms:
        failures.append(f"p95_ms {summary.p95_ms:.2f} exceeded threshold {max_p95_ms:.2f}")
    return failures


def normalize_base_url(base_url: str, *, require_https: bool) -> str:
    """Validate a smoke target without allowing credentials into evidence output."""
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--base-url must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("--base-url must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("--base-url must not contain a query string or fragment")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("--base-url must contain a valid port") from exc
    if require_https and parsed.scheme != "https":
        raise ValueError("--require-https requires an https:// base URL")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def normalize_endpoint(endpoint: str) -> str:
    """Accept only a path so release artifacts cannot retain URL credentials."""
    parsed = urlsplit(endpoint)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        raise ValueError("--endpoint must be an absolute path")
    if parsed.query or parsed.fragment:
        raise ValueError("--endpoint must not contain a query string or fragment")
    return parsed.path


def run_load_smoke(base_url: str, endpoints: list[str], requests_per_endpoint: int, concurrency: int, timeout: float) -> tuple[list[Sample], LoadSummary]:
    work = [(base_url, endpoint, timeout) for endpoint in endpoints for _ in range(requests_per_endpoint)]
    samples = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(request_once, *item) for item in work]
        for future in as_completed(futures):
            samples.append(future.result())
    return samples, summarize_results(samples)


def build_evidence_artifact(
    *,
    base_url: str,
    endpoints: list[str],
    requests_per_endpoint: int,
    concurrency: int,
    timeout: float,
    max_error_rate: float,
    max_p95_ms: float,
    samples: list[Sample],
    summary: LoadSummary,
    failures: list[str],
) -> dict[str, object]:
    """Return a redacted, portable record suitable for a release attachment."""
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "endpoints": endpoints,
        "requests_per_endpoint": requests_per_endpoint,
        "concurrency": concurrency,
        "timeout_seconds": timeout,
        "thresholds": {
            "max_error_rate": max_error_rate,
            "max_p95_ms": max_p95_ms,
        },
        "summary": summary._asdict(),
        "samples": [sample._asdict() for sample in samples],
        "failures": failures,
        "passed": not failures,
    }


def write_evidence_artifact(artifact: dict[str, object], output_file: Path) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a lightweight DocPilot API load smoke check.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--endpoint", action="append", dest="endpoints", default=None)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--max-p95-ms", type=float, default=1000.0)
    parser.add_argument("--require-https", action="store_true", help="reject a non-HTTPS smoke target")
    parser.add_argument("--output-file", type=Path, help="write a redacted JSON release-evidence artifact")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        base_url = normalize_base_url(args.base_url, require_https=args.require_https)
        endpoints = [normalize_endpoint(endpoint) for endpoint in args.endpoints or ["/health", "/openapi.json"]]
    except ValueError as exc:
        print(f"invalid smoke target: {exc}")
        return 2
    samples, summary = run_load_smoke(
        base_url=base_url,
        endpoints=endpoints,
        requests_per_endpoint=args.requests,
        concurrency=args.concurrency,
        timeout=args.timeout,
    )

    print(f"total={summary.total} failures={summary.failures} error_rate={summary.error_rate:.2%} avg_ms={summary.avg_ms:.2f} p95_ms={summary.p95_ms:.2f}")
    for endpoint in endpoints:
        endpoint_samples = [sample for sample in samples if sample.endpoint == endpoint]
        endpoint_summary = summarize_results(endpoint_samples)
        print(f"endpoint={endpoint} total={endpoint_summary.total} failures={endpoint_summary.failures} avg_ms={endpoint_summary.avg_ms:.2f} p95_ms={endpoint_summary.p95_ms:.2f}")

    failures = check_thresholds(summary, max_error_rate=args.max_error_rate, max_p95_ms=args.max_p95_ms)
    for failure in failures:
        print(failure)
    if args.output_file is not None:
        artifact_path = write_evidence_artifact(
            build_evidence_artifact(
                base_url=base_url,
                endpoints=endpoints,
                requests_per_endpoint=args.requests,
                concurrency=args.concurrency,
                timeout=args.timeout,
                max_error_rate=args.max_error_rate,
                max_p95_ms=args.max_p95_ms,
                samples=samples,
                summary=summary,
                failures=failures,
            ),
            args.output_file,
        )
        print(f"evidence_artifact={artifact_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
