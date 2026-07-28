import hashlib
import json
from pathlib import Path
import re

from app.projects.demo_data import DEMO_DOCUMENTS


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEMO_ROOT = REPOSITORY_ROOT / "sample-data" / "bidpilot-demo"

HIGH_CONFIDENCE_SECRET_PATTERNS = (
    re.compile(r"(?i)\bsk-[a-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\btvly-[a-z0-9_-]{16,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
)
PERSONAL_IDENTIFIER_PATTERNS = (
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
)


def test_synthetic_demo_material_pack_is_fixed_and_traceable() -> None:
    manifest = json.loads((DEMO_ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["dataset_id"] == "bidpilot-demo-v1"
    assert manifest["origin"] == "synthetic"
    assert manifest["license"].startswith("LicenseRef-")
    assert {document["role"] for document in manifest["documents"]} == {
        "rfp",
        "supplier_capability",
        "case_study",
    }
    assert manifest["acceptance_expectations"]["minimum_documents"] == 3

    for document in manifest["documents"]:
        payload = (DEMO_ROOT / document["path"]).read_bytes()
        content = payload.decode("utf-8")
        assert hashlib.sha256(payload).hexdigest() == document["sha256"]
        for expected_anchor in document["expected_anchors"]:
            assert expected_anchor in content

    content_by_id = {
        document["id"]: (DEMO_ROOT / document["path"]).read_text(encoding="utf-8")
        for document in manifest["documents"]
    }
    expectations = manifest["acceptance_expectations"]
    for requirement in expectations["expected_requirements"]:
        source = content_by_id[requirement["source"]]
        assert requirement["heading"] in source
        assert requirement["anchor"] in source
    for evidence in expectations["expected_evidence"]:
        source = content_by_id[evidence["source"]]
        assert evidence["heading"] in source
        assert evidence["anchor"] in source

    assert {document.filename: document.content for document in DEMO_DOCUMENTS} == {
        entry["path"]: (DEMO_ROOT / entry["path"]).read_text(encoding="utf-8")
        for entry in manifest["documents"]
    }


def test_synthetic_demo_material_pack_contains_no_obvious_secrets_or_personal_data() -> None:
    for path in DEMO_ROOT.rglob("*"):
        if not path.is_file():
            continue

        content = path.read_text(encoding="utf-8")
        for pattern in HIGH_CONFIDENCE_SECRET_PATTERNS:
            assert pattern.search(content) is None, path.name
        for pattern in PERSONAL_IDENTIFIER_PATTERNS:
            assert pattern.search(content) is None, path.name
