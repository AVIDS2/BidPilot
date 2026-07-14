"""add requirement ledger trace models

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("requirement_item", sa.Column("original_text", sa.Text(), nullable=True))
    op.add_column(
        "requirement_item",
        sa.Column(
            "source_document_id",
            sa.String(length=36),
            sa.ForeignKey("source_document.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("requirement_item", sa.Column("source_locator_json", sa.JSON(), nullable=True))
    op.add_column(
        "requirement_item",
        sa.Column(
            "owner_user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "requirement_item",
        sa.Column(
            "reviewer_user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("requirement_item", sa.Column("due_at", sa.DateTime(), nullable=True))
    op.add_column(
        "requirement_item",
        sa.Column(
            "verification_status",
            sa.String(length=30),
            nullable=False,
            server_default="unverified",
        ),
    )
    op.add_column(
        "requirement_item",
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "requirement_item",
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "requirement_item",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_requirement_item_owner_user_id", "requirement_item", ["owner_user_id"])
    op.create_index("ix_requirement_item_reviewer_user_id", "requirement_item", ["reviewer_user_id"])
    op.create_index("ix_requirement_item_verification_status", "requirement_item", ["verification_status"])
    op.create_index(
        "ix_requirement_item_project_verification",
        "requirement_item",
        ["project_id", "verification_status"],
    )

    op.create_table(
        "bid_requirement_profile",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "requirement_id",
            sa.String(length=36),
            sa.ForeignKey("requirement_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bid_category", sa.String(length=30), nullable=False, server_default="technical"),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("score_weight", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(length=30), nullable=False, server_default="normal"),
        sa.Column("coverage_status", sa.String(length=30), nullable=False, server_default="uncovered"),
        sa.Column("evidence_status", sa.String(length=30), nullable=False, server_default="missing"),
        sa.Column("deadline_at", sa.DateTime(), nullable=True),
        sa.Column("submission_metadata_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("requirement_id", name="uq_bid_requirement_profile_requirement"),
    )
    op.create_index("ix_bid_requirement_profile_bid_category", "bid_requirement_profile", ["bid_category"])
    op.create_index("ix_bid_requirement_profile_risk_level", "bid_requirement_profile", ["risk_level"])
    op.create_index("ix_bid_requirement_profile_coverage_status", "bid_requirement_profile", ["coverage_status"])
    op.create_index("ix_bid_requirement_profile_evidence_status", "bid_requirement_profile", ["evidence_status"])

    op.create_table(
        "requirement_evidence_link",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "requirement_id",
            sa.String(length=36),
            sa.ForeignKey("requirement_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            sa.String(length=36),
            sa.ForeignKey("evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(length=30), nullable=False, server_default="supports"),
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="unverified"),
        sa.Column(
            "created_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "requirement_id",
            "evidence_id",
            "relation_type",
            name="uq_requirement_evidence_relation",
        ),
    )
    op.create_index("ix_requirement_evidence_link_requirement_id", "requirement_evidence_link", ["requirement_id"])
    op.create_index("ix_requirement_evidence_link_evidence_id", "requirement_evidence_link", ["evidence_id"])

    op.create_table(
        "claim",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=30), nullable=False, server_default="factual"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column(
            "section_version_id",
            sa.String(length=36),
            sa.ForeignKey("section_version.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "generation_run_id",
            sa.String(length=36),
            sa.ForeignKey("execution_run.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_by_actor", sa.String(length=30), nullable=False, server_default="ai"),
        sa.Column(
            "created_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_claim_project_id", "claim", ["project_id"])

    op.create_table(
        "requirement_claim_link",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "requirement_id",
            sa.String(length=36),
            sa.ForeignKey("requirement_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "claim_id",
            sa.String(length=36),
            sa.ForeignKey("claim.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("coverage_role", sa.String(length=30), nullable=False, server_default="direct"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("requirement_id", "claim_id", name="uq_requirement_claim"),
    )
    op.create_index("ix_requirement_claim_link_requirement_id", "requirement_claim_link", ["requirement_id"])
    op.create_index("ix_requirement_claim_link_claim_id", "requirement_claim_link", ["claim_id"])

    op.create_table(
        "claim_evidence_link",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "claim_id",
            sa.String(length=36),
            sa.ForeignKey("claim.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            sa.String(length=36),
            sa.ForeignKey("evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(length=30), nullable=False, server_default="supports"),
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="unverified"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "claim_id",
            "evidence_id",
            "relation_type",
            name="uq_claim_evidence_relation",
        ),
    )
    op.create_index("ix_claim_evidence_link_claim_id", "claim_evidence_link", ["claim_id"])
    op.create_index("ix_claim_evidence_link_evidence_id", "claim_evidence_link", ["evidence_id"])

    op.create_table(
        "requirement_decision",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "requirement_id",
            sa.String(length=36),
            sa.ForeignKey("requirement_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision_type", sa.String(length=30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column(
            "requested_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id"),
            nullable=False,
        ),
        sa.Column(
            "approved_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_requirement_decision_requirement_id", "requirement_decision", ["requirement_id"])


def downgrade() -> None:
    op.drop_index("ix_requirement_decision_requirement_id", table_name="requirement_decision")
    op.drop_table("requirement_decision")
    op.drop_index("ix_claim_evidence_link_evidence_id", table_name="claim_evidence_link")
    op.drop_index("ix_claim_evidence_link_claim_id", table_name="claim_evidence_link")
    op.drop_table("claim_evidence_link")
    op.drop_index("ix_requirement_claim_link_claim_id", table_name="requirement_claim_link")
    op.drop_index("ix_requirement_claim_link_requirement_id", table_name="requirement_claim_link")
    op.drop_table("requirement_claim_link")
    op.drop_index("ix_claim_project_id", table_name="claim")
    op.drop_table("claim")
    op.drop_index("ix_requirement_evidence_link_evidence_id", table_name="requirement_evidence_link")
    op.drop_index("ix_requirement_evidence_link_requirement_id", table_name="requirement_evidence_link")
    op.drop_table("requirement_evidence_link")
    op.drop_index("ix_bid_requirement_profile_evidence_status", table_name="bid_requirement_profile")
    op.drop_index("ix_bid_requirement_profile_coverage_status", table_name="bid_requirement_profile")
    op.drop_index("ix_bid_requirement_profile_risk_level", table_name="bid_requirement_profile")
    op.drop_index("ix_bid_requirement_profile_bid_category", table_name="bid_requirement_profile")
    op.drop_table("bid_requirement_profile")
    op.drop_index("ix_requirement_item_project_verification", table_name="requirement_item")
    op.drop_index("ix_requirement_item_verification_status", table_name="requirement_item")
    op.drop_index("ix_requirement_item_reviewer_user_id", table_name="requirement_item")
    op.drop_index("ix_requirement_item_owner_user_id", table_name="requirement_item")
    op.drop_column("requirement_item", "updated_at")
    op.drop_column("requirement_item", "lock_version")
    op.drop_column("requirement_item", "extraction_confidence")
    op.drop_column("requirement_item", "verification_status")
    op.drop_column("requirement_item", "due_at")
    op.drop_column("requirement_item", "reviewer_user_id")
    op.drop_column("requirement_item", "owner_user_id")
    op.drop_column("requirement_item", "source_locator_json")
    op.drop_column("requirement_item", "source_document_id")
    op.drop_column("requirement_item", "original_text")
