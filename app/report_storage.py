"""Persist run reports in SQLite (до 100 записей, полный JSON)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from app.report_trim import report_max_bytes_from_env, trim_report_for_max_bytes
from app.run_database import insert_run, list_run_rows, load_run as db_load_run


def _first_n_words(text: str, n: int) -> str:
    """Склейка первых n слов без перевода и без обрезки середины слова."""
    parts = str(text or "").split()
    if not parts:
        return ""
    return " ".join(parts[:n])


def _is_stub_llm_report(payload: dict[str, Any]) -> bool:
    """True, если все этапы на offline/stub-провайдере."""
    llm = payload.get("llm") or {}
    stages = llm.get("stages") or {}
    if stages:
        for info in stages.values():
            if str((info or {}).get("provider", "")) != "offline":
                return False
        return True
    return str(llm.get("provider", "")) == "offline"


def _persist_stub_reports() -> bool:
    raw = os.environ.get("FAIRYNEWS_PERSIST_STUB_REPORTS", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def save_run_report(payload: dict[str, Any]) -> str | None:
    """Записать отчёт в БД; stub не сохраняем без FAIRYNEWS_PERSIST_STUB_REPORTS."""
    if _is_stub_llm_report(payload) and not _persist_stub_reports():
        return None
    run_id = str(payload.get("run_id") or uuid.uuid4())
    payload = {**payload, "run_id": run_id}
    trace = payload.pop("llm_trace", None)
    limit = report_max_bytes_from_env()
    if limit is not None:
        payload = trim_report_for_max_bytes(payload, limit)
    insert_run(payload, llm_trace=trace)
    return run_id


def list_run_summaries() -> list[dict[str, Any]]:
    """Новее первыми: колонки для таблицы отчётов."""
    rows: list[dict[str, Any]] = []
    for _rid, _created, data in list_run_rows():
        timing = data.get("timing") or {}
        news_raw = str(data.get("news_raw", ""))
        tale = str(data.get("tale", ""))
        brief = data.get("news_brief") or {}
        summary_line = str(brief.get("summary", ""))
        news_head = news_raw if news_raw else summary_line
        rid = str(data.get("run_id", ""))
        rows.append(
            {
                "run_id": rid,
                "created_at": data.get("created_at", ""),
                "run_by": data.get("run_by", "anonymous"),
                "duration_sec": timing.get("pipeline_wall_sec"),
                "news_preview": _first_n_words(news_head, 30),
                "tale_preview": _first_n_words(tale, 30),
                "chosen_tale_source": data.get("chosen_tale_source", ""),
                "tale_chars": len(tale),
                "audit_approved": (
                    (data.get("audit") or {}).get("approved", False)
                ),
                "rag_backend": (data.get("rag") or {}).get("backend", ""),
                "news_id": data.get("news_id"),
                "llm_log_url": (
                    f"/reports-ui/llm-log.html?id={rid}"
                    if rid
                    else None
                ),
            }
        )
    return rows


def load_run_report(run_id: str) -> dict[str, Any] | None:
    return db_load_run(run_id)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
