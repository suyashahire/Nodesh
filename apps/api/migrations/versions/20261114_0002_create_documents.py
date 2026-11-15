"""create workspace documents

Revision ID: 20261114_0002
Revises: 20261114_0001
Create Date: 2026-11-14 00:00:01
"""

from alembic import op
import sqlalchemy as sa

revision = "20261114_0002"
down_revision = "20261114_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=127), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("extracted_characters", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_workspace_id", table_name="documents")
    op.drop_table("documents")
