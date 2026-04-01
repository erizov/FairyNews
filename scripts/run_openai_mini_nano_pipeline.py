#!/usr/bin/env python3
"""Два прогона пайплайна: ``gpt-4o-mini`` и ``gpt-4.1-nano`` (uniform).

Вторая модель — ближайший поддерживаемый «nano»-tier OpenAI на OpenRouter /
AITunnel: ``gpt-4o-nano`` **нет** в каталоге (400). Id: ``openai/gpt-4.1-nano``.

Нужны ``OPENAI_API_KEY`` и при прокси — ``OPENAI_API_BASE`` в корневом ``.env``
(как ``python -m app.llm_connect_try``). Для AITunnel / OpenRouter id модели
без ``/`` получает префикс ``openai/``.

Пример::

    python scripts/run_openai_mini_nano_pipeline.py
    python scripts/run_openai_mini_nano_pipeline.py --news docs/other.txt
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_MODELS: tuple[str, ...] = ("gpt-4o-mini", "gpt-4.1-nano")


def _utf8_stdout() -> None:
    so = sys.stdout
    reconf = getattr(so, "reconfigure", None)
    if callable(reconf):
        try:
            reconf(encoding="utf-8")
        except OSError:
            pass


def _clear_llm_scenario_env() -> None:
    keys = [
        "FAIRYNEWS_LLM_PER_STAGE",
        "FAIRYNEWS_TEST_PROFILE",
    ]
    for k in keys:
        os.environ.pop(k, None)
    for k in list(os.environ.keys()):
        if k.startswith("FAIRYNEWS_STAGE_"):
            os.environ.pop(k, None)


def _run_pipeline(
    *,
    news: str,
    preset_id: str,
    model_raw: str,
    log_path: Path,
) -> dict[str, Any]:
    from dotenv import load_dotenv

    from app.agents_pipeline import run_four_agent_pipeline
    from app.llm_utils import (
        openai_base_url_from_env,
        resolve_openai_chat_model_id,
    )
    from app.presets import get_preset

    load_dotenv(_ROOT / ".env", override=True)
    base = openai_base_url_from_env()
    ex = model_raw.strip() or None
    model = resolve_openai_chat_model_id(explicit=ex, base_url=base)

    os.environ["FAIRYNEWS_RAG_BACKEND"] = "snapshot"
    os.environ["FAIRYNEWS_LLM_BACKEND"] = "openai"
    os.environ["FAIRYNEWS_LLM_UNIFORM_STAGES"] = "1"
    os.environ["FAIRYNEWS_UNIFORM_BACKEND"] = "openai"
    os.environ["FAIRYNEWS_UNIFORM_MODEL"] = model
    os.environ["FAIRYNEWS_TEST_PROFILE"] = f"openai_uniform_{model_raw}"

    preset = get_preset(preset_id)
    hint = str(preset["retrieval_hint"])
    domains = preset.get("domains")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] start model={model!r} preset={preset_id}\n")

    try:
        out = run_four_agent_pipeline(
            news,
            hint,
            domains,
            preset_id=preset_id,
            news_id=None,
            rag_backend="snapshot",
        )
        rep = out.get("report") or {}
        timing = rep.get("timing") or {}
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(
                f"[{stamp}] ok model={model!r} "
                f"wall={timing.get('pipeline_wall_sec')}\n"
            )
        return {"ok": True, "report": rep, "output": out, "model_resolved": model}
    except Exception as exc:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] error model={model!r} {exc!r}\n")
        return {"ok": False, "error": str(exc), "model_resolved": model}


def main() -> None:
    _utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--news",
        type=Path,
        default=_ROOT / "docs" / "pipeline_walkthrough_news.txt",
    )
    ap.add_argument("--preset", default="russian_folk")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="каталог (по умолчанию experiments/openai_mini_nano/<UTC>/ )",
    )
    args = ap.parse_args()

    news_path = args.news
    if not news_path.is_file():
        print(f"Нет файла новости: {news_path}", file=sys.stderr)
        raise SystemExit(2)
    news = news_path.read_text(encoding="utf-8").strip()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = args.out or (_ROOT / "experiments" / "openai_mini_nano" / stamp)
    out.mkdir(parents=True, exist_ok=True)
    (out / "news_input.txt").write_text(news, encoding="utf-8")

    log_path = out / "run.log"
    log_path.write_text("", encoding="utf-8")

    rows: list[tuple[str, dict[str, Any]]] = []
    _clear_llm_scenario_env()
    for raw in _MODELS:
        res = _run_pipeline(
            news=news,
            preset_id=args.preset,
            model_raw=raw,
            log_path=log_path,
        )
        rows.append((raw, res))
        safe = raw.replace("/", "_")
        if res.get("ok"):
            rp = res.get("report")
            if isinstance(rp, dict):
                (out / f"report_{safe}.json").write_text(
                    json.dumps(rp, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

    # Краткая сводка Markdown
    lines = [
        "# Прогон пайплайна: gpt-4o-mini и gpt-4.1-nano",
        "",
        f"- Новость: `{news_path.relative_to(_ROOT)}`",
        f"- Пресет: `{args.preset}`",
        "- Режим: uniform, backend `openai`",
        "",
        "| Модель (запрос) | Id для API | Успех | wall_s | llm_s | tale_chars |",
        "|---|---|---|---:|---:|---:|",
    ]
    for raw, res in rows:
        ok = "да" if res.get("ok") else "нет"
        mres = str(res.get("model_resolved", ""))
        if res.get("ok"):
            rep = res.get("report") or {}
            tim = rep.get("timing") or {}
            gen = rep.get("generation") or {}
            wall = tim.get("pipeline_wall_sec")
            llm_t = tim.get("llm_total_sec")
            tc = gen.get("tale_chars")
        else:
            wall = llm_t = tc = "—"
        lines.append(
            f"| `{raw}` | `{mres}` | {ok} | {wall} | {llm_t} | {tc} |"
        )
    lines.append("")
    for raw, res in rows:
        if not res.get("ok"):
            lines.append(f"**Ошибка** (`{raw}`): `{res.get('error')}`")
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")

    print("out:", out)
    print("log:", log_path)
    print("summary:", out / "SUMMARY.md")
    for raw, res in rows:
        print(raw, "OK" if res.get("ok") else f"FAIL {res.get('error','')[:120]}")


if __name__ == "__main__":
    main()
