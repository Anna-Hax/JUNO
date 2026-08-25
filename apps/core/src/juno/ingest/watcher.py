"""Inbox folder watcher — drop files to ingest (ADR-01: queue onto the serve loop)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from juno.ingest.pipeline import IngestResult

logger = logging.getLogger("juno.ingest.watcher")

PROCESSED_DIR = ".processed"
FAILED_DIR = ".failed"
IGNORE_NAMES = {".gitkeep"}
IGNORE_SUFFIXES = {".tmp", ".temp", ".part", ".crdownload", ".download"}

IngestFn = Callable[[Path], Awaitable[IngestResult]]
PausedFn = Callable[[], bool]


def should_skip(path: Path) -> bool:
    name = path.name
    if name.startswith("."):
        return True
    if name in IGNORE_NAMES:
        return True
    if path.suffix.lower() in IGNORE_SUFFIXES:
        return True
    return False


async def wait_stable(
    path: Path,
    *,
    checks: int = 2,
    interval: float = 0.15,
    attempts: int = 50,
    min_age: float = 0.5,
) -> bool:
    """Wait until size+mtime stop changing so we don't ingest a half-copied file."""
    try:
        if path.is_file() and (time.time() - path.stat().st_mtime) >= min_age:
            return True
    except OSError:
        return False
    last: tuple[int, int] | None = None
    stable = 0
    for _ in range(attempts):
        if not path.is_file():
            return False
        stat = path.stat()
        marker = (stat.st_size, stat.st_mtime_ns)
        if last is None:
            last = marker
            if checks <= 1:
                return True
        elif marker == last:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
            last = marker
        await asyncio.sleep(interval)
    return path.is_file()


def archive_inbox_file(inbox_dir: Path, path: Path, status: str) -> Path | None:
    folder = FAILED_DIR if status == "failed" else PROCESSED_DIR
    dest_dir = inbox_dir / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if dest.exists():
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        dest = dest_dir / f"{path.stem}-{stamp}{path.suffix}"
    try:
        path.replace(dest)
        return dest
    except OSError:
        logger.warning("could not archive %s -> %s", path, dest, exc_info=True)
        return None


class _QueueHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[Path]) -> None:
        super().__init__()
        self._loop = loop
        self._queue = queue

    def _submit(self, src: str) -> None:
        path = Path(src)
        if should_skip(path):
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, path)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._submit(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._submit(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            dest = getattr(event, "dest_path", None) or event.src_path
            self._submit(dest)


class InboxWatcher:
    """Watch `inbox_dir` and ingest new files on the shared asyncio loop."""

    def __init__(
        self,
        inbox_dir: Path,
        ingest: IngestFn,
        *,
        is_paused: PausedFn | None = None,
        settle_checks: int = 2,
        settle_interval: float = 0.15,
        settle_min_age: float = 0.5,
    ) -> None:
        self.inbox_dir = inbox_dir
        self._ingest = ingest
        self._is_paused = is_paused
        self._settle_checks = settle_checks
        self._settle_interval = settle_interval
        self._settle_min_age = settle_min_age
        self._queue: asyncio.Queue[Path] | None = None
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._observer: Observer | None = None
        self._inflight: set[str] = set()
        self._done: set[str] = set()

    async def start(self) -> None:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="juno-inbox-watcher")
        observer = Observer()
        observer.schedule(_QueueHandler(loop, self._queue), str(self.inbox_dir), recursive=False)
        observer.start()
        self._observer = observer
        logger.info("Inbox watcher started on %s", self.inbox_dir.resolve())
        await self.scan_existing()

    async def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            self._observer.stop()
            observer = self._observer
            self._observer = None
            await asyncio.to_thread(observer.join, 2)
        if self._task is not None:
            await self._task
            self._task = None
        logger.info("Inbox watcher stopped")

    async def scan_existing(self) -> int:
        """Ingest files already in the inbox (dropped while Juno was off)."""
        n = 0
        if not self.inbox_dir.is_dir():
            return 0
        for path in sorted(self.inbox_dir.iterdir()):
            if path.is_file() and not should_skip(path):
                await self._process(path)
                n += 1
        return n

    async def _run(self) -> None:
        assert self._queue is not None
        while not self._stop.is_set():
            try:
                path = await asyncio.wait_for(self._queue.get(), timeout=0.4)
            except TimeoutError:
                continue
            await self._process(path)

    async def _process(self, path: Path) -> None:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in self._inflight or key in self._done:
            return
        if self._is_paused is not None and self._is_paused():
            return
        if should_skip(path) or not path.is_file():
            return
        self._inflight.add(key)
        try:
            if not await wait_stable(
                path,
                checks=self._settle_checks,
                interval=self._settle_interval,
                min_age=self._settle_min_age,
            ):
                return
            result = await self._ingest(path)
            archived = await asyncio.to_thread(
                archive_inbox_file, self.inbox_dir, path, result.status
            )
            if archived is not None:
                self._done.add(key)
            logger.info(
                "Ingested inbox file %s -> capture %s (%s)",
                path.name,
                result.capture_id,
                result.status,
            )
        except Exception:  # noqa: BLE001
            logger.exception("inbox ingest failed for %s", path)
        finally:
            self._inflight.discard(key)
