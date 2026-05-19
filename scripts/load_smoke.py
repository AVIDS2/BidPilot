from __future__ import annotations

import argparse
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import NamedTuple
from urllib.error import HTTPError, URLError
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
    except URLError as exc:
        status_code = None
        error = str(exc.reason)
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


def run_load_smoke(base_url: str, endpoints: list[str], requests_per_endpoint: int, concurrency: int, timeout: float) -> tuple[list[Sample], LoadSummary]:
    work = [(base_url, endpoint, timeout) for endpoint in endpoints for _ in range(requests_per_endpoint)]
    samples = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(request_once, *item) for item in work]
        for future in as_completed(futures):
            samples.append(future.result())
    return samples, summarize_results(samples)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a lightweight DocPilot API load smoke check.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--endpoint", action="append", dest="endpoints", default=None)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--max-p95-ms", type=float, default=1000.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoints = args.endpoints or ["/health", "/openapi.json"]
    samples, summary = run_load_smoke(
        base_url=args.base_url,
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
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
