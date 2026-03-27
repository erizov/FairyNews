# FairyNews / Нейро-сказочник — обзор репозитория

Дипломный проект: LLM + RAG по сказкам + новости (политика в RAG не индексируется).
Краткий слоган: *«сказки нашего века — с каждым днём всё сказочнее жить, сменили
амплуа герои сказок».*

Документ описывает **что уже сделано в коде и данных**, как **собрать RAG по
сказкам**, как **посмотреть отчёт** по индексу и как **запустить пайплайн**
периодического обновления. Политические **новости в RAG не индексируются**
(только сказки и смежные тексты).

## Структура

| Путь | Назначение |
|------|------------|
| `etap1_utverzhdenie_temy.md` | Этап 1: тема, мультиагентная архитектура |
| `etap2_sbor_i_obrabotka_bazy.md` | Этап 2: сбор базы, источники |
| `istochniki_skazok_novostey_i_rag.md` | Списки сайтов, заметки по RAG / агентам |
| `rag/` | Код RAG: индексация, отчёт, пайплайн |
| `rag/sources/fairy_tale_seeds.yaml` | Семена Gutenberg + локальные маски `.txt` |
| `data/chroma_fairy_tales/` | Локальная БД Chroma (векторы, метаданные) |
| `data/raw/local_tales/` | Локальные UTF‑8 `.txt`: общий каталог, подпапки `russian/`, `soviet/` |
| `data/rag_pipeline_state.json` | Хеши источников для инкрементального update |
| `app/` | FastAPI; цепочка из 4 LLM-агентов: `agents_pipeline.py` |
| `tests/` | Pytest; e2e: `test_e2e_multi_agent.py` |
| `frontend/` | Статика: три шага + блок аудита и вопрос–ответ |
| `scripts/start_web.ps1`, `stop_web.ps1` | Запуск/остановка uvicorn (Windows) |
| `scripts/start_web.sh`, `stop_web.sh` | Запуск (foreground) / остановка порта (Linux/macOS) |
| `requirements.txt` | Python-зависимости |

## Что сделано

1. **Индекс RAG только для сказочных текстов** (сюжеты, опоры для **агента
   генерации сказки**): загрузка Project Gutenberg по ID из YAML, чанкование
   (~900 символов, перекрытие 120), эмбеддинги
   `paraphrase-multilingual-MiniLM-L12-v2`, хранение в **ChromaDB**.
2. Метаданные чанков: `domain`, `source`, `work_note`, `author`, `country`,
   `heroes`, `content_lang`, `content_sha256`, `chunk_index`.
3. **Полная пересборка**: `python -m rag --reset` (стирает коллекцию и
   переиндексирует всё).
4. **Отчёт** по коллекции: чанки, число произведений (уникальный `source`),
   разрезы по домену / стране / автору, подсказки по героям.
5. **Инкрементальный пайплайн**: сравнение SHA‑256 полного текста источника с
   сохранённым; при изменении — удаление старых чанков по `source` и повторная
   запись. Файл состояния: `data/rag_pipeline_state.json`.
6. **Фоновый цикл** (простой `sleep` между прогонами): `rag.pipeline daemon`.

Подробные оценки объёма и примечания: `rag/VOLUME_ESTIMATES.md`.

## Установка

```bash
cd /path/to/Diploma
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

Первый запуск подтянет модель с Hugging Face (нужен интернет).

## Веб-MVP (нейро-сказочник)

Три шага в браузере: **новость** (мок-список или свой текст) → **пресет сказки**
(RAG-фильтры) → **текст, аудит, вопрос с эталонным ответом**. На сервере:
агент новостей (JSON-сводка) → **ретрив и выбор якорного `source` в Chroma по
схожести** → агент генерации → аудит → вопрос–ответ (четыре вызова LLM).

**Интеграционный e2e** (мок LLM, нужен собранный RAG):

```bash
python -m pytest tests/test_e2e_multi_agent.py -q
```

Живой OpenAI в том же файле: `RUN_LIVE_OPENAI_E2E=1` и `OPENAI_API_KEY`.

**Подготовка:** собрать индекс сказок и задать ключ API.

```bash
python -m rag --reset
# Windows PowerShell:
$env:OPENAI_API_KEY = "sk-..."   # или постоянно в системе
# опционально: $env:OPENAI_MODEL = "gpt-4o-mini"
```

### Запуск и остановка сервера

Из корня репозитория (с активированным `.venv` при ручном запуске).

**Windows (отдельное окно uvicorn):**

```powershell
.\scripts\start_web.ps1
# другой порт: .\scripts\start_web.ps1 -Port 9000
```

Остановка процесса на порту **8765**:

```powershell
.\scripts\stop_web.ps1
# .\scripts\stop_web.ps1 -Port 9000
```

**Вручную (любая ОС, foreground):**

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Останов — `Ctrl+C` в том же терминале.

**Linux/macOS:** foreground — `chmod +x scripts/start_web.sh && ./scripts/start_web.sh`
(переменная `PORT` опциональна). Остановка фонового процесса:
`chmod +x scripts/stop_web.sh && ./scripts/stop_web.sh` (нужны `fuser` или `lsof`).

Откройте в браузере: `http://127.0.0.1:8765/`.

### `ModuleNotFoundError: No module named 'chromadb'`

Зависимости не установлены для того интерпретатора, которым вы вызываете
`python -m rag...`. Выполните из каталога проекта:

```bash
python -m pip install -r requirements.txt
```

Либо активируйте виртуальное окружение (`.venv`) и снова выполните тот же
`pip install`. Убедитесь, что `where python` / `Get-Command python` указывает
нужный Python.

## RAG

Индекс только **сказочных** текстов (без политических новостей): чанки в
**ChromaDB** (`data/chroma_fairy_tales/` — каталог в `.gitignore`, создаётся при
сборке). Подробности по объёму: `rag/VOLUME_ESTIMATES.md`.

### Команды

```bash
python -m rag --reset
python -m rag.pipeline update
python -m rag.report
```

- **`python -m rag --reset`** — полная пересборка: стирается коллекция Chroma и
  заново качаются/читаются все источники из `rag/sources/fairy_tale_seeds.yaml`.
  Без `--reset` повторный запуск **наслоит** дубликаты — для чистой пересборки
  нужен именно `--reset`.
- **`python -m rag.pipeline update`** — инкремент: пересчитываются только
  источники с изменившимся SHA‑256 текста; на stdout — JSON
  (`updated_sources`, `skipped_sources`, `chunks_added`).
- **`python -m rag.report`** — сводка по индексу (по умолчанию русские подписи с
  английским в скобках). Полезно: `--json`, `--show-chunks-per-work`,
  `--lang en`.

После смены метаданных в YAML имеет смысл сделать **`--reset`**, удалить
`data/rag_pipeline_state.json` и затем снова вызывать `pipeline update`, чтобы
хеши совпали.

**Периодический режим** (цикл с паузой, не реже **5 минут** между прогонами):

```bash
python -m rag.pipeline daemon --interval-hours 24
```

Останов — `Ctrl+C`. В проде чаще ставят **планировщик ОС** на
`python -m rag.pipeline update` из каталога проекта с активированным venv.

### Основные источники

| Что | Где |
|-----|-----|
| Семена Gutenberg + маски локальных `.txt` | `rag/sources/fairy_tale_seeds.yaml` |
| Европейские / восточные PD, русский фольклор в **англ.** переводе на Gutenberg, пример **Л. Н. Толстой** — ebook **38025** | те же семена, ID в YAML |
| Локальные русские и советские тексты (UTF‑8) | `data/raw/local_tales/russian/`, `data/raw/local_tales/soviet/` |
| Состояние инкремента (хеши по `source`) | `data/rag_pipeline_state.json` (в `.gitignore`) |

**Язык текста в чанках** (`content_lang`): тексты с Gutenberg по умолчанию
**английские** (`en`); файлы под `local_tales/` — **русские** (`ru`). Редкий
русский полнотекст с Gutenberg: задайте в YAML `content_lang: ru`.

### Отчёт: поля и опции

```bash
python -m rag.report --lang ru
python -m rag.report --lang en
python -m rag.report --show-chunks-per-work
python -m rag.report --json
```

В отчёте: число чанков и произведений, разрезы по `domain` / `country` /
`author` / `content_lang`, подсказки `heroes`. В `--json` дополнительно
`chunks_per_work`, `by_content_lang`, `summary`. Отдельные **сказки** внутри
большого сборника без разметки по заголовкам в отчёт не попадают — только уровень
книги/файла.

### Почему в индексе не было Л. Толстого, Е. Шварца и др.

- **Л. Н. Толстой** — в семена добавлен Gutenberg **38025** (*Fables for
  Children, Stories for Children…*, PD, английский перевод). Раньше в отчёте по
  авторам были в основном **народные** сборники и переводчики, без отдельной
  строки «Tolstoy». После правок YAML нужна пересборка: `python -m rag --reset`.
- **Е. Л. Шварц** и большинство **советских** текстов XX века в Project Gutenberg
  в PD **нет** (авторское право). Подключать **локально**: UTF‑8 `.txt` в
  `data/raw/local_tales/soviet/` (при необходимости — `author` в YAML для маски)
  с соблюдением лицензий.

## Локальные тексты

- `data/raw/local_tales/soviet/**/*.txt` — **советские** авторы (при допустимых
  правах); в индексе метаданные `country: USSR`.
- `data/raw/local_tales/russian/**/*.txt` — русскоязычный слой (народные,
  дореволюционные, современные PD и т.д.); `country: RU`.
- Любые другие `.txt` под `data/raw/local_tales/**/*.txt` — тоже `RU`, если не
  попали в подпапки выше.

Порядок масок в YAML важен: более узкие папки должны идти **раньше** (дедупликация
по пути файла). Опционально на маску: поля `author`, `country`, `heroes`.

В **Gutenberg** добавлены англоязычные PD-сборники русского фольклора (Афанасьев,
Полевой, Рэнсом и др.) — см. `rag/sources/fairy_tale_seeds.yaml`.

## Связь с агентами (контекст)

Цепочка из этапа 1: **агент новостей** (без RAG сказок) → **агент генерации**
(промпт + `rag.retrieve` / `rag.agent_bridge`) → **аудит** → **вопрос–ответ**.
Веб (FastAPI + простой фронт) — оболочка; внутри — несколько вызовов GPT с
разными промптами.
