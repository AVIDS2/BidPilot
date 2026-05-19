def schedule_ingest(bundle_id: str) -> dict[str, str]:
    return {"bundle_id": bundle_id, "status": "queued"}
