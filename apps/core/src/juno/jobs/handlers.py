"""Job bodies. Digest/resurfacing pushes land in later M4 issues — ticks only log here."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("juno.jobs")


async def digest_daily(app: Any) -> None:
    logger.info("job digest_daily tick (push body deferred to #88)")


async def digest_weekly(app: Any) -> None:
    logger.info("job digest_weekly tick (push body deferred to #88)")


async def resurfacing(app: Any) -> None:
    logger.info("job resurfacing tick (push body deferred to #89)")
