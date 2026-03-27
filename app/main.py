"""FastAPI MVP: three-step UI + RAG + OpenAI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agents_pipeline import run_four_agent_pipeline
from app.mock_news import MOCK_NEWS, get_news_item
from app.presets import TALE_PRESETS, get_preset, list_preset_ids

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="FairyNews MVP", version="0.1.0")


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/news")
def list_news() -> dict[str, list[dict[str, Any]]]:
    return {"items": MOCK_NEWS}


@app.get("/api/tale-presets")
def list_tale_presets() -> dict[str, list[dict[str, Any]]]:
    return {"items": TALE_PRESETS}


class GenerateRequest(BaseModel):
    """Either send raw ``news_text`` or ``news_id`` from mock list."""

    news_text: str | None = Field(default=None, max_length=8000)
    news_id: str | None = None
    preset_id: str = "default"


@app.post("/api/generate")
def run_generate(body: GenerateRequest) -> dict[str, Any]:
    if body.preset_id not in list_preset_ids():
        raise HTTPException(status_code=400, detail="Неизвестный preset_id")

    text: str
    if body.news_text and body.news_text.strip():
        text = body.news_text.strip()
    elif body.news_id:
        try:
            item = get_news_item(body.news_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=400,
                detail="Неизвестный news_id",
            ) from exc
        text = f"{item['title']}\n\n{item['summary']}"
    else:
        raise HTTPException(
            status_code=400,
            detail="Нужны news_text или news_id",
        )

    try:
        preset = get_preset(body.preset_id)
        domains = preset.get("domains")
        result = run_four_agent_pipeline(
            text,
            str(preset["retrieval_hint"]),
            domains,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        logger.exception("generate failed")
        raise HTTPException(
            status_code=500,
            detail="Ошибка генерации",
        ) from None

    return {
        "tale": result["tale"],
        "news_brief": result["news_brief"],
        "chosen_tale_source": result["chosen_tale_source"],
        "rag_chunks_used": result["rag_chunks_used"],
        "audit": result["audit"],
        "qa": result["qa"],
    }
