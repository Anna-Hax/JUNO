"""Draft artifact kinds. Stay HITL until approve; never auto-publish (ADR-09)."""

from __future__ import annotations

DRAFT_KIND_JOURNAL = "journal"
DRAFT_KIND_FLASHCARD = "flashcard"
DRAFT_KIND_DOC = "doc"
DRAFT_KINDS = frozenset({DRAFT_KIND_JOURNAL, DRAFT_KIND_FLASHCARD, DRAFT_KIND_DOC})

GENERATOR_TEMPLATE = "template"

STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_DISCARDED = "discarded"
PUBLISHED_NO = "false"


def require_draft_kind(kind: str) -> str:
    value = (kind or "").strip().lower()
    if value not in DRAFT_KINDS:
        allowed = ", ".join(sorted(DRAFT_KINDS))
        raise ValueError(f"unknown draft kind {kind!r}; expected one of {allowed}")
    return value
