"""Clean up demo data from the database."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

from app.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()
tables = [
    "audit_event", "review_comment", "review_thread", "evidence",
    "section_version", "execution_run", "deliverable_section",
    "deliverable", "requirement_item", "knowledge_chunk",
    "parsed_asset", "source_document", "bundle", "project", '"user"',
]
for t in tables:
    try:
        db.execute(text(f"DELETE FROM {t}"))
    except Exception:
        pass
db.commit()
print("Cleaned up all demo data")
