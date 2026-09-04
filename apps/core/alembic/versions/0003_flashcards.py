"""0003 flashcards — SRS rows after HITL flashcard drafts (#108).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flashcards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("capture_id", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ease", sa.Float(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["draft_artifacts.id"],
            name=op.f("fk_flashcards_artifact_id_draft_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["captures.id"],
            name=op.f("fk_flashcards_capture_id_captures"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flashcards")),
    )
    with op.batch_alter_table("flashcards", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_flashcards_artifact_id"), ["artifact_id"], unique=True)
        batch_op.create_index(batch_op.f("ix_flashcards_fingerprint"), ["fingerprint"], unique=True)
        batch_op.create_index(batch_op.f("ix_flashcards_capture_id"), ["capture_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_flashcards_due_at"), ["due_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("flashcards", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_flashcards_due_at"))
        batch_op.drop_index(batch_op.f("ix_flashcards_capture_id"))
        batch_op.drop_index(batch_op.f("ix_flashcards_fingerprint"))
        batch_op.drop_index(batch_op.f("ix_flashcards_artifact_id"))
    op.drop_table("flashcards")
