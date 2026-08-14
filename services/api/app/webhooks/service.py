"""Durable outbound webhook configuration and at-least-once delivery."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.schemas import CurrentUser
from app.db import SessionLocal
from app.documents.web_import import validate_public_http_url
from app.models import WebhookDelivery, WebhookEndpoint
from app.security.secrets import SecretConfigurationError, decrypt_secret, encrypt_secret, mask_secret

from .schemas import (
    WebhookDeliveryActionRead,
    WebhookDeliveryRead,
    WebhookEndpointCreate,
    WebhookEndpointCreateRead,
    WebhookEndpointRead,
    WebhookEndpointUpdate,
    WebhookEventType,
    WebhookOverviewRead,
    WebhookOverviewSummary,
)


SUPPORTED_EVENTS: tuple[WebhookEventType, ...] = (
    "radar.notice.matched",
    "radar.notice.saved",
    "radar.notice.converted",
)
_TERMINAL_STATUSES = {"delivered", "failed"}
_DELIVERY_LEASE = timedelta(minutes=2)
_HTTP_TIMEOUT = 10.0


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _org_id(current_user: CurrentUser) -> str:
    return current_user.org_id or "default"


def _require_org_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only organization admins can manage webhooks")


def _public_url(value: str) -> str:
    try:
        return validate_public_http_url(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _endpoint_for_org(db: Session, *, endpoint_id: str, org_id: str) -> WebhookEndpoint:
    endpoint = db.scalar(
        select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id, WebhookEndpoint.org_id == org_id)
    )
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    return endpoint


def _delivery_for_org(db: Session, *, delivery_id: str, org_id: str) -> WebhookDelivery:
    delivery = db.scalar(
        select(WebhookDelivery)
        .options(selectinload(WebhookDelivery.endpoint))
        .where(WebhookDelivery.id == delivery_id, WebhookDelivery.org_id == org_id)
    )
    if delivery is None:
        raise HTTPException(status_code=404, detail="Webhook delivery not found")
    return delivery


def _endpoint_read(endpoint: WebhookEndpoint) -> WebhookEndpointRead:
    return WebhookEndpointRead(
        id=endpoint.id,
        name=endpoint.name,
        target_url=endpoint.target_url,
        events=list(endpoint.events_json or []),  # type: ignore[arg-type]
        is_active=endpoint.is_active,
        signing_secret_hint=mask_secret(endpoint.signing_secret_ciphertext),
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


def _delivery_read(delivery: WebhookDelivery) -> WebhookDeliveryRead:
    return WebhookDeliveryRead(
        id=delivery.id,
        endpoint_id=delivery.endpoint_id,
        endpoint_name=delivery.endpoint.name if delivery.endpoint is not None else "已删除端点",
        event_type=delivery.event_type,
        status=delivery.status,  # type: ignore[arg-type]
        attempt_count=delivery.attempt_count,
        max_attempts=delivery.max_attempts,
        available_at=delivery.available_at,
        last_http_status=delivery.last_http_status,
        last_error_code=delivery.last_error_code,
        delivered_at=delivery.delivered_at,
        created_at=delivery.created_at,
        payload=dict(delivery.payload_json or {}),
    )


def list_webhook_overview_query(db: Session, *, current_user: CurrentUser) -> WebhookOverviewRead:
    _require_org_admin(current_user)
    org_id = _org_id(current_user)
    endpoints = list(
        db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.org_id == org_id).order_by(WebhookEndpoint.created_at.desc()))
    )
    deliveries = list(
        db.scalars(
            select(WebhookDelivery)
            .options(selectinload(WebhookDelivery.endpoint))
            .where(WebhookDelivery.org_id == org_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(80)
        )
    )
    return WebhookOverviewRead(
        summary=WebhookOverviewSummary(
            active_endpoint_count=sum(1 for endpoint in endpoints if endpoint.is_active),
            delivery_count=len(deliveries),
            failed_delivery_count=sum(1 for delivery in deliveries if delivery.status == "failed"),
            pending_delivery_count=sum(1 for delivery in deliveries if delivery.status in {"pending", "delivering"}),
        ),
        supported_events=list(SUPPORTED_EVENTS),
        endpoints=[_endpoint_read(endpoint) for endpoint in endpoints],
        deliveries=[_delivery_read(delivery) for delivery in deliveries],
    )


def create_webhook_endpoint_command(
    db: Session,
    *,
    payload: WebhookEndpointCreate,
    current_user: CurrentUser,
) -> WebhookEndpointCreateRead:
    _require_org_admin(current_user)
    secret = f"whsec_{secrets.token_urlsafe(32)}"
    try:
        encrypted_secret = encrypt_secret(secret)
    except SecretConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Webhook secret encryption is not configured") from exc
    endpoint = WebhookEndpoint(
        org_id=_org_id(current_user),
        name=payload.name,
        target_url=_public_url(payload.target_url),
        signing_secret_ciphertext=encrypted_secret,
        events_json=list(dict.fromkeys(payload.events)),
        created_by_user_id=current_user.id,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return WebhookEndpointCreateRead(endpoint=_endpoint_read(endpoint), signing_secret=secret)


def update_webhook_endpoint_command(
    db: Session,
    *,
    endpoint_id: str,
    payload: WebhookEndpointUpdate,
    current_user: CurrentUser,
) -> WebhookEndpointRead:
    _require_org_admin(current_user)
    endpoint = _endpoint_for_org(db, endpoint_id=endpoint_id, org_id=_org_id(current_user))
    if payload.name is not None:
        endpoint.name = payload.name
    if payload.target_url is not None:
        endpoint.target_url = _public_url(payload.target_url)
    if payload.events is not None:
        endpoint.events_json = list(dict.fromkeys(payload.events))
    if payload.is_active is not None:
        endpoint.is_active = payload.is_active
    db.commit()
    db.refresh(endpoint)
    return _endpoint_read(endpoint)


def delete_webhook_endpoint_command(db: Session, *, endpoint_id: str, current_user: CurrentUser) -> None:
    _require_org_admin(current_user)
    endpoint = _endpoint_for_org(db, endpoint_id=endpoint_id, org_id=_org_id(current_user))
    db.delete(endpoint)
    db.commit()


def rotate_webhook_secret_command(
    db: Session,
    *,
    endpoint_id: str,
    current_user: CurrentUser,
) -> WebhookEndpointCreateRead:
    _require_org_admin(current_user)
    endpoint = _endpoint_for_org(db, endpoint_id=endpoint_id, org_id=_org_id(current_user))
    secret = f"whsec_{secrets.token_urlsafe(32)}"
    try:
        endpoint.signing_secret_ciphertext = encrypt_secret(secret)
    except SecretConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Webhook secret encryption is not configured") from exc
    db.commit()
    db.refresh(endpoint)
    return WebhookEndpointCreateRead(endpoint=_endpoint_read(endpoint), signing_secret=secret)


def queue_webhook_event(
    db: Session,
    *,
    org_id: str,
    event_type: WebhookEventType,
    data: dict[str, Any],
) -> int:
    """Append eligible delivery intents inside the caller's business transaction."""

    endpoints = list(
        db.scalars(
            select(WebhookEndpoint).where(
                WebhookEndpoint.org_id == org_id,
                WebhookEndpoint.is_active.is_(True),
            )
        )
    )
    created = 0
    for endpoint in endpoints:
        if event_type not in set(endpoint.events_json or []):
            continue
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            org_id=org_id,
            event_type=event_type,
            payload_json={},
        )
        db.add(delivery)
        db.flush()
        delivery.payload_json = {
            "id": delivery.id,
            "type": event_type,
            "created_at": _now().replace(tzinfo=UTC).isoformat(),
            "data": data,
        }
        created += 1
    return created


def _queue_test_delivery(db: Session, *, endpoint: WebhookEndpoint) -> WebhookDelivery:
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        org_id=endpoint.org_id,
        event_type="webhook.test",
        payload_json={},
    )
    db.add(delivery)
    db.flush()
    delivery.payload_json = {
        "id": delivery.id,
        "type": "webhook.test",
        "created_at": _now().replace(tzinfo=UTC).isoformat(),
        "data": {"message": "BidPilot webhook endpoint verification"},
    }
    return delivery


def test_webhook_endpoint_command(
    db: Session,
    *,
    endpoint_id: str,
    current_user: CurrentUser,
) -> WebhookDeliveryActionRead:
    _require_org_admin(current_user)
    endpoint = _endpoint_for_org(db, endpoint_id=endpoint_id, org_id=_org_id(current_user))
    if not endpoint.is_active:
        raise HTTPException(status_code=409, detail="Enable the webhook endpoint before sending a test")
    delivery = _queue_test_delivery(db, endpoint=endpoint)
    db.commit()
    delivered = deliver_webhook_delivery(db, delivery_id=delivery.id)
    return WebhookDeliveryActionRead(delivery=_delivery_read(delivered))


def retry_webhook_delivery_command(
    db: Session,
    *,
    delivery_id: str,
    current_user: CurrentUser,
) -> WebhookDeliveryActionRead:
    _require_org_admin(current_user)
    delivery = _delivery_for_org(db, delivery_id=delivery_id, org_id=_org_id(current_user))
    if delivery.endpoint is None or not delivery.endpoint.is_active:
        raise HTTPException(status_code=409, detail="Enable the webhook endpoint before retrying a delivery")
    delivery.status = "pending"
    delivery.available_at = _now()
    delivery.lease_expires_at = None
    delivery.last_error_code = None
    db.commit()
    delivered = deliver_webhook_delivery(db, delivery_id=delivery.id)
    return WebhookDeliveryActionRead(delivery=_delivery_read(delivered))


def _claim_delivery(db: Session, *, delivery_id: str) -> WebhookDelivery | None:
    current = _now()
    delivery = db.scalar(
        select(WebhookDelivery)
        .options(selectinload(WebhookDelivery.endpoint))
        .where(WebhookDelivery.id == delivery_id)
        .with_for_update()
    )
    if delivery is None or delivery.status in _TERMINAL_STATUSES:
        return None
    if delivery.status == "pending":
        if delivery.available_at > current:
            return None
    elif delivery.status == "delivering":
        if delivery.lease_expires_at is not None and delivery.lease_expires_at > current:
            return None
    else:
        return None
    if delivery.endpoint is None or not delivery.endpoint.is_active:
        delivery.status = "failed"
        delivery.lease_expires_at = None
        delivery.last_error_code = "endpoint_inactive"
        db.commit()
        return delivery
    delivery.status = "delivering"
    delivery.attempt_count += 1
    delivery.lease_expires_at = current + _DELIVERY_LEASE
    delivery.last_error_code = None
    db.commit()
    return delivery


def _signed_headers(delivery: WebhookDelivery, secret: str, body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("utf-8") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "User-Agent": "BidPilot-Webhooks/1.0",
        "X-BidPilot-Event": delivery.event_type,
        "X-BidPilot-Delivery": delivery.id,
        "X-BidPilot-Timestamp": timestamp,
        "X-BidPilot-Signature": f"sha256={signature}",
    }


def _retryable_status(status_code: int) -> bool:
    return status_code == 408 or status_code == 409 or status_code == 425 or status_code == 429 or status_code >= 500


def _mark_delivery_failure(
    db: Session,
    *,
    delivery_id: str,
    error_code: str,
    http_status: int | None = None,
    retryable: bool,
) -> WebhookDelivery:
    delivery = db.scalar(
        select(WebhookDelivery)
        .options(selectinload(WebhookDelivery.endpoint))
        .where(WebhookDelivery.id == delivery_id)
        .with_for_update()
    )
    if delivery is None:
        raise RuntimeError("Webhook delivery disappeared")
    delivery.last_http_status = http_status
    delivery.last_error_code = error_code
    delivery.lease_expires_at = None
    if retryable and delivery.attempt_count < delivery.max_attempts:
        delay_seconds = min(900, 15 * (2 ** max(0, delivery.attempt_count - 1)))
        delivery.status = "pending"
        delivery.available_at = _now() + timedelta(seconds=delay_seconds)
    else:
        delivery.status = "failed"
    db.commit()
    return delivery


def _mark_delivery_succeeded(db: Session, *, delivery_id: str, http_status: int) -> WebhookDelivery:
    delivery = db.scalar(
        select(WebhookDelivery)
        .options(selectinload(WebhookDelivery.endpoint))
        .where(WebhookDelivery.id == delivery_id)
        .with_for_update()
    )
    if delivery is None:
        raise RuntimeError("Webhook delivery disappeared")
    delivery.status = "delivered"
    delivery.last_http_status = http_status
    delivery.last_error_code = None
    delivery.lease_expires_at = None
    delivery.delivered_at = _now()
    db.commit()
    return delivery


def deliver_webhook_delivery(db: Session, *, delivery_id: str) -> WebhookDelivery:
    """Deliver a single record after leasing it. Safe to call from API or worker."""

    delivery = _claim_delivery(db, delivery_id=delivery_id)
    if delivery is None:
        existing = db.scalar(
            select(WebhookDelivery)
            .options(selectinload(WebhookDelivery.endpoint))
            .where(WebhookDelivery.id == delivery_id)
        )
        if existing is None:
            raise HTTPException(status_code=404, detail="Webhook delivery not found")
        return existing
    if delivery.status == "failed":
        return delivery
    endpoint = delivery.endpoint
    if endpoint is None:
        return _mark_delivery_failure(
            db, delivery_id=delivery.id, error_code="endpoint_missing", retryable=False
        )
    try:
        target_url = validate_public_http_url(endpoint.target_url)
        secret = decrypt_secret(endpoint.signing_secret_ciphertext)
    except (ValueError, SecretConfigurationError):
        return _mark_delivery_failure(
            db, delivery_id=delivery.id, error_code="endpoint_configuration_invalid", retryable=False
        )
    body = json.dumps(delivery.payload_json, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=False, trust_env=False) as client:
            response = client.post(target_url, content=body, headers=_signed_headers(delivery, secret, body))
    except httpx.TimeoutException:
        return _mark_delivery_failure(
            db, delivery_id=delivery.id, error_code="delivery_timeout", retryable=True
        )
    except httpx.HTTPError:
        return _mark_delivery_failure(
            db, delivery_id=delivery.id, error_code="delivery_unavailable", retryable=True
        )
    if 200 <= response.status_code < 300:
        return _mark_delivery_succeeded(db, delivery_id=delivery.id, http_status=response.status_code)
    return _mark_delivery_failure(
        db,
        delivery_id=delivery.id,
        error_code=f"http_{response.status_code}",
        http_status=response.status_code,
        retryable=_retryable_status(response.status_code),
    )


def deliver_due_webhook_deliveries(*, limit: int = 100) -> dict[str, int]:
    """Worker recovery loop for pending deliveries and expired leases."""

    current = _now()
    db = SessionLocal()
    try:
        delivery_ids = list(
            db.scalars(
                select(WebhookDelivery.id)
                .where(
                    or_(
                        and_(WebhookDelivery.status == "pending", WebhookDelivery.available_at <= current),
                        and_(
                            WebhookDelivery.status == "delivering",
                            WebhookDelivery.lease_expires_at.is_not(None),
                            WebhookDelivery.lease_expires_at <= current,
                        ),
                    )
                )
                .order_by(WebhookDelivery.available_at.asc(), WebhookDelivery.created_at.asc())
                .limit(limit)
            )
        )
    finally:
        db.close()

    delivered = 0
    failed = 0
    deferred = 0
    for delivery_id in delivery_ids:
        work_db = SessionLocal()
        try:
            result = deliver_webhook_delivery(work_db, delivery_id=delivery_id)
            if result.status == "delivered":
                delivered += 1
            elif result.status == "failed":
                failed += 1
            else:
                deferred += 1
        except Exception:
            work_db.rollback()
            failed += 1
        finally:
            work_db.close()
    return {"delivered": delivered, "failed": failed, "deferred": deferred}
