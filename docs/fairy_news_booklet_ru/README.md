# Русский буклет Fairy News (три DOCX)

Сборка даёт **три** файла в этой папке:

| Файл | Назначение |
|------|------------|
| `Fairy_News_RU_Booklet.docx` | Основной буклет: коллаж, каналы (школа / родчаты / Хабр), глоссарий, этика, пайплайн, чек-лист, готовый пост. **Без** длинных выгрузок DOM. |
| `Fairy_News_RU_Booklet_Prilozhenie_DOM.docx` | Вложение: полный текст, извлечённый из сохранённых HTML (сказка, отчёты, JSON журнала LLM). |
| `Fairy_News_RU_Booklet_Lite.docx` | Короткая версия для соцсетей; в конце — ссылка на полный буклет и приложение. |

На первой странице основного и Lite-буклетов вставляется **коллаж**
(`frontend/collage/`, как на сайте). Playwright сохраняет полный HTML каждой
страницы в `html/`, затем приложение собирает Word из извлечённого DOM.

**Демо-URL** в тексте буклета: переменная окружения
`FAIRYNEWS_BOOKLET_DEMO_URL` (если не задана — ссылка на репозиторий GitHub).

Сборка (сервер с `FAIRYNEWS_SAVE_REPORTS=1`):

```powershell
python scripts/build_fairy_news_ru_booklet.py --port 8765
```

Повторная сборка только из уже сохранённых HTML: `--skip-capture`.

Зависимости: `python-docx`, `beautifulsoup4`, `playwright`.
