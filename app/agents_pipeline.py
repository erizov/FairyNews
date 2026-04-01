"""Four LLM agents + deterministic RAG tale anchor (этап 1, этап 4)."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from rag.rag_enhanced import run_retrieval
from rag.snapshot_retrieve import DEFAULT_SNAPSHOT_PATH

from app.heuristics import compute_news_tale_heuristics
from app.llm_providers import LLMProvider, resolve_pipeline_llm_providers
from app.report_storage import utc_now_iso
from app.story_service import normalize_news_text

logger = logging.getLogger(__name__)

_TOP_FOR_VOTE = 10


def _rag_k_from_env() -> int:
    raw = os.environ.get("FAIRYNEWS_RAG_K", "15").strip()
    try:
        k = int(raw)
    except ValueError:
        return 15
    return max(1, min(k, 50))


def default_snapshot_path() -> Path:
    return DEFAULT_SNAPSHOT_PATH


def _pick_primary_source(
    records: list[tuple[str, dict[str, Any], float]],
) -> tuple[str, list[tuple[str, dict[str, Any], float]]]:
    if not records:
        return "", []
    scores: dict[str, float] = defaultdict(float)
    for _doc, meta, dist in records[:_TOP_FOR_VOTE]:
        src = str(meta.get("source", ""))
        if not src:
            continue
        scores[src] += 1.0 / (1.0 + float(dist))
    if not scores:
        return str(records[0][1].get("source", "")), list(records[:8])
    chosen = max(scores, key=scores.get)
    same = [(d, m, x) for d, m, x in records if str(m.get("source", "")) == chosen]
    curated = same[:12] if len(same) >= 2 else list(records[:8])
    return chosen, curated


def _build_rag_block(
    curated: list[tuple[str, dict[str, Any], float]],
) -> str:
    blocks: list[str] = []
    for doc, meta, _dist in curated:
        header_parts = [
            str(meta.get("domain", "")),
            str(meta.get("source", "")),
            str(meta.get("content_lang", "")),
            str(meta.get("work_note", "")),
        ]
        header = " | ".join(p for p in header_parts if p)
        blocks.append(f"[{header}]\n{doc}")
    return "\n\n---\n\n".join(blocks)


def _top_k_for_report(
    records: list[tuple[str, dict[str, Any], float]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for doc, meta, dist in records[:limit]:
        out.append(
            {
                "source": str(meta.get("source", "")),
                "work_note": str(meta.get("work_note", "")),
                "domain": str(meta.get("domain", "")),
                "distance": round(float(dist), 6),
                "snippet": doc[:200].replace("\n", " "),
            }
        )
    return out


def run_four_agent_pipeline(
    news_text: str,
    retrieval_hint: str,
    domains: Sequence[str] | None,
    *,
    llm: LLMProvider | None = None,
    rag_backend: str | None = None,
    snapshot_path: Path | None = None,
    preset_id: str | None = None,
    news_id: str | None = None,
    run_by: str | None = None,
) -> dict[str, Any]:
    """News → RAG → story → audit → Q&A. Adds ``report`` for persistence."""
    wall0 = time.perf_counter()
    per_stage_on, stage_llm = resolve_pipeline_llm_providers(llm=llm)
    uni_raw = os.environ.get("FAIRYNEWS_LLM_UNIFORM_STAGES", "").strip().lower()
    uniform_stages = uni_raw in ("1", "true", "yes", "on")
    backend = (
        rag_backend
        or os.environ.get("FAIRYNEWS_RAG_BACKEND", "chroma")
    ).strip().lower()

    news_raw = normalize_news_text(news_text)
    llm_trace: list[dict[str, Any]] = []

    news_sys = (
        "Ты агент новостей. Сожми вход в JSON: summary (строка), "
        "themes (массив 2–5 строк), retrieval_keywords (одна строка "
        "для гибридного поиска по сказкам: по-русски, 4–12 ключевых "
        "слов и устойчивых сочетаний, характерных сказочные образы "
        "и предметы (царь, изба, дорога, справедливость и т.п.), "
        "без цитирования заголовка дословно)."
    )
    news_user = f"Новость:\n{news_raw}"
    _t0 = time.perf_counter()
    news_json = stage_llm["news"].chat_json_object(
        news_sys, news_user, temperature=0.2, max_tokens=1200
    )
    t_news = time.perf_counter() - _t0
    llm_trace.append(
        {
            "step": "news",
            "call": "chat_json_object",
            "request": {
                "system": news_sys,
                "user": news_user,
                "temperature": 0.2,
                "max_tokens": 1200,
            },
            "response": news_json,
        },
    )
    summary = str(news_json.get("summary", news_raw))[:1200]
    themes_raw = news_json.get("themes")
    themes = themes_raw if isinstance(themes_raw, list) else []
    themes = [str(t) for t in themes[:5]]
    kw = str(news_json.get("retrieval_keywords", ""))

    rag_query = (
        f"{retrieval_hint}\n{kw}\n"
        f"Темы: {', '.join(themes)}\nСводка: {summary}"
    )

    snap = snapshot_path or default_snapshot_path()
    rag_k = _rag_k_from_env()
    hint_for_focus = (retrieval_hint or "").strip()
    focus_phrases = list(themes) + [kw, summary[:400]]
    if hint_for_focus:
        focus_phrases.append(hint_for_focus)
    _t_r0 = time.perf_counter()
    try:
        records, rag_meta = run_retrieval(
            rag_query,
            k=rag_k,
            backend=backend,
            domains=domains,
            snapshot_path=snap if backend == "snapshot" else None,
            focus_phrases=focus_phrases,
        )
    except Exception:
        logger.exception("RAG retrieve failed")
        raise RuntimeError(
            "Не удалось прочитать индекс сказок. "
            "Chroma: python -m rag --reset; snapshot: проверьте JSON."
        ) from None
    t_rag = time.perf_counter() - _t_r0

    if not records:
        raise RuntimeError(
            "Индекс пуст или снимок пуст. Для Chroma: python -m rag --reset; "
            "для snapshot: data/notebook_rag_snapshot.json"
        )

    chosen_source, curated = _pick_primary_source(records)
    rag_block = _build_rag_block(curated)
    vote_weights: dict[str, float] = defaultdict(float)
    for _d, m, dist in records[:_TOP_FOR_VOTE]:
        s = str(m.get("source", ""))
        if s:
            vote_weights[s] += 1.0 / (1.0 + float(dist))

    story_sys = (
        "Ты агент генерации сказки. Оригинальный русский текст в духе "
        "русской народной сказки; отрази идеи новости метафорически. "
        "Опора из RAG получена гибридным поиском (вектор + BM25, слияние "
        "рангов RRF), при необходимости второй проход с уточнённым запросом; "
        "фрагменты чанков сжаты по бюджету с приоритетом релевантных "
        "предложений в порядке чтения. Не копируй корпус дословно — "
        "мотивы и атмосфера, не формулировки источника."
    )
    story_user = (
        f"Новость (структурировано):\n{summary}\n"
        f"Темы: {', '.join(themes)}\n\n"
        f"Опорная сказка из RAG (источник: {chosen_source}):\n"
        f"{rag_block}\n\n"
        "Напиши цельную сказку примерно 600–1200 слов с завершённым финалом."
    )
    _t1 = time.perf_counter()
    tale_draft = stage_llm["story"].chat_text(
        story_sys,
        story_user,
        temperature=0.85,
        max_tokens=3500,
    )
    t_story = time.perf_counter() - _t1
    llm_trace.append(
        {
            "step": "story",
            "call": "chat_text",
            "request": {
                "system": story_sys,
                "user": story_user,
                "temperature": 0.85,
                "max_tokens": 3500,
            },
            "response": {"text": tale_draft},
        },
    )

    audit_sys = (
        "Ты агент аудита. Проверь связность, сказочный стиль, отсутствие "
        "прямой политической агитации. Верни JSON: approved (bool), "
        "notes (строка), tale (полный исправленный текст или пустая строка)."
    )
    audit_user = f"Сводка новости:\n{summary}\n\nСказка:\n{tale_draft}\n"
    _t2 = time.perf_counter()
    audit_json = stage_llm["audit"].chat_json_object(
        audit_sys, audit_user, temperature=0.2, max_tokens=1200
    )
    t_audit = time.perf_counter() - _t2
    llm_trace.append(
        {
            "step": "audit",
            "call": "chat_json_object",
            "request": {
                "system": audit_sys,
                "user": audit_user,
                "temperature": 0.2,
                "max_tokens": 1200,
            },
            "response": audit_json,
        },
    )
    approved = bool(audit_json.get("approved", True))
    notes = str(audit_json.get("notes", ""))
    revised = str(audit_json.get("tale", "")).strip()
    tale_final = revised if revised else tale_draft

    qa_sys = (
        "Ты агент «вопрос–ответ». Один вопрос по сказке и эталонный ответ. "
        "JSON: question, reference_answer (по-русски)."
    )
    qa_user = f"Сказка:\n{tale_final}\n"
    _t3 = time.perf_counter()
    qa_json = stage_llm["qa"].chat_json_object(
        qa_sys,
        qa_user,
        temperature=0.4,
        max_tokens=900,
    )
    t_qa = time.perf_counter() - _t3
    llm_trace.append(
        {
            "step": "qa",
            "call": "chat_json_object",
            "request": {
                "system": qa_sys,
                "user": qa_user,
                "temperature": 0.4,
                "max_tokens": 900,
            },
            "response": qa_json,
        },
    )
    question = str(qa_json.get("question", ""))
    ref_ans = str(qa_json.get("reference_answer", ""))

    heur = compute_news_tale_heuristics(
        summary,
        themes,
        tale_final,
        chunk_sources=[str(m.get("source", "")) for _d, m, _ in records[:8]],
    )

    llm_sum = t_news + t_story + t_audit + t_qa
    timing: dict[str, Any] = {
        "rag_retrieve_sec": round(t_rag, 4),
        "llm_news_sec": round(t_news, 4),
        "llm_story_sec": round(t_story, 4),
        "llm_audit_sec": round(t_audit, 4),
        "llm_qa_sec": round(t_qa, 4),
        "llm_total_sec": round(llm_sum, 4),
        "pipeline_wall_sec": round(time.perf_counter() - wall0, 4),
    }

    client: dict[str, Any] = {
        "tale": tale_final,
        "news_brief": {
            "summary": summary,
            "themes": themes,
            "retrieval_keywords": kw,
        },
        "chosen_tale_source": chosen_source or "(unknown)",
        "rag_chunks_used": len(curated),
        "audit": {"approved": approved, "notes": notes},
        "qa": {
            "question": question,
            "reference_answer": ref_ans,
        },
    }

    report_payload: dict[str, Any] = {
        "created_at": utc_now_iso(),
        "preset_id": preset_id,
        "news_id": news_id,
        "run_by": (run_by or "").strip() or "anonymous",
        "news_raw": news_raw,
        "rag_query_chars": len(rag_query),
        "tale": tale_final,
        "news_brief": client["news_brief"],
        "chosen_tale_source": client["chosen_tale_source"],
        "rag_chunks_used": client["rag_chunks_used"],
        "audit": client["audit"],
        "qa": client["qa"],
        "rag": {
            "backend": backend,
            "k_retrieve": rag_k,
            "snapshot_path": str(snap) if backend == "snapshot" else None,
            "top_k": _top_k_for_report(records),
            "anchor_vote_weights": {
                k: round(v, 6) for k, v in vote_weights.items()
            },
            "chunks_in_prompt": len(curated),
            **rag_meta,
        },
        "llm": {
            "per_stage": per_stage_on,
            "uniform_stages": uniform_stages,
            "provider": (
                "mixed"
                if per_stage_on and not uniform_stages
                else stage_llm["news"].provider_name
            ),
            "model": (
                stage_llm["story"].model_label
                if per_stage_on
                else stage_llm["news"].model_label
            ),
            "stages": {
                s: {
                    "provider": stage_llm[s].provider_name,
                    "model": stage_llm[s].model_label,
                }
                for s in stage_llm
            },
        },
        "timing": timing,
        "generation": {
            "tale_chars": len(tale_final),
            "audit_revised": bool(revised),
            "question_len": len(question),
            "answer_len": len(ref_ans),
        },
        "heuristics": heur,
        "llm_trace": llm_trace,
        "agent_prompts": {
            "news": {
                "system": news_sys,
                "user": news_user,
                "temperature": 0.2,
                "max_tokens": 1200,
            },
            "story": {
                "system": story_sys,
                "user": story_user,
                "temperature": 0.85,
                "max_tokens": 3500,
            },
            "audit": {
                "system": audit_sys,
                "user": audit_user,
                "temperature": 0.2,
                "max_tokens": 1200,
            },
            "qa": {
                "system": qa_sys,
                "user": qa_user,
                "temperature": 0.4,
                "max_tokens": 900,
            },
        },
        "agent_outputs": {
            "news_json": news_json,
            "story_draft": tale_draft,
            "audit_json": audit_json,
            "qa_json": qa_json,
        },
    }
    prof = os.environ.get("FAIRYNEWS_TEST_PROFILE", "").strip()
    if prof:
        report_payload["test_profile"] = prof
    client["report"] = report_payload
    return client
