"""Policy resolution for durable notification channels.

Routers expose these choices, while business services call this module before
creating a channel-specific notification. This keeps notification policy out
of route modules and never gates the underlying business transaction.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NotificationPreference


def notification_channel_enabled(
    db: Session,
    *,
    user_id: str,
    category: str,
    channel: str,
) -> bool:
    preferences = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    if preferences is None:
        return True
    if channel == "in_app" and not preferences.in_app_enabled:
        return False
    if channel == "email" and not preferences.email_enabled:
        return False
    category_field = {
        "review": "review_updates",
        "agent": "agent_updates",
        "radar": "radar_updates",
        "material": "material_updates",
    }.get(category)
    if category_field is None:
        return True
    return bool(getattr(preferences, category_field))
