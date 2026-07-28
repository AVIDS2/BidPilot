from __future__ import annotations

from uuid import uuid4

import pytest

from app.db import SessionLocal
from app.execution.review_resume import DurableReviewResumeError, resolve_durable_review_resume
from app.graph.builder import resume_graph
from app.graph.nodes.human_approval import human_approval_node
from app.models import Deliverable, DeliverableSection, ExecutionRun, Organization, Project, ReviewThread, SectionVersion
from contracts.models import ReviewComment


def _create_review_resume_fixture(*, decision: str) -> tuple[str, str]:
    suffix = uuid4().hex[:10]
    db = SessionLocal()
    try:
        org = Organization(slug=f"resume-{suffix}", name="Resume Test Org")
        db.add(org)
        db.flush()
        project = Project(
            slug=f"resume-project-{suffix}",
            name="Resume Test Project",
            org_id=org.id,
            scenario_package="bidpilot",
        )
        db.add(project)
        db.flush()
        deliverable = Deliverable(project_id=project.id, type="proposal", title="Resume Proposal")
        db.add(deliverable)
        db.flush()
        section = DeliverableSection(
            deliverable_id=deliverable.id,
            section_key="technical",
            title="Technical",
        )
        db.add(section)
        db.flush()
        run = ExecutionRun(project_id=project.id, run_type="draft_section", status="running", input_json={})
        db.add(run)
        db.flush()
        version = SectionVersion(
            deliverable_section_id=section.id,
            version_number=1,
            content_markdown="Candidate draft",
            generation_run_id=run.id,
            generation_iteration=1,
        )
        db.add(version)
        db.flush()
        thread = ReviewThread(
            deliverable_section_id=section.id,
            section_version_id=version.id,
            status=decision,
            opened_by=run.id,
            resolved_by="reviewer",
        )
        db.add(thread)
        db.flush()
        if decision == "rejected":
            db.add(
                ReviewComment(
                    review_thread_id=thread.id,
                    author_type="human",
                    author_id="reviewer",
                    body="请补充可定位的资质证据。",
                )
            )
        run.input_json = {
            "review_resume": {
                "sequence": 1,
                "review_thread_id": thread.id,
                "section_version_id": version.id,
            }
        }
        db.commit()
        return run.id, version.id
    finally:
        db.close()


def test_review_resume_uses_committed_rejection_not_stale_broker_args() -> None:
    run_id, _ = _create_review_resume_fixture(decision="rejected")

    decision, feedback = resolve_durable_review_resume(
        run_id=run_id,
        requested_decision="approved",
        requested_feedback=None,
    )

    assert decision == "rejected_with_feedback"
    assert feedback == "请补充可定位的资质证据。"


def test_review_resume_rejects_mismatched_candidate_reference() -> None:
    run_id, _ = _create_review_resume_fixture(decision="approved")
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        assert run is not None
        run.input_json = {
            "review_resume": {
                "sequence": 1,
                "review_thread_id": run.input_json["review_resume"]["review_thread_id"],
                "section_version_id": str(uuid4()),
            }
        }
        db.commit()
    finally:
        db.close()

    with pytest.raises(DurableReviewResumeError, match="review_resume_version_mismatch"):
        resolve_durable_review_resume(
            run_id=run_id,
            requested_decision="approved",
            requested_feedback=None,
        )


def test_resume_graph_rejects_unknown_decision_before_loading_checkpoint() -> None:
    with pytest.raises(ValueError, match="Unsupported LangGraph human approval decision"):
        resume_graph(run_id=str(uuid4()), decision="approve", feedback=None)


def test_human_approval_node_does_not_default_missing_decision_to_approval(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.graph.nodes.human_approval.interrupt",
        lambda _: {"feedback": "没有明确决定"},
    )

    with pytest.raises(ValueError, match="Unsupported human approval decision"):
        human_approval_node(
            {
                "section_key": "technical",
                "draft_markdown": "Candidate draft",
                "review_result": {"overall_score": 0.92, "issues": []},
                "iteration": 1,
                "runtime_run_id": None,
            }
        )
