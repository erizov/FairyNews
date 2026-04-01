#!/usr/bin/env python3
"""Uvicorn + Playwright: PNG сквозного сценария веб-интерфейса."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 9777
BASE = f"http://127.0.0.1:{PORT}"
OUT = ROOT / "e2e_screenshots"
_NEWS_FILE = ROOT / "docs" / "pipeline_walkthrough_news.txt"

# См. docs/pipeline_walkthrough.md — тот же текст.
NEWS_FOR_PIPELINE = _NEWS_FILE.read_text(encoding="utf-8").strip()


def _wait_health(timeout: float = 90.0) -> None:
    url = f"{BASE}/api/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise RuntimeError("server did not become ready in time")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    env = os.environ.copy()
    env["FAIRYNEWS_RAG_BACKEND"] = "snapshot"
    env["FAIRYNEWS_SAVE_REPORTS"] = "1"
    # Parent shells (e.g. PowerShell) often cannot unset OPENAI_API_KEY for
    # this process; an invalid inherited key yields HTTP 500 and a timeout.
    use_openai = os.environ.get(
        "FAIRYNEWS_CAPTURE_USE_OPENAI", ""
    ).strip().lower() in ("1", "true", "yes")
    if use_openai and env.get("OPENAI_API_KEY", "").strip():
        pass  # real completions
    else:
        env["FAIRYNEWS_LLM_MODE"] = "stub"
        env["OPENAI_API_KEY"] = ""

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    meta_lines: list[str] = []
    try:
        _wait_health(120)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1100, "height": 900},
                locale="ru-RU",
            )
            page = context.new_page()

            page.goto(f"{BASE}/", wait_until="networkidle", timeout=120000)
            page.wait_for_selector("#newsList li", timeout=60000)
            page.fill("#customNews", NEWS_FOR_PIPELINE)
            page.screenshot(
                path=str(OUT / "01_step1_news_custom_text.png"),
                full_page=True,
            )
            meta_lines.append(
                "- **01_step1_news_custom_text.png** — шаг 1: введён текст "
                "новости (KP.ru), список примеров не используется."
            )

            page.locator("#toStep2").click()
            page.wait_for_selector("#page2.active", timeout=10000)
            page.select_option("#presetSelect", value="russian_folk")
            page.screenshot(path=str(OUT / "02_step2_preset_russian_folk.png"))
            meta_lines.append(
                "- **02_step2_preset_russian_folk.png** — шаг 2: пресет "
                "«Русский фольклор»."
            )

            page.locator("#runGen").click()
            try:
                page.wait_for_function(
                    "() => {"
                    "const t = document.getElementById('tale');"
                    "return t && t.textContent.length > 50;"
                    "}",
                    timeout=240000,
                )
            except Exception as exc:
                err_el = page.locator("#err2")
                msg = ""
                if err_el.is_visible():
                    msg = err_el.inner_text() or ""
                raise RuntimeError(
                    "Нет текста сказки на шаге 3. Сообщение UI: "
                    f"{msg!r}"
                ) from exc
            page.screenshot(
                path=str(OUT / "03_step3_tale_qa_result.png"),
                full_page=True,
            )
            meta_lines.append(
                "- **03_step3_tale_qa_result.png** — шаг 3: сказка, сводка "
                "по этапам, вопрос и эталонный ответ."
            )

            report_href = page.locator("#metaOut a").get_attribute("href")
            run_id = None
            if report_href and "id=" in report_href:
                run_id = report_href.split("id=")[-1].split("&")[0]

            page.goto(
                f"{BASE}/reports-ui/index.html",
                wait_until="networkidle",
            )
            time.sleep(0.5)
            page.screenshot(path=str(OUT / "04_reports_index.png"))
            meta_lines.append(
                "- **04_reports_index.png** — сводная страница отчётов."
            )

            if run_id:
                page.goto(
                    f"{BASE}/reports-ui/detail.html?id={run_id}",
                    wait_until="networkidle",
                    timeout=60000,
                )
                page.screenshot(
                    path=str(OUT / "05_report_detail_run.png"),
                    full_page=True,
                )
                meta_lines.append(
                    "- **05_report_detail_run.png** — детальный отчёт "
                    "(top-k RAG, эвристики)."
                )

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    kp_note = (
        "**Источник новости:** [KP.ru]"
        "(https://www.kp.ru/daily/27769.5/5228392/). "
        "**Пресет RAG:** `russian_folk`. "
        "**Индекс сказок:** снимок `data/notebook_rag_snapshot.json`. "
        "**LLM:** параметры задаются через `OPENAI_API_KEY`, "
        "при необходимости `OPENAI_BASE_URL` и `OPENAI_MODEL`. "
        "**Описание пайплайна:** `docs/pipeline_walkthrough.md`."
    )
    md = OUT / "SCREENSHOTS.md"
    body = "\n".join(
        [
            "# E2E: скриншоты прогона",
            "",
            kp_note,
            "",
            "## Файлы",
            "",
            *meta_lines,
            "",
            "Скрипт: `scripts/capture_e2e_screenshots.py`.",
            "",
        ]
    )
    md.write_text(body, encoding="utf-8")
    print("Saved:", OUT)


if __name__ == "__main__":
    main()
