"""Relevance, recency, and a light importance weight for push vs review."""

from __future__ import annotations

from datetime import UTC, datetime

HALF_LIFE_DAYS = 30.0
# Recency never zeroes an older note. A strong match can still surface.
_RECENCY_FLOOR = 0.7


def salience_score(
    relevance: float,
    captured_at: datetime | None,
    now: datetime,
    *,
    text: str = "",
    has_highlights: bool = False,
) -> float:
    """Blend cosine relevance with recency and whether the note is substantial."""
    importance = 1.0
    if has_highlights:
        importance = 1.15
    elif len((text or "").strip()) < 80:
        importance = 0.75
    when = captured_at or now
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    age_days = max(0.0, (current - when).total_seconds() / 86400.0)
    recency = 0.5 ** (age_days / HALF_LIFE_DAYS)
    factor = _RECENCY_FLOOR + (1.0 - _RECENCY_FLOOR) * recency
    raw = max(0.0, float(relevance)) * importance * factor
    return max(0.0, min(1.0, raw))


def has_highlights(raw_json: object) -> bool:
    if not isinstance(raw_json, dict):
        return False
    highlights = raw_json.get("highlights")
    return bool(highlights)
