from __future__ import annotations

import hashlib
import hmac
import json

from sqlalchemy import delete, select

from app.auth.schemas import CurrentUser
from app.models import WebhookDelivery, WebhookEndpoint
from app.security.secrets import decrypt_secret
from app.webhooks.schemas import WebhookEndpointCreate
from app.webhooks.service import (
    create_webhook_endpoint_command,
    deliver_webhook_delivery,
    queue_webhook_event,
)


def _admin(org_id: str) -> CurrentUser:
    return CurrentUser(
        id="dev-user",
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=org_id,
        org_slug="default",
    )


def _cleanup(db, org_id: str) -> None:
    db.execute(delete(WebhookEndpoint).where(WebhookEndpoint.org_id == org_id))
    db.commit()


def test_webhook_event_is_signed_and_delivered_with_a_durable_record(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    from app.webhooks import service

    _cleanup(test_db, default_org_id)
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 204

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def post(self, url: str, *, content: bytes, headers: dict[str, str]):
            captured.update({"url": url, "content": content, "headers": headers})
            return FakeResponse()

    monkeypatch.setattr(service.httpx, "Client", FakeClient)
    try:
        created = create_webhook_endpoint_command(
            test_db,
            payload=WebhookEndpointCreate(
                name="招采自动化",
                target_url="https://automation.example.test/bidpilot/events",
                events=["radar.notice.matched"],
            ),
            current_user=_admin(default_org_id),
        )
        assert created.signing_secret.startswith("whsec_")
        assert created.endpoint.signing_secret_hint != created.signing_secret

        assert queue_webhook_event(
            test_db,
            org_id=default_org_id,
            event_type="radar.notice.matched",
            data={"notice": {"id": "notice-100", "title": "智慧交通采购"}, "matches": []},
        ) == 1
        test_db.commit()
        delivery = test_db.scalar(select(WebhookDelivery).where(WebhookDelivery.endpoint_id == created.endpoint.id))
        assert delivery is not None

        result = deliver_webhook_delivery(test_db, delivery_id=delivery.id)

        assert result.status == "delivered"
        assert result.attempt_count == 1
        assert result.last_http_status == 204
        assert captured["url"] == created.endpoint.target_url
        body = captured["content"]
        headers = captured["headers"]
        assert isinstance(body, bytes)
        assert isinstance(headers, dict)
        assert json.loads(body.decode("utf-8"))["type"] == "radar.notice.matched"
        assert headers["X-BidPilot-Event"] == "radar.notice.matched"
        endpoint = test_db.get(WebhookEndpoint, created.endpoint.id)
        assert endpoint is not None
        secret = decrypt_secret(endpoint.signing_secret_ciphertext)
        expected = hmac.new(
            secret.encode("utf-8"),
            headers["X-BidPilot-Timestamp"].encode("utf-8") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        assert headers["X-BidPilot-Signature"] == f"sha256={expected}"
    finally:
        _cleanup(test_db, default_org_id)


def test_retryable_http_failure_returns_delivery_to_pending(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    from app.webhooks import service

    _cleanup(test_db, default_org_id)

    class FakeResponse:
        status_code = 503

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(service.httpx, "Client", FakeClient)
    try:
        endpoint = create_webhook_endpoint_command(
            test_db,
            payload=WebhookEndpointCreate(
                name="临时不可用目标",
                target_url="https://automation.example.test/bidpilot/events",
                events=["radar.notice.saved"],
            ),
            current_user=_admin(default_org_id),
        ).endpoint
        queue_webhook_event(
            test_db,
            org_id=default_org_id,
            event_type="radar.notice.saved",
            data={"notice": {"id": "notice-200"}, "matches": []},
        )
        test_db.commit()
        delivery = test_db.scalar(select(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint.id))
        assert delivery is not None

        result = deliver_webhook_delivery(test_db, delivery_id=delivery.id)

        assert result.status == "pending"
        assert result.attempt_count == 1
        assert result.last_error_code == "http_503"
        assert result.available_at is not None
    finally:
        _cleanup(test_db, default_org_id)
