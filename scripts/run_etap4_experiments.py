#!/usr/bin/env python3
"""Пять прогонов этапа 4 (разные LLM / RAG); пишет experiments/ETAP4_RUN_RESULTS.md."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / "docs" / "pipeline_walkthrough_news.txt"
OUT_MD = ROOT / "experiments" / "ETAP4_RUN_RESULTS.md"
RUNNER = ROOT / "scripts" / "etap4_run_one.py"
PRESET = "russian_folk"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k:
            os.environ[k] = v


def _base_child_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    env["FAIRYNEWS_RAG_BACKEND"] = "snapshot"
    env["PYTHONUTF8"] = "1"
    env["FAIRYNEWS_SAVE_REPORTS"] = "0"
    env.pop("FAIRYNEWS_LLM_MODE", None)
    return env


def _run_case(
    name: str,
    extra: dict[str, str],
) -> dict[str, object]:
    env = _base_child_env()
    env.update(extra)
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            str(NEWS),
            PRESET,
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
    err = (proc.stderr or "").strip()[:500]
    try:
        data = json.loads(line) if line else {"ok": False, "error": "empty stdout"}
    except json.JSONDecodeError:
        data = {
            "ok": False,
            "error": f"bad json stdout: {line[:200]}",
            "stderr": err,
            "code": proc.returncode,
        }
    data["_case_name"] = name
    data["_returncode"] = proc.returncode
    return data


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    _load_dotenv(ROOT / ".env")
    cases: list[tuple[str, dict[str, str]]] = [
        (
            "Вариант 1 — Groq (эконом, llama-3.3-70b-versatile)",
            {"FAIRYNEWS_LLM_BACKEND": "groq"},
        ),
        (
            "Вариант 2 — OpenAI gpt-4o-mini",
            {
                "FAIRYNEWS_LLM_BACKEND": "openai",
                "OPENAI_MODEL": "gpt-4o-mini",
            },
        ),
        (
            "Вариант 3 — GigaChat",
            {"FAIRYNEWS_LLM_BACKEND": "gigachat"},
        ),
        (
            "Вариант 4 — DeepSeek deepseek-chat",
            {"FAIRYNEWS_LLM_BACKEND": "deepseek"},
        ),
        (
            "Вариант 5 — GigaChat, узкий RAG (k=8)",
            {
                "FAIRYNEWS_LLM_BACKEND": "gigachat",
                "FAIRYNEWS_RAG_K": "8",
            },
        ),
    ]

    if not NEWS.is_file():
        print("Нет файла новости:", NEWS, file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list[dict[str, object]] = []
    for title, extra in cases:
        print("Running:", title, flush=True)
        if extra.get("FAIRYNEWS_LLM_BACKEND") == "openai":
            if not os.environ.get("OPENAI_API_KEY", "").strip():
                rows.append(
                    {
                        "_case_name": title,
                        "ok": False,
                        "skip": True,
                        "error": "нет OPENAI_API_KEY в окружении",
                    },
                )
                continue
        try:
            rows.append(_run_case(title, extra))
        except subprocess.TimeoutExpired:
            rows.append(
                {"_case_name": title, "ok": False, "error": "timeout 600s"},
            )
        except Exception as exc:
            rows.append(
                {"_case_name": title, "ok": False, "error": repr(exc)},
            )

    lines: list[str] = [
        "# Этап 4 — результаты пяти прогонов",
        "",
        f"**Время запуска (UTC):** `{stamp}`  ",
        f"**Новость:** `docs/pipeline_walkthrough_news.txt`  ",
        f"**Пресет:** `{PRESET}`, **RAG:** snapshot (кроме явного `FAIRYNEWS_RAG_K`).",
        "",
        "## Сводка",
        "",
        "| Вариант | Успех | Провайдер / модель | Сказка (симв.) | Якорь RAG | k |",
        "|---|:---:|---|---|---:|---:|",
    ]
    for r in rows:
        name = str(r.get("_case_name", "—"))
        if r.get("skip"):
            lines.append(
                f"| {name} | ⏭ пропуск | — | — | — | — |",
            )
            continue
        ok = "да" if r.get("ok") else "нет"
        prov = f"{r.get('llm_provider', '—')} / {r.get('llm_model', '—')}"
        if not r.get("ok"):
            prov = str(r.get("error", "—"))[:60]
        chars = r.get("tale_chars", "—")
        src = str(r.get("chosen_tale_source", "—"))[:40]
        rk = r.get("rag_k", "—")
        lines.append(
            f"| {name} | {ok} | {prov} | {chars} | {src} | {rk} |",
        )

    lines.extend(
        [
            "",
            "## Детали",
            "",
        ],
    )
    for r in rows:
        lines.append(f"### {r.get('_case_name', '—')}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(r, ensure_ascii=False, indent=2)[:8000])
        lines.append("```")
        lines.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
