"""Pydantic-модели ответов публичного Web API (контракт для UI и OpenAPI)."""

from __future__ import annotations

from pathlib import Path
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


_COLLAGE_TILES: list[
    tuple[str, str, Literal["news", "folktale", "neutral"]]
] = [
    ("tile-00", "Стопка газет и бумаг, общий фон", "news"),
    ("tile-01", "Текстура старой бумаги", "neutral"),
    ("tile-02", "Городской пейзаж с высоты", "news"),
    ("tile-03", "Звёздное небо (скопление Плеяд)", "folktale"),
    ("tile-04", "Книга на подставке", "folktale"),
    ("tile-05", "Старинные книги", "folktale"),
    ("tile-06", "Лесная тропа", "neutral"),
    ("tile-07", "Текстура дерева", "neutral"),
]


def _collage_assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "frontend" / "collage"


def _resolved_collage_file(stem: str) -> tuple[str, str]:
    """Имя файла в ``static/collage`` и опциональный fallback SVG URL."""
    directory = _collage_assets_dir()
    for ext in (".webp", ".png", ".jpg", ".jpeg", ".svg"):
        path = directory / f"{stem}{ext}"
        if path.is_file():
            name = path.name
            if name.endswith(".svg"):
                return name, ""
            svg = directory / f"{stem}.svg"
            if svg.is_file():
                return name, f"/static/collage/{stem}.svg"
            return name, ""
    return f"{stem}.svg", ""


def default_collage_tiles() -> list[CollageTileOut]:
    """Локальные файлы ``frontend/collage/`` (растр или SVG).

    Растр: ``python scripts/download_collage_images.py``; запасной ряд SVG:
    ``python scripts/generate_collage_assets.py``.
    """
    items: list[CollageTileOut] = []
    for stem, alt, motif in _COLLAGE_TILES:
        filename, fallback = _resolved_collage_file(stem)
        items.append(
            CollageTileOut(
                src=f"/static/collage/{filename}",
                alt=alt,
                motif=motif,
                placeholder=False,
                fallback_src=fallback,
            )
        )
    return items
