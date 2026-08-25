#!/usr/bin/env python3
"""Validate a serialized Deep Research result without calling a model."""

from __future__ import annotations

import json
import sys
from typing import Any


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("query", "sources", "claims", "report"):
        if key not in payload:
            errors.append(f"missing:{key}")
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    source_ids = set()
    for source in sources:
        if not isinstance(source, dict):
            errors.append("source:not_object")
            continue
        source_id = str(source.get("source_id") or "")
        source_ids.add(source_id)
        for key in ("source_id", "title", "url", "status"):
            if not str(source.get(key) or "").strip():
                errors.append(f"source_missing:{key}")
    claims = payload.get("claims") if isinstance(payload.get("claims"), list) else []
    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("claim:not_object")
            continue
        if not str(claim.get("claim") or "").strip():
            errors.append("claim_missing:text")
        references = claim.get("source_ids") if isinstance(claim.get("source_ids"), list) else []
        if not references or any(str(value) not in source_ids for value in references):
            errors.append(f"claim_unlinked:{claim.get('claim_id') or 'unknown'}")
        if claim.get("verification") not in {"verified", "uncertain"}:
            errors.append(f"claim_verification:{claim.get('claim_id') or 'unknown'}")
    if not isinstance(payload.get("report"), str) or not payload["report"].strip():
        errors.append("report:empty")
    return errors


def main() -> int:
    payload = json.load(sys.stdin)
    errors = validate_payload(payload)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
