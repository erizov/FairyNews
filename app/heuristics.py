"""Lightweight news–tale overlap metrics (этап 4)."""

from __future__ import annotations

from typing import Any


def compute_news_tale_heuristics(
    summary: str,
    themes: list[str],
    tale: str,
    *,
    chunk_sources: list[str],
) -> dict[str, Any]:
    """Theme / keyword overlap; no external embeddings."""
    tale_l = tale.lower()
    summary_l = summary.lower()

    theme_hits = [
        t for t in themes if len(str(t)) > 2 and str(t).lower() in tale_l
    ]
    summary_words = [
        w.strip(".,!?«»\"'()")
        for w in summary_l.split()
        if len(w) > 4 and w[:2].isalpha()
    ]
    keyword_hits = [w for w in summary_words if w in tale_l]
    denom = max(len(summary_words), 1)
    keyword_score = round(len(keyword_hits) / denom, 4)

    short_sources = [s for s in chunk_sources if s][:5]

    return {
        "theme_overlap_count": len(theme_hits),
        "theme_hits": theme_hits,
        "keyword_overlap_count": len(keyword_hits),
        "keyword_overlap_score": keyword_score,
        "rag_source_prefixes": short_sources,
    }
