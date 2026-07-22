"""add provider profiles

Revision ID: ab1c2d3e4f5
Revises: fa0b1c2d3e4
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ab1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "fa0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("provider_config", sa.Column("provider_id", sa.String(length=64), nullable=True))
    op.execute(
        """
        UPDATE provider_config
        SET provider_id = CASE
            WHEN provider_type = 'anthropic'
                 AND lower(coalesce(api_url, '')) LIKE '%api.deepseek.com/anthropic%'
                THEN 'deepseek-anthropic'
            WHEN lower(coalesce(api_url, '')) LIKE '%api.openai.com%'
                THEN 'openai'
            WHEN lower(coalesce(api_url, '')) LIKE '%api.deepseek.com%'
                THEN 'deepseek'
            WHEN lower(coalesce(api_url, '')) LIKE '%dashscope.aliyuncs.com%'
                THEN 'dashscope'
            WHEN lower(coalesce(api_url, '')) LIKE '%ark.cn-beijing.volces.com%'
                THEN 'doubao'
            WHEN lower(coalesce(api_url, '')) LIKE '%api.anthropic.com%'
                THEN 'anthropic'
            WHEN lower(coalesce(api_url, '')) LIKE '%bigmodel.cn%'
                THEN 'zhipu'
            WHEN lower(coalesce(api_url, '')) LIKE '%minimax%'
                THEN 'minimax'
            WHEN lower(coalesce(api_url, '')) LIKE '%siliconflow.cn%'
                THEN 'siliconflow'
            WHEN lower(coalesce(api_url, '')) LIKE '%openrouter.ai%'
                THEN 'openrouter'
            WHEN lower(coalesce(api_url, '')) LIKE '%xiaomimimo.com%'
                THEN 'mimo'
            WHEN provider_type = 'anthropic'
                THEN 'custom-anthropic'
            ELSE 'custom-openai'
        END
        """
    )
    op.alter_column(
        "provider_config",
        "provider_id",
        existing_type=sa.String(length=64),
        nullable=False,
        server_default="custom-openai",
    )


def downgrade() -> None:
    op.drop_column("provider_config", "provider_id")
