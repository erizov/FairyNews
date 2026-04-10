# E2E: скриншоты прогона

**Источник новости:** [KP.ru](https://www.kp.ru/daily/27769.5/5228392/). **Пресет RAG:** `russian_folk`. **Индекс сказок:** снимок `data/notebook_rag_snapshot.json`. **LLM:** параметры задаются через `OPENAI_API_KEY`, при необходимости `OPENAI_BASE_URL` и `OPENAI_MODEL`. **Описание пайплайна:** `docs/pipeline_walkthrough.md`.

## Файлы

- **01_step1_news_custom_text.png** — шаг 1: введён текст новости (KP.ru), список примеров не используется.
- **02_step2_preset_russian_folk.png** — шаг 2: пресет «Русский фольклор».
- **03_step3_tale_qa_result.png** — шаг 3: сказка, сводка по этапам, вопрос и эталонный ответ.
- **04_reports_index.png** — сводная страница отчётов.
- **05_report_detail_run.png** — детальный отчёт (top-k RAG, эвристики).

Скрипт: `scripts/capture_e2e_screenshots.py`.