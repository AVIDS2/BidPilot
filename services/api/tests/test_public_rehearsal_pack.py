from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _load_script_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


fetch_public_rehearsal = _load_script_module(
    "fetch_bidpilot_public_rehearsal",
    REPOSITORY_ROOT / "scripts" / "fetch_bidpilot_public_rehearsal.py",
)

golden_path = _load_script_module(
    "run_bidpilot_golden_path",
    REPOSITORY_ROOT / "scripts" / "run_bidpilot_golden_path.py",
)


def test_public_rehearsal_manifest_is_pinned_and_public_only() -> None:
    manifest_path = REPOSITORY_ROOT / "sample-data" / "bidpilot-public-rehearsal" / "manifest.json"

    manifest, documents, manifest_hash = fetch_public_rehearsal._load_manifest(manifest_path)

    assert manifest["dataset_id"] == "bidpilot-public-rehearsal-v1"
    assert manifest["origin"] == "public_historical_procurement"
    assert len(documents) == 3
    assert len(manifest_hash) == 64
    assert all(document["source_url"].startswith("https://") for document in documents)
    assert all(document["content_type"] == "application/pdf" for document in documents)


def test_public_rehearsal_verifier_rejects_changed_source(tmp_path: Path) -> None:
    path = tmp_path / "source.pdf"
    payload = b"%PDF-public-rehearsal"
    path.write_bytes(payload)
    document = {
        "id": "source",
        "expected_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }

    receipt = fetch_public_rehearsal._verify_file(path, document)

    assert receipt["filename"] == "source.pdf"
    path.write_bytes(b"%PDF-changed")
    try:
        fetch_public_rehearsal._verify_file(path, document)
    except fetch_public_rehearsal.PublicRehearsalError as exc:
        assert "Pinned byte length differs" in str(exc)
    else:
        raise AssertionError("Changed public source should fail closed")


def test_default_golden_path_still_loads_synthetic_pack() -> None:
    pack = golden_path._load_material_pack(
        argparse.Namespace(
            material_dir=golden_path.SAMPLE_PACK,
            material_manifest=golden_path.SAMPLE_PACK / "manifest.json",
            material_origin="synthetic_checked_in_pack",
        )
    )

    assert pack.dataset_id == "bidpilot-demo-v1"
    assert pack.origin == "synthetic_checked_in_pack"
    assert len(pack.documents) == 3
    assert not pack.retrieval_checks


def test_role_aware_synthetic_pack_separates_buyer_requirements_from_supplier_evidence() -> None:
    pack = golden_path._load_material_pack(
        argparse.Namespace(
            material_dir=golden_path.SAMPLE_PACK,
            material_manifest=golden_path.SAMPLE_PACK / "manifest.json",
            material_origin="synthetic_checked_in_pack",
            material_label="Role-aware fixture",
            bundle_mode="role_aware",
        )
    )

    assert {(bundle.key, bundle.source_type) for bundle in pack.bundles} == {
        ("buyer-rfp", "buyer_rfp"),
        ("supplier-evidence", "supplier_evidence"),
    }
    assert {
        (document.id, document.bundle_key)
        for document in pack.documents
    } == {
        ("rfp", "buyer-rfp"),
        ("supplier-capability", "supplier-evidence"),
        ("case-study", "supplier-evidence"),
    }
    assert pack.requirement_evidence_acceptance is not None
    assert pack.requirement_evidence_acceptance.requirement_document_id == "rfp"
    assert pack.requirement_evidence_acceptance.evidence_document_id == "case-study"
