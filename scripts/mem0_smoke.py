"""Run a redacted, isolated smoke test against the official Mem0 adapter.

The command is intentionally opt-in. It uses random entity IDs, writes one
low-risk preference, waits for the Platform's asynchronous extraction, and
deletes both user and agent scopes before exiting. It never prints a key,
provider payload, or stored memory text.

Run from the API environment after injecting the server secret:

    uv run --directory services/api python ../../scripts/mem0_smoke.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import secrets
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.memory.mem0_provider import (  # noqa: E402
    capture_profile_memory,
    delete_profile_memory,
    mem0_enabled,
    search_profile_memory,
)


async def _search_until_visible(*, user_id: str, org_id: str, query: str) -> bool:
    for _attempt in range(8):
        if search_profile_memory(user_id=user_id, org_id=org_id, query=query, top_k=4):
            return True
        await asyncio.sleep(2)
    return False


async def main() -> int:
    if not mem0_enabled():
        print("mem0_disabled: set DOCPILOT_MEM0_ENABLED=true and inject the server key")
        return 2

    nonce = secrets.token_hex(8)
    user_id = f"docpilot-smoke-user-{nonce}"
    org_id = f"docpilot-smoke-org-{nonce}"
    run_id = f"docpilot-smoke-run-{nonce}"
    query = f"BidPilot smoke preference {nonce}"
    captured = False
    deleted = False
    try:
        result = capture_profile_memory(
            user_id=user_id,
            org_id=org_id,
            run_id=run_id,
            messages=[
                {
                    "role": "user",
                    "content": f"For this isolated smoke test only, prefer Chinese replies and lead with the conclusion. Marker {nonce}.",
                },
                {"role": "assistant", "content": "Acknowledged for the isolated smoke test."},
            ],
        )
        print(f"capture_status={result.get('status')}; event_id_present={bool(result.get('event_id'))}")
        if result.get("status") != "queued":
            return 1

        captured = await _search_until_visible(user_id=user_id, org_id=org_id, query=query)
        print(f"search_visible={captured}")
        return 0 if captured else 1
    finally:
        deletion = delete_profile_memory(user_id=user_id, org_id=org_id)
        deleted = deletion.get("status") == "deleted"
        print(f"cleanup_status={deletion.get('status')}; isolated_entities_removed={deleted}")
        if not deleted:
            print(f"cleanup_warning_at={datetime.now(UTC).isoformat()}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
