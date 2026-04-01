# Запуск веб-сервера и рабочий процесс FairyNews

## Веб-сервер FastAPI (локально)

Из корня репозитория, с активированным venv:

**Запуск:**

```bash
cd e:\Python\GptEngineer\Diploma
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Останов:** в том же терминале нажмите **Ctrl+C**.

Откройте в браузере: `http://127.0.0.1:8000/` — пошаговый интерфейс (новость →
пресет → генерация). Отчёты: `http://127.0.0.1:8000/reports-ui/index.html`.

### Переменные окружения (по желанию)

- **`GIGACHAT_API_KEY`** — приоритетный LLM для пайплайна (см. `app/llm_providers.py`).
- **`GIGACHAT_SSL_VERIFY=0`** — только при необходимости (ошибка цепочки
  сертификатов Сбера на корпоративной сети / Windows); снижает защиту от MITM.
- **`FAIRYNEWS_LLM_MODE=stub`** — без внешних вызовов (демо-тексты).
- **`FAIRYNEWS_RAG_BACKEND=snapshot`** — RAG из `data/notebook_rag_snapshot.json` без Chroma.
- **`FAIRYNEWS_SAVE_REPORTS=1`** — сохранять JSON прогонов в `data/reports/runs/`.
- **`FAIRYNEWS_LLM_BACKEND`** — принудительно: `gigachat`, `groq`, `deepseek`, `openai`
  (для опытов этапа 4, см. `scripts/run_etap4_experiments.py`).

В Windows можно задать ключи в файле **`.env`** в корне (файл не коммитьте).

### OpenAI: регион не поддержан и ошибка curl

Сообщение API **`unsupported_country_region_territory`** значит: с вашего IP /
региона прямой вызов `api.openai.com` для этого ключа **запрещён политикой
OpenAI** (не баг кода FairyNews).

**Варианты:**

1. **Прокси с OpenAI-compatible API** (ключ того сервиса, не обязательно
   OpenAI): в `.env` задайте **`OPENAI_API_BASE`** на базовый URL до `/v1`
   (пример: `https://api.example.com/v1`). Без кавычек и пробелов в конце
   строки. См. документацию выбранного провайдера.
2. **Другой LLM в проекте:** `FAIRYNEWS_LLM_BACKEND=groq|deepseek|gigachat`
   (см. `app/llm_providers.py`).
3. Официально: VPN/доступ из **поддерживаемой** страны или **Azure OpenAI**
   в разрешённом регионе — по правилам вашей организации.

**`curl: (3) URL rejected: Bad hostname`** чаще всего из-за **битого URL** в
команде или в **`OPENAI_API_BASE`**: лишние кавычки внутри значения, пробел,
перенос строки, опечатка хоста, или переменная пустая и в curl подставилось
`https://`. Проверьте: один хост, схема `https://`, без пробелов; для проверки:

```bash
curl -sS -o NUL -w "%{http_code}" "https://ВАШ_ХОСТ/v1/models"
```

(подставьте реальный хост прокси; для OpenAI напрямую — только из
поддерживаемого региона).

---

## Этап 4: пять прогонов с реальными LLM

Один и тот же текст новости и пресет `russian_folk`, разные провайдеры:

```bash
python scripts/run_etap4_experiments.py
```

Результат: **`experiments/ETAP4_RUN_RESULTS.md`**. Длительность — несколько минут,
нужны сеть и ключи в `.env`. Вариант с OpenAI пропускается, если нет
`OPENAI_API_KEY`.

Один прогон вручную (для отладки):

```bash
set FAIRYNEWS_LLM_BACKEND=groq
set FAIRYNEWS_RAG_BACKEND=snapshot
python scripts/etap4_run_one.py docs/pipeline_walkthrough_news.txt russian_folk
```

---

## Скриншоты интерфейса (Playwright)

Без внешнего LLM (в подпроцессе включается демо-режим, если нет ключа):

```bash
python scripts/capture_e2e_screenshots.py
```

Встроенный HTML со снимками внутри одного файла:

```bash
python scripts/build_embedded_screenshots_html.py
```

---

## Отчёт этапа 3 в Word

Нужен установленный [Pandoc](https://pandoc.org):

```bash
python scripts/build_etap3_docx.py
```

Файл: `docs/etap3_report.docx`.

---

## TEST 1 / TEST 2 (разные vs одна модель по этапам)

1. Скопируйте ``experiments/test12/test1.example.env`` → ``test1.env`` и
   ``test2.example.env`` → ``test2.env``, задайте ключи и модели.
2. Запуск (логи, ``COMPARISON_*.md/html``, скриншоты в ``screenshots/``):

   ```bash
   python scripts/run_test1_test2_comparison.py
   ```

   Без Playwright: ``python scripts/run_test1_test2_comparison.py --no-screenshot``.

В отчёте пайплайна поле ``timing`` — секунды по этапам и сумма LLM.

### AITunnel: two runs на одной новости (mixed vs uniform)

Нужны ``OPENAI_API_KEY`` и ``OPENAI_API_BASE`` (например
``https://api.aitunnel.ru/v1``). Сначала проверка одним запросом:

```bash
python -m app.llm_connect_try
```

Код выхода **0** — связь есть; **1** — нет ключа, base или ответа API.
Бенчмарк пайплайна сначала делает ту же проверку (отключение:
``--skip-connection-check``).

Новость по умолчанию — ``docs/pipeline_walkthrough_news.txt``; иначе
встроенная сводка ТАСС, если файла нет; свой файл: ``--news path``.

```bash
python scripts/run_aitunnel_pipeline_benchmark.py
python scripts/run_aitunnel_pipeline_benchmark.py --no-screenshot
```

Каталог: ``experiments/aitunnel_benchmark/<UTC>/`` — ``run.log``,
``report_*.json``, ``RECOMMENDATION.md``, ``BENCHMARK_SUMMARY.html``,
``screenshots/benchmark_full.png``.

### Два прогона: gpt-4o-mini и gpt-4.1-nano (uniform OpenAI)

Те же переменные, что для ``python -m app.llm_connect_try``. Пайплайн дважды
с RAG snapshot и новостью по умолчанию:

```bash
python scripts/run_openai_mini_nano_pipeline.py
```

Результат: ``experiments/openai_mini_nano/<штамп>/`` — ``report_*.json``,
``SUMMARY.md``, ``run.log``.

## Тесты pytest

```bash
pytest tests/test_e2e_multi_agent.py -q
```

Живой OpenAI + Chroma (по желанию): задайте `RUN_LIVE_OPENAI_E2E=1` и
`OPENAI_API_KEY`, заполните Chroma.
