"""Retention cleanup for private assistant attachment staging objects."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select

from app.adapters.storage import delete_storage_key
from app.db import SessionLocal
from app.models import AssistantAttachment

logger = logging.getLogger(__name__)


def purge_expired_assistant_attachments(*, batch_size: int = 200) -> dict[str, str]:
    """Delete unconsumed expired attachments and retry failed consumed-object cleanup.

    Project source documents have already been copied to project-scoped storage,
    so this function only ever removes the private staging object.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    db = SessionLocal()
    try:
        candidates = list(
            db.scalars(
                select(AssistantAttachment)
                .where(
                    AssistantAttachment.storage_key != "",
                    or_(
                        and_(
                            AssistantAttachment.status.in_(("staged", "staging", "expired")),
                            AssistantAttachment.expires_at <= now,
                        ),
                        AssistantAttachment.status == "attached",
                    ),
                )
                .order_by(AssistantAttachment.expires_at.asc())
                .limit(batch_size)
            ).all()
        )
        expired = 0
        for attachment in candidates:
            if attachment.status != "attached":
                attachment.status = "expired"
                attachment.extracted_text = ""
                attachment.extraction_error = None
                expired += 1
        db.commit()

        deleted = 0
        failed = 0
        for attachment in candidates:
            storage_key = attachment.storage_key
            if not storage_key:
                continue
            try:
                delete_storage_key(storage_key)
            except Exception as exc:
                failed += 1
                logger.warning("Assistant attachment cleanup failed: %s", type(exc).__name__)
                continue
            attachment.storage_key = ""
            deleted += 1
        db.commit()
        return {
            "status": "ok",
            "expired": str(expired),
            "deleted": str(deleted),
            "failed": str(failed),
        }
    except Exception:
        db.rollback()
        logger.exception("Assistant attachment cleanup database failure")
        raise
    finally:
        db.close()
