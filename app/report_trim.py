"""Ограничение размера сохраняемого отчёта (байты UTF-8 после сериализации)."""

from __future__ import annotations

import copy
import json
import os
from typing import Any


def _report_byte_size(data: dict[str, Any]) -> int:
    return len(
        json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    )


def trim_report_for_max_bytes(
    payload: dict[str, Any],
    max_bytes: int,
) -> dict[str, Any]:
    """Возвращает копию ``payload``, укладывающуюся в ``max_bytes`` UTF-8.

    Длинные поля (сказка, сниппеты RAG) укорачиваются; пути и структура
    отчёта не вычищаются — только объём текста.
    """
    if max_bytes <= 0:
        return payload
    out = copy.deepcopy(payload)
    if _report_byte_size(out) <= max_bytes:
        return out
    meta = out.setdefault("_size_limit", {})
    meta["max_bytes"] = max_bytes
    meta["truncated"] = True

    tale_key = "tale"
    while tale_key in out and _report_byte_size(out) > max_bytes:
        tale = str(out.get(tale_key, ""))
        if len(tale) <= 400:
            break
        cut = max(200, len(tale) // 2)
        out[tale_key] = tale[:cut].rstrip() + "…"

    rag = out.get("rag")
    if isinstance(rag, dict):
        top = rag.get("top_k")
        if isinstance(top, list):
            for row in top:
                if not isinstance(row, dict):
                    continue
                sn = str(row.get("snippet", ""))
                if len(sn) > 120:
                    row["snippet"] = sn[:117].rstrip() + "…"

    while _report_byte_size(out) > max_bytes and tale_key in out:
        tale = str(out.get(tale_key, ""))
        if len(tale) <= 200:
            break
        out[tale_key] = tale[: max(100, len(tale) // 2)].rstrip() + "…"

    ap = out.get("agent_prompts")
    if isinstance(ap, dict):
        for _stage, block in ap.items():
            if not isinstance(block, dict):
                continue
            for ukey in ("user", "system"):
                raw_t = str(block.get(ukey, ""))
                if len(raw_t) > 6000:
                    block[ukey] = raw_t[:5997].rstrip() + "…"

    if _report_byte_size(out) > max_bytes:
        meta["note"] = "report still oversized; trim tale/rag manually"
    return out


def report_max_bytes_from_env() -> int | None:
    """``FAIRYNEWS_REPORT_MAX_BYTES`` / 0 = без лимита."""
    raw = os.environ.get("FAIRYNEWS_REPORT_MAX_BYTES", "").strip()
    if not raw:
        return 200_000
    try:
        n = int(raw)
    except ValueError:
        return 200_000
    if n <= 0:
        return None
    return n
