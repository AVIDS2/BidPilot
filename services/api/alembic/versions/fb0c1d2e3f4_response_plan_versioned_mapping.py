"""add versioned response plan and section mappings

Revision ID: fb0c1d2e3f4
Revises: e6f7a8b9c0d1
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fb0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "response_plan",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("deliverable_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "unmapped_requirement_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("created_by_actor", sa.String(length=30), nullable=False, server_default="workflow"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverable.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deliverable_id",
            "version_number",
            name="uq_response_plan_deliverable_version",
        ),
    )
    op.create_index("ix_response_plan_project_id", "response_plan", ["project_id"])
    op.create_index("ix_response_plan_deliverable_id", "response_plan", ["deliverable_id"])
    op.create_index("ix_response_plan_status", "response_plan", ["status"])
    op.create_index("ix_response_plan_source_fingerprint", "response_plan", ["source_fingerprint"])
    op.create_index(
        "ix_response_plan_project_deliverable_status",
        "response_plan",
        ["project_id", "deliverable_id", "status"],
    )

    op.create_table(
        "response_plan_section",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("response_plan_id", sa.String(length=36), nullable=False),
        sa.Column("deliverable_section_id", sa.String(length=36), nullable=False),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("title_snapshot", sa.String(length=255), nullable=False),
        sa.Column("sort_order_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="planned"),
        sa.ForeignKeyConstraint(["response_plan_id"], ["response_plan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["deliverable_section_id"],
            ["deliverable_section.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "response_plan_id",
            "deliverable_section_id",
            name="uq_response_plan_section",
        ),
    )
    op.create_index(
        "ix_response_plan_section_response_plan_id",
        "response_plan_section",
        ["response_plan_id"],
    )
    op.create_index(
        "ix_response_plan_section_deliverable_section_id",
        "response_plan_section",
        ["deliverable_section_id"],
    )

    op.create_table(
        "response_plan_requirement",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("response_plan_section_id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("requirement_lock_version", sa.Integer(), nullable=False),
        sa.Column("requirement_text_snapshot", sa.Text(), nullable=False),
        sa.Column("priority_snapshot", sa.String(length=30), nullable=False),
        sa.Column("owner_user_id_snapshot", sa.String(length=36), nullable=True),
        sa.Column("verification_status_snapshot", sa.String(length=30), nullable=False),
        sa.Column(
            "assignment_reason",
            sa.String(length=100),
            nullable=False,
            server_default="section_key_exact_match",
        ),
        sa.ForeignKeyConstraint(
            ["response_plan_section_id"],
            ["response_plan_section.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirement_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "response_plan_section_id",
            "requirement_id",
            name="uq_response_plan_section_requirement",
        ),
    )
    op.create_index(
        "ix_response_plan_requirement_response_plan_section_id",
        "response_plan_requirement",
        ["response_plan_section_id"],
    )
    op.create_index(
        "ix_response_plan_requirement_requirement_id",
        "response_plan_requirement",
        ["requirement_id"],
    )

    op.create_table(
        "response_plan_evidence_binding",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("response_plan_section_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_set_id", sa.String(length=36), nullable=False),
        sa.Column("execution_run_id", sa.String(length=36), nullable=False),
        sa.Column("generation_iteration", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_plan_json", sa.JSON(), nullable=False),
        sa.Column("evidence_set_status", sa.String(length=30), nullable=False),
        sa.Column(
            "unmet_requirement_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "degraded_reasons_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(
            ["response_plan_section_id"],
            ["response_plan_section.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["evidence_set_id"], ["evidence_set.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["execution_run_id"], ["execution_run.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "execution_run_id",
            "generation_iteration",
            name="uq_response_plan_binding_run_iteration",
        ),
    )
    op.create_index(
        "ix_response_plan_evidence_binding_response_plan_section_id",
        "response_plan_evidence_binding",
        ["response_plan_section_id"],
    )
    op.create_index(
        "ix_response_plan_evidence_binding_evidence_set_id",
        "response_plan_evidence_binding",
        ["evidence_set_id"],
    )
    op.create_index(
        "ix_response_plan_evidence_binding_execution_run_id",
        "response_plan_evidence_binding",
        ["execution_run_id"],
    )

    op.add_column(
        "section_version",
        sa.Column("response_plan_section_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_section_version_response_plan_section_id",
        "section_version",
        "response_plan_section",
        ["response_plan_section_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_section_version_response_plan_section_id",
        "section_version",
        ["response_plan_section_id"],
    )
    op.add_column(
        "section_version",
        sa.Column("response_plan_evidence_binding_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_section_version_response_plan_evidence_binding_id",
        "section_version",
        "response_plan_evidence_binding",
        ["response_plan_evidence_binding_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_section_version_response_plan_evidence_binding_id",
        "section_version",
        ["response_plan_evidence_binding_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_section_version_response_plan_evidence_binding_id",
        table_name="section_version",
    )
    op.drop_constraint(
        "fk_section_version_response_plan_evidence_binding_id",
        "section_version",
        type_="foreignkey",
    )
    op.drop_column("section_version", "response_plan_evidence_binding_id")
    op.drop_index("ix_section_version_response_plan_section_id", table_name="section_version")
    op.drop_constraint(
        "fk_section_version_response_plan_section_id",
        "section_version",
        type_="foreignkey",
    )
    op.drop_column("section_version", "response_plan_section_id")

    op.drop_index(
        "ix_response_plan_evidence_binding_execution_run_id",
        table_name="response_plan_evidence_binding",
    )
    op.drop_index(
        "ix_response_plan_evidence_binding_evidence_set_id",
        table_name="response_plan_evidence_binding",
    )
    op.drop_index(
        "ix_response_plan_evidence_binding_response_plan_section_id",
        table_name="response_plan_evidence_binding",
    )
    op.drop_table("response_plan_evidence_binding")

    op.drop_index(
        "ix_response_plan_requirement_requirement_id",
        table_name="response_plan_requirement",
    )
    op.drop_index(
        "ix_response_plan_requirement_response_plan_section_id",
        table_name="response_plan_requirement",
    )
    op.drop_table("response_plan_requirement")

    op.drop_index(
        "ix_response_plan_section_deliverable_section_id",
        table_name="response_plan_section",
    )
    op.drop_index(
        "ix_response_plan_section_response_plan_id",
        table_name="response_plan_section",
    )
    op.drop_table("response_plan_section")

    op.drop_index(
        "ix_response_plan_project_deliverable_status",
        table_name="response_plan",
    )
    op.drop_index("ix_response_plan_source_fingerprint", table_name="response_plan")
    op.drop_index("ix_response_plan_status", table_name="response_plan")
    op.drop_index("ix_response_plan_deliverable_id", table_name="response_plan")
    op.drop_index("ix_response_plan_project_id", table_name="response_plan")
    op.drop_table("response_plan")
