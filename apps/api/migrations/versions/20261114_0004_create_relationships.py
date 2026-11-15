"""create concept relationships

Revision ID: 20261114_0004
Revises: 20261114_0003
Create Date: 2026-11-14 00:00:03
"""

from alembic import op
import sqlalchemy as sa

revision = "20261114_0004"
down_revision = "20261114_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "concept_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_concept_id", sa.Uuid(), nullable=False),
        sa.Column("target_concept_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "source_concept_id", "target_concept_id", "relationship_type"),
    )
    op.create_index("ix_concept_relationships_workspace_id", "concept_relationships", ["workspace_id"])
    op.create_table(
        "relationship_evidence",
        sa.Column("relationship_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("source_occurrences", sa.Integer(), nullable=False),
        sa.Column("target_occurrences", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relationship_id"], ["concept_relationships.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("relationship_id", "document_id"),
    )


def downgrade() -> None:
    op.drop_table("relationship_evidence")
    op.drop_index("ix_concept_relationships_workspace_id", table_name="concept_relationships")
    op.drop_table("concept_relationships")
