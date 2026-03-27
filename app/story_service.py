"""Shared news text normalization for agents."""

from __future__ import annotations

_MAX_NEWS_CHARS = 2500


def normalize_news_text(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) > _MAX_NEWS_CHARS:
        return collapsed[:_MAX_NEWS_CHARS] + "…"
    return collapsed
