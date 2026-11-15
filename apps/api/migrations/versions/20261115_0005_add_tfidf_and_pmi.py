"""add tfidf and pmi metrics

Revision ID: 20261115_0005
Revises: 20261114_0004
Create Date: 2026-11-15 00:00:01
"""

from alembic import op
import sqlalchemy as sa

revision = "20261115_0005"
down_revision = "20261114_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("concept_relationships") as batch_op:
        batch_op.add_column(sa.Column("pmi", sa.Float(), nullable=False, server_default="0.0"))
        batch_op.add_column(sa.Column("npmi", sa.Float(), nullable=False, server_default="0.0"))

    with op.batch_alter_table("concepts") as batch_op:
        batch_op.add_column(sa.Column("tfidf_score", sa.Float(), nullable=False, server_default="0.0"))

    with op.batch_alter_table("document_concepts") as batch_op:
        batch_op.add_column(sa.Column("tfidf_score", sa.Float(), nullable=False, server_default="0.0"))


def downgrade() -> None:
    with op.batch_alter_table("document_concepts") as batch_op:
        batch_op.drop_column("tfidf_score")

    with op.batch_alter_table("concepts") as batch_op:
        batch_op.drop_column("tfidf_score")

    with op.batch_alter_table("concept_relationships") as batch_op:
        batch_op.drop_column("npmi")
        batch_op.drop_column("pmi")
