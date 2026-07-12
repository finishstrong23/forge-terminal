"""Scope executed_trades signature uniqueness to (user_id, signature).

A global unique constraint on `signature` let any user pre-claim a public
on-chain signature and block another user from recording their own trade.
Uniqueness belongs per-user.

Revision ID: 003
Revises: 002
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Drop the old global unique constraint (Postgres auto-names it
    # <table>_<col>_key for an unnamed UniqueConstraint(col)).
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE executed_trades "
            "DROP CONSTRAINT IF EXISTS executed_trades_signature_key"
        )
    op.create_unique_constraint(
        "uq_executed_trade_user_signature",
        "executed_trades",
        ["user_id", "signature"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_executed_trade_user_signature", "executed_trades", type_="unique"
    )
    op.create_unique_constraint(
        "executed_trades_signature_key", "executed_trades", ["signature"]
    )
