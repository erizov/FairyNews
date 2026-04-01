"""Pydantic-модели ответов публичного Web API (контракт для UI и OpenAPI)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    ok: bool = True


class NewsItemOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    date: str = ""
    summary: str = ""
    source: str = ""
    lang: str = ""
    link: str = ""


class NewsListResponse(BaseModel):
    items: list[NewsItemOut]


class TalePresetOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    label: str
    description: str = ""
    retrieval_hint: str = ""


class TalePresetsResponse(BaseModel):
    items: list[TalePresetOut]


class ReportRunSummaryOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    created_at: str = ""
    run_by: str = ""
    duration_sec: float | None = None
    news_preview: str = ""
    tale_preview: str = ""
    chosen_tale_source: str = ""
    tale_chars: int = 0
    audit_approved: bool = False
    rag_backend: str = ""
    news_id: str | None = None
    llm_log_url: str | None = None


class ReportsListResponse(BaseModel):
    items: list[ReportRunSummaryOut]


class CollageTileOut(BaseModel):
    """Один фрагмент коллажа: без привязки к конкретной новости/сказке."""

    src: str = Field(
        default="",
        description="URL изображения; пусто при placeholder (без сетевых картинок)",
    )
    alt: str = Field(description="Нейтральный alt / aria-label для доступности")
    motif: Literal["news", "folktale", "neutral"] = Field(
        description="Семантическая группа и стиль CSS-плейсхолдера",
    )
    placeholder: bool = Field(
        default=True,
        description="False — показать src в UI; True — только CSS-плейсхолдер",
    )
    fallback_src: str = Field(
        default="",
        description="Запасной URL, если основной src не загрузился",
    )


class CollageResponse(BaseModel):
    items: list[CollageTileOut]


class NewsBriefOut(BaseModel):
    summary: str = ""
    themes: list[str] = Field(default_factory=list)
    retrieval_keywords: str = ""


class AuditOut(BaseModel):
    approved: bool = False
    notes: str = ""


class QAOut(BaseModel):
    question: str = ""
    reference_answer: str = ""


class GenerateResponse(BaseModel):
    tale: str
    news_brief: NewsBriefOut
    chosen_tale_source: str
    rag_chunks_used: int
    audit: AuditOut
    qa: QAOut
    run_id: str | None = None
    report_detail_url: str | None = None
    llm_log_url: str | None = None


class LLMLogResponse(BaseModel):
    """Журнал шагов LLM для прогона (запрос/ответ по этапам)."""

    run_id: str
    created_at: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)


class ReportRunDocument(BaseModel):
    """Полный отчёт: известные поля + произвольные (совместимость версий)."""

    model_config = ConfigDict(extra="allow")

    run_id: str | None = None
    created_at: str | None = None
    preset_id: str | None = None
    run_by: str | None = None
    news_id: str | None = None
    news_raw: str = ""
    tale: str = ""
    news_brief: dict[str, Any] | None = None
    chosen_tale_source: str | None = None
    rag_chunks_used: int | None = None
    audit: dict[str, Any] | None = None
    qa: dict[str, Any] | None = None
    rag: dict[str, Any] | None = None
    llm: dict[str, Any] | None = None
    timing: dict[str, Any] | None = None
    agent_outputs: dict[str, Any] | None = None
    agent_prompts: dict[str, Any] | None = None
    heuristics: dict[str, Any] | None = None
    llm_log_url: str | None = None


_COLLAGE_FILES: list[
    tuple[str, str, Literal["news", "folktale", "neutral"]]
] = [
    ("tile-00.svg", "Стопка газет и бумаг, общий фон", "news"),
    ("tile-01.svg", "Текстура старой бумаги", "neutral"),
    ("tile-02.svg", "Абстрактный городской фон", "news"),
    ("tile-03.svg", "Ночное небо со звёздами", "folktale"),
    ("tile-04.svg", "Разворот книги, без названия", "folktale"),
    ("tile-05.svg", "Книжные корешки в ряд", "folktale"),
    ("tile-06.svg", "Тропа в лесу, без сюжета", "neutral"),
    ("tile-07.svg", "Мягкий тёплый блик, абстрактно", "neutral"),
]


def default_collage_tiles() -> list[CollageTileOut]:
    """Локальные ``frontend/collage/tile-*.svg`` (без внешних URL в рантайме).

    Сборка ассетов: ``python scripts/generate_collage_assets.py``.
    """
    return [
        CollageTileOut(
            src=f"/static/collage/{fn}",
            alt=alt,
            motif=motif,
            placeholder=False,
            fallback_src="",
        )
        for fn, alt, motif in _COLLAGE_FILES
    ]
