"""Run the local P0-D6 BidPilot Golden Path against real API and Worker services.

The script is deliberately limited to local services and the checked-in
synthetic bid pack. It creates an isolated organization and leaves its project
in place for inspection after the run. No provider credential, JWT, response
body, or document content is written to stdout or the evidence artifact.

Example:
    $env:DOCPILOT_DATABASE_URL = "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot"
    uv run --directory services/api --locked --no-sync python ../../scripts/run_bidpilot_golden_path.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import secrets
import sys
import time
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse
from uuid import uuid4

import httpx


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPOSITORY_ROOT / "services" / "api"
SAMPLE_PACK = REPOSITORY_ROOT / "sample-data" / "bidpilot-demo"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
TERMINAL_FAILURES = {"failed", "cancelled", "error"}

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


class GoldenPathError(RuntimeError):
    """Raised when a governed Golden Path checkpoint is not reached."""


T = TypeVar("T")


@dataclass
class GoldenPathEvidence:
    run_label: str
    started_at: str
    steps: list[str] = field(default_factory=list)
    project_id: str | None = None
    bundle_id: str | None = None
    document_count: int = 0
    initial_execution_run_id: str | None = None
    retry_source_run_id: str | None = None
    retry_execution_run_id: str | None = None
    deliverable_id: str | None = None
    exported_docx_bytes: int | None = None
    completed_at: str | None = None
    passed: bool = False
    failure_type: str | None = None

    def mark(self, step: str) -> None:
        self.steps.append(step)
        print(step, flush=True)

    def artifact(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "kind": "bidpilot_p0_d6_golden_path",
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "passed": self.passed,
            "failure_type": self.failure_type,
            "run_label": self.run_label,
            "steps": self.steps,
            "project_id": self.project_id,
            "bundle_id": self.bundle_id,
            "document_count": self.document_count,
            "initial_execution_run_id": self.initial_execution_run_id,
            "retry_source_run_id": self.retry_source_run_id,
            "retry_execution_run_id": self.retry_execution_run_id,
            "deliverable_id": self.deliverable_id,
            "exported_docx_bytes": self.exported_docx_bytes,
            "material_origin": "synthetic_checked_in_pack",
            "fault_injection": "isolated_retry_source_only" if self.retry_source_run_id else None,
        }


class ApiClient:
    def __init__(self, base_url: str, token: str, timeout_seconds: float) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def json(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._request(method, path, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            raise GoldenPathError(f"{method} {path} returned invalid JSON") from exc

    def bytes(self, method: str, path: str, **kwargs: Any) -> bytes:
        return self._request(method, path, **kwargs).content

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self._client.request(method, path, **kwargs)
        if response.is_success:
            return response
        # Do not preserve potentially sensitive upstream/provider payloads in an
        # artifact. Status and route are sufficient to identify the failed boundary.
        raise GoldenPathError(f"{method} {path} returned HTTP {response.status_code}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local BidPilot P0-D6 Golden Path.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DOCPILOT_DATABASE_URL", ""),
        help="local app database URL used only to bootstrap an isolated verified actor and retry fixture",
    )
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("tmp") / "p0-d6-golden-path.json",
        help="redacted JSON evidence artifact, relative to the repository by default",
    )
    parser.add_argument(
        "--skip-retry",
        action="store_true",
        help="skip the isolated retry/recovery checkpoint while debugging an earlier step",
    )
    return parser.parse_args()


def _assert_local_target(base_url: str, database_url: str) -> None:
    parsed_api = urlparse(base_url)
    if parsed_api.scheme not in {"http", "https"} or parsed_api.hostname not in LOCAL_HOSTS:
        raise GoldenPathError("Golden Path only runs against a loopback API URL")

    parsed_database = urlparse(database_url)
    database_name = parsed_database.path.rsplit("/", 1)[-1]
    if parsed_database.hostname not in LOCAL_HOSTS or database_name != "docpilot":
        raise GoldenPathError(
            "Golden Path bootstrap requires the local app database named 'docpilot'; it refuses remote and test targets"
        )


def _output_path(path: Path) -> Path:
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _write_artifact(evidence: GoldenPathEvidence, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(evidence.artifact(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"evidence_artifact={output_file}", flush=True)


def _bootstrap_actor(database_url: str, run_label: str) -> tuple[str, str]:
    """Create an isolated verified local user through the real auth service.

    The API itself still handles login and token issuance. Direct persistence is
    limited to making the synthetic local account verified, avoiding SMTP and
    browser Turnstile dependencies in an integration fixture.
    """

    os.environ["DOCPILOT_DATABASE_URL"] = database_url

    from app.auth.schemas import UserRegister
    from app.auth.service import register_user_command
    from app.db import SessionLocal
    from app.models import User

    suffix = run_label.replace("p0d6-", "")
    email = f"p0d6-{suffix}@local.test"
    password = f"P0d6!{secrets.token_urlsafe(18)}A1"
    org_slug = f"p0d6-{suffix}"[:80]

    db = SessionLocal()
    try:
        actor = register_user_command(
            db,
            UserRegister(
                email=email,
                display_name="P0-D6 Golden Path",
                password=password,
                org_name=f"P0-D6 {suffix}",
                org_slug=org_slug,
            ),
        )
        user = db.get(User, actor.id)
        if user is None:
            raise GoldenPathError("Synthetic Golden Path user was not persisted")
        user.email_verified = True
        db.commit()
        return email, password
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _login(base_url: str, email: str, password: str, timeout_seconds: float) -> str:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds) as client:
        response = client.post("/auth/login", json={"email": email, "password": password})
    if not response.is_success:
        raise GoldenPathError(f"POST /auth/login returned HTTP {response.status_code}")
    try:
        token = response.json()["access_token"]
    except (KeyError, TypeError, ValueError) as exc:
        raise GoldenPathError("POST /auth/login did not return an access token") from exc
    if not isinstance(token, str) or not token:
        raise GoldenPathError("POST /auth/login returned an empty access token")
    return token


def _wait_until(
    *,
    description: str,
    timeout_seconds: float,
    probe: Callable[[], T],
    predicate: Callable[[T], bool],
    failure: Callable[[T], str | None] | None = None,
) -> T:
    deadline = time.monotonic() + timeout_seconds
    latest: T | None = None
    while time.monotonic() < deadline:
        latest = probe()
        if failure is not None:
            failure_reason = failure(latest)
            if failure_reason:
                raise GoldenPathError(f"{description}: {failure_reason}")
        if predicate(latest):
            return latest
        time.sleep(1.0)
    raise GoldenPathError(f"Timed out waiting for {description}")


def _wait_for_documents(client: ApiClient, bundle_id: str, expected_count: int, timeout_seconds: float) -> list[dict[str, Any]]:
    def probe() -> list[dict[str, Any]]:
        response = client.json("GET", "/documents", params={"bundle_id": bundle_id})
        return list(response.get("items") or [])

    def complete(documents: list[dict[str, Any]]) -> bool:
        return len(documents) == expected_count and all(
            item.get("parse_status") == "parsed" and item.get("index_status") == "indexed"
            for item in documents
        )

    def failure(documents: list[dict[str, Any]]) -> str | None:
        if any(
            item.get("parse_status") == "failed" or item.get("index_status") == "failed"
            for item in documents
        ):
            return "document parsing or indexing failed"
        return None

    return _wait_until(
        description="document parse and index",
        timeout_seconds=timeout_seconds,
        probe=probe,
        predicate=complete,
        failure=failure,
    )


def _get_run(client: ApiClient, run_id: str) -> dict[str, Any]:
    return dict(client.json("GET", f"/execution/runs/{run_id}"))


def _wait_for_run_status(
    client: ApiClient,
    run_id: str,
    expected: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    def failure(run: dict[str, Any]) -> str | None:
        status = str(run.get("status") or "")
        if status in TERMINAL_FAILURES:
            return f"execution entered {status}"
        return None

    return _wait_until(
        description=f"workflow run {run_id} -> {expected}",
        timeout_seconds=timeout_seconds,
        probe=lambda: _get_run(client, run_id),
        predicate=lambda run: run.get("status") == expected,
        failure=failure,
    )


def _select_deliverable_and_section(client: ApiClient, project_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    deliverables = list(client.json("GET", "/deliverables", params={"project_id": project_id}))
    if len(deliverables) != 1:
        raise GoldenPathError("Expected one default deliverable for the isolated project")
    deliverable = dict(deliverables[0])
    sections = list(client.json("GET", f"/deliverables/{deliverable['id']}/sections"))
    section = next((item for item in sections if item.get("section_key") == "technical-approach"), None)
    if not isinstance(section, dict):
        raise GoldenPathError("BidPilot default technical-approach section was not created")
    return deliverable, section


def _latest_candidate(client: ApiClient, section_id: str, run_id: str, previous_id: str | None = None) -> dict[str, Any]:
    versions = list(client.json("GET", "/versions", params={"section_id": section_id}))
    candidates = [
        item
        for item in versions
        if item.get("generation_run_id") == run_id and item.get("id") != previous_id
    ]
    if not candidates:
        raise GoldenPathError("Workflow reached human review without a durable section candidate")
    return max(candidates, key=lambda item: int(item.get("version_number") or 0))


def _wait_for_new_candidate(
    client: ApiClient,
    section_id: str,
    run_id: str,
    prior_version_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    def probe() -> list[dict[str, Any]]:
        versions = list(client.json("GET", "/versions", params={"section_id": section_id}))
        return [
            item
            for item in versions
            if item.get("generation_run_id") == run_id and item.get("id") != prior_version_id
        ]

    candidates = _wait_until(
        description="redraft candidate",
        timeout_seconds=timeout_seconds,
        probe=probe,
        predicate=bool,
    )
    return max(candidates, key=lambda item: int(item.get("version_number") or 0))


def _submit_review(
    client: ApiClient,
    *,
    section_id: str,
    version_id: str,
    decision: str,
    comment: str | None = None,
) -> None:
    payload: dict[str, str] = {
        "section_id": section_id,
        "section_version_id": version_id,
        "decision": decision,
    }
    if comment:
        payload["comment"] = comment
    client.json("POST", "/review/decisions", json=payload)


def _create_retry_fixture(
    database_url: str,
    *,
    project_id: str,
    section_key: str,
    user_identity: dict[str, Any],
) -> str:
    """Create one isolated failed source for exercising the real retry path.

    This is controlled fault injection only. The subsequent retry is initiated
    through the public API and executes the actual outbox, Worker, LangGraph,
    review, and export boundaries.
    """

    os.environ["DOCPILOT_DATABASE_URL"] = database_url

    from app.auth.schemas import CurrentUser
    from app.db import SessionLocal
    from app.models import ExecutionRun
    from app.runtime.service import create_workflow_bridge_run

    user = CurrentUser.model_validate(user_identity)
    db = SessionLocal()
    try:
        source = ExecutionRun(
            project_id=project_id,
            run_type="draft_section",
            status="failed",
            input_json={
                "section_key": section_key,
                "p0_d6_controlled_fault_injection": True,
            },
        )
        db.add(source)
        db.flush()
        bridge = create_workflow_bridge_run(
            db,
            user,
            execution_run_id=source.id,
            project_id=project_id,
            reasoning_effort="low",
            commit=False,
        )
        bridge.status = "failed"
        bridge.error_code = "p0_d6_controlled_fault"
        db.commit()
        return source.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run(args: argparse.Namespace, evidence: GoldenPathEvidence) -> None:
    _assert_local_target(args.base_url, args.database_url)
    if not SAMPLE_PACK.is_dir():
        raise GoldenPathError("Checked-in synthetic BidPilot material pack is missing")

    evidence.mark("1/9 Created an isolated verified local Golden Path actor")
    email, password = _bootstrap_actor(args.database_url, evidence.run_label)
    token = _login(args.base_url, email, password, args.timeout_seconds)
    client = ApiClient(args.base_url, token, args.timeout_seconds)
    try:
        evidence.mark("2/9 Created an isolated BidPilot project and default deliverable")
        project = dict(
            client.json(
                "POST",
                "/projects",
                json={
                    "name": f"P0-D6 Synthetic Bid {evidence.run_label}",
                    "scenario_package": "bidpilot",
                },
            )
        )
        evidence.project_id = str(project["id"])
        deliverable, section = _select_deliverable_and_section(client, evidence.project_id)
        evidence.deliverable_id = str(deliverable["id"])

        evidence.mark("3/9 Uploaded the checked-in synthetic bid material pack")
        bundle = dict(
            client.json(
                "POST",
                "/bundles",
                json={
                    "project_id": evidence.project_id,
                    "label": "P0-D6 synthetic bid materials",
                    "source_type": "synthetic_fixture",
                },
            )
        )
        evidence.bundle_id = str(bundle["id"])
        material_files = sorted(SAMPLE_PACK.glob("*.md"))
        if len(material_files) < 3:
            raise GoldenPathError("Synthetic bid pack must contain at least three Markdown materials")
        for material in material_files:
            client.json(
                "POST",
                "/documents/upload",
                params={"bundle_id": evidence.bundle_id},
                files={"file": (material.name, material.read_bytes(), "text/markdown")},
            )
        evidence.document_count = len(material_files)

        evidence.mark("4/9 Queued and verified real Worker parsing plus 1536-dimension indexing")
        client.json("POST", f"/bundles/{evidence.bundle_id}/reingest")
        _wait_for_documents(client, evidence.bundle_id, evidence.document_count, args.timeout_seconds)

        evidence.mark("5/9 Started a real LangGraph draft and waited for durable human review")
        initial = dict(
            client.json(
                "POST",
                "/drafting/sections",
                json={
                    "project_id": evidence.project_id,
                    "section_key": section["section_key"],
                    "reasoning_effort": "low",
                },
            )
        )
        initial_run_id = str(initial["run_id"])
        evidence.initial_execution_run_id = initial_run_id
        _wait_for_run_status(client, initial_run_id, "awaiting_human", args.timeout_seconds)
        first_candidate = _latest_candidate(client, str(section["id"]), initial_run_id)

        evidence.mark("6/9 Rejected the immutable candidate and waited for a redraft checkpoint")
        _submit_review(
            client,
            section_id=str(section["id"]),
            version_id=str(first_candidate["id"]),
            decision="rejected",
            comment="请补充与招标需求的对应关系，并保持可追溯的证据表述。",
        )
        _wait_for_run_status(client, initial_run_id, "awaiting_human", args.timeout_seconds)
        revised_candidate = _wait_for_new_candidate(
            client,
            str(section["id"]),
            initial_run_id,
            str(first_candidate["id"]),
            args.timeout_seconds,
        )

        evidence.mark("7/9 Approved the revised candidate and verified approved-only DOCX export")
        _submit_review(
            client,
            section_id=str(section["id"]),
            version_id=str(revised_candidate["id"]),
            decision="approved",
        )
        _wait_for_run_status(client, initial_run_id, "succeeded", args.timeout_seconds)
        export_bytes = client.bytes("GET", f"/export/deliverables/{evidence.deliverable_id}/docx")
        if len(export_bytes) < 100:
            raise GoldenPathError("Approved-only DOCX export returned an unexpectedly small artifact")
        evidence.exported_docx_bytes = len(export_bytes)

        if args.skip_retry:
            evidence.mark("8/9 Skipped retry checkpoint by explicit request")
        else:
            evidence.mark("8/9 Exercised controlled failed-run retry through the public API and Worker")
            user_identity = dict(client.json("GET", "/auth/me"))
            retry_source_run_id = _create_retry_fixture(
                args.database_url,
                project_id=evidence.project_id,
                section_key=str(section["section_key"]),
                user_identity=user_identity,
            )
            evidence.retry_source_run_id = retry_source_run_id
            retry = dict(client.json("POST", f"/execution/runs/{retry_source_run_id}/retry"))
            retry_run_id = str(retry["id"])
            evidence.retry_execution_run_id = retry_run_id
            _wait_for_run_status(client, retry_run_id, "awaiting_human", args.timeout_seconds)
            retry_candidate = _latest_candidate(client, str(section["id"]), retry_run_id)
            _submit_review(
                client,
                section_id=str(section["id"]),
                version_id=str(retry_candidate["id"]),
                decision="approved",
            )
            _wait_for_run_status(client, retry_run_id, "succeeded", args.timeout_seconds)

        evidence.mark("9/9 Golden Path completed with real API, Worker, LangGraph, HITL, export, and retry boundaries")
    finally:
        client.close()


def main() -> int:
    args = _parse_args()
    if not args.database_url:
        print("--database-url or DOCPILOT_DATABASE_URL is required", file=sys.stderr)
        return 2
    if args.timeout_seconds <= 0:
        print("--timeout-seconds must be positive", file=sys.stderr)
        return 2

    evidence = GoldenPathEvidence(
        run_label=f"p0d6-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
        started_at=datetime.now(UTC).isoformat(),
    )
    output_file = _output_path(args.output_file)
    try:
        _run(args, evidence)
    except Exception as exc:
        evidence.failure_type = type(exc).__name__
        print(f"Golden Path failed: {type(exc).__name__}: {exc}", file=sys.stderr)
    else:
        evidence.passed = True
    finally:
        evidence.completed_at = datetime.now(UTC).isoformat()
        _write_artifact(evidence, output_file)
    return 0 if evidence.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
