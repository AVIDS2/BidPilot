"""add bid governance P1 domains

Revision ID: a04b5c6d7e8f
Revises: ff4b5c6d7e8f
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a04b5c6d7e8f"
down_revision: Union[str, Sequence[str], None] = "ff4b5c6d7e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "opportunity_assessment" not in tables:
        op.create_table(
            "opportunity_assessment",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("decision", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("scorecard_json", sa.JSON(), nullable=False),
            sa.Column("risk_summary_json", sa.JSON(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("decided_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint(
                "status IN ('draft', 'ready', 'decided', 'archived')",
                name="ck_opportunity_assessment_status",
            ),
            sa.CheckConstraint(
                "decision IN ('pending', 'go', 'no_go', 'conditional_go')",
                name="ck_opportunity_assessment_decision",
            ),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["decided_by_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id"),
        )
        op.create_index("ix_opportunity_assessment_project_id", "opportunity_assessment", ["project_id"])
        op.create_index("ix_opportunity_assessment_decision", "opportunity_assessment", ["decision"])
        op.create_index(
            "ix_opportunity_assessment_project_decision",
            "opportunity_assessment",
            ["project_id", "decision"],
        )

    if "opportunity_assessment_decision" not in tables:
        op.create_table(
            "opportunity_assessment_decision",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("assessment_id", sa.String(length=36), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("decision", sa.String(length=30), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("scorecard_json", sa.JSON(), nullable=False),
            sa.Column("risk_summary_json", sa.JSON(), nullable=False),
            sa.Column("decided_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint(
                "decision IN ('go', 'no_go', 'conditional_go')",
                name="ck_opportunity_assessment_decision_value",
            ),
            sa.ForeignKeyConstraint(["assessment_id"], ["opportunity_assessment.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["decided_by_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("assessment_id", "sequence", name="uq_opportunity_assessment_decision_sequence"),
        )
        op.create_index(
            "ix_opportunity_assessment_decision_assessment_id",
            "opportunity_assessment_decision",
            ["assessment_id"],
        )
        op.create_index(
            "ix_opportunity_assessment_decision_decided_by_user_id",
            "opportunity_assessment_decision",
            ["decided_by_user_id"],
        )

    if "content_library_entry" not in tables:
        op.create_table(
            "content_library_entry",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("org_id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=50), nullable=False, server_default="answer"),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("tags_json", sa.JSON(), nullable=False),
            sa.Column("lifecycle_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("review_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("owner_user_id", sa.String(length=36), nullable=True),
            sa.Column("effective_from", sa.DateTime(), nullable=True),
            sa.Column("effective_until", sa.DateTime(), nullable=True),
            sa.Column("supersedes_entry_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint(
                "lifecycle_status IN ('draft', 'published', 'archived')",
                name="ck_content_library_entry_lifecycle",
            ),
            sa.CheckConstraint(
                "review_status IN ('draft', 'approved', 'rejected')",
                name="ck_content_library_entry_review",
            ),
            sa.ForeignKeyConstraint(["org_id"], ["organization.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["supersedes_entry_id"], ["content_library_entry.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_content_library_entry_org_id", "content_library_entry", ["org_id"])
        op.create_index("ix_content_library_entry_category", "content_library_entry", ["category"])
        op.create_index("ix_content_library_entry_lifecycle_status", "content_library_entry", ["lifecycle_status"])
        op.create_index("ix_content_library_entry_review_status", "content_library_entry", ["review_status"])
        op.create_index("ix_content_library_entry_owner_user_id", "content_library_entry", ["owner_user_id"])
        op.create_index("ix_content_library_entry_supersedes_entry_id", "content_library_entry", ["supersedes_entry_id"])
        op.create_index("ix_content_library_entry_org_lifecycle", "content_library_entry", ["org_id", "lifecycle_status"])

    if "content_library_version" not in tables:
        op.create_table(
            "content_library_version",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("entry_id", sa.String(length=36), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("content_markdown", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("source_json", sa.JSON(), nullable=True),
            sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["entry_id"], ["content_library_entry.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("entry_id", "version_number", name="uq_content_library_version_number"),
            sa.UniqueConstraint("entry_id", "content_hash", name="uq_content_library_version_hash"),
        )
        op.create_index("ix_content_library_version_entry_id", "content_library_version", ["entry_id"])
        op.create_index("ix_content_library_version_created_by_user_id", "content_library_version", ["created_by_user_id"])

    if "content_library_usage" not in tables:
        op.create_table(
            "content_library_usage",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("entry_id", sa.String(length=36), nullable=False),
            sa.Column("content_version_id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("deliverable_section_id", sa.String(length=36), nullable=True),
            sa.Column("usage_purpose", sa.String(length=50), nullable=False, server_default="reference"),
            sa.Column("used_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["entry_id"], ["content_library_entry.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["content_version_id"], ["content_library_version.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["deliverable_section_id"], ["deliverable_section.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["used_by_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "content_version_id",
                "project_id",
                "deliverable_section_id",
                "usage_purpose",
                name="uq_content_library_usage_target",
            ),
        )
        op.create_index("ix_content_library_usage_entry_id", "content_library_usage", ["entry_id"])
        op.create_index("ix_content_library_usage_content_version_id", "content_library_usage", ["content_version_id"])
        op.create_index("ix_content_library_usage_project_id", "content_library_usage", ["project_id"])
        op.create_index("ix_content_library_usage_deliverable_section_id", "content_library_usage", ["deliverable_section_id"])
        op.create_index("ix_content_library_usage_used_by_user_id", "content_library_usage", ["used_by_user_id"])
        op.create_index("ix_content_library_usage_project_created", "content_library_usage", ["project_id", "created_at"])

    if "document_change_set" not in tables:
        op.create_table(
            "document_change_set",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("previous_document_id", sa.String(length=36), nullable=False),
            sa.Column("replacement_document_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_parse"),
            sa.Column("summary_json", sa.JSON(), nullable=False),
            sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint(
                "status IN ('pending_parse', 'analyzed', 'accepted', 'dismissed')",
                name="ck_document_change_set_status",
            ),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["previous_document_id"], ["source_document.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["replacement_document_id"], ["source_document.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("replacement_document_id"),
            sa.UniqueConstraint("project_id", "replacement_document_id", name="uq_document_change_set_project_replacement"),
        )
        op.create_index("ix_document_change_set_project_id", "document_change_set", ["project_id"])
        op.create_index("ix_document_change_set_previous_document_id", "document_change_set", ["previous_document_id"])
        op.create_index("ix_document_change_set_replacement_document_id", "document_change_set", ["replacement_document_id"])
        op.create_index("ix_document_change_set_status", "document_change_set", ["status"])
        op.create_index("ix_document_change_set_created_by_user_id", "document_change_set", ["created_by_user_id"])
        op.create_index("ix_document_change_set_reviewed_by_user_id", "document_change_set", ["reviewed_by_user_id"])

    if "document_change_impact" not in tables:
        op.create_table(
            "document_change_impact",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("change_set_id", sa.String(length=36), nullable=False),
            sa.Column("impact_key", sa.String(length=128), nullable=False),
            sa.Column("requirement_id", sa.String(length=36), nullable=True),
            sa.Column("deliverable_section_id", sa.String(length=36), nullable=True),
            sa.Column("impact_type", sa.String(length=50), nullable=False),
            sa.Column("severity", sa.String(length=30), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("locator_json", sa.JSON(), nullable=True),
            sa.Column("acknowledged_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint(
                "status IN ('open', 'acknowledged', 'resolved', 'dismissed')",
                name="ck_document_change_impact_status",
            ),
            sa.CheckConstraint(
                "severity IN ('low', 'medium', 'high', 'critical')",
                name="ck_document_change_impact_severity",
            ),
            sa.ForeignKeyConstraint(["change_set_id"], ["document_change_set.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requirement_id"], ["requirement_item.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["deliverable_section_id"], ["deliverable_section.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["acknowledged_by_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["resolved_by_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("change_set_id", "impact_key", name="uq_document_change_impact_key"),
        )
        op.create_index("ix_document_change_impact_change_set_id", "document_change_impact", ["change_set_id"])
        op.create_index("ix_document_change_impact_requirement_id", "document_change_impact", ["requirement_id"])
        op.create_index("ix_document_change_impact_deliverable_section_id", "document_change_impact", ["deliverable_section_id"])
        op.create_index("ix_document_change_impact_status", "document_change_impact", ["status"])


def downgrade() -> None:
    tables = _tables()
    for table_name in (
        "document_change_impact",
        "document_change_set",
        "content_library_usage",
        "content_library_version",
        "content_library_entry",
        "opportunity_assessment_decision",
        "opportunity_assessment",
    ):
        if table_name in tables:
            op.drop_table(table_name)
