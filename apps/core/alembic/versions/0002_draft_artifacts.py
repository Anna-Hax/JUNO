"""0002 draft_artifacts — HITL auto-generated artifacts (M5 / #107).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "draft_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("extra_json", sa.JSON(), nullable=True),
        sa.Column("generator", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published", sa.String(length=8), nullable=False),
        sa.Column("review_item_id", sa.Integer(), nullable=True),
        sa.Column("source_capture_ids", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["review_item_id"],
            ["review_items.id"],
            name=op.f("fk_draft_artifacts_review_item_id_review_items"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_draft_artifacts")),
    )
    with op.batch_alter_table("draft_artifacts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_draft_artifacts_kind"), ["kind"], unique=False)
        batch_op.create_index(batch_op.f("ix_draft_artifacts_status"), ["status"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_draft_artifacts_review_item_id"),
            ["review_item_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("draft_artifacts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_draft_artifacts_review_item_id"))
        batch_op.drop_index(batch_op.f("ix_draft_artifacts_status"))
        batch_op.drop_index(batch_op.f("ix_draft_artifacts_kind"))
    op.drop_table("draft_artifacts")
