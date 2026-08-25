"""Text extractors for inbox files and URLs (txt / md / pdf / html / url)."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any

import httpx

MAX_FILE_BYTES = 50 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 30.0
USER_AGENT = "Juno/0.1 (+local-first personal knowledge graph)"

TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
HTML_SUFFIXES = {".html", ".htm"}
_URL_ONLY = re.compile(r"^https?://\S+$", re.IGNORECASE)
_TITLE_RE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")


class ExtractError(Exception):
    """Extraction failed; the pipeline records a failed capture."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass
class Extracted:
    text: str
    title: str | None
    uri: str | None
    source_type: str
    raw: dict[str, Any] = field(default_factory=dict)


def _single_http_url(text: str) -> str | None:
    stripped = (text or "").strip()
    if not stripped or "\n" in stripped or "\r" in stripped:
        return None
    if _URL_ONLY.match(stripped):
        return stripped
    return None


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _extract_text_file(path: Path) -> Extracted:
    text = _read_text(path)
    return Extracted(
        text=text,
        title=path.stem,
        uri=_file_uri(path),
        source_type="upload",
        raw={"extractor": path.suffix.lstrip(".").lower() or "txt", "filename": path.name},
    )


def _extract_pdf(path: Path) -> Extracted:
    import pymupdf

    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001 — any open failure is a bad PDF
        raise ExtractError(f"unreadable pdf: {exc}") from exc

    try:
        if getattr(doc, "needs_pass", False):
            raise ExtractError("encrypted pdf")
        if doc.is_encrypted and not doc.authenticate(""):
            raise ExtractError("encrypted pdf")
        if not getattr(doc, "is_pdf", True):
            raise ExtractError("unreadable pdf: not a pdf")
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text() or "")
        meta = doc.metadata or {}
        title = (meta.get("title") or "").strip() or path.stem
        text = "\n".join(pages).strip()
        return Extracted(
            text=text,
            title=title,
            uri=_file_uri(path),
            source_type="upload",
            raw={
                "extractor": "pdf",
                "filename": path.name,
                "pages": doc.page_count,
            },
        )
    finally:
        doc.close()


def _parse_internet_shortcut(path: Path) -> str:
    text = _read_text(path)
    for line in text.splitlines():
        if line.lower().startswith("url="):
            url = line.split("=", 1)[1].strip()
            if url.startswith(("http://", "https://")):
                return url
    raise ExtractError("url file has no http(s) shortcut")


def _rough_text_from_html(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_html(html: str, *, url: str | None = None) -> Extracted:
    """Pull main text from HTML (trafilatura, with a tag-strip fallback)."""
    from trafilatura import extract as trafi_extract

    text = trafi_extract(
        html,
        url=url,
        favor_recall=True,
        include_comments=False,
        include_tables=True,
    )
    title: str | None = None
    try:
        from trafilatura import extract_metadata

        meta = extract_metadata(html, default_url=url)
        if meta is not None:
            title = getattr(meta, "title", None) or None
    except Exception:  # noqa: BLE001
        title = None
    if not title:
        match = _TITLE_RE.search(html)
        if match:
            title = unescape(re.sub(r"\s+", " ", match.group(1))).strip() or None
    if not (text and text.strip()):
        text = _rough_text_from_html(html)
    if not text.strip():
        raise ExtractError("no extractable text from html")
    return Extracted(
        text=text.strip(),
        title=title,
        uri=url,
        source_type="url" if url and url.startswith(("http://", "https://")) else "upload",
        raw={"extractor": "html", "uri": url},
    )


def _extract_html_file(path: Path) -> Extracted:
    html = _read_text(path)
    extracted = extract_html(html, url=_file_uri(path))
    extracted.source_type = "upload"
    extracted.raw["filename"] = path.name
    extracted.uri = _file_uri(path)
    if not extracted.title:
        extracted.title = path.stem
    return extracted


async def extract_url(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Extracted:
    if not url.startswith(("http://", "https://")):
        raise ExtractError("url must be http(s)")
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        )
    try:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExtractError(f"url fetch failed: {exc}") from exc
        if len(response.content) > MAX_FILE_BYTES:
            raise ExtractError("url response too large")
        html = response.text
    finally:
        if own_client:
            await client.aclose()
    extracted = await asyncio.to_thread(extract_html, html, url=url)
    extracted.source_type = "url"
    extracted.uri = url
    return extracted


async def extract_path(path: Path) -> Extracted:
    if not path.is_file():
        raise ExtractError("file not found")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ExtractError("file too large")
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        extracted = await asyncio.to_thread(_extract_text_file, path)
        url = _single_http_url(extracted.text)
        if url:
            return await extract_url(url)
        return extracted
    if suffix == ".pdf":
        return await asyncio.to_thread(_extract_pdf, path)
    if suffix in HTML_SUFFIXES:
        return await asyncio.to_thread(_extract_html_file, path)
    if suffix == ".url":
        url = await asyncio.to_thread(_parse_internet_shortcut, path)
        return await extract_url(url)
    raise ExtractError(f"unsupported file type: {suffix or path.name}")
