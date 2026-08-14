"""Run the deterministic Pi-style harness acceptance suite and write a score."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
REPOSITORY_ROOT = PROJECT_ROOT.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.evaluation.harness_metrics import HarnessEvaluationCase, score_harness_cases, write_harness_report  # noqa: E402
from app.evaluation.harness_suite import HARNESS_EVALUATION_TARGETS  # noqa: E402
from scripts.test_database_safety import UnsafeTestDatabaseError, build_test_environment  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Pi-style harness engineering evaluation")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/evaluations/pi-harness-v1"))
    parser.add_argument(
        "--test-database-url",
        help="Dedicated PostgreSQL test database URL. Overrides DOCPILOT_TEST_DATABASE_URL for this run.",
    )
    args = parser.parse_args()
    test_environment = os.environ.copy()
    if args.test_database_url:
        test_environment["DOCPILOT_TEST_DATABASE_URL"] = args.test_database_url
    try:
        test_environment = build_test_environment(test_environment)
    except UnsafeTestDatabaseError as exc:
        parser.error(str(exc))

    output_dir = args.output_dir.resolve()
    logs_dir = output_dir / "cases"
    logs_dir.mkdir(parents=True, exist_ok=True)
    cases: list[HarnessEvaluationCase] = []

    for target in HARNESS_EVALUATION_TARGETS:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *target.pytest_targets],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            env=test_environment,
            check=False,
        )
        (logs_dir / f"{target.id}.txt").write_text(
            f"$ {' '.join(completed.args)}\n\n{completed.stdout}\n{completed.stderr}",
            encoding="utf-8",
        )
        cases.append(
            HarnessEvaluationCase(
                id=target.id,
                dimension=target.dimension,
                passed=completed.returncode == 0,
                p0=target.p0,
                detail=target.detail,
            )
        )

    report = score_harness_cases(
        cases,
        caveats=(
            "本报告评价确定性运行时合同和本地集成，不评价未固定模型的主观回答质量。",
            "真实浏览器金链路、真实外部站点和用户本机 companion 需要在目标环境单独运行。",
            "每个案例的 pytest 输出位于 cases/，失败结果不得用总分掩盖。",
        ),
    )
    json_path, markdown_path = write_harness_report(report, output_dir)
    print(f"engineering_score={report.engineering_score:.1f}/100")
    print(f"passed={report.passed} cases={report.passed_case_count}/{report.total_case_count}")
    print(f"report={markdown_path}")
    print(f"json={json_path}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
