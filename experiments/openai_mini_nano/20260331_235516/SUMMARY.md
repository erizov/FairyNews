# Прогон пайплайна: gpt-4o-mini и gpt-4.1-nano

- Новость: `docs\pipeline_walkthrough_news.txt`
- Пресет: `russian_folk`
- Режим: uniform, backend `openai`

| Модель (запрос) | Id для API | Успех | wall_s | llm_s | tale_chars |
|---|---|---|---:|---:|---:|
| `gpt-4o-mini` | `openai/gpt-4o-mini` | да | 59.9796 | 53.793 | 3802 |
| `gpt-4o-nano` | `openai/gpt-4o-nano` | нет | — | — | — |

**Ошибка** (`gpt-4o-nano`): `Error code: 400 - {'error': {'message': 'openai/gpt-4o-nano is not a valid model ID', 'code': 400}, 'user_id': 'user_2kYRNpZ8quaNe32XFTvgGRIuNMH', 'model': 'openai/gpt-4o-nano'}`