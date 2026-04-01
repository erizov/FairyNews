#!/usr/bin/env python3
"""Собирает docs/interface_screenshots_embedded.html с PNG в base64."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "e2e_screenshots"
OUT = ROOT / "docs" / "interface_screenshots_embedded.html"

ITEMS: list[tuple[str, str, str]] = [
    (
        "01_step1_news_custom_text.png",
        "Шаг 1 — новость",
        "На первом экране вводится или выбирается новость — исходный "
        "текст для сказки.",
    ),
    (
        "02_step2_preset_russian_folk.png",
        "Шаг 2 — пресет",
        "Второй шаг задаёт стиль опоры для поиска похожих сюжетов "
        "(в примере — русский фольклор).",
    ),
    (
        "03_step3_tale_qa_result.png",
        "Шаг 3 — сказка и вопрос",
        "После запуска показываются сказка, сводка по этапам, вопрос по "
        "тексту и ответ для сверки.",
    ),
    (
        "04_reports_index.png",
        "Сводка отчётов",
        "Страница со списком сохранённых прогонов: время, объём текста, "
        "ссылка на детали.",
    ),
    (
        "05_report_detail_run.png",
        "Детали прогона",
        "Развёрнутая карточка прогона: подсказки из индекса, оценки "
        "согласованности, полный текст.",
    ),
]


def main() -> None:
    chunks: list[str] = [
        "<!DOCTYPE html>\n",
        '<html lang="ru">\n',
        "<head>\n",
        '<meta charset="utf-8">\n',
        '<meta name="viewport" content="width=device-width, '
        'initial-scale=1">\n',
        "<title>Интерфейс — скриншоты</title>\n",
        "<style>\n",
        "body { font-family: Georgia, \"Times New Roman\", serif; "
        "max-width: 48rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; "
        "background: #f6f0e6; color: #1a1410; line-height: 1.5; }\n",
        "h1 { color: #6b4226; font-size: 1.4rem; }\n",
        "h2 { color: #6b4226; font-size: 1.05rem; margin-top: 2rem; }\n",
        "p.desc { color: #5c5348; font-size: 0.95rem; "
        "margin-bottom: 0.75rem; }\n",
        "figure { margin: 1rem 0; background: #fffef9; padding: 0.75rem; "
        "border-radius: 8px; box-shadow: 0 1px 6px rgba(0,0,0,0.06); }\n",
        "img { max-width: 100%; height: auto; display: block; "
        "border-radius: 4px; }\n",
        "</style>\n",
        "</head>\n",
        "<body>\n",
        "<h1>Скриншоты интерфейса</h1>\n",
        '<p class="desc">Документ самодостаточный: изображения встроены в '
        "файл (data URI), внешние ссылки на картинки не нужны.</p>\n",
    ]

    for fname, title, desc in ITEMS:
        path = SHOTS / fname
        if not path.is_file():
            print("Missing:", path, file=sys.stderr)
            raise SystemExit(1)
        b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        uri = f"data:image/png;base64,{b64}"
        safe_t = title.replace('"', "&quot;")
        chunks.append(f"<h2>{title}</h2>\n")
        chunks.append(f'<p class="desc">{desc}</p>\n')
        chunks.append(
            f'<figure><img alt="{safe_t}" src="{uri}"></figure>\n'
        )

    chunks.append("</body>\n</html>\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(chunks), encoding="utf-8")
    print("Wrote", OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
