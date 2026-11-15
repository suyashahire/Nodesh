"""create workspace concepts

Revision ID: 20261114_0003
Revises: 20261114_0002
Create Date: 2026-11-14 00:00:02
"""

from alembic import op
import sqlalchemy as sa

revision = "20261114_0003"
down_revision = "20261114_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "concepts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("total_occurrences", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "normalized_name"),
    )
    op.create_index("ix_concepts_workspace_id", "concepts", ["workspace_id"])
    op.create_table(
        "document_concepts",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "concept_id"),
    )


def downgrade() -> None:
    op.drop_table("document_concepts")
    op.drop_index("ix_concepts_workspace_id", table_name="concepts")
    op.drop_table("concepts")
