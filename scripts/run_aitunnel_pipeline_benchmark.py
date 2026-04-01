#!/usr/bin/env python3
"""Два прогона пайплайна через OpenAI-compatible API (AITunnel и др.).

Сценарии: (A) разные дешёвые модели по этапам; (B) одна модель на все этапы.
Один текст новости → логи, JSON отчёты, HTML, скриншоты, рекомендация.

Требуется в .env: OPENAI_API_KEY, OPENAI_API_BASE (например
https://api.aitunnel.ru/v1). Ключ не храните в коде.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Дешёвые модели в формате OpenRouter / AITunnel (при ошибке 404 смените в
# кабинете на доступные вам id).
# ID из каталога AITunnel / OpenRouter (gpt-4o-mini у многих прокси не заведён).
_MODEL_UNIFORM = "openai/gpt-5"
_MODEL_JSON_STAGES = "openai/gpt-5"
_MODEL_STORY_ONLY = "openai/gpt-4o"


def _utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except OSError:
            pass


def _log(path: Path, msg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {msg}\n")


def _clear_scenario_env() -> None:
    keys = [
        "FAIRYNEWS_LLM_PER_STAGE",
        "FAIRYNEWS_LLM_UNIFORM_STAGES",
        "FAIRYNEWS_UNIFORM_BACKEND",
        "FAIRYNEWS_UNIFORM_MODEL",
        "FAIRYNEWS_TEST_PROFILE",
        "FAIRYNEWS_LLM_BACKEND",
    ]
    for k in keys:
        os.environ.pop(k, None)
    for k in list(os.environ.keys()):
        if k.startswith("FAIRYNEWS_STAGE_"):
            os.environ.pop(k, None)


def _apply_mixed_cheap() -> None:
    """Сценарий 1: разные модели (JSON дешевле, story — flash)."""
    os.environ["FAIRYNEWS_LLM_PER_STAGE"] = "1"
    os.environ["FAIRYNEWS_TEST_PROFILE"] = "scenario_mixed_models"
    for stage, model in (
        ("NEWS", _MODEL_JSON_STAGES),
        ("STORY", _MODEL_STORY_ONLY),
        ("AUDIT", _MODEL_JSON_STAGES),
        ("QA", _MODEL_JSON_STAGES),
    ):
        os.environ[f"FAIRYNEWS_STAGE_{stage}_BACKEND"] = "openai"
        os.environ[f"FAIRYNEWS_STAGE_{stage}_MODEL"] = model


def _apply_uniform_cheap() -> None:
    """Сценарий 2: одна дешёвая модель на все этапы."""
    os.environ["FAIRYNEWS_LLM_UNIFORM_STAGES"] = "1"
    os.environ["FAIRYNEWS_UNIFORM_BACKEND"] = "openai"
    os.environ["FAIRYNEWS_UNIFORM_MODEL"] = _MODEL_UNIFORM
    os.environ["FAIRYNEWS_TEST_PROFILE"] = "scenario_uniform_model"


def _default_news_tass() -> str:
    """Краткая сводка темы ТАСС (веб, март 2026). Источник внизу."""
    return (
        "(ТАСС). Минобороны России сообщило, что за прошедшую ночь средства "
        "ПВО уничтожили 155 украинских беспилотников над российскими "
        "регионами. Пострадавших на земле не сообщалось.\n\n"
        "Источник: https://tass.com/defense/2108341"
    )


def _run_once(
    log_file: Path,
    preset_id: str,
    news: str,
) -> dict[str, Any]:
    from dotenv import load_dotenv

    from app.agents_pipeline import run_four_agent_pipeline
    from app.presets import get_preset

    load_dotenv(_ROOT / ".env", override=True)

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise RuntimeError("В .env нужен OPENAI_API_KEY (AITunnel / прокси).")
    base = (
        os.environ.get("OPENAI_API_BASE", "").strip()
        or os.environ.get("OPENAI_BASE_URL", "").strip()
    )
    if not base:
        raise RuntimeError(
            "В .env нужен OPENAI_API_BASE (или OPENAI_BASE_URL), "
            "напр. https://api.aitunnel.ru/v1"
        )

    os.environ["FAIRYNEWS_RAG_BACKEND"] = "snapshot"
    os.environ.pop("FAIRYNEWS_LLM_MODE", None)
    # Явно openai-совместимый контур; не тянуть GigaChat из цепочки.
    os.environ["FAIRYNEWS_LLM_BACKEND"] = "openai"

    preset = get_preset(preset_id)
    hint = str(preset["retrieval_hint"])
    domains = preset.get("domains")

    prof = os.environ.get("FAIRYNEWS_TEST_PROFILE", "?")
    _log(log_file, f"start {prof} preset={preset_id}")

    try:
        out_data = run_four_agent_pipeline(
            news,
            hint,
            domains,
            preset_id=preset_id,
            news_id=None,
            rag_backend="snapshot",
        )
        rep = out_data.get("report") or {}
        timing = rep.get("timing") or {}
        _log(
            log_file,
            f"ok {prof} wall_sec={timing.get('pipeline_wall_sec')} "
            f"llm_total={timing.get('llm_total_sec')}",
        )
        return {"ok": True, "report": rep, "output": out_data}
    except Exception as exc:
        _log(log_file, f"error {prof} {type(exc).__name__}: {exc}")
        return {"ok": False, "error": str(exc)}


def _write_rec_md(
    path: Path,
    mixed: dict[str, Any],
    uni: dict[str, Any],
) -> None:
    def _timing(b: dict[str, Any], key: str) -> str:
        if not b.get("ok"):
            return "—"
        t = (b.get("report") or {}).get("timing") or {}
        v = t.get(key)
        return f"{v}" if v is not None else "—"

    def _tale_len(b: dict[str, Any]) -> str:
        if not b.get("ok"):
            return "—"
        g = (b.get("report") or {}).get("generation") or {}
        return str(g.get("tale_chars", "—"))

    lines = [
        "# Рекомендация по моделям (AITunnel / OpenRouter)",
        "",
        "## Что сравнивали",
        "",
        "- **Сценарий 1 (mixed):** news/audit/qa — "
        f"`{_MODEL_JSON_STAGES}`, story — `{_MODEL_STORY_ONLY}`.",
        "- **Сценарий 2 (uniform):** все этапы — "
        f"`{_MODEL_UNIFORM}`.",
        "",
        "## Метрики",
        "",
        "| Показатель | Mixed | Uniform |",
        "|------------|-------|---------|",
        f"| pipeline_wall_sec | {_timing(mixed, 'pipeline_wall_sec')} | "
        f"{_timing(uni, 'pipeline_wall_sec')} |",
        f"| llm_total_sec | {_timing(mixed, 'llm_total_sec')} | "
        f"{_timing(uni, 'llm_total_sec')} |",
        f"| tale_chars | {_tale_len(mixed)} | {_tale_len(uni)} |",
        "",
        "## Вывод",
        "",
    ]

    if mixed.get("ok") and uni.get("ok"):
        tm = float(
            (mixed.get("report") or {}).get("timing", {}).get("llm_total_sec") or 0
        )
        tu = float(
            (uni.get("report") or {}).get("timing", {}).get("llm_total_sec") or 0
        )
        if tu <= tm * 1.05:
            lines.append(
                "- **Предпочтительнее uniform** с одной поддерживаемой моделью: "
                "проще "
                "конфигурация, время сопоставимо или лучше, стиль единый "
                "между этапами."
            )
            lines.append(
                "- **Mixed** имеет смысл, если нужен более «тяжёлый» story "
                "и готовы платить за отдельную модель на длинном тексте; "
                "сравните сказки вручную в JSON-отчётах."
            )
        else:
            lines.append(
                "- **Предпочтительнее оценить вручную:** при заметно большем "
                "`llm_total_sec` у mixed сопоставьте качество сказки; часто "
                "uniform остаётся дефолтом для отчёта."
            )
    elif mixed.get("ok"):
        lines.append(
            "- Работает только **mixed**; проверьте `.env` и доступность "
            "модели для uniform."
        )
    elif uni.get("ok"):
        lines.append(
            "- Работает только **uniform**; возможно, модель story в mixed "
            "недоступна в AITunnel — смените `_MODEL_STORY_ONLY` в скрипте."
        )
    else:
        lines.append("- Оба прогона с ошибкой; см. `run.log` и сообщения API.")

    path.write_text("\n".join(lines), encoding="utf-8")


def _html_summary(
    out: Path,
    news: str,
    mixed: dict[str, Any],
    uni: dict[str, Any],
) -> Path:
    def _blk(title: str, data: dict[str, Any]) -> str:
        if data.get("ok"):
            rep = data.get("report") or {}
            blob = json.dumps(
                {
                    "timing": rep.get("timing"),
                    "llm": rep.get("llm"),
                    "generation": rep.get("generation"),
                },
                ensure_ascii=False,
                indent=2,
            )
            esc = (
                blob.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            return f"<h2>{title}</h2><pre>{esc}</pre>"
        err = html.escape(str(data.get("error", "")))
        return (
            f"<h2>{title}</h2><p style='color:#a00'>Ошибка: {err}</p>"
        )

    news_esc = (
        news[:1200].replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    doc = (
        "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
        "<title>AITunnel benchmark</title>"
        "<style>body{font-family:system-ui;margin:1rem;max-width:52rem;}"
        "pre{background:#f6f6f0;padding:.75rem;overflow:auto;font-size:11px;}"
        "</style></head><body>"
        "<h1>Пайплайн: mixed vs uniform (одна новость)</h1>"
        f"<h3>Новость</h3><pre>{news_esc}</pre>"
        + _blk("Сценарий 1 — разные модели", mixed)
        + _blk("Сценарий 2 — одна модель", uni)
        + "</body></html>"
    )
    hp = out / "BENCHMARK_SUMMARY.html"
    hp.write_text(doc, encoding="utf-8")
    return hp


def _mini_scenario_html(path: Path, title: str, rep: dict[str, Any]) -> None:
    blob = json.dumps(
        {"timing": rep.get("timing"), "llm": rep.get("llm")},
        ensure_ascii=False,
        indent=2,
    )
    esc = blob.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    doc = (
        "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui;margin:1rem;}pre{background:#f4f4ea;"
        "padding:.75rem;font-size:11px;white-space:pre-wrap;}</style></head>"
        f"<body><h1>{html.escape(title)}</h1><pre>{esc}</pre></body></html>"
    )
    path.write_text(doc, encoding="utf-8")


def _screenshot(html_path: Path, png_path: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    uri = html_path.resolve().as_uri()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 960, "height": 1100})
            page.goto(uri)
            page.screenshot(path=str(png_path), full_page=True)
            browser.close()
        return True
    except Exception:
        return False


def main() -> None:
    _utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--news",
        type=Path,
        default=_ROOT / "docs" / "pipeline_walkthrough_news.txt",
        help="файл новости UTF-8 (по умолчанию docs/pipeline_walkthrough_news.txt)",
    )
    ap.add_argument("--preset", default="russian_folk")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="каталог вывода",
    )
    ap.add_argument("--no-screenshot", action="store_true")
    ap.add_argument(
        "--skip-connection-check",
        action="store_true",
        help="не вызывать verify_openai_env_chat перед пайплайном",
    )
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = args.out or (_ROOT / "experiments" / "aitunnel_benchmark" / stamp)
    out.mkdir(parents=True, exist_ok=True)

    if args.news.is_file():
        news = args.news.read_text(encoding="utf-8").strip()
    else:
        news = _default_news_tass()
    (out / "news_input.txt").write_text(news, encoding="utf-8")

    log_file = out / "run.log"
    _log(log_file, "benchmark start")

    if not args.skip_connection_check:
        from app.llm_utils import verify_openai_env_chat

        ok_c, msg_c = verify_openai_env_chat()
        _log(log_file, f"connection_check ok={ok_c} {msg_c[:500]}")
        print("connection_check:", "OK" if ok_c else "FAIL", msg_c)
        if not ok_c:
            print(
                "Остановка: исправьте .env или запустите "
                "python -m app.llm_connect_try",
                file=sys.stderr,
            )
            raise SystemExit(2)

    _clear_scenario_env()
    _apply_mixed_cheap()
    mixed = _run_once(log_file, args.preset, news)
    if mixed.get("ok"):
        (out / "report_mixed_models.json").write_text(
            json.dumps(mixed["report"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    _clear_scenario_env()
    _apply_uniform_cheap()
    uni = _run_once(log_file, args.preset, news)
    if uni.get("ok"):
        (out / "report_uniform_model.json").write_text(
            json.dumps(uni["report"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    rec = out / "RECOMMENDATION.md"
    _write_rec_md(rec, mixed, uni)

    hp = _html_summary(out, news, mixed, uni)
    shots = out / "screenshots"
    shots.mkdir(exist_ok=True)
    if not args.no_screenshot:
        ok_any = False
        if _screenshot(hp, shots / "benchmark_full.png"):
            print("screenshot:", shots / "benchmark_full.png")
            ok_any = True
        if mixed.get("ok"):
            mh = out / "scenario_mixed_only.html"
            _mini_scenario_html(mh, "Сценарий 1 — разные модели", mixed["report"])
            if _screenshot(mh, shots / "scenario_mixed.png"):
                print("screenshot:", shots / "scenario_mixed.png")
                ok_any = True
        if uni.get("ok"):
            uh = out / "scenario_uniform_only.html"
            _mini_scenario_html(uh, "Сценарий 2 — одна модель", uni["report"])
            if _screenshot(uh, shots / "scenario_uniform.png"):
                print("screenshot:", shots / "scenario_uniform.png")
                ok_any = True
        if not ok_any:
            print("скриншоты пропущены (нет playwright или ошибка)", file=sys.stderr)

    print("out:", out)
    print("log:", log_file)
    print("recommendation:", rec)
    print("html:", hp)


if __name__ == "__main__":
    main()
