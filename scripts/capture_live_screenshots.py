#!/usr/bin/env python3
"""Playwright + uvicorn: скриншоты при реальных вызовах LLM.

Читает корневой ``.env``, проверяет ключи (без записи значений в отчёт),
выбирает первый рабочий OpenAI-совместимый endpoint, поднимает сервер и
снимает PNG в ``docs/live_run/``. Пишет ``docs/pipeline_walkthrough_live.md``.

Секреты никогда не попадают в сгенерированный markdown.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PORT = 9778
BASE = f"http://127.0.0.1:{PORT}"
OUT = ROOT / "docs" / "live_run"
_NEWS_FILE = ROOT / "docs" / "pipeline_walkthrough_news.txt"
_GROQ_BASE = "https://api.groq.com/openai/v1"


def _openai_probe_base_url() -> str:
    """Как ``app.llm_utils.openai_base_url_from_env``; иначе официальный API."""
    from app.llm_utils import openai_base_url_from_env

    b = openai_base_url_from_env()
    if b:
        return b
    return "https://api.openai.com/v1"


_GROQ_MODELS = (
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
)


def load_env_file(path: Path) -> set[str]:
    """Merge ``KEY=value`` into ``os.environ``; return keys seen in file."""
    defined: set[str] = set()
    if not path.is_file():
        return defined
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key or val is None:
            continue
        defined.add(key)
        if key == "DEEPSEEK_API_KEY" and val.endswith("="):
            val = val[:-1]
        os.environ[key] = val
    return defined


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _probe_chat(
    api_key: str,
    base_url: str,
    model: str,
) -> tuple[bool, str]:
    from app.llm_utils import create_openai_client

    try:
        client = create_openai_client(
            api_key,
            base_url=base_url,
            timeout=45.0,
        )
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with OK only."}],
            max_tokens=6,
        )
        txt = (completion.choices[0].message.content or "").strip()
        return bool(txt), txt[:80] or "(empty)"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"[:220]


@dataclass
class ProviderCandidate:
    label: str
    env_key: str
    base_url: str
    model: str


def _gather_probes(
    raw_env: dict[str, str],
    dotenv_keys: set[str],
) -> list[dict[str, Any]]:
    """Diagnostics only; values never logged."""
    rows: list[dict[str, Any]] = []

    def in_env(*names: str) -> bool:
        return any(n in dotenv_keys for n in names)

    def add(
        name: str,
        present: bool,
        kind: str,
        works: bool | None,
        note: str,
    ) -> None:
        rows.append(
            {
                "name": name,
                "present": present,
                "kind": kind,
                "works": works,
                "note": note,
            }
        )

    openai_k = raw_env.get("OPENAI_API_KEY", "").strip()
    ds_k = raw_env.get("DEEPSEEK_API_KEY", "").strip()
    if ds_k.endswith("="):
        ds_k = ds_k[:-1]
    groq_k = (
        raw_env.get("GROQ_API_KEY", "").strip()
        or raw_env.get("GROQ_KEY", "").strip()
    )
    gig_k = raw_env.get("GIGACHAT_API_KEY", "").strip()

    add(
        "OPENAI_API_KEY",
        in_env("OPENAI_API_KEY"),
        "OpenAI API",
        None,
        "—",
    )
    add(
        "DEEPSEEK_API_KEY",
        in_env("DEEPSEEK_API_KEY"),
        "OpenAI-compatible",
        None,
        "—",
    )
    add(
        "GROQ_KEY / GROQ_API_KEY",
        in_env("GROQ_KEY", "GROQ_API_KEY"),
        "OpenAI-compatible",
        None,
        "—",
    )
    add(
        "GIGACHAT_API_KEY",
        in_env("GIGACHAT_API_KEY"),
        "Сбер GigaChat",
        None,
        "—",
    )

    if openai_k:
        from app.llm_utils import resolve_openai_chat_model_id

        base = _openai_probe_base_url()
        model = resolve_openai_chat_model_id(explicit=None, base_url=base)
        ok, msg = _probe_chat(openai_k, base, model)
        rows[0]["works"] = ok
        rows[0]["note"] = msg

    if ds_k:
        ok, msg = _probe_chat(
            ds_k,
            "https://api.deepseek.com/v1",
            "deepseek-chat",
        )
        rows[1]["works"] = ok
        rows[1]["note"] = msg

    if groq_k:
        ok = False
        msg = ""
        for gm in _GROQ_MODELS:
            ok, msg = _probe_chat(groq_k, _GROQ_BASE, gm)
            if ok:
                msg = f"ok ({gm})"
                break
        rows[2]["works"] = ok
        rows[2]["note"] = msg

    rows[3]["works"] = None
    rows[3]["note"] = (
        "Не вызывается из app.llm_providers: нужен отдельный SDK/endpoint."
    )

    return rows


def _pick_provider(
    raw_env: dict[str, str],
) -> tuple[ProviderCandidate | None, str]:
    openai_k = raw_env.get("OPENAI_API_KEY", "").strip()
    ds_k = raw_env.get("DEEPSEEK_API_KEY", "").strip()
    if ds_k.endswith("="):
        ds_k = ds_k[:-1]
    groq_k = (
        raw_env.get("GROQ_API_KEY", "").strip()
        or raw_env.get("GROQ_KEY", "").strip()
    )

    chosen: list[tuple[ProviderCandidate, str]] = []

    if openai_k:
        from app.llm_utils import resolve_openai_chat_model_id

        base = _openai_probe_base_url()
        model = resolve_openai_chat_model_id(explicit=None, base_url=base)
        cand = ProviderCandidate(
            "OpenAI или совместимый (OPENAI_*)",
            "OPENAI_API_KEY",
            base,
            model,
        )
        ok, _ = _probe_chat(openai_k, base, model)
        if ok:
            chosen.append((cand, openai_k))

    if ds_k:
        cand = ProviderCandidate(
            "DeepSeek",
            "DEEPSEEK_API_KEY",
            "https://api.deepseek.com/v1",
            "deepseek-chat",
        )
        ok, _ = _probe_chat(
            ds_k, "https://api.deepseek.com/v1", "deepseek-chat"
        )
        if ok:
            chosen.append((cand, ds_k))

    if groq_k:
        for gm in _GROQ_MODELS:
            ok, _ = _probe_chat(groq_k, _GROQ_BASE, gm)
            if ok:
                chosen.append(
                    (
                        ProviderCandidate(
                            "Groq",
                            "GROQ_KEY",
                            _GROQ_BASE,
                            gm,
                        ),
                        groq_k,
                    )
                )
                break

    if chosen:
        return chosen[0]
    return None, ""


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


_MARK_BEGIN = "<!-- CAPTURE_LIVE:BEGIN -->\n"
_MARK_END = "<!-- CAPTURE_LIVE:END -->\n"


def _write_live_markdown(
    *,
    stamp: str,
    probe_rows: list[dict[str, Any]],
    provider_label: str,
    model: str,
    base_url: str,
    screenshots_ok: bool,
    error_hint: str,
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md_path = ROOT / "docs" / "pipeline_walkthrough_live.md"

    def fmt_works(w: bool | None) -> str:
        if w is True:
            return "да"
        if w is False:
            return "нет"
        return "н/д"

    table_lines = [
        "| Переменная / сервис | В файле .env | Тип | Проверка | Примечание |",
        "|---|---:|---|---|---|",
    ]
    for r in probe_rows:
        table_lines.append(
            "| {name} | {pres} | {kind} | {works} | {note} |".format(
                name=r["name"],
                pres="да" if r["present"] else "нет",
                kind=r["kind"],
                works=fmt_works(r["works"]),
                note=str(r["note"]).replace("|", "\\|"),
            )
        )

    img_block: list[str]
    if screenshots_ok:
        img_block = [
            "![Шаг 1 — новость](live_run/01_step1_news_custom_text.png)",
            "",
            "![Шаг 2 — пресет](live_run/02_step2_preset_russian_folk.png)",
            "",
            "![Шаг 3 — результат](live_run/03_step3_tale_qa_result.png)",
            "",
            "![Отчёты — список](live_run/04_reports_index.png)",
            "",
            "![Отчёт — деталка](live_run/05_report_detail_run.png)",
            "",
        ]
    else:
        safe_err = (error_hint or "нет рабочего ключа").replace("`", "'")
        img_block = [
            f"*Скриншоты не созданы:* {safe_err}. Повторите "
            "`python scripts/capture_live_screenshots.py` после пополнения "
            "баланса, смены региона/VPN или обновления ключа.",
            "",
        ]

    fragment = "\n".join(
        [
            f"**Время прогона (UTC):** `{stamp}`  ",
            "",
            "**Новость:** [`pipeline_walkthrough_news.txt`]"
            "(pipeline_walkthrough_news.txt); пресет **`russian_folk`**, "
            "RAG **`FAIRYNEWS_RAG_BACKEND=snapshot`**, порт захвата "
            f"**{PORT}**.",
            "",
            "### Статус ключей из `.env` (значения не печатаются)",
            "",
            "Короткий вызов `chat.completions` (как у сервера).",
            "",
            *table_lines,
            "",
            "### Провайдер для скриншотов",
            "",
            f"- **Выбран:** {provider_label or '—'}",
            f"- **Base URL:** `{base_url or '—'}`",
            f"- **Модель:** `{model or '—'}`",
            "",
            "### Скриншоты (`docs/live_run/`)",
            "",
            *img_block,
            "_Скрипт:_ `scripts/capture_live_screenshots.py`.",
            "",
        ]
    )

    if not md_path.is_file():
        raise RuntimeError("docs/pipeline_walkthrough_live.md not found")
    full = md_path.read_text(encoding="utf-8")
    if _MARK_BEGIN not in full or _MARK_END not in full:
        raise RuntimeError(
            "docs/pipeline_walkthrough_live.md: add CAPTURE_LIVE markers"
        )
    pre, rest = full.split(_MARK_BEGIN, 1)
    _, post = rest.split(_MARK_END, 1)
    md_path.write_text(
        pre + _MARK_BEGIN + fragment + _MARK_END + post,
        encoding="utf-8",
    )


def main() -> int:
    env_path = ROOT / ".env"
    snapshot_before = dict(os.environ)
    dotenv_keys = load_env_file(env_path)

    raw_env = {
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY", ""),
        "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", ""),
        "GROQ_KEY": os.environ.get("GROQ_KEY", ""),
        "GIGACHAT_API_KEY": os.environ.get("GIGACHAT_API_KEY", ""),
    }

    probe_rows = _gather_probes(raw_env, dotenv_keys)
    cand, api_key = _pick_provider(raw_env)

    stamp = _utc_stamp()
    if not cand or not api_key:
        _write_live_markdown(
            stamp=stamp,
            probe_rows=probe_rows,
            provider_label="",
            model="",
            base_url="",
            screenshots_ok=False,
            error_hint="нет рабочего OpenAI-совместимого ключа",
        )
        print("No working provider; wrote docs/pipeline_walkthrough_live.md")
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 1

    news_text = _NEWS_FILE.read_text(encoding="utf-8").strip()
    env = snapshot_before.copy()
    env.update(os.environ)
    env["OPENAI_API_KEY"] = api_key
    env["OPENAI_BASE_URL"] = cand.base_url
    env["OPENAI_MODEL"] = cand.model
    env.pop("FAIRYNEWS_LLM_MODE", None)
    env["FAIRYNEWS_RAG_BACKEND"] = "snapshot"
    env["FAIRYNEWS_SAVE_REPORTS"] = "1"

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
    err_hint = ""
    shots_ok = False
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
            page.fill("#customNews", news_text)
            page.screenshot(
                path=str(OUT / "01_step1_news_custom_text.png"),
                full_page=True,
            )
            page.locator("#toStep2").click()
            page.wait_for_selector("#page2.active", timeout=10000)
            page.select_option("#presetSelect", value="russian_folk")
            page.screenshot(
                path=str(OUT / "02_step2_preset_russian_folk.png"),
            )
            page.locator("#runGen").click()
            try:
                page.wait_for_function(
                    "() => {"
                    "const t = document.getElementById('tale');"
                    "return t && t.textContent.length > 200;"
                    "}",
                    timeout=600000,
                )
            except Exception as exc:
                err_el = page.locator("#err2")
                msg = ""
                if err_el.is_visible():
                    msg = err_el.inner_text() or ""
                err_hint = msg or repr(exc)
                raise
            page.screenshot(
                path=str(OUT / "03_step3_tale_qa_result.png"),
                full_page=True,
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
            if run_id:
                page.goto(
                    f"{BASE}/reports-ui/detail.html?id={run_id}",
                    wait_until="networkidle",
                    timeout=120000,
                )
                page.screenshot(
                    path=str(OUT / "05_report_detail_run.png"),
                    full_page=True,
                )
            browser.close()
        shots_ok = True
    except Exception as exc:
        err_hint = err_hint or f"{type(exc).__name__}: {exc}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()

    _write_live_markdown(
        stamp=stamp,
        probe_rows=probe_rows,
        provider_label=cand.label,
        model=cand.model,
        base_url=cand.base_url,
        screenshots_ok=shots_ok,
        error_hint=err_hint,
    )
    print("Saved:", OUT, "and docs/pipeline_walkthrough_live.md")
    return 0 if shots_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
