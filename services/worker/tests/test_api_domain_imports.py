"""Keep worker-only images able to run scheduled domain tasks."""


def test_worker_can_import_radar_and_webhook_services() -> None:
    from app.radar.service import poll_due_notice_sources
    from app.webhooks.service import deliver_due_webhook_deliveries

    assert callable(poll_due_notice_sources)
    assert callable(deliver_due_webhook_deliveries)
