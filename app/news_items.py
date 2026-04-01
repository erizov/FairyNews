"""Публичный список новостей (RSS) и разрешение id для пайплайна."""

from __future__ import annotations

import os
from typing import Any

from app.live_news import (
    get_cached_news_items,
    get_item_by_id,
    offline_fallback_items,
)


def _fallback_enabled() -> bool:
    raw = os.environ.get("FAIRYNEWS_NEWS_OFFLINE", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


_SLOT_IDS: tuple[str, ...] = (
    "en-0",
    "en-1",
    "en-2",
    "ru-0",
    "ru-1",
    "ru-2",
)


def _merge_slots_with_stubs(
    live: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Всегда 6 карточек: живой RSS по id, пустые слоты — wire-заглушки."""
    by_id = {str(x["id"]): x for x in live}
    stubs = {str(x["id"]): x for x in offline_fallback_items()}
    partial = bool(live)
    out: list[dict[str, Any]] = []
    for sid in _SLOT_IDS:
        if sid in by_id:
            out.append(dict(by_id[sid]))
        elif sid in stubs:
            row = dict(stubs[sid])
            if partial:
                src = str(row.get("source", "")).strip()
                row["source"] = f"{src} · слот без RSS" if src else "слот без RSS"
            out.append(row)
    return out


def list_public_news_items() -> list[dict[str, Any]]:
    """Шесть слотов: RSS; при сбое части лент — заглушки для пустых слотов.

    Полностью офлайн: ``FAIRYNEWS_NEWS_OFFLINE`` — только статический набор.
    """
    if _fallback_enabled():
        return offline_fallback_items()
    live = get_cached_news_items()
    return _merge_slots_with_stubs(live)


def get_news_item(news_id: str) -> dict[str, Any]:
    """Карточка по id (en-0 … ru-2): кэш RSS, иначе заглушка слота (как в UI)."""
    got = get_item_by_id(news_id)
    if got is not None:
        return got
    if _fallback_enabled():
        by = {str(x["id"]): x for x in offline_fallback_items()}
        if news_id in by:
            return dict(by[news_id])
        raise KeyError(news_id)
    stubs = {str(x["id"]): x for x in offline_fallback_items()}
    if news_id in stubs:
        return dict(stubs[news_id])
    raise KeyError(news_id)


def list_news_ids() -> set[str]:
    """Все известные на данный момент id (для валидации)."""
    return {str(x["id"]) for x in list_public_news_items()}
