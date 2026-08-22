"""Provision an isolated, visual demo workspace for an existing account.

This is deliberately idempotent. It never modifies the account's existing
projects or memberships; it creates (or reuses) the account's personal
workspace and makes it the active workspace before seeding the demo records.

Usage:
    uv run --directory services/api python ../../scripts/seed_workspace_demo.py \
        --email leho@bidpilot.local
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

from app.auth.schemas import CurrentUser
from app.auth.service import check_plan_limit
from app.db import SessionLocal
from app.models import (
    BidRequirementProfile,
    Bundle,
    Deliverable,
    DeliverableSection,
    Evidence,
    KnowledgeChunk,
    NoticeItem,
    NoticeMatch,
    NoticeSource,
    NoticeSubscription,
    ParsedAsset,
    Project,
    RequirementEvidenceLink,
    RequirementItem,
    RuntimeEvent,
    RuntimeRun,
    SectionVersion,
    SourceDocument,
    User,
)
from app.organizations.service import (
    ensure_personal_workspace_for_user_command,
    switch_user_org_command,
)
from app.entitlements.service import upsert_organization_subscription_command
from app.projects.demo import create_demo_project_command
from app.projects.demo_data import BUILTIN_DEMO_STORAGE_PREFIX, DEMO_DOCUMENTS
from app.projects.schemas import ProjectCreate
from app.projects.service import _create_project_with_defaults


WORKSPACE_NAME = "Leho 的 BidPilot 工作区"
COMPLETED_PROJECT_NAME = "演示 · 园区综合能源管理平台响应"
ACTIVE_PROJECT_NAME = "演示 · 区域医疗数据治理服务"
RADAR_SOURCE_NAME = "演示数据 · 本地招采信号"
RADAR_SUBSCRIPTION_NAME = "华东政务 AI 与数据治理"
DELIVERABLE_TITLE = "区域医疗数据治理服务投标响应文件"


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def current_user(user: User, org_id: str, org_slug: str) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        plan="enterprise",
        email_verified=user.email_verified,
        disabled=user.disabled,
        org_id=org_id,
        org_slug=org_slug,
    )


def find_project(db: Session, *, org_id: str, name: str) -> Project | None:
    return db.scalar(select(Project).where(Project.org_id == org_id, Project.name == name))


def seed_project_fixture(
    db: Session,
    *,
    user: User,
    org_id: str,
    name: str,
    status: str,
    requirements: list[dict[str, object]],
) -> Project:
    existing = find_project(db, org_id=org_id, name=name)
    if existing is not None:
        return existing

    check_plan_limit(db, user.id, "projects", delta=1, org_id=org_id)
    project = _create_project_with_defaults(
        db,
        ProjectCreate(name=name, scenario_package="bidpilot"),
        org_id,
        user.id,
    )
    project.status = status
    db.flush()

    document_definition = DEMO_DOCUMENTS[0]
    content = document_definition.content
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    bundle = Bundle(
        project_id=project.id,
        label="公开公告与项目资料（演示）",
        source_type="agent_remote_demo",
        ingest_status="ingested",
    )
    db.add(bundle)
    db.flush()
    document = SourceDocument(
        bundle_id=bundle.id,
        storage_key=f"{BUILTIN_DEMO_STORAGE_PREFIX}{document_definition.key}",
        source_url=f"https://example.com/bidpilot-demo/{project.slug}.md",
        mime_type="text/markdown; charset=utf-8",
        checksum=content_hash,
        original_filename=document_definition.filename,
        page_count=1,
        parse_status="parsed",
        parser_name="bidpilot_builtin_demo",
        parser_version="1",
        parsed_at=utcnow(),
        index_status="degraded",
        index_error_code="builtin_demo_sparse_only",
        version_number=1,
    )
    db.add(document)
    db.flush()
    db.add(
        ParsedAsset(
            source_document_id=document.id,
            parser_name="bidpilot_builtin_demo",
            parser_version="1",
            content_json={"text": content, "source_kind": "workspace_demo"},
            layout_json={"format": "markdown", "source_kind": "workspace_demo"},
        )
    )
    db.add(
        KnowledgeChunk(
            project_id=project.id,
            source_document_id=document.id,
            chunk_index=0,
            chunk_key=hashlib.sha256(f"{document.id}:{content_hash}:0".encode("utf-8")).hexdigest(),
            content=content,
            metadata_json={"source_kind": "workspace_demo", "document": document.original_filename},
            retrieval_text=content,
            embedding_status="not_indexed",
        )
    )

    for index, spec in enumerate(requirements):
        coverage = str(spec["coverage"])
        evidence_status = str(spec["evidence_status"])
        assigned = bool(spec.get("assigned", True))
        requirement = RequirementItem(
            project_id=project.id,
            section_key=str(spec["section"]),
            requirement_text=str(spec["text"]),
            original_text=str(spec["text"]),
            source_document_id=document.id,
            source_locator_json={
                "source_kind": "workspace_demo",
                "document": document.original_filename,
                "chunk_index": 0,
            },
            priority="high" if bool(spec.get("mandatory", True)) else "medium",
            status="confirmed",
            owner_user_id=user.id if assigned else None,
            reviewer_user_id=user.id if coverage == "covered" else None,
            due_at=utcnow() + timedelta(days=7 + index),
            verification_status="verified" if coverage == "covered" else "unverified",
            extraction_confidence=0.92,
        )
        db.add(requirement)
        db.flush()
        db.add(
            BidRequirementProfile(
                requirement_id=requirement.id,
                bid_category=str(spec.get("category", "technical")),
                is_mandatory=bool(spec.get("mandatory", True)),
                score_weight=float(spec.get("weight", 8)),
                risk_level="high" if coverage != "covered" else "normal",
                coverage_status=coverage,
                evidence_status=evidence_status,
                deadline_at=utcnow() + timedelta(days=14),
                submission_metadata_json={"source_kind": "workspace_demo"},
            )
        )
        if evidence_status != "missing":
            evidence = Evidence(
                project_id=project.id,
                source_document_id=document.id,
                quote_text=f"演示证据：{spec['text']}",
                locator_json={"source_kind": "workspace_demo", "chunk_index": 0},
                confidence=0.96 if evidence_status == "sufficient" else 0.68,
            )
            db.add(evidence)
            db.flush()
            db.add(
                RequirementEvidenceLink(
                    requirement_id=requirement.id,
                    evidence_id=evidence.id,
                    relation_type="supports",
                    verification_status="verified" if coverage == "covered" else "unverified",
                    created_by_user_id=user.id,
                )
            )

    db.flush()
    return project


def seed_runtime_runs(db: Session, *, user: User, org_id: str, project: Project) -> None:
    approval_key = "workspace-demo-approval-v1"
    approval_run = db.scalar(
        select(RuntimeRun).where(RuntimeRun.org_id == org_id, RuntimeRun.idempotency_key == approval_key)
    )
    if approval_run is None:
        approval_run = RuntimeRun(
            kind="workflow_bridge",
            status="awaiting_approval",
            org_id=org_id,
            user_id=user.id,
            project_id=project.id,
            engine="langgraph",
            trace_id="workspace-demo-approval-trace",
            idempotency_key=approval_key,
            model="demo-control-plane",
            policy_snapshot_json={"source_kind": "workspace_demo"},
            input_json={"goal": "确认医疗数据治理服务的交付范围"},
            result_json={"next_step": "等待团队确认关键交付边界"},
            started_at=utcnow() - timedelta(minutes=12),
        )
        db.add(approval_run)
        db.flush()
        db.add_all(
            [
                RuntimeEvent(
                    run_id=approval_run.id,
                    sequence=1,
                    event_type="run.started",
                    public_summary="已建立区域医疗数据治理服务的响应计划。",
                    payload_json={"source_kind": "workspace_demo"},
                ),
                RuntimeEvent(
                    run_id=approval_run.id,
                    sequence=2,
                    event_type="approval.requested",
                    public_summary="范围与交付节奏需要负责人确认。",
                    payload_json={"source_kind": "workspace_demo"},
                ),
            ]
        )

    completed_key = "workspace-demo-completed-v1"
    if db.scalar(
        select(RuntimeRun).where(
            RuntimeRun.org_id == org_id,
            RuntimeRun.idempotency_key == completed_key,
        )
    ) is None:
        db.add(
            RuntimeRun(
                kind="assistant_turn",
                status="succeeded",
                org_id=org_id,
                user_id=user.id,
                project_id=project.id,
                engine="harness",
                trace_id="workspace-demo-completed-trace",
                idempotency_key=completed_key,
                model="demo-control-plane",
                policy_snapshot_json={"source_kind": "workspace_demo"},
                input_json={"goal": "汇总资料与要求基线"},
                result_json={"summary": "已识别 5 条要求并生成待确认事项。"},
                started_at=utcnow() - timedelta(hours=2),
                finished_at=utcnow() - timedelta(hours=2) + timedelta(minutes=3),
            )
        )


def seed_deliverable(db: Session, *, project: Project) -> Deliverable:
    deliverable = db.scalar(
        select(Deliverable).where(
            Deliverable.project_id == project.id,
            Deliverable.title == DELIVERABLE_TITLE,
        )
    )
    if deliverable is None:
        deliverable = Deliverable(
            project_id=project.id,
            type="proposal",
            title=DELIVERABLE_TITLE,
            status="in_review",
            export_status="not_exported",
        )
        db.add(deliverable)
        db.flush()

    sections = [
        (
            "executive-summary",
            "项目理解与总体响应",
            "本项目以区域医疗数据治理为主线，建立标准、质量、安全和运营一体化体系。投标人将以可追溯的数据目录为基础，分阶段完成现状调研、标准落地、系统对接与试点验收。",
        ),
        (
            "technical-approach",
            "技术方案与实施路径",
            "技术路线覆盖医疗数据目录、主数据管理、质量规则、交换共享与安全审计。实施采用小步验证方式，先完成重点系统接入与指标校验，再逐步扩展到区域协同场景。",
        ),
        (
            "delivery-plan",
            "交付计划与质量保障",
            "交付分为启动与调研、方案设计、平台实施、联调试运行、验收移交五个阶段。每个阶段均保留评审记录、问题清单和验收证据，确保交付过程可审计、可恢复。",
        ),
        (
            "service-commitment",
            "运维服务与风险控制",
            "项目建立分级响应、持续监测和应急演练机制。对接口变更、数据质量波动及安全事件设置负责人、处置时限和复盘要求，并通过月度服务报告持续改进。",
        ),
    ]
    for sort_order, (section_key, title, content) in enumerate(sections):
        section = db.scalar(
            select(DeliverableSection).where(
                DeliverableSection.deliverable_id == deliverable.id,
                DeliverableSection.section_key == section_key,
            )
        )
        if section is None:
            section = DeliverableSection(
                deliverable_id=deliverable.id,
                section_key=section_key,
                title=title,
                status="approved",
                assignee_type="ai",
                sort_order=sort_order,
            )
            db.add(section)
            db.flush()
        version = db.scalar(
            select(SectionVersion).where(
                SectionVersion.deliverable_section_id == section.id,
                SectionVersion.version_number == 1,
            )
        )
        if version is None:
            version = SectionVersion(
                deliverable_section_id=section.id,
                version_number=1,
                content_json={"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": content}]}]},
                content_markdown=content,
                created_by_actor="ai",
                generation_iteration=1,
            )
            db.add(version)
            db.flush()
        section.approved_version_id = version.id
        section.status = "approved"
    db.flush()
    return deliverable


def seed_radar(db: Session, *, user: User, org_id: str) -> None:
    source = db.scalar(
        select(NoticeSource).where(NoticeSource.org_id == org_id, NoticeSource.name == RADAR_SOURCE_NAME)
    )
    if source is None:
        source = NoticeSource(
            org_id=org_id,
            name=RADAR_SOURCE_NAME,
            kind="webhook",
            endpoint_url=None,
            is_active=True,
            polling_interval_minutes=60,
            last_polled_at=utcnow(),
            last_success_at=utcnow(),
            created_by_user_id=user.id,
        )
        db.add(source)
        db.flush()

    subscription = db.scalar(
        select(NoticeSubscription).where(
            NoticeSubscription.org_id == org_id,
            NoticeSubscription.name == RADAR_SUBSCRIPTION_NAME,
        )
    )
    if subscription is None:
        subscription = NoticeSubscription(
            org_id=org_id,
            name=RADAR_SUBSCRIPTION_NAME,
            keywords_json=["数据治理", "人工智能", "政务服务"],
            regions_json=["上海", "江苏", "浙江"],
            categories_json=["软件服务", "数字政府"],
            budget_min=1_000_000,
            budget_max=30_000_000,
            is_active=True,
            created_by_user_id=user.id,
        )
        db.add(subscription)
        db.flush()

    notices = [
        ("城市运行管理服务平台建设项目", "上海市城市运行管理中心", "上海", "数字政府", 12_800_000, "tender", "saved"),
        ("区域医疗数据治理与互联互通服务", "江苏省卫生信息中心", "江苏", "医疗信息化", 8_600_000, "tender", "new"),
        ("政务服务智能问答与知识运营采购", "杭州市政务服务管理办公室", "浙江", "人工智能", 4_200_000, "intent", "new"),
        ("城市安全风险综合监测预警项目", "宁波市应急管理局", "浙江", "公共安全", 9_500_000, "tender", "saved"),
        ("社区治理数据中台运维服务", "苏州市民政局", "江苏", "数据治理", 3_800_000, "tender", "new"),
        ("营商环境智能分析应用建设", "上海市发展和改革委员会", "上海", "数据分析", 5_600_000, "rfi", "new"),
        ("政务云资源运营支撑服务", "无锡市大数据管理局", "江苏", "云服务", 7_200_000, "tender", "new"),
        ("基层治理 AI 助手试点采购", "嘉兴市社会治理综合指挥中心", "浙江", "人工智能", 2_600_000, "intent", "new"),
        ("公共数据授权运营咨询服务", "上海市数据局", "上海", "数据治理", 1_900_000, "rfi", "new"),
    ]
    now = utcnow()
    for index, (title, buyer, region, category, budget, notice_type, status) in enumerate(notices):
        external_id = f"leho-workspace-demo-{index + 1}"
        notice = db.scalar(
            select(NoticeItem).where(NoticeItem.source_id == source.id, NoticeItem.external_id == external_id)
        )
        if notice is None:
            notice = NoticeItem(
                org_id=org_id,
                source_id=source.id,
                external_id=external_id,
                title=title,
                buyer_name=buyer,
                notice_type=notice_type,
                region=region,
                category=category,
                budget_amount=budget,
                published_at=now - timedelta(days=(index * 2) % 14),
                deadline_at=now + timedelta(days=3 + index),
                source_url=f"https://example.com/bidpilot-demo/radar/{index + 1}",
                summary="本地注入的演示机会，用于展示招采雷达的趋势、匹配理由和处理队列。",
                source_snapshot_json={"source_kind": "workspace_demo"},
                status=status,
                saved_by_user_id=user.id if status == "saved" else None,
            )
            db.add(notice)
            db.flush()
        match = db.scalar(
            select(NoticeMatch).where(
                NoticeMatch.notice_id == notice.id,
                NoticeMatch.subscription_id == subscription.id,
            )
        )
        if match is None:
            db.add(
                NoticeMatch(
                    notice_id=notice.id,
                    subscription_id=subscription.id,
                    score=95 - index * 3,
                    reasons_json=[f"命中关键词：{category}", f"关注区域：{region}"],
                )
            )


def seed(email: str) -> dict[str, object]:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email.ilike(email)))
        if user is None:
            raise ValueError(f"Account not found: {email}")

        workspace, _created = ensure_personal_workspace_for_user_command(
            db,
            user_id=user.id,
            actor_user_id=user.id,
            reason="workspace_demo_seed",
            commit=False,
        )
        workspace.name = WORKSPACE_NAME
        switch_user_org_command(db, user.id, workspace.id, commit=False)
        db.commit()
        db.refresh(user)
        db.refresh(workspace)

        upsert_organization_subscription_command(
            db,
            org_id=workspace.id,
            billing_owner_user_id=user.id,
            plan="enterprise",
            status="active",
            seat_limit=10,
            billable_seat_count=1,
            commit=False,
        )

        actor = current_user(user, workspace.id, workspace.slug)
        demo_project, _created_demo = create_demo_project_command(db, actor)
        completed_project = seed_project_fixture(
            db,
            user=user,
            org_id=workspace.id,
            name=COMPLETED_PROJECT_NAME,
            status="completed",
            requirements=[
                {"section": "technical", "text": "完成园区能耗数据接入与统一指标建模。", "coverage": "covered", "evidence_status": "sufficient", "weight": 10},
                {"section": "delivery", "text": "按计划完成部署、联调、试运行和验收支持。", "coverage": "covered", "evidence_status": "sufficient", "weight": 8},
                {"section": "security", "text": "提供账号权限、审计日志和数据访问控制。", "coverage": "covered", "evidence_status": "sufficient", "weight": 8},
                {"section": "service", "text": "提供持续运维、巡检与问题响应机制。", "coverage": "covered", "evidence_status": "sufficient", "weight": 6},
            ],
        )
        active_project = seed_project_fixture(
            db,
            user=user,
            org_id=workspace.id,
            name=ACTIVE_PROJECT_NAME,
            status="active",
            requirements=[
                {"section": "data", "text": "建立区域医疗数据目录、标准与质量治理机制。", "coverage": "covered", "evidence_status": "sufficient", "weight": 10},
                {"section": "integration", "text": "完成医院系统、区域平台和监管接口的安全集成。", "coverage": "partial", "evidence_status": "weak", "weight": 9},
                {"section": "security", "text": "落实数据分级分类、脱敏和访问审计要求。", "coverage": "partial", "evidence_status": "sufficient", "weight": 9},
                {"section": "delivery", "text": "明确试点范围、里程碑和验收边界。", "coverage": "uncovered", "evidence_status": "missing", "weight": 8, "assigned": False},
                {"section": "service", "text": "补齐上线后的运行监控与应急响应承诺。", "coverage": "uncovered", "evidence_status": "missing", "weight": 6, "assigned": False},
            ],
        )
        seed_runtime_runs(db, user=user, org_id=workspace.id, project=active_project)
        deliverable = seed_deliverable(db, project=active_project)
        seed_radar(db, user=user, org_id=workspace.id)
        db.commit()

        return {
            "workspace_id": workspace.id,
            "workspace_slug": workspace.slug,
            "projects": [demo_project.name, completed_project.name, active_project.name],
            "radar_source": RADAR_SOURCE_NAME,
            "deliverable_id": deliverable.id,
            "plan": "enterprise",
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Existing account email")
    args = parser.parse_args()
    result = seed(args.email)
    print("Workspace demo ready")
    print(f"workspace: {result['workspace_slug']} ({result['workspace_id']})")
    print("projects:")
    for project_name in result["projects"]:
        print(f"- {project_name}")
    print(f"radar source: {result['radar_source']}")
    print(f"deliverable: {result['deliverable_id']}")
    print(f"plan: {result['plan']}")


if __name__ == "__main__":
    main()
