#!/usr/bin/env python3
"""TEST 1 vs TEST 2: прогон, логи, сравнение по времени, HTML, скриншот."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except OSError:
            pass


def _merge_env_file(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if (len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'"):
            val = val[1:-1]
        os.environ[key] = val


def _clear_fairynews_test_keys() -> None:
    extra = {
        "FAIRYNEWS_LLM_PER_STAGE",
        "FAIRYNEWS_LLM_UNIFORM_STAGES",
        "FAIRYNEWS_UNIFORM_BACKEND",
        "FAIRYNEWS_UNIFORM_MODEL",
        "FAIRYNEWS_TEST_PROFILE",
    }
    for k in list(os.environ.keys()):
        if k in extra or k.startswith("FAIRYNEWS_STAGE_"):
            os.environ.pop(k, None)


def _append_log(path: Path, msg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {msg}\n")


def _run_pipeline(
    news_path: Path,
    preset_id: str,
    log_path: Path,
) -> dict:
    from dotenv import load_dotenv

    from app.agents_pipeline import run_four_agent_pipeline
    from app.presets import get_preset

    load_dotenv(_ROOT / ".env")
    news = news_path.read_text(encoding="utf-8").strip()
    preset = get_preset(preset_id)
    hint = str(preset["retrieval_hint"])
    domains = preset.get("domains")
    backend = os.environ.get("FAIRYNEWS_RAG_BACKEND", "snapshot").strip()

    profile = os.environ.get("FAIRYNEWS_TEST_PROFILE", "?")
    _append_log(log_path, f"start profile={profile} preset={preset_id}")

    try:
        out = run_four_agent_pipeline(
            news,
            hint,
            domains,
            preset_id=preset_id,
            news_id=None,
            rag_backend=backend,
        )
        rep = out.get("report") or {}
        timing = rep.get("timing") or {}
        _append_log(
            log_path,
            f"ok profile={profile} wall_sec={timing.get('pipeline_wall_sec')}",
        )
        return {"ok": True, "output": out, "report": rep}
    except Exception as exc:
        _append_log(log_path, f"error profile={profile} {type(exc).__name__}: {exc}")
        return {"ok": False, "error": str(exc)}


def _write_comparison_md(
    path: Path,
    t1: dict,
    t2: dict,
    label1: str,
    label2: str,
) -> None:
    lines = [
        "# Сравнение TEST 1 и TEST 2",
        "",
        f"- **{label1}**: разные модели по этапам.",
        f"- **{label2}**: один backend и одна модель на все этапы "
        "(``FAIRYNEWS_LLM_UNIFORM_STAGES``).",
        "",
        "## Время и объём",
        "",
        "| Метрика | TEST 1 | TEST 2 |",
        "|--------|--------|--------|",
    ]

    def T(which: dict, key: str) -> str:
        if not which.get("ok"):
            return "—"
        tm = (which.get("report") or {}).get("timing") or {}
        v = tm.get(key)
        return str(v) if v is not None else "—"

    def gen(which: dict, key: str) -> str:
        if not which.get("ok"):
            return "—"
        g = (which.get("report") or {}).get("generation") or {}
        v = g.get(key)
        return str(v) if v is not None else "—"

    rows = [
        ("pipeline_wall_sec", "Стена пайплайна, с"),
        ("llm_total_sec", "Сумма LLM-вызовов, с"),
        ("rag_retrieve_sec", "RAG retrieve, с"),
        ("llm_news_sec", "Этап news, с"),
        ("llm_story_sec", "Этап story, с"),
        ("llm_audit_sec", "Этап audit, с"),
        ("llm_qa_sec", "Этап qa, с"),
    ]
    for k, title in rows:
        lines.append(f"| {title} | {T(t1, k)} | {T(t2, k)} |")

    lines.extend(
        [
            f"| Символов в сказке | {gen(t1, 'tale_chars')} | "
            f"{gen(t2, 'tale_chars')} |",
            "",
            "## Конфигурация LLM (из отчёта)",
            "",
        ]
    )
    for tag, block in ((label1, t1), (label2, t2)):
        lines.append(f"### {tag}")
        if not block.get("ok"):
            lines.append(f"_Ошибка: {block.get('error')}_")
            lines.append("")
            continue
        llm = (block.get("report") or {}).get("llm") or {}
        lines.append(f"- per_stage: {llm.get('per_stage')}")
        lines.append(f"- uniform_stages: {llm.get('uniform_stages')}")
        lines.append(f"- provider: {llm.get('provider')}")
        stages = llm.get("stages") or {}
        for sk, sv in stages.items():
            lines.append(
                f"  - {sk}: {sv.get('provider')} / {sv.get('model')}"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_comparison_html(path: Path, md_path: Path) -> None:
    body = md_path.read_text(encoding="utf-8")
    esc = (
        body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    # crude markdown-ish: lines starting with # -> h1/h2
    html_lines = ["<!DOCTYPE html>", '<html lang="ru">', "<head>"]
    html_lines.extend(
        [
            '<meta charset="utf-8">',
            "<title>TEST1 vs TEST2</title>",
            "<style>",
            "body{font-family:system-ui,sans-serif;max-width:56rem;margin:0 auto;"
            "padding:1.2rem;background:#f8f6f2;color:#1a1410;}"
            "table{border-collapse:collapse;width:100%;background:#fff;"
            "box-shadow:0 1px 4px rgba(0,0,0,.08);}"
            "td,th{border:1px solid #ccc;padding:.45rem .6rem;font-size:.9rem;}"
            "th{background:#eae4dc;}",
            "pre{white-space:pre-wrap;background:#fff;padding:1rem;"
            "border-radius:6px;}",
            "</style>",
            "</head><body>",
            "<pre>",
            esc,
            "</pre>",
            "</body></html>",
        ]
    )
    path.write_text("\n".join(html_lines), encoding="utf-8")


def _try_screenshot(html_path: Path, png_path: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright не установлен — пропуск скриншота", file=sys.stderr)
        return False
    uri = html_path.resolve().as_uri()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": 920, "height": 1200},
            )
            page.goto(uri)
            page.screenshot(path=str(png_path), full_page=True)
            browser.close()
        return True
    except Exception as exc:
        print(f"screenshot failed: {exc}", file=sys.stderr)
        return False


def main() -> None:
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="TEST 1 vs TEST 2 benchmark")
    ap.add_argument(
        "--out",
        type=Path,
        default=_ROOT / "experiments" / "test12",
        help="каталог отчётов, логов и скриншотов",
    )
    ap.add_argument(
        "--test1-env",
        type=Path,
        default=None,
        help="env для TEST 1 (по умолчанию out/test1.env)",
    )
    ap.add_argument(
        "--test2-env",
        type=Path,
        default=None,
        help="env для TEST 2 (по умолчанию out/test2.env)",
    )
    ap.add_argument(
        "--news",
        type=Path,
        default=_ROOT / "docs" / "pipeline_walkthrough_news.txt",
    )
    ap.add_argument("--preset", default="russian_folk")
    ap.add_argument("--no-screenshot", action="store_true")
    args = ap.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    logs = out / "logs"
    reports = out / "reports"
    shots = out / "screenshots"

    t1_env = args.test1_env or (out / "test1.env")
    t2_env = args.test2_env or (out / "test2.env")
    ex1, ex2 = out / "test1.example.env", out / "test2.example.env"

    if not t1_env.is_file():
        if ex1.is_file():
            print(f"Нет {t1_env}; подсказка: copy {ex1} → test1.env")
        raise SystemExit(2)
    if not t2_env.is_file():
        if ex2.is_file():
            print(f"Нет {t2_env}; подсказка: copy {ex2} → test2.env")
        raise SystemExit(2)
    if not args.news.is_file():
        print("Нет файла новости:", args.news, file=sys.stderr)
        raise SystemExit(2)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_combined = logs / f"comparison_{stamp}.log"

    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")

    _clear_fairynews_test_keys()
    _merge_env_file(t1_env)
    r1 = _run_pipeline(args.news, args.preset, log_combined)
    if r1.get("ok"):
        (reports / f"test1_{stamp}.json").write_text(
            json.dumps(r1.get("report"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    _clear_fairynews_test_keys()
    _merge_env_file(t2_env)
    r2 = _run_pipeline(args.news, args.preset, log_combined)
    if r2.get("ok"):
        (reports / f"test2_{stamp}.json").write_text(
            json.dumps(r2.get("report"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    cmp_md = out / f"COMPARISON_{stamp}.md"
    _write_comparison_md(cmp_md, r1, r2, "TEST 1", "TEST 2")
    cmp_html = out / f"COMPARISON_{stamp}.html"
    _write_comparison_html(cmp_html, cmp_md)

    shots.mkdir(parents=True, exist_ok=True)

    def _run_detail_html(title: str, rep: dict[str, Any]) -> None:
        timing = rep.get("timing") or {}
        llm = rep.get("llm") or {}
        blocks = [f"# {title}", "", "## timing", json.dumps(timing, indent=2)]
        blocks.extend(["", "## llm.stages", json.dumps(llm.get("stages"), indent=2)])
        raw = "\n".join(blocks)
        esc = (
            raw.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        hp = shots / f"{title.replace(' ', '_').lower()}_{stamp}_detail.html"
        hp.write_text(
            "<!DOCTYPE html><html lang=\"ru\"><head><meta charset=\"utf-8\">"
            "<title>" + title + "</title>"
            "<style>body{font-family:monospace;padding:1rem;background:#fff;}"
            "pre{white-space:pre-wrap;}</style></head><body><pre>"
            + esc
            + "</pre></body></html>",
            encoding="utf-8",
        )
        return hp

    if r1.get("ok"):
        h1 = _run_detail_html("TEST_1", r1["report"])
        p1 = shots / f"test1_{stamp}.png"
        if not args.no_screenshot:
            _try_screenshot(h1, p1)
            print("screenshot test1:", p1)
    if r2.get("ok"):
        h2 = _run_detail_html("TEST_2", r2["report"])
        p2 = shots / f"test2_{stamp}.png"
        if not args.no_screenshot:
            _try_screenshot(h2, p2)
            print("screenshot test2:", p2)

    if not args.no_screenshot:
        png = shots / f"comparison_{stamp}.png"
        if _try_screenshot(cmp_html, png):
            print("screenshot compare:", png)
    print("comparison md:", cmp_md)
    print("comparison html:", cmp_html)
    print("log:", log_combined)


if __name__ == "__main__":
    main()
