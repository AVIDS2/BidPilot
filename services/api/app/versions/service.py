from sqlalchemy.orm import Session

from app.access.service import require_deliverable_section_capability
from app.auth.schemas import CurrentUser

from .repository import list_versions_by_section
from .schemas import SectionVersionRead


def list_versions_query(
    db: Session,
    section_id: str,
    current_user: CurrentUser,
) -> list[SectionVersionRead]:
    require_deliverable_section_capability(
        db,
        current_user=current_user,
        section_id=section_id,
        capability="project.read",
    )
    versions = list_versions_by_section(db, section_id)
    return [
        SectionVersionRead(
            id=v.id,
            deliverable_section_id=v.deliverable_section_id,
            version_number=v.version_number,
            content_markdown=v.content_markdown,
            created_by_actor=v.created_by_actor,
            generation_run_id=v.generation_run_id,
            evidence_set_id=v.evidence_set_id,
            response_plan_section_id=v.response_plan_section_id,
            response_plan_evidence_binding_id=v.response_plan_evidence_binding_id,
        )
        for v in versions
    ]
