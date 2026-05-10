"""add tier_level and pump_fun_url to tokens

Revision ID: 001
Revises: None
Create Date: 2026-05-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tokens", sa.Column("tier_level", sa.String(), nullable=True, server_default="free"))
    op.add_column("tokens", sa.Column("pump_fun_url", sa.String(), nullable=True))
    op.create_index("ix_tokens_tier_level", "tokens", ["tier_level"])


def downgrade() -> None:
    op.drop_index("ix_tokens_tier_level", table_name="tokens")
    op.drop_column("tokens", "pump_fun_url")
    op.drop_column("tokens", "tier_level")
