from __future__ import annotations

from sqlalchemy import delete, select

from app.auth.schemas import CurrentUser
from app.models import (
    AuditEvent,
    Deliverable,
    DeliverableSection,
    NoticeItem,
    NoticeMatch,
    NoticeSource,
    NoticeSubscription,
    Project,
    ProjectMember,
)
from app.radar.schemas import NoticeProjectConvert, NoticeSourceCreate, NoticeStatusUpdate, NoticeSubscriptionCreate
from app.radar.service import (
    convert_notice_to_project_command,
    create_notice_source_command,
    create_subscription_command,
    list_radar_overview_query,
    poll_notice_source_command,
    update_notice_status_command,
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


def _cleanup_radar(db, org_id: str) -> None:
    project_ids = list(db.scalars(delete(NoticeItem).returning(NoticeItem.converted_project_id)))
    db.execute(delete(NoticeMatch))
    db.execute(delete(NoticeSubscription).where(NoticeSubscription.org_id == org_id))
    db.execute(delete(NoticeSource).where(NoticeSource.org_id == org_id))
    for project_id in filter(None, project_ids):
        db.execute(delete(AuditEvent).where(AuditEvent.project_id == project_id))
        deliverable_ids = list(db.scalars(select(Deliverable.id).where(Deliverable.project_id == project_id)))
        for deliverable_id in deliverable_ids:
            db.execute(delete(DeliverableSection).where(DeliverableSection.deliverable_id == deliverable_id))
        db.execute(delete(Deliverable).where(Deliverable.project_id == project_id))
        db.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
        db.execute(delete(Project).where(Project.id == project_id))
    db.commit()


def test_json_feed_creates_deduplicated_recommendations_and_converts_to_project(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    from app.radar import service

    _cleanup_radar(test_db, default_org_id)
    user = _admin(default_org_id)
    payload = '''{
      "items": [{
        "id": "external-1001",
        "title": "城市交通信号系统投标公告",
        "url": "https://procurement.example.test/notices/1001",
        "buyer": "城市交通局",
        "type": "tender",
        "region": "上海",
        "category": "智慧交通",
        "budget": 1200000,
        "published_at": "2026-08-08T09:00:00Z",
        "deadline_at": "2026-08-16T09:00:00Z",
        "summary": "建设城市交通信号优化与平台服务。"
      }]
    }'''.encode("utf-8")
    monkeypatch.setattr(
        service,
        "fetch_public_http_resource",
        lambda _url: (payload, "application/json", "https://procurement.example.test/feed.json"),
    )

    try:
        subscription = create_subscription_command(
            test_db,
            payload=NoticeSubscriptionCreate(name="智慧交通", keywords=["交通", "信号"], regions=["上海"]),
            current_user=user,
        )
        source = create_notice_source_command(
            test_db,
            payload=NoticeSourceCreate(
                name="公开采购 JSON Feed",
                kind="json_feed",
                endpoint_url="https://procurement.example.test/feed.json",
            ),
            current_user=user,
        )

        first = poll_notice_source_command(test_db, source_id=source.id, current_user=user)
        second = poll_notice_source_command(test_db, source_id=source.id, current_user=user)

        assert first.status == "succeeded"
        assert (first.discovered_count, first.created_count, first.updated_count) == (1, 1, 0)
        assert (second.discovered_count, second.created_count, second.updated_count) == (1, 0, 1)

        overview = list_radar_overview_query(test_db, current_user=user)
        assert overview.summary.recommended_count == 1
        assert overview.subscriptions[0].id == subscription.id
        assert overview.notices[0].matches[0].score >= 57
        assert "关键词命中" in overview.notices[0].matches[0].reasons[0]

        saved = update_notice_status_command(
            test_db,
            notice_id=overview.notices[0].id,
            payload=NoticeStatusUpdate(status="saved"),
            current_user=user,
        )
        assert saved.status == "saved"

        converted = convert_notice_to_project_command(
            test_db,
            notice_id=saved.id,
            payload=NoticeProjectConvert(project_name="城市交通信号系统响应"),
            current_user=user,
        )
        assert converted.notice.status == "converted"
        assert converted.notice.converted_project_id == converted.project_id
        assert test_db.get(Project, converted.project_id) is not None
    finally:
        _cleanup_radar(test_db, default_org_id)
