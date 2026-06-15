"""merge chat and provider heads

Revision ID: b4c5d6e7f8a9
Revises: 8f929f4a7307, a1b2c3d4e5f6
Create Date: 2026-06-10 09:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = ("8f929f4a7307", "a1b2c3d4e5f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
