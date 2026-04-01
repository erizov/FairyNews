"""Shared news text normalization for agents."""

from __future__ import annotations

# Согласовано с GenerateRequest.news_text (max 8000)
_MAX_NEWS_CHARS = 8000


def normalize_news_text(text: str) -> str:
    """Чистит пробелы по строкам, сохраняет переносы; режет по длине."""
    lines: list[str] = []
    for line in text.splitlines():
        cleaned = " ".join(line.split())
        if cleaned:
            lines.append(cleaned)
    out = "\n".join(lines)
    if len(out) > _MAX_NEWS_CHARS:
        return out[:_MAX_NEWS_CHARS] + "…"
    return out
