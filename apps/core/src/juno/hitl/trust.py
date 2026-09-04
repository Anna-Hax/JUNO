"""Per-category trust dials (PRD §8 P2). Mobile and drafts stay gated."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from juno.graph.db import Database
from juno.models import AppSetting

CATEGORIES = ("merge", "browser", "ide_error", "mobile", "drafts")
LOCKED = frozenset({"mobile", "drafts"})
DEFAULT_THRESHOLD = 5
HIGH_CONFIDENCE = 0.8


@dataclass(frozen=True)
class TrustDial:
    category: str
    successes: int
    threshold: int
    auto: bool
    locked: bool

    def summary(self) -> str:
        if self.locked:
            return f"{self.category}: gated (always HITL)"
        mode = "auto-commit on" if self.auto else "HITL"
        return f"{self.category}: {mode} ({self.successes}/{self.threshold} approved)"


def _success_key(category: str) -> str:
    return f"trust.{category}.successes"


def _auto_key(category: str) -> str:
    return f"trust.{category}.auto"


def _threshold_key(category: str) -> str:
    return f"trust.{category}.threshold"


async def get_dial(db: Database, category: str) -> TrustDial:
    if category not in CATEGORIES:
        raise ValueError(f"unknown trust category {category!r}")

    async def load(session: AsyncSession) -> TrustDial:
        return await _dial_from_session(session, category)

    return await db.read(load)


async def list_dials(db: Database) -> list[TrustDial]:
    async def load(session: AsyncSession) -> list[TrustDial]:
        return [await _dial_from_session(session, cat) for cat in CATEGORIES]

    return await db.read(load)


async def record_success(db: Database, category: str) -> TrustDial:
    if category not in CATEGORIES:
        raise ValueError(f"unknown trust category {category!r}")

    async def write(session: AsyncSession) -> TrustDial:
        dial = await _dial_from_session(session, category)
        successes = dial.successes + 1
        await _put(session, _success_key(category), str(successes))
        auto = dial.auto
        if not dial.locked and successes >= dial.threshold:
            auto = True
            await _put(session, _auto_key(category), "true")
        return TrustDial(
            category=category,
            successes=successes,
            threshold=dial.threshold,
            auto=auto,
            locked=dial.locked,
        )

    return await db.write(write)


async def set_auto(db: Database, category: str, enabled: bool) -> TrustDial:
    if category not in CATEGORIES:
        raise ValueError(f"unknown trust category {category!r}")
    if category in LOCKED and enabled:
        raise ValueError(f"{category} stays gated")

    async def write(session: AsyncSession) -> TrustDial:
        await _put(session, _auto_key(category), "true" if enabled else "false")
        return await _dial_from_session(session, category)

    return await db.write(write)


async def should_auto_commit(
    db: Database,
    category: str,
    confidence: float,
) -> bool:
    if category in LOCKED:
        return False
    dial = await get_dial(db, category)
    return dial.auto and confidence >= HIGH_CONFIDENCE


def format_trust(dials: list[TrustDial]) -> str:
    lines = ["Trust dials (per category, not a global switch):"]
    lines.extend(f"• {d.summary()}" for d in dials)
    lines.append("Toggle: /trust merge|browser|ide_error on|off")
    lines.append("mobile and drafts stay gated.")
    return "\n".join(lines)


async def _dial_from_session(session: AsyncSession, category: str) -> TrustDial:
    successes = int(await _get(session, _success_key(category), "0"))
    threshold = int(await _get(session, _threshold_key(category), str(DEFAULT_THRESHOLD)))
    auto_raw = await _get(session, _auto_key(category), "false")
    locked = category in LOCKED
    auto = (not locked) and auto_raw.strip().lower() in {"1", "true", "yes", "on"}
    return TrustDial(
        category=category,
        successes=successes,
        threshold=threshold,
        auto=auto,
        locked=locked,
    )


async def _get(session: AsyncSession, key: str, default: str) -> str:
    row = await session.get(AppSetting, key)
    return default if row is None else row.value


async def _put(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
