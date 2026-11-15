"""create anonymous workspaces

Revision ID: 20261114_0001
Revises:
Create Date: 2026-11-14 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20261114_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workspaces")
