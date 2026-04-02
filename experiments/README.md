# Эксперименты (этап 4)

Формат сдачи: **Markdown** (структурированные варианты, итог в конце).

- Шаблон блока: [`EXPERIMENTS_TEMPLATE.md`](EXPERIMENTS_TEMPLATE.md).
- Результаты прогонов и **рекомендации по моделям**:
  [`ETAP4_RUN_RESULTS.md`](ETAP4_RUN_RESULTS.md) — таблица и JSON из
  `python scripts/run_etap4_experiments.py`; сравнение TEST 1 / TEST 2 —
  `python scripts/run_test1_test2_comparison.py`, каталог `test12/`.
- Бенчмарк AITunnel (mixed vs uniform, по умолчанию новость
  `docs/pipeline_walkthrough_news.txt`; опция `--news`):
  `python scripts/run_aitunnel_pipeline_benchmark.py` →
  `experiments/aitunnel_benchmark/<stamp>/`.
- Два прогона uniform на **gpt-4o-mini** и **gpt-4.1-nano** (не ``gpt-4o-nano``:
  нет в каталоге прокси)
  (тот же `.env`, что `python -m app.llm_connect_try`):
  `python scripts/run_openai_mini_nano_pipeline.py` →
  `experiments/openai_mini_nano/<stamp>/`.
  См. [`docs/WORKFLOW.md`](../docs/WORKFLOW.md).
- Скриншоты UI в **Word** (главная → шаги 2–3 → отчёты; нужен работающий
  сервер и `playwright install chromium`):
  `python scripts/build_etap4_screenshots_docx.py` →
  `experiments/etap4_screenshots/etap4_screenshots.docx` (PNG в
  `experiments/etap4_screenshots/png/`). Опции: `--port`, `--run-id`,
  `--skip-capture` (только сборка .docx из уже снятых PNG).
- Буклет **Fairy News** (англ., польза для детей/взрослых + полные скриншоты
  пайплайна и отчётов с переходами по id / trace):
  `python scripts/build_fairy_news_booklet.py` →
  `docs/fairy_news_booklet/Fairy_News_Booklet.docx`
  (см.   [`docs/fairy_news_booklet/README.md`](../docs/fairy_news_booklet/README.md)).
- Русский буклет **из HTML** (без PNG, полный текст страниц в DOCX):
  `python scripts/build_fairy_news_ru_booklet.py` →
  `docs/fairy_news_booklet_ru/Fairy_News_RU_Booklet.docx`,
  `…_Lite.docx`, `…_Prilozhenie_DOM.docx`; опционально
  `FAIRYNEWS_BOOKLET_DEMO_URL`
  (см. [`docs/fairy_news_booklet_ru/README.md`](../docs/fairy_news_booklet_ru/README.md)).

## Веб-сервер (uvicorn)

По умолчанию порт **8765** (`http://127.0.0.1:8765/`), как в корневом
[`README.md`](../README.md). Другой порт: параметр `-Port` (PowerShell) или
переменная `PORT` (bash). Автоперезапуск кода: `-Reload` (ps1) или
`UVICORN_RELOAD=1` (sh).

**Windows (PowerShell), из корня репозитория:**

```powershell
.\scripts\start_web.ps1
.\scripts\start_web.ps1 -Port 8000
.\scripts\start_web.ps1 -Reload
.\scripts\stop_web.ps1
.\scripts\stop_web.ps1 -Port 8000
.\scripts\restart_web.ps1
.\scripts\restart_web.ps1 -Reload
```

**Linux / macOS (bash), из корня:**

```bash
chmod +x scripts/start_web.sh scripts/stop_web.sh scripts/restart_web.sh
./scripts/start_web.sh
PORT=8000 ./scripts/start_web.sh
UVICORN_RELOAD=1 ./scripts/start_web.sh
./scripts/stop_web.sh
PORT=8000 ./scripts/stop_web.sh
./scripts/restart_web.sh
```

`start_web.ps1` поднимает сервер в **отдельном** свёрнутом окне; `stop_web`
завершает процесс, слушающий указанный порт. Подробнее:
[`docs/WORKFLOW.md`](../docs/WORKFLOW.md) (ручной `uvicorn` на порту 8000 —
эквивалентно, задайте тот же порт в скриптах).
