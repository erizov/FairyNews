"""SQLite-хранилище до 100 последних прогонов (полный JSON отчёта)."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from rag.config import ROOT

_DEFAULT_DB = ROOT / "data" / "reports" / "runs.db"
_MAX_ROWS = 100
_MAX_LLM_LOG_RUNS = 5


def db_path() -> Path:
    override = os.environ.get("FAIRYNEWS_REPORTS_DB_PATH", "").strip()
    if override:
        return Path(override)
    return _DEFAULT_DB


def _connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_logs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            trace TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runs_created_at "
        "ON runs(created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_logs_created_at "
        "ON llm_logs(created_at DESC)"
    )


def _trim_llm_logs(conn: sqlite3.Connection, keep: int = _MAX_LLM_LOG_RUNS) -> None:
    cur = conn.execute("SELECT COUNT(*) FROM llm_logs")
    n = int(cur.fetchone()[0])
    if n <= keep:
        return
    cur = conn.execute(
        """
        SELECT run_id FROM llm_logs
        ORDER BY created_at ASC, run_id ASC
        LIMIT ?
        """,
        (n - keep,),
    )
    old = [r[0] for r in cur.fetchall()]
    conn.executemany(
        "DELETE FROM llm_logs WHERE run_id = ?",
        [(i,) for i in old],
    )


def insert_run(
    payload: dict[str, Any],
    *,
    llm_trace: list[Any] | None = None,
) -> None:
    """Сохранить отчёт; обрезать runs; опционально журнал LLM (последние 5)."""
    run_id = str(payload.get("run_id", ""))
    if not run_id:
        raise ValueError("run_id required")
    created = str(payload.get("created_at", ""))
    blob = json.dumps(payload, ensure_ascii=False)
    trace_blob: str | None = None
    if llm_trace is not None:
        trace_blob = json.dumps(llm_trace, ensure_ascii=False)
    with _connect() as conn:
        init_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, created_at, payload) "
            "VALUES (?, ?, ?)",
            (run_id, created, blob),
        )
        if trace_blob is not None:
            conn.execute(
                "INSERT OR REPLACE INTO llm_logs (run_id, created_at, trace) "
                "VALUES (?, ?, ?)",
                (run_id, created, trace_blob),
            )
            _trim_llm_logs(conn, _MAX_LLM_LOG_RUNS)
        cur = conn.execute("SELECT COUNT(*) FROM runs")
        n = int(cur.fetchone()[0])
        if n > _MAX_ROWS:
            cur = conn.execute(
                """
                SELECT run_id FROM runs
                ORDER BY created_at ASC, run_id ASC
                LIMIT ?
                """,
                (n - _MAX_ROWS,),
            )
            old_ids = [r[0] for r in cur.fetchall()]
            conn.executemany(
                "DELETE FROM runs WHERE run_id = ?",
                [(i,) for i in old_ids],
            )
            conn.executemany(
                "DELETE FROM llm_logs WHERE run_id = ?",
                [(i,) for i in old_ids],
            )
        conn.commit()


def load_llm_log(run_id: str) -> dict[str, Any] | None:
    """Полный объект журнала: run_id, created_at, steps (массив шагов)."""
    with _connect() as conn:
        init_schema(conn)
        cur = conn.execute(
            "SELECT created_at, trace FROM llm_logs WHERE run_id = ?",
            (run_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        created_at, raw = row[0], row[1]
        try:
            steps = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return {
            "run_id": run_id,
            "created_at": created_at,
            "steps": steps,
        }


def load_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        init_schema(conn)
        cur = conn.execute(
            "SELECT payload FROM runs WHERE run_id = ?",
            (run_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None


def list_run_rows() -> list[tuple[str, str, dict[str, Any]]]:
    """(run_id, created_at, payload) новее первыми, не более MAX_ROWS."""
    with _connect() as conn:
        init_schema(conn)
        cur = conn.execute(
            """
            SELECT run_id, created_at, payload FROM runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (_MAX_ROWS,),
        )
        out: list[tuple[str, str, dict[str, Any]]] = []
        for rid, created, blob in cur.fetchall():
            try:
                payload = json.loads(blob)
            except json.JSONDecodeError:
                continue
            out.append((rid, created, payload))
        return out
