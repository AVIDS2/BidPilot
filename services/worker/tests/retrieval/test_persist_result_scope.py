import uuid

from app.db import SessionLocal
from app.graph.nodes.persist_result import _find_or_create_section
from app.models import Deliverable, DeliverableSection, Organization, Project


def test_persist_result_never_reuses_a_same_named_section_from_another_project() -> None:
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        organization = Organization(id=f"org-{suffix}", slug=f"scope-{suffix}", name="Scope Test")
        target_project = Project(
            id=f"target-project-{suffix}",
            org_id=organization.id,
            name="Target Project",
            slug=f"target-{suffix}",
            scenario_package="bidpilot",
        )
        foreign_project = Project(
            id=f"foreign-project-{suffix}",
            org_id=organization.id,
            name="Foreign Project",
            slug=f"foreign-{suffix}",
            scenario_package="bidpilot",
        )
        db.add(organization)
        db.commit()
        db.add_all((target_project, foreign_project))
        db.commit()

        target_deliverable = Deliverable(
            id=f"target-deliverable-{suffix}",
            project_id=target_project.id,
            type="proposal",
            title="Target Deliverable",
        )
        foreign_deliverable = Deliverable(
            id=f"foreign-deliverable-{suffix}",
            project_id=foreign_project.id,
            type="proposal",
            title="Foreign Deliverable",
        )
        db.add_all((target_deliverable, foreign_deliverable))
        db.commit()

        foreign_section = DeliverableSection(
            id=f"foreign-section-{suffix}",
            deliverable_id=foreign_deliverable.id,
            section_key="technical-approach",
            title="Technical Approach",
        )
        db.add(foreign_section)
        db.commit()

        section = _find_or_create_section(db, target_project.id, "technical-approach")

        assert section.id != foreign_section.id
        assert section.deliverable_id == target_deliverable.id
    finally:
        db.rollback()
        db.close()
