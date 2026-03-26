"""Character-based chunking with overlap for tale texts."""

from __future__ import annotations


def chunk_text(
    text: str,
    target_chars: int,
    overlap_chars: int,
) -> list[str]:
    """Split *text* into overlapping segments of about *target_chars*."""
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    if target_chars <= 0:
        raise ValueError("target_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= target_chars:
        raise ValueError("overlap_chars must be in [0, target_chars)")

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + target_chars, length)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = end - overlap_chars
    return chunks
