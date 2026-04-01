# Этап 4 — результаты прогонов и рекомендации по моделям

Документ: **сравнение TEST 1 (разные модели по этапам) и TEST 2 (одна модель
на все этапы)** на **одной и той же новости**, затем краткие **рекомендации**
и нейтральный обзор дополнительного прогона пяти провайдеров. Процедура выбора
модели и без «разбора ошибок» — в [etap4.md §9.1](../etap4.md).

**Время бенчмарка (UTC):** `2026-03-31T22:04:41Z`  
**Новость:** `docs/pipeline_walkthrough_news.txt` (текст про дачников и найм
работников, источник КП внизу файла)  
**Пресет:** `russian_folk`, **RAG:** snapshot  
**LLM:** OpenAI-compatible (AITunnel / `.env`: `OPENAI_API_KEY`, `OPENAI_API_BASE`)

**Обновление RAG (после доработки пайплайна):** по умолчанию включены **гибридный**
поиск (эмбеддинги + BM25, слияние **RRF** с настраиваемым `FAIRYNEWS_RAG_RRF_K`),
**второй проход** с расширением запроса фрагментами топ‑чанков; для **Chroma**
итоговый набор после двух проходов дополнительно **сливается по RRF позиций**
(`iterative_merge: rrf_ranks` в `report.rag`). **Сжатие** чанков до бюджета
символов сохраняет релевантные предложения **в порядке чтения**, затем хвост
(`chunk_compression: ordered_relevance`). Для сравнения «до/после» на той же
новости и модели задайте **`FAIRYNEWS_RAG_LEGACY=1`** и сравните
`chosen_tale_source`, `rag.top_k`, длину сказки и эвристики — автоматический
«золотой» критерий в репозитории не фиксирован; регрессия: **`pytest -q`**
(snapshot + stub; live по маркеру `RUN_LIVE_OPENAI_E2E`).

**Команда:**

```text
python scripts/run_aitunnel_pipeline_benchmark.py
```

(по умолчанию подставляется `docs/pipeline_walkthrough_news.txt`; каталог вывода
`experiments/aitunnel_benchmark/<штамп>/`).

Перед прогоном полезна проверка: `python -m app.llm_connect_try`. Если
`verify_openai_env_chat` даёт сбой сети, можно однократно:
`--skip-connection-check` (пайплайн всё равно ходит в API).

## Сводка: TEST 1 (mixed) vs TEST 2 (uniform)

| Сценарий | Успех | Модели | `pipeline_wall_s` | `llm_total_s` | Сказка (симв.) | Замечание |
|----------|:-----:|--------|------------------:|--------------:|---------------:|-----------|
| TEST 1 — разные модели | да | news / audit / qa — `openai/gpt-5`, story — `openai/gpt-4o` | 68.7 | 60.4 | 2935 | QA и audit в норме |
| TEST 2 — одна модель | да | все этапы — `openai/gpt-5` | 121.0 | 114.8 | 5411 | В этом прогоне блок **qa** пустой (вопрос/ответ не заполнились); стоит контролировать при сдаче |

**Итог по времени:** mixed заметно быстрее за счёт более короткого этапа story и
меньшего суммарного времени LLM; uniform дал **вдвое длиннее** сказку по объёму
символов при **~1,9×** большем `llm_total_sec`.

**Артефакты этого запуска:** `experiments/aitunnel_benchmark/20260331_220441/`
(`report_mixed_models.json`, `report_uniform_model.json`, `RECOMMENDATION.md`,
`BENCHMARK_SUMMARY.html`, `screenshots/`, `run.log`).

## Вывод по сравнению mixed / uniform (эта новость, март 2026)

1. **Качество и объём:** uniform на `openai/gpt-5` дал развернутее сказку;
   mixed с `openai/gpt-4o` на story уложился в меньше времени и короче текст —
   субъективно сравнить стиль и связность с новости по JSON-отчётам.
2. **Стабильность этапов:** в uniform-прогоне стоит разобраться с пустым QA
   (повторить прогон, при необходимости поднять лимиты на qa-вызов или
   проверить ответ прокси).
3. **Для отчёта диплома:** если важны **скорость и предсказуемый JSON** на всех
   шагах — mixed с лёгкой моделью на JSON-этапах и отдельной story-моделью
   остаётся практичным; если важен **единый стиль** и допустима большая длительность
   — uniform предпочтительнее при условии, что **qa** стабильно заполняется.

Регрессии кода по-прежнему: `pytest tests/test_e2e_multi_agent.py`,
`tests/test_per_stage_llm.py`.

---

## Рекомендации: какие модели и режимы использовать

### Режим по умолчанию

**TEST 2 (uniform):** `FAIRYNEWS_LLM_UNIFORM_STAGES=1` +
`FAIRYNEWS_UNIFORM_BACKEND` + `FAIRYNEWS_UNIFORM_MODEL` — проще конфиг и один
стиль между агентами; проверяйте, что финальные поля отчёта (включая qa)
заполняются.

**TEST 1 (per-stage):** переменные `FAIRYNEWS_STAGE_NEWS_*` … `FAIRYNEWS_STAGE_QA_*`
— имеет смысл, когда нужно **сэкономить** на JSON-этапах и **усилить только
story**; сравнивайте `report.timing` и текст сказки.

| Приоритет | Провайдер (uniform) | Модель (ориентир) | Зачем |
|-----------|---------------------|-------------------|--------|
| Прямой OpenAI API | `openai` | `gpt-4o-mini` | Устойчивый JSON + сказка |
| AITunnel / OpenRouter | `openai` | id из кабинета, напр. `openai/gpt-5` | У прокси часто нет «mini» без проверки каталога |
| Экономия итераций | `groq` | `llama-3.1-8b-instant` / `llama-3.3-70b-versatile` | Быстрые прогоны при доступном ключе |
| РФ / русский | `gigachat` | линейка Pro | После настройки TLS / `GIGACHAT_SSL_VERIFY` |
| Альтернатива | `deepseek` | `deepseek-chat` | При стабильном балансе |

**AITunnel:** `OPENAI_API_KEY`, `OPENAI_API_BASE=https://api.aitunnel.ru/v1`;
модель см.-также `OPENAI_MODEL` / `LLM_CONNECT_TRY_MODEL`.

Сравнение TEST 1 / TEST 2 отдельным сценарием (другие точки входа):
`python scripts/run_test1_test2_comparison.py` → `experiments/test12/`.

---

## Дополнительный прогон: пять облачных вариантов (март 2026)

**Рабочая связка LLM** в этом репозитории — та же, что у smoke-test
[`app/llm_connect_try.py`](../app/llm_connect_try.py): в корневом `.env` задаются
`OPENAI_API_KEY` и `OPENAI_API_BASE` (при необходимости — `OPENAI_BASE_URL`, если
base пуст; dotenv с `override=True`). Обычно это **OpenAI-compatible прокси**
(например AITunnel), а не обязательно прямой `api.openai.com`.

Скрипт `python scripts/run_etap4_experiments.py` прогоняет набор **альтернативных**
маршрутов (Groq, GigaChat, DeepSeek, прямой OpenAI и варианты RAG). Итоги
зависят от ключей и политик доступа; таблицу имеет смысл обновлять после
стабилизации окружения. Перед длинными сериями: `python -m app.llm_connect_try`.
Методика выбора модели: [etap4.md §9.1](../etap4.md).

Подробнее по командам: [docs/WORKFLOW.md](../docs/WORKFLOW.md), задание этапа:
[etap4.md](../etap4.md) (п. 10.1).
