# Пайплайн «нейро-сказочник»: живой LLM, ключи из `.env`, скриншоты

Ниже автоматически обновляемый блок (команда
`python scripts/capture_live_screenshots.py`) — статус ключей, провайдер
и снимки из `docs/live_run/`. Остальной документ совпадает по структуре с
[`pipeline_walkthrough.md`](pipeline_walkthrough.md).

<!-- CAPTURE_LIVE:BEGIN -->
**Время прогона (UTC):** `2026-03-28T15:54:55Z`  

**Новость:** [`pipeline_walkthrough_news.txt`](pipeline_walkthrough_news.txt); пресет **`russian_folk`**, RAG **`FAIRYNEWS_RAG_BACKEND=snapshot`**, порт захвата **9778**.

### Статус ключей из `.env` (значения не печатаются)

Короткий вызов `chat.completions` (как у сервера).

| Переменная / сервис | В файле .env | Тип | Проверка | Примечание |
|---|---:|---|---|---|
| OPENAI_API_KEY | нет | OpenAI API | нет | PermissionDeniedError: Error code: 403 - {'error': {'code': 'unsupported_country_region_territory', 'message': 'Country, region, or territory not supported', 'param': None, 'type': 'request_forbidden'}} |
| DEEPSEEK_API_KEY | да | OpenAI-compatible | нет | APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient Balance', 'type': 'unknown_error', 'param': None, 'code': 'invalid_request_error'}} |
| GROQ_KEY / GROQ_API_KEY | да | OpenAI-compatible | нет | PermissionDeniedError: Error code: 403 - {'error': {'message': 'Forbidden'}} |
| GIGACHAT_API_KEY | да | Сбер GigaChat | н/д | Не вызывается из app.llm_providers: нужен отдельный SDK/endpoint. |

### Провайдер для скриншотов

- **Выбран:** —
- **Base URL:** `—`
- **Модель:** `—`

### Скриншоты (`docs/live_run/`)

*Скриншоты не созданы:* нет рабочего OpenAI-совместимого ключа. Повторите `python scripts/capture_live_screenshots.py` после пополнения баланса, смены региона/VPN или обновления ключа.

_Скрипт:_ `scripts/capture_live_screenshots.py`.
<!-- CAPTURE_LIVE:END -->

---

## 1. Исходная новость (длинный текст)

Тот же материал, что в
[`pipeline_walkthrough_news.txt`](pipeline_walkthrough_news.txt).

```text
Дачники, нанимающие нелегалов, заплатят за их депортацию: как
правильно выбрать рабочих

Кстати, к ответственности за наем на работу нелегальных мигрантов
могут привлечь не только дачников. Например, вы пригласили няню для
присмотра за детьми или пожилыми родственниками, наняли плиточника или
штукатура, чтобы сделать ремонт в квартире или частном доме — во всех
этих случаях вы становитесь работодателем и несете ответственность и за
себя, и за тех, кого пригласили.

Юристы напоминают: формальный договор и копии документов не
освобождают от проверки законности пребывания наемных работников.
Если у иностранца нет разрешения на труд, штрафы и расходы на выдворение
могут лечь на того, кто организовал работу и оплату. На практике это
касается не только крупных компаний, но и частных бригад на даче:
от покоса травы до возведения теплицы.

Как снизить риски. Спросите у кандидатов патент, разрешение или иной
законный статус и сверьте данные через официальные сервисы. Храните
сканы с согласия исполнителя, фиксируйте даты и объём работ. При
сомнениях лучше обратиться в юрконсультацию или нанять бригаду через
организацию с лицензией: тогда ответственность за кадры распределена
явно. Помните: экономия на «серых» схемах часто оборачивается
десятикратными расходами и испорченным соседским миром.

В ведомствах подчеркивают: гражданская солидарность не отменяет
контроля за трудовым правом. Сказать работнику «ты сам знаешь, как
устроиться» — недостаточно. Работодатель обязан удостовериться, что
смежные требования соблюдены, иначе споры перейдут в суды и
административные комиссии — без сказочного финала.

Источник: https://www.kp.ru/daily/27769.5/5228392/
```

---

## 2. Публичный HTTP API (оболочка)

Отдельных URL «на каждого агента» нет: все четыре вызываются из одного
запроса **`POST /api/generate`** в `app.main`.

| Метод | Назначение |
|-------|------------|
| `POST /api/generate` | Полный прогон: новости → RAG → сказка → аудит → Q&A |
| `GET /api/reports/runs` | Список сохранённых прогонов |
| `GET /api/reports/runs/{run_id}` | JSON отчёта (RAG top-k, эвристики, сказка) |
| `GET /api/health` | Проверка живости сервера |
| `GET /api/news` | Список примеров новостей для UI |
| `GET /api/tale-presets` | Пресеты RAG для UI |

### Переменные окружения и `.env`

Скрипт `capture_live_screenshots.py` читает корневой **`.env`** (не
коммитьте его). Поддерживаются:

| Переменная | Назначение |
|------------|------------|
| `OPENAI_API_KEY` | Прямой OpenAI или совместимый эндпоинт |
| `OPENAI_BASE_URL` | Необязательно, по умолчанию `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Необязательно, по умолчанию `gpt-4o-mini` |
| `DEEPSEEK_API_KEY` | DeepSeek (`https://api.deepseek.com/v1`, модель `deepseek-chat`) |
| `GROQ_KEY` или `GROQ_API_KEY` | Groq OpenAI-compatible |

`GIGACHAT_API_KEY` в текущем коде **не** подключён к `app.llm_providers`
(нужна отдельная интеграция).

Приоритет выбора рабочего ключа: OpenAI → DeepSeek → Groq. Перед съёмкой
выполняется короткий пробный `chat.completions`.

### Пример: запуск пайплайна

```bash
curl -s -X POST "http://127.0.0.1:8000/api/generate" \
  -H "Content-Type: application/json" \
  -d "$(python -c "
import json, pathlib
p = pathlib.Path('docs/pipeline_walkthrough_news.txt')
body = {'news_text': p.read_text(encoding='utf-8').strip(),
        'preset_id': 'russian_folk'}
print(json.dumps(body, ensure_ascii=False))
")"
```

---

## 3. Внутренняя цепочка: RAG и четыре вызова LLM

Реализация: `app.agents_pipeline.run_four_agent_pipeline`; провайдер —
`LLMProvider` (`app.llm_providers`): методы `chat_json_object` и
`chat_text`.

### Шаг 0 — нормализация текста

- `normalize_news_text(news_text)` (`app.story_service`).

### Шаг A — RAG (не LLM)

После агента новостей строится `rag_query` (подсказка пресета, ключевые
слова, темы, сводка). Дальше:

- **`FAIRYNEWS_RAG_BACKEND=snapshot`** —
  `retrieve_plot_records_from_snapshot` (`rag/snapshot_retrieve.py`),
  векторизация запроса, **k = 15**;
- иначе — `retrieve_plot_records` (Chroma).

### Агент 1 — «Новости» (сжатие в JSON)

| | |
|---|---|
| **Метод API провайдера** | `chat_json_object` |
| **temperature / max_tokens** | 0.2 / 1200 |

**System (смысл):** сжать новость в JSON: `summary`, `themes`,
`retrieval_keywords`.

### Агент 2 — «Сказка» (длинный текст)

| | |
|---|---|
| **Метод** | `chat_text` |
| **temperature / max_tokens** | 0.85 / 3500 |

### Агент 3 — «Аудит» (JSON)

| | |
|---|---|
| **Метод** | `chat_json_object` |
| **temperature / max_tokens** | 0.2 / 1200 |

### Агент 4 — «Вопрос–ответ» (JSON)

| | |
|---|---|
| **Метод** | `chat_json_object` |
| **temperature / max_tokens** | 0.4 / 900 |

---

## 4. Итоговая сказка при живом прогоне

Текст сказки, вопрос и эталон — **в ответе API** и на **шаге 3**
интерфейса; полный след — в JSON отчёта `GET /api/reports/runs/{id}`.
Детерминированный офлайн-пример без внешнего API см. в
[`pipeline_walkthrough.md`](pipeline_walkthrough.md) (раздел 4).

---

## 5. Скриншоты без внешнего API (сравнение)

Автозахват без оплаты LLM: `scripts/capture_e2e_screenshots.py` →
`e2e_screenshots/`.
