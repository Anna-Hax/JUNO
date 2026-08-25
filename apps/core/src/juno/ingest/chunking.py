"""Split extracted text into overlapping chunks for embeddings."""

from __future__ import annotations

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 150


def chunk_text(
    text: str,
    *,
    size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Pack text into chunks of about `size` characters with `overlap`.

    Breaks on the last space before the size limit when possible so words are
    not split. Empty / whitespace-only input yields no chunks.
    """
    body = (text or "").strip()
    if not body:
        return []
    if size < 1:
        raise ValueError("size must be >= 1")
    overlap = max(0, min(overlap, size - 1))
    if len(body) <= size:
        return [body]

    chunks: list[str] = []
    start = 0
    length = len(body)
    while start < length:
        end = min(start + size, length)
        if end < length:
            brk = body.rfind(" ", start, end)
            if brk > start:
                end = brk
        piece = body[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        nxt = end - overlap
        start = nxt if nxt > start else end
    return chunks
