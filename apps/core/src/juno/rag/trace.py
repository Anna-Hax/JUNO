"""One JSON line per search, under the local data directory."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("juno.rag")


def record_search_trace(
    trace_dir: Path,
    *,
    query: str,
    mode: str,
    hits: list[dict[str, Any]],
    llm_used: bool,
    cites_valid: bool,
) -> None:
    """Append a trace. A failed write must not fail the answer."""
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "query": (query or "")[:240],
        "mode": mode,
        "hit_ids": [hit.get("chroma_id") for hit in hits],
        "scores": [hit.get("score") for hit in hits],
        "llm_used": llm_used,
        "cites_valid": cites_valid,
    }
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)
        path = trace_dir / f"{datetime.now(UTC):%Y-%m-%d}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("search trace write failed")
