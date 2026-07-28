"""Run a local BidPilot governed workflow against real API and Worker services.

The default pack is the checked-in synthetic fixture used for P0-D6. The same
runtime can also be pointed at a pinned public rehearsal pack for P0-D7. It
creates an isolated organization and leaves its project in place for inspection
after the run. No provider credential, JWT, response body, or document content
is written to stdout or the evidence artifact.

Example:
    $env:DOCPILOT_DATABASE_URL = "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot"
    uv run --directory services/api --locked --no-sync python ../../scripts/run_bidpilot_golden_path.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path, PurePath
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
MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


class GoldenPathError(RuntimeError):
    """Raised when a governed Golden Path checkpoint is not reached."""


T = TypeVar("T")


@dataclass(frozen=True)
class RunnerDefaults:
    description: str
    evidence_kind: str
    run_prefix: str
    output_file: Path
    material_dir: Path
    material_manifest: Path
    material_origin: str
    material_label: str
    project_name_prefix: str
    actor_label: str


DEFAULT_GOLDEN_PATH = RunnerDefaults(
    description="Run the local BidPilot P0-D6 Golden Path.",
    evidence_kind="bidpilot_p0_d6_golden_path",
    run_prefix="p0d6",
    output_file=Path("tmp") / "p0-d6-golden-path.json",
    material_dir=SAMPLE_PACK,
    material_manifest=SAMPLE_PACK / "manifest.json",
    material_origin="synthetic_checked_in_pack",
    material_label="P0-D6 synthetic bid materials",
    project_name_prefix="P0-D6 Synthetic Bid",
    actor_label="P0-D6 Golden Path",
)


@dataclass(frozen=True)
class MaterialDocument:
    id: str
    path: Path
    mime_type: str
    sha256: str


@dataclass(frozen=True)
class MaterialPack:
    dataset_id: str
    dataset_version: int
    manifest_sha256: str
    origin: str
    documents: tuple[MaterialDocument, ...]
    retrieval_checks: tuple[dict[str, str], ...]


@dataclass
class GoldenPathEvidence:
    run_label: str
    started_at: str
    kind: str
    material_origin: str
    material_dataset_id: str | None = None
    material_dataset_version: int | None = None
    material_manifest_sha256: str | None = None
    retrieval_checks: list[dict[str, object]] = field(default_factory=list)
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
            "kind": self.kind,
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
            "material_origin": self.material_origin,
            "material_dataset_id": self.material_dataset_id,
            "material_dataset_version": self.material_dataset_version,
            "material_manifest_sha256": self.material_manifest_sha256,
            "retrieval_checks": self.retrieval_checks,
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


def _parse_args(defaults: RunnerDefaults) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=defaults.description)
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
        default=defaults.output_file,
        help="redacted JSON evidence artifact, relative to the repository by default",
    )
    parser.add_argument(
        "--material-dir",
        type=Path,
        default=defaults.material_dir,
        help="repository-local directory containing manifest-pinned source materials",
    )
    parser.add_argument(
        "--material-manifest",
        type=Path,
        default=defaults.material_manifest,
        help="manifest with source names, hashes, and optional retrieval checks",
    )
    parser.add_argument("--material-origin", default=defaults.material_origin)
    parser.add_argument("--material-label", default=defaults.material_label)
    parser.add_argument("--project-name-prefix", default=defaults.project_name_prefix)
    parser.add_argument("--actor-label", default=defaults.actor_label)
    parser.add_argument("--run-prefix", default=defaults.run_prefix)
    parser.add_argument("--evidence-kind", default=defaults.evidence_kind)
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


def _safe_relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise GoldenPathError("Material manifest document path is required")
    path = PurePath(value)
    if path.is_absolute() or ".." in path.parts or path.name != value:
        raise GoldenPathError("Material manifest document paths must be simple filenames")
    return Path(value)


def _material_mime_type(path: Path) -> str:
    mime_type = MIME_BY_EXTENSION.get(path.suffix.lower())
    if mime_type is None:
        raise GoldenPathError(f"Unsupported material type in manifest: {path.name}")
    return mime_type


def _load_material_pack(args: argparse.Namespace) -> MaterialPack:
    material_dir = _output_path(args.material_dir).resolve()
    manifest_path = _output_path(args.material_manifest).resolve()
    try:
        material_dir.relative_to(REPOSITORY_ROOT.resolve())
        manifest_path.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as exc:
        raise GoldenPathError("Golden Path material directories and manifests must stay inside the repository") from exc

    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldenPathError("Could not read material pack manifest") from exc
    if not isinstance(manifest, dict):
        raise GoldenPathError("Material pack manifest must be a JSON object")

    dataset_id = manifest.get("dataset_id")
    dataset_version = manifest.get("dataset_version")
    entries = manifest.get("documents")
    if not isinstance(dataset_id, str) or not dataset_id or not isinstance(dataset_version, int) or dataset_version < 1:
        raise GoldenPathError("Material pack manifest must declare dataset_id and a positive dataset_version")
    if not isinstance(entries, list) or len(entries) < 3:
        raise GoldenPathError("Material pack manifest must contain at least three documents")

    documents: list[MaterialDocument] = []
    seen_document_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise GoldenPathError("Material pack document entries must be objects")
        document_id = entry.get("id")
        if not isinstance(document_id, str) or not document_id or document_id in seen_document_ids:
            raise GoldenPathError("Material pack document ids must be present and unique")
        seen_document_ids.add(document_id)

        filename = _safe_relative_path(entry.get("path") or entry.get("filename"))
        document_path = (material_dir / filename).resolve()
        try:
            document_path.relative_to(material_dir)
        except ValueError as exc:
            raise GoldenPathError("Material pack document resolved outside its material directory") from exc
        if not document_path.is_file():
            raise GoldenPathError(f"Material pack document is missing: {filename.name}")

        expected_sha256 = entry.get("sha256")
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            raise GoldenPathError(f"Material pack document sha256 is invalid: {filename.name}")
        actual_sha256 = hashlib.sha256(document_path.read_bytes()).hexdigest()
        if actual_sha256 != expected_sha256:
            raise GoldenPathError(f"Material pack document checksum differs: {filename.name}")
        documents.append(
            MaterialDocument(
                id=document_id,
                path=document_path,
                mime_type=_material_mime_type(document_path),
                sha256=actual_sha256,
            )
        )

    retrieval_checks: list[dict[str, str]] = []
    for check in manifest.get("retrieval_checks") or []:
        if not isinstance(check, dict):
            raise GoldenPathError("Material pack retrieval checks must be objects")
        query = check.get("query")
        document_id = check.get("document_id")
        required_anchor = check.get("required_anchor")
        if not all(isinstance(value, str) and value for value in (query, document_id, required_anchor)):
            raise GoldenPathError("Material pack retrieval checks require query, document_id, and required_anchor")
        if document_id not in seen_document_ids:
            raise GoldenPathError("Material pack retrieval check references an unknown document")
        retrieval_checks.append({"query": query, "document_id": document_id, "required_anchor": required_anchor})

    return MaterialPack(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        origin=str(args.material_origin),
        documents=tuple(documents),
        retrieval_checks=tuple(retrieval_checks),
    )


def _write_artifact(evidence: GoldenPathEvidence, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(evidence.artifact(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"evidence_artifact={output_file}", flush=True)


def _bootstrap_actor(database_url: str, run_label: str, actor_label: str) -> tuple[str, str]:
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

    run_prefix, separator, suffix = run_label.partition("-")
    if not separator or not run_prefix.isalnum() or not suffix:
        raise GoldenPathError("Golden Path run label must start with an alphanumeric prefix")
    email = f"{run_prefix}-{suffix}@local.test"
    password = f"{run_prefix.title()}!{secrets.token_urlsafe(18)}A1"
    org_slug = f"{run_prefix}-{suffix}"[:80]

    db = SessionLocal()
    try:
        actor = register_user_command(
            db,
            UserRegister(
                email=email,
                display_name=actor_label,
                password=password,
                org_name=f"{actor_label} {suffix}",
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


def _verify_retrieval_checks(
    client: ApiClient,
    *,
    project_id: str,
    uploaded_document_ids: dict[str, str],
    checks: tuple[dict[str, str], ...],
) -> list[dict[str, object]]:
    """Verify public-pack retrieval without retaining document text in evidence."""

    verified: list[dict[str, object]] = []
    for check in checks:
        expected_document_id = uploaded_document_ids[check["document_id"]]
        response = dict(
            client.json(
                "POST",
                "/retrieval/search",
                json={"project_id": project_id, "query": check["query"], "top_k": 10},
            )
        )
        match: dict[str, Any] | None = None
        for raw_result in response.get("results") or []:
            result = dict(raw_result)
            citation = dict(result.get("citation") or {})
            locator_text = " ".join(
                str(value or "")
                for value in (
                    result.get("content"),
                    citation.get("heading"),
                    citation.get("text_anchor"),
                )
            )
            if result.get("source_document_id") == expected_document_id and check["required_anchor"].casefold() in locator_text.casefold():
                match = result
                break
        if match is None:
            raise GoldenPathError(f"Retrieval did not return the expected public source for {check['document_id']}")

        citation = dict(match.get("citation") or {})
        validation_status = str(citation.get("validation_status") or "")
        if validation_status == "invalid":
            raise GoldenPathError(f"Retrieval returned an invalid locator for {check['document_id']}")
        verified.append(
            {
                "document_id": check["document_id"],
                "locator_validation_status": validation_status,
                "methods": list(match.get("methods") or ()),
            }
        )
    return verified


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
    material_pack = _load_material_pack(args)
    evidence.material_origin = material_pack.origin
    evidence.material_dataset_id = material_pack.dataset_id
    evidence.material_dataset_version = material_pack.dataset_version
    evidence.material_manifest_sha256 = material_pack.manifest_sha256
    total_steps = 10 if material_pack.retrieval_checks else 9

    evidence.mark(f"1/{total_steps} Created an isolated verified local Golden Path actor")
    email, password = _bootstrap_actor(args.database_url, evidence.run_label, str(args.actor_label))
    token = _login(args.base_url, email, password, args.timeout_seconds)
    client = ApiClient(args.base_url, token, args.timeout_seconds)
    try:
        evidence.mark(f"2/{total_steps} Created an isolated BidPilot project and default deliverable")
        project = dict(
            client.json(
                "POST",
                "/projects",
                json={
                    "name": f"{args.project_name_prefix} {evidence.run_label}",
                    "scenario_package": "bidpilot",
                },
            )
        )
        evidence.project_id = str(project["id"])
        deliverable, section = _select_deliverable_and_section(client, evidence.project_id)
        evidence.deliverable_id = str(deliverable["id"])

        evidence.mark(f"3/{total_steps} Uploaded the manifest-pinned bid material pack")
        bundle = dict(
            client.json(
                "POST",
                "/bundles",
                json={
                    "project_id": evidence.project_id,
                    "label": str(args.material_label),
                    "source_type": (
                        "synthetic_fixture"
                        if material_pack.origin == "synthetic_checked_in_pack"
                        else "public_rehearsal"
                    ),
                },
            )
        )
        evidence.bundle_id = str(bundle["id"])
        uploaded_document_ids: dict[str, str] = {}
        for material in material_pack.documents:
            uploaded = dict(
                client.json(
                    "POST",
                    "/documents/upload",
                    params={"bundle_id": evidence.bundle_id},
                    files={"file": (material.path.name, material.path.read_bytes(), material.mime_type)},
                )
            )
            uploaded_document_ids[material.id] = str(uploaded["id"])
        evidence.document_count = len(material_pack.documents)

        evidence.mark(f"4/{total_steps} Queued and verified real Worker parsing plus 1536-dimension indexing")
        client.json("POST", f"/bundles/{evidence.bundle_id}/reingest")
        _wait_for_documents(client, evidence.bundle_id, evidence.document_count, args.timeout_seconds)

        workflow_step = 5
        if material_pack.retrieval_checks:
            evidence.mark(f"5/{total_steps} Queried indexed material and verified source locators")
            evidence.retrieval_checks = _verify_retrieval_checks(
                client,
                project_id=evidence.project_id,
                uploaded_document_ids=uploaded_document_ids,
                checks=material_pack.retrieval_checks,
            )
            workflow_step = 6

        evidence.mark(f"{workflow_step}/{total_steps} Started a real LangGraph draft and waited for durable human review")
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

        evidence.mark(f"{workflow_step + 1}/{total_steps} Rejected the immutable candidate and waited for a redraft checkpoint")
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

        evidence.mark(f"{workflow_step + 2}/{total_steps} Approved the revised candidate and verified approved-only DOCX export")
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
            evidence.mark(f"{workflow_step + 3}/{total_steps} Skipped retry checkpoint by explicit request")
        else:
            evidence.mark(
                f"{workflow_step + 3}/{total_steps} Exercised controlled failed-run retry through the public API and Worker"
            )
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

        evidence.mark(
            f"{total_steps}/{total_steps} Golden Path completed with real API, Worker, LangGraph, HITL, export, and retry boundaries"
        )
    finally:
        client.close()


def main(*, defaults: RunnerDefaults = DEFAULT_GOLDEN_PATH) -> int:
    args = _parse_args(defaults)
    if not args.database_url:
        print("--database-url or DOCPILOT_DATABASE_URL is required", file=sys.stderr)
        return 2
    if args.timeout_seconds <= 0:
        print("--timeout-seconds must be positive", file=sys.stderr)
        return 2
    if not isinstance(args.run_prefix, str) or not args.run_prefix.isalnum():
        print("--run-prefix must be alphanumeric", file=sys.stderr)
        return 2

    evidence = GoldenPathEvidence(
        run_label=f"{args.run_prefix}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
        started_at=datetime.now(UTC).isoformat(),
        kind=str(args.evidence_kind),
        material_origin=str(args.material_origin),
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
