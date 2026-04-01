"""FastAPI MVP: three-step UI + RAG + LLM abstraction + отчёты."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import APIStatusError
from pydantic import BaseModel, Field

from app.api_schemas import (
    CollageResponse,
    GenerateResponse,
    HealthResponse,
    LLMLogResponse,
    NewsItemOut,
    NewsListResponse,
    ReportRunDocument,
    ReportRunSummaryOut,
    ReportsListResponse,
    TalePresetOut,
    TalePresetsResponse,
    default_collage_tiles,
)
from app.agents_pipeline import run_four_agent_pipeline
from app.news_items import get_news_item, list_public_news_items
from app.presets import TALE_PRESETS, get_preset, list_preset_ids
from app.report_storage import list_run_summaries, load_run_report, save_run_report
from app.run_database import load_llm_log

logger = logging.getLogger(__name__)


def _provider_error_message(exc: APIStatusError) -> str:
    """Сообщение из JSON (detail или error.message), иначе из исключения."""
    body = exc.body
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        err = body.get("error")
        if isinstance(err, dict):
            msg = err.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
    return str(exc.message or "").strip()


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
REPORTS_UI_DIR = FRONTEND_DIR / "reports"

app = FastAPI(
    title="FairyNews",
    version="0.3.0",
    description="Web API + Pydantic-схемы; UI потребляет JSON-контракты.",
)


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True)


@app.get("/api/ui/collage", response_model=CollageResponse)
def ui_collage() -> CollageResponse:
    """Декоративные тайлы для визуального коллажа (без привязки к контенту)."""
    return CollageResponse(items=default_collage_tiles())


@app.get("/api/news", response_model=NewsListResponse)
def list_news() -> NewsListResponse:
    raw = list_public_news_items()
    items = [NewsItemOut.model_validate(x) for x in raw]
    return NewsListResponse(items=items)


@app.get("/api/tale-presets", response_model=TalePresetsResponse)
def list_tale_presets() -> TalePresetsResponse:
    items = [TalePresetOut.model_validate(x) for x in TALE_PRESETS]
    return TalePresetsResponse(items=items)


@app.get("/api/reports/runs", response_model=ReportsListResponse)
def api_list_reports() -> ReportsListResponse:
    rows = [
        ReportRunSummaryOut.model_validate(x) for x in list_run_summaries()
    ]
    return ReportsListResponse(items=rows)


@app.get("/api/reports/runs/{run_id}", response_model=ReportRunDocument)
def api_get_report(run_id: str) -> ReportRunDocument:
    data = load_run_report(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="run not found")
    sid = str(data.get("run_id", run_id))
    log_row = load_llm_log(sid)
    merged = {
        **data,
        "llm_log_url": (
            f"/reports-ui/llm-log.html?id={sid}"
            if log_row is not None
            else None
        ),
    }
    return ReportRunDocument.model_validate(merged)


@app.get("/api/reports/llm-logs/{run_id}", response_model=LLMLogResponse)
def api_llm_log(run_id: str) -> LLMLogResponse:
    data = load_llm_log(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="llm log not found")
    return LLMLogResponse.model_validate(data)


class GenerateRequest(BaseModel):
    """Текст вручную, одна новость по id или до трёх id из списка API."""

    news_text: str | None = Field(default=None, max_length=8000)
    news_id: str | None = None
    news_ids: list[str] | None = Field(default=None, max_length=3)
    preset_id: str = "default"
    run_by: str | None = Field(default=None, max_length=200)


def _should_save_reports() -> bool:
    v = os.environ.get("FAIRYNEWS_SAVE_REPORTS", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


@app.post("/api/generate", response_model=GenerateResponse)
def run_generate(
    body: GenerateRequest,
    request: Request,
) -> GenerateResponse:
    if body.preset_id not in list_preset_ids():
        raise HTTPException(status_code=400, detail="Неизвестный preset_id")

    if body.news_id and body.news_ids:
        raise HTTPException(
            status_code=400,
            detail="Укажите либо news_id, либо news_ids, не оба.",
        )

    runner = (body.run_by or "").strip()
    if not runner:
        runner = (request.headers.get("X-FairyNews-Runner") or "").strip()

    text: str
    nid: str | None
    ids_multi: list[str] = [x for x in (body.news_ids or []) if x.strip()]
    if body.news_text and body.news_text.strip():
        text = body.news_text.strip()
        nid = None
    elif ids_multi:
        if len(ids_multi) > 3:
            raise HTTPException(
                status_code=400,
                detail="Не более трёх новостей (news_ids).",
            )
        parts: list[str] = []
        for raw_id in ids_multi:
            try:
                item = get_news_item(raw_id)
            except KeyError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Неизвестный news_id: {raw_id}",
                ) from exc
            parts.append(f"{item['title']}\n\n{item['summary']}")
        text = "\n\n---\n\n".join(parts)
        nid = None
    elif body.news_id:
        try:
            item = get_news_item(body.news_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=400,
                detail="Неизвестный news_id",
            ) from exc
        text = f"{item['title']}\n\n{item['summary']}"
        nid = body.news_id
    else:
        raise HTTPException(
            status_code=400,
            detail="Нужны news_text, news_id или news_ids (до 3 шт.).",
        )

    logger.info(
        "generate start preset_id=%s news_id=%s news_ids_n=%s custom_text=%s",
        body.preset_id,
        nid,
        len(ids_multi) if ids_multi else 0,
        bool(body.news_text and body.news_text.strip()),
    )
    try:
        preset = get_preset(body.preset_id)
        domains = preset.get("domains")
        raw = run_four_agent_pipeline(
            text,
            str(preset["retrieval_hint"]),
            domains,
            preset_id=body.preset_id,
            news_id=nid,
            run_by=runner or None,
        )
    except RuntimeError as exc:
        msg = str(exc)
        logger.warning("generate runtime: %s", msg)
        raise HTTPException(status_code=503, detail=msg) from exc
    except APIStatusError as exc:
        code = int(exc.status_code or 0)
        err_msg = str(exc.message or exc).strip()
        prov_msg = _provider_error_message(exc)
        logger.warning(
            "LLM API status %s: %s body_preview=%s",
            code,
            err_msg,
            repr(prov_msg)[:200],
        )
        if code == 402:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"HTTP 402 от LLM. Провайдер: {prov_msg or err_msg or '—'}. "
                    "Код часто означает «нельзя списать»; при положительном "
                    "балансе проверьте, что OPENAI_API_KEY от того же аккаунта, "
                    "и id модели из каталога (формат openai/… для AITunnel), "
                    "см. python -m app.llm_connect_try."
                ),
            ) from exc
        if code == 401:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Провайдер LLM вернул 401: неверный или просроченный ключ. "
                    "Проверьте OPENAI_API_KEY и базовый URL прокси."
                ),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=(
                f"Ошибка HTTP LLM ({code}): {err_msg or 'см. логи сервера'}"
            ),
        ) from exc
    except Exception:
        logger.exception("generate failed")
        raise HTTPException(
            status_code=500,
            detail="Ошибка генерации",
        ) from None

    report = raw.pop("report", None)
    timing = (report or {}).get("timing") or {}
    logger.info(
        "generate ok preset_id=%s wall_sec=%s llm_total=%s",
        body.preset_id,
        timing.get("pipeline_wall_sec"),
        timing.get("llm_total_sec"),
    )
    run_id: str | None = None
    if report is not None and _should_save_reports():
        run_id = save_run_report(report)

    out: dict[str, Any] = {
        "tale": raw["tale"],
        "news_brief": raw["news_brief"],
        "chosen_tale_source": raw["chosen_tale_source"],
        "rag_chunks_used": raw["rag_chunks_used"],
        "audit": raw["audit"],
        "qa": raw["qa"],
    }
    if run_id:
        out["run_id"] = run_id
        out["report_detail_url"] = f"/reports-ui/detail.html?id={run_id}"
        out["llm_log_url"] = f"/reports-ui/llm-log.html?id={run_id}"
    return GenerateResponse.model_validate(out)


app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="frontend_static",
)

if REPORTS_UI_DIR.is_dir():
    app.mount(
        "/reports-ui",
        StaticFiles(directory=str(REPORTS_UI_DIR), html=True),
        name="reports_ui",
    )
