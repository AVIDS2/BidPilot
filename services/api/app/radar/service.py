"""Durable tender radar source ingestion and opportunity control plane."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import urljoin

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.auth.service import check_plan_limit
from app.documents.web_import import fetch_public_http_resource
from app.models import NoticeItem, NoticeMatch, NoticeSource, NoticeSubscription
from app.projects.schemas import ProjectCreate
from app.projects.service import _create_project_with_defaults
from app.webhooks.service import queue_webhook_event

from .schemas import (
    NoticeMatchRead,
    NoticePollRead,
    NoticeProjectConvert,
    NoticeProjectConvertRead,
    NoticeRead,
    NoticeSourceCreate,
    NoticeSourceIngestItem,
    NoticeSourceRead,
    NoticeSourceUpdate,
    NoticeStatusUpdate,
    NoticeSubscriptionCreate,
    NoticeSubscriptionRead,
    NoticeSubscriptionUpdate,
    RadarOverviewRead,
    RadarSummaryRead,
    RadarTrendPoint,
)


_NOTICE_TYPES = {"intent", "tender", "prequalification", "rfi", "other"}
_POLLABLE_KINDS = {"rss", "json_feed"}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _org_id(current_user: CurrentUser) -> str:
    return current_user.org_id or "default"


def _require_org_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only organization admins can manage radar sources")


def _collapse(value: object | None, *, limit: int = 500) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit] if text else None


def _normalize_values(values: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _collapse(value, limit=120)
        if normalized and normalized.casefold() not in seen:
            seen.add(normalized.casefold())
            unique.append(normalized)
    return unique


def _naive_datetime(value: object | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
            return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed
        except (TypeError, ValueError):
            return None


def _number(value: object | None) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?[\d,]+(?:\.\d+)?", str(value))
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _strip_html(value: object | None) -> str | None:
    text = _collapse(value, limit=12000)
    if text is None:
        return None
    return _collapse(re.sub(r"<[^>]+>", " ", text), limit=12000)


def _source_read(source: NoticeSource, *, notice_count: int = 0) -> NoticeSourceRead:
    return NoticeSourceRead(
        id=source.id,
        name=source.name,
        kind=source.kind,  # type: ignore[arg-type]
        endpoint_url=source.endpoint_url,
        is_active=source.is_active,
        polling_interval_minutes=source.polling_interval_minutes,
        last_polled_at=source.last_polled_at,
        last_success_at=source.last_success_at,
        last_error_code=source.last_error_code,
        notice_count=notice_count,
    )


def _subscription_read(subscription: NoticeSubscription, *, match_count: int = 0) -> NoticeSubscriptionRead:
    return NoticeSubscriptionRead(
        id=subscription.id,
        name=subscription.name,
        keywords=list(subscription.keywords_json or []),
        regions=list(subscription.regions_json or []),
        categories=list(subscription.categories_json or []),
        budget_min=subscription.budget_min,
        budget_max=subscription.budget_max,
        is_active=subscription.is_active,
        match_count=match_count,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
    )


def _notice_read(item: NoticeItem) -> NoticeRead:
    matches = sorted(item.matches, key=lambda match: (-match.score, match.created_at or _now()))
    return NoticeRead(
        id=item.id,
        source_id=item.source_id,
        source_name=item.source.name if item.source is not None else "已移除来源",
        external_id=item.external_id,
        title=item.title,
        buyer_name=item.buyer_name,
        notice_type=item.notice_type,  # type: ignore[arg-type]
        region=item.region,
        category=item.category,
        budget_amount=item.budget_amount,
        published_at=item.published_at,
        deadline_at=item.deadline_at,
        source_url=item.source_url,
        summary=item.summary,
        status=item.status,  # type: ignore[arg-type]
        converted_project_id=item.converted_project_id,
        created_at=item.created_at,
        matches=[
            NoticeMatchRead(
                subscription_id=match.subscription_id,
                subscription_name=match.subscription.name if match.subscription is not None else "已删除订阅",
                score=match.score,
                reasons=list(match.reasons_json or []),
            )
            for match in matches
        ],
    )


def _source_for_org(db: Session, *, source_id: str, org_id: str) -> NoticeSource:
    source = db.scalar(select(NoticeSource).where(NoticeSource.id == source_id, NoticeSource.org_id == org_id))
    if source is None:
        raise HTTPException(status_code=404, detail="Radar source not found")
    return source


def _notice_for_org(db: Session, *, notice_id: str, org_id: str) -> NoticeItem:
    statement = (
        select(NoticeItem)
        .options(
            selectinload(NoticeItem.source),
            selectinload(NoticeItem.matches).selectinload(NoticeMatch.subscription),
        )
        .where(NoticeItem.id == notice_id, NoticeItem.org_id == org_id)
    )
    notice = db.scalar(statement)
    if notice is None:
        raise HTTPException(status_code=404, detail="Radar notice not found")
    return notice


def list_radar_overview_query(
    db: Session,
    *,
    current_user: CurrentUser,
    view: str = "recommended",
    query: str | None = None,
    notice_type: str | None = None,
) -> RadarOverviewRead:
    org_id = _org_id(current_user)
    sources = list(db.scalars(select(NoticeSource).where(NoticeSource.org_id == org_id).order_by(NoticeSource.created_at.desc())))
    subscriptions = list(
        db.scalars(select(NoticeSubscription).where(NoticeSubscription.org_id == org_id).order_by(NoticeSubscription.created_at.desc()))
    )
    notices = list(
        db.scalars(
            select(NoticeItem)
            .options(
                selectinload(NoticeItem.source),
                selectinload(NoticeItem.matches).selectinload(NoticeMatch.subscription),
            )
            .where(NoticeItem.org_id == org_id)
            .order_by(NoticeItem.published_at.desc().nullslast(), NoticeItem.created_at.desc())
            .limit(160)
        )
    )
    normalized_query = (query or "").casefold().strip()
    visible: list[NoticeItem] = []
    for item in notices:
        if view == "recommended" and not item.matches:
            continue
        if view == "saved" and item.status != "saved":
            continue
        if view == "ignored" and item.status != "ignored":
            continue
        if view == "intent" and item.notice_type != "intent":
            continue
        if view == "tender" and item.notice_type != "tender":
            continue
        if notice_type and item.notice_type != notice_type:
            continue
        if normalized_query:
            haystack = " ".join(filter(None, [item.title, item.buyer_name, item.region, item.category, item.summary])).casefold()
            if normalized_query not in haystack:
                continue
        visible.append(item)

    source_counts = Counter(item.source_id for item in notices)
    subscription_counts = Counter(match.subscription_id for item in notices for match in item.matches)
    today = _now().date()
    period = [today - timedelta(days=offset) for offset in range(13, -1, -1)]
    published_counts = Counter(
        (item.published_at or item.created_at).date()
        for item in notices
        if item.published_at is not None or item.created_at is not None
    )
    due_soon = sum(
        1
        for item in notices
        if item.status not in {"ignored", "converted"}
        and item.deadline_at is not None
        and today <= item.deadline_at.date() <= today + timedelta(days=14)
    )
    summary = RadarSummaryRead(
        active_source_count=sum(1 for source in sources if source.is_active),
        source_attention_count=sum(1 for source in sources if source.is_active and source.last_error_code is not None),
        active_subscription_count=sum(1 for subscription in subscriptions if subscription.is_active),
        recommended_count=sum(1 for item in notices if item.matches and item.status not in {"ignored", "converted"}),
        saved_count=sum(1 for item in notices if item.status == "saved"),
        due_soon_count=due_soon,
        trends=[RadarTrendPoint(day=day.isoformat(), notice_count=published_counts[day]) for day in period],
    )
    return RadarOverviewRead(
        summary=summary,
        sources=[_source_read(source, notice_count=source_counts[source.id]) for source in sources],
        subscriptions=[_subscription_read(subscription, match_count=subscription_counts[subscription.id]) for subscription in subscriptions],
        notices=[_notice_read(item) for item in visible],
    )


def create_notice_source_command(
    db: Session,
    *,
    payload: NoticeSourceCreate,
    current_user: CurrentUser,
) -> NoticeSourceRead:
    _require_org_admin(current_user)
    source = NoticeSource(
        org_id=_org_id(current_user),
        name=payload.name,
        kind=payload.kind,
        endpoint_url=payload.endpoint_url,
        polling_interval_minutes=payload.polling_interval_minutes,
        created_by_user_id=current_user.id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _source_read(source)


def update_notice_source_command(
    db: Session,
    *,
    source_id: str,
    payload: NoticeSourceUpdate,
    current_user: CurrentUser,
) -> NoticeSourceRead:
    _require_org_admin(current_user)
    source = _source_for_org(db, source_id=source_id, org_id=_org_id(current_user))
    for field in ("name", "endpoint_url", "polling_interval_minutes", "is_active"):
        value = getattr(payload, field)
        if value is not None:
            setattr(source, field, value)
    if source.kind in _POLLABLE_KINDS and not source.endpoint_url:
        raise HTTPException(status_code=422, detail="Polling sources require a public endpoint URL")
    db.commit()
    db.refresh(source)
    return _source_read(source)


def create_subscription_command(
    db: Session,
    *,
    payload: NoticeSubscriptionCreate,
    current_user: CurrentUser,
) -> NoticeSubscriptionRead:
    subscription = NoticeSubscription(
        org_id=_org_id(current_user),
        name=payload.name,
        keywords_json=_normalize_values(payload.keywords),
        regions_json=_normalize_values(payload.regions),
        categories_json=_normalize_values(payload.categories),
        budget_min=payload.budget_min,
        budget_max=payload.budget_max,
        created_by_user_id=current_user.id,
    )
    db.add(subscription)
    db.flush()
    _recompute_matches_for_subscription(db, subscription)
    db.commit()
    db.refresh(subscription)
    match_count = int(
        db.scalar(select(func.count()).select_from(NoticeMatch).where(NoticeMatch.subscription_id == subscription.id)) or 0
    )
    return _subscription_read(subscription, match_count=match_count)


def update_subscription_command(
    db: Session,
    *,
    subscription_id: str,
    payload: NoticeSubscriptionUpdate,
    current_user: CurrentUser,
) -> NoticeSubscriptionRead:
    subscription = db.scalar(
        select(NoticeSubscription).where(
            NoticeSubscription.id == subscription_id,
            NoticeSubscription.org_id == _org_id(current_user),
        )
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Radar subscription not found")
    if payload.name is not None:
        subscription.name = payload.name
    for field, value in (("keywords_json", payload.keywords), ("regions_json", payload.regions), ("categories_json", payload.categories)):
        if value is not None:
            setattr(subscription, field, _normalize_values(value))
    if payload.budget_min is not None:
        subscription.budget_min = payload.budget_min
    if payload.budget_max is not None:
        subscription.budget_max = payload.budget_max
    if subscription.budget_min is not None and subscription.budget_max is not None and subscription.budget_min > subscription.budget_max:
        raise HTTPException(status_code=422, detail="Budget minimum cannot exceed budget maximum")
    if payload.is_active is not None:
        subscription.is_active = payload.is_active
    _recompute_matches_for_subscription(db, subscription)
    db.commit()
    db.refresh(subscription)
    match_count = int(
        db.scalar(select(func.count()).select_from(NoticeMatch).where(NoticeMatch.subscription_id == subscription.id)) or 0
    )
    return _subscription_read(subscription, match_count=match_count)


def ingest_notice_items_command(
    db: Session,
    *,
    source: NoticeSource,
    items: Iterable[NoticeSourceIngestItem],
) -> tuple[int, int]:
    created_count = 0
    updated_count = 0
    for payload in items:
        external_id = payload.external_id or _fallback_external_id(payload.title, payload.source_url, payload.published_at)
        item = db.scalar(
            select(NoticeItem).where(NoticeItem.source_id == source.id, NoticeItem.external_id == external_id)
        )
        snapshot = dict(payload.source_snapshot or {})
        was_created = item is None
        if was_created:
            item = NoticeItem(
                org_id=source.org_id,
                source_id=source.id,
                external_id=external_id,
                title=payload.title,
                source_url=payload.source_url,
                buyer_name=payload.buyer_name,
                notice_type=payload.notice_type,
                region=payload.region,
                category=payload.category,
                budget_amount=payload.budget_amount,
                published_at=_naive_datetime(payload.published_at),
                deadline_at=_naive_datetime(payload.deadline_at),
                summary=payload.summary,
                source_snapshot_json=snapshot or None,
            )
            db.add(item)
            db.flush()
            created_count += 1
        else:
            item.title = payload.title
            item.source_url = payload.source_url
            item.buyer_name = payload.buyer_name
            item.notice_type = payload.notice_type
            item.region = payload.region
            item.category = payload.category
            item.budget_amount = payload.budget_amount
            item.published_at = _naive_datetime(payload.published_at)
            item.deadline_at = _naive_datetime(payload.deadline_at)
            item.summary = payload.summary
            item.source_snapshot_json = snapshot or item.source_snapshot_json
            updated_count += 1
        _recompute_matches_for_notice(db, item)
        if was_created:
            matches = list(
                db.scalars(
                    select(NoticeMatch)
                    .options(selectinload(NoticeMatch.subscription))
                    .where(NoticeMatch.notice_id == item.id)
                    .order_by(NoticeMatch.score.desc())
                )
            )
            if matches:
                queue_webhook_event(
                    db,
                    org_id=source.org_id,
                    event_type="radar.notice.matched",
                    data=_notice_event_data(item, matches=matches),
                )
    return created_count, updated_count


def ingest_notice_source_command(
    db: Session,
    *,
    source_id: str,
    items: Iterable[NoticeSourceIngestItem],
    current_user: CurrentUser,
) -> NoticePollRead:
    _require_org_admin(current_user)
    source = _source_for_org(db, source_id=source_id, org_id=_org_id(current_user))
    materialized = list(items)
    created_count, updated_count = ingest_notice_items_command(db, source=source, items=materialized)
    source.last_polled_at = _now()
    source.last_success_at = source.last_polled_at
    source.last_error_code = None
    db.commit()
    return NoticePollRead(
        source_id=source.id,
        status="succeeded",
        discovered_count=len(materialized),
        created_count=created_count,
        updated_count=updated_count,
    )


def poll_notice_source_command(
    db: Session,
    *,
    source_id: str,
    current_user: CurrentUser,
) -> NoticePollRead:
    _require_org_admin(current_user)
    source = _source_for_org(db, source_id=source_id, org_id=_org_id(current_user))
    return poll_notice_source(db, source=source)


def poll_notice_source(db: Session, *, source: NoticeSource) -> NoticePollRead:
    if not source.is_active or source.kind not in _POLLABLE_KINDS:
        return NoticePollRead(source_id=source.id, status="skipped")
    source.last_polled_at = _now()
    if not source.endpoint_url:
        source.last_error_code = "missing_endpoint"
        db.commit()
        return NoticePollRead(source_id=source.id, status="failed", error_code=source.last_error_code)
    try:
        data, content_type, final_url = fetch_public_http_resource(source.endpoint_url)
        items = _parse_feed(data, content_type=content_type, base_url=final_url, kind=source.kind)
        created_count, updated_count = ingest_notice_items_command(db, source=source, items=items)
    except (ValueError, json.JSONDecodeError, ET.ParseError):
        source.last_error_code = "source_unavailable_or_invalid"
        db.commit()
        return NoticePollRead(source_id=source.id, status="failed", error_code=source.last_error_code)
    source.last_success_at = _now()
    source.last_error_code = None
    db.commit()
    return NoticePollRead(
        source_id=source.id,
        status="succeeded",
        discovered_count=len(items),
        created_count=created_count,
        updated_count=updated_count,
    )


def poll_due_notice_sources() -> dict[str, int]:
    """Worker entry point for scheduled public-source polling."""

    from app.db import SessionLocal

    db = SessionLocal()
    completed = failed = skipped = 0
    try:
        now = _now()
        sources = list(
            db.scalars(
                select(NoticeSource).where(NoticeSource.is_active.is_(True), NoticeSource.kind.in_(_POLLABLE_KINDS))
            )
        )
        for source in sources:
            if source.last_polled_at is not None and source.last_polled_at + timedelta(minutes=source.polling_interval_minutes) > now:
                skipped += 1
                continue
            result = poll_notice_source(db, source=source)
            if result.status == "succeeded":
                completed += 1
            elif result.status == "failed":
                failed += 1
            else:
                skipped += 1
    finally:
        db.close()
    return {"completed": completed, "failed": failed, "skipped": skipped}


def update_notice_status_command(
    db: Session,
    *,
    notice_id: str,
    payload: NoticeStatusUpdate,
    current_user: CurrentUser,
) -> NoticeRead:
    notice = _notice_for_org(db, notice_id=notice_id, org_id=_org_id(current_user))
    notice.status = payload.status
    notice.saved_by_user_id = current_user.id if payload.status == "saved" else None
    if payload.status == "saved":
        queue_webhook_event(
            db,
            org_id=_org_id(current_user),
            event_type="radar.notice.saved",
            data=_notice_event_data(notice),
        )
    db.commit()
    refreshed = _notice_for_org(db, notice_id=notice_id, org_id=_org_id(current_user))
    return _notice_read(refreshed)


def convert_notice_to_project_command(
    db: Session,
    *,
    notice_id: str,
    payload: NoticeProjectConvert,
    current_user: CurrentUser,
) -> NoticeProjectConvertRead:
    notice = _notice_for_org(db, notice_id=notice_id, org_id=_org_id(current_user))
    if notice.converted_project_id:
        raise HTTPException(status_code=409, detail="This notice is already connected to a project")
    try:
        check_plan_limit(db, current_user.id, "projects", delta=1, org_id=_org_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    project = _create_project_with_defaults(
        db,
        ProjectCreate(name=payload.project_name or notice.title, scenario_package="bidpilot"),
        _org_id(current_user),
        current_user.id,
    )
    notice.status = "converted"
    notice.converted_project_id = project.id
    record_audit_event(
        db,
        project_id=project.id,
        event_type="radar.notice_converted",
        actor_type="user",
        actor_id=current_user.id,
        payload={"notice_id": notice.id, "source_id": notice.source_id},
    )
    queue_webhook_event(
        db,
        org_id=_org_id(current_user),
        event_type="radar.notice.converted",
        data={
            **_notice_event_data(notice),
            "project": {"id": project.id, "slug": project.slug, "name": project.name},
        },
    )
    db.commit()
    refreshed = _notice_for_org(db, notice_id=notice_id, org_id=_org_id(current_user))
    return NoticeProjectConvertRead(
        notice=_notice_read(refreshed),
        project_id=project.id,
        project_slug=project.slug,
    )


def _fallback_external_id(title: str, source_url: str, published_at: datetime | None) -> str:
    raw = "|".join((title.strip(), source_url.strip(), published_at.isoformat() if published_at else ""))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _notice_event_data(item: NoticeItem, *, matches: Iterable[NoticeMatch] | None = None) -> dict[str, object]:
    """Return a public, action-oriented notice snapshot for external systems."""

    active_matches = list(matches if matches is not None else item.matches)
    return {
        "notice": {
            "id": item.id,
            "title": item.title,
            "source_url": item.source_url,
            "buyer_name": item.buyer_name,
            "notice_type": item.notice_type,
            "region": item.region,
            "category": item.category,
            "budget_amount": item.budget_amount,
            "published_at": item.published_at.replace(tzinfo=UTC).isoformat() if item.published_at else None,
            "deadline_at": item.deadline_at.replace(tzinfo=UTC).isoformat() if item.deadline_at else None,
            "status": item.status,
        },
        "matches": [
            {
                "subscription_id": match.subscription_id,
                "subscription_name": match.subscription.name if match.subscription is not None else None,
                "score": match.score,
                "reasons": list(match.reasons_json or []),
            }
            for match in active_matches
        ],
    }


def _match_subscription(item: NoticeItem, subscription: NoticeSubscription) -> tuple[int, list[str]] | None:
    keywords = [value.casefold() for value in subscription.keywords_json or []]
    regions = [value.casefold() for value in subscription.regions_json or []]
    categories = [value.casefold() for value in subscription.categories_json or []]
    haystack = " ".join(filter(None, [item.title, item.buyer_name, item.summary, item.region, item.category])).casefold()
    score = 0
    reasons: list[str] = []
    matched_keywords = [value for value in subscription.keywords_json or [] if value.casefold() in haystack]
    if keywords:
        if not matched_keywords:
            return None
        score += min(70, 42 + 7 * len(matched_keywords))
        reasons.append(f"关键词命中：{'、'.join(matched_keywords[:3])}")
    if regions:
        if item.region is None or item.region.casefold() not in regions:
            return None
        score += 15
        reasons.append(f"地区匹配：{item.region}")
    if categories:
        if item.category is None or item.category.casefold() not in categories:
            return None
        score += 15
        reasons.append(f"类别匹配：{item.category}")
    if subscription.budget_min is not None or subscription.budget_max is not None:
        if item.budget_amount is None:
            return None
        if subscription.budget_min is not None and item.budget_amount < subscription.budget_min:
            return None
        if subscription.budget_max is not None and item.budget_amount > subscription.budget_max:
            return None
        score += 10
        reasons.append("预算范围匹配")
    if not reasons:
        return 50, ["订阅未设置筛选条件"]
    return min(score, 100), reasons


def _recompute_matches_for_notice(db: Session, item: NoticeItem) -> None:
    subscriptions = list(
        db.scalars(
            select(NoticeSubscription).where(
                NoticeSubscription.org_id == item.org_id,
                NoticeSubscription.is_active.is_(True),
            )
        )
    )
    existing = {
        match.subscription_id: match
        for match in db.scalars(select(NoticeMatch).where(NoticeMatch.notice_id == item.id))
    }
    active_ids: set[str] = set()
    for subscription in subscriptions:
        matched = _match_subscription(item, subscription)
        if matched is None:
            continue
        active_ids.add(subscription.id)
        score, reasons = matched
        match = existing.get(subscription.id)
        if match is None:
            db.add(NoticeMatch(notice_id=item.id, subscription_id=subscription.id, score=score, reasons_json=reasons))
        else:
            match.score = score
            match.reasons_json = reasons
    for subscription_id, match in existing.items():
        if subscription_id not in active_ids:
            db.delete(match)


def _recompute_matches_for_subscription(db: Session, subscription: NoticeSubscription) -> None:
    items = list(db.scalars(select(NoticeItem).where(NoticeItem.org_id == subscription.org_id)))
    for item in items:
        _recompute_matches_for_notice(db, item)


def _parse_feed(data: bytes, *, content_type: str, base_url: str, kind: str) -> list[NoticeSourceIngestItem]:
    if kind == "json_feed" or "json" in content_type:
        return _parse_json_feed(data, base_url=base_url)
    return _parse_xml_feed(data, base_url=base_url)


def _parse_json_feed(data: bytes, *, base_url: str) -> list[NoticeSourceIngestItem]:
    decoded = json.loads(data.decode("utf-8"))
    raw_items: object
    if isinstance(decoded, list):
        raw_items = decoded
    elif isinstance(decoded, dict):
        raw_items = decoded.get("items") or decoded.get("results") or decoded.get("data") or []
    else:
        raise ValueError("JSON feed must contain a list of notice items")
    if not isinstance(raw_items, list):
        raise ValueError("JSON feed items must be a list")
    items: list[NoticeSourceIngestItem] = []
    for raw in raw_items[:200]:
        if not isinstance(raw, dict):
            continue
        title = _collapse(raw.get("title") or raw.get("name") or raw.get("headline"))
        link = _collapse(raw.get("url") or raw.get("link") or raw.get("source_url"), limit=2048)
        if not title or not link:
            continue
        items.append(
            NoticeSourceIngestItem(
                external_id=_collapse(raw.get("id") or raw.get("guid") or raw.get("external_id")),
                title=title,
                source_url=urljoin(base_url, link),
                buyer_name=_collapse(raw.get("buyer") or raw.get("buyer_name") or raw.get("purchaser") or raw.get("agency"), limit=255),
                notice_type=_normal_notice_type(raw.get("notice_type") or raw.get("type")),
                region=_collapse(raw.get("region"), limit=120),
                category=_collapse(raw.get("category"), limit=120),
                budget_amount=_number(raw.get("budget_amount") or raw.get("budget")),
                published_at=_naive_datetime(raw.get("published_at") or raw.get("published") or raw.get("date")),
                deadline_at=_naive_datetime(raw.get("deadline_at") or raw.get("deadline") or raw.get("closing_date")),
                summary=_strip_html(raw.get("summary") or raw.get("description")),
                source_snapshot={key: value for key, value in raw.items() if key in {"id", "title", "url", "link", "published_at", "deadline_at", "buyer", "category", "region"}},
            )
        )
    return items


def _parse_xml_feed(data: bytes, *, base_url: str) -> list[NoticeSourceIngestItem]:
    root = ET.fromstring(data)
    entries = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    items: list[NoticeSourceIngestItem] = []
    for entry in entries[:200]:
        title = _xml_text(entry, "title")
        link = _xml_link(entry)
        if not title or not link:
            continue
        items.append(
            NoticeSourceIngestItem(
                external_id=_xml_text(entry, "guid") or _xml_text(entry, "id"),
                title=title,
                source_url=urljoin(base_url, link),
                buyer_name=_xml_text(entry, "buyer") or _xml_text(entry, "author"),
                notice_type=_normal_notice_type(_xml_text(entry, "notice_type") or _xml_text(entry, "type")),
                region=_xml_text(entry, "region"),
                category=_xml_text(entry, "category"),
                budget_amount=_number(_xml_text(entry, "budget")),
                published_at=_naive_datetime(_xml_text(entry, "pubDate") or _xml_text(entry, "published") or _xml_text(entry, "updated")),
                deadline_at=_naive_datetime(_xml_text(entry, "deadline") or _xml_text(entry, "closing_date")),
                summary=_strip_html(_xml_text(entry, "description") or _xml_text(entry, "summary") or _xml_text(entry, "content")),
                source_snapshot={"title": title, "link": urljoin(base_url, link)},
            )
        )
    return items


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_text(entry: ET.Element, name: str) -> str | None:
    for child in entry.iter():
        if _local_name(child.tag).casefold() == name.casefold():
            return _collapse(child.text, limit=12000 if name in {"description", "summary", "content"} else 500)
    return None


def _xml_link(entry: ET.Element) -> str | None:
    for child in entry.iter():
        if _local_name(child.tag).casefold() != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return _collapse(href, limit=2048)
        if child.text:
            return _collapse(child.text, limit=2048)
    return None


def _normal_notice_type(value: object | None) -> str:
    normalized = (str(value or "other").strip().casefold().replace("-", "_") or "other")
    aliases = {"prequalification": "prequalification", "pre_qualification": "prequalification", "intention": "intent", "procurement_intent": "intent"}
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in _NOTICE_TYPES else "other"
