"""Four LLM agents + deterministic RAG tale anchor (этап 1)."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Sequence

from rag.retrieve import retrieve_plot_records

from app.llm_utils import (
    chat_json_object,
    chat_text,
    get_model_name,
    get_openai_client,
)
from app.story_service import normalize_news_text

logger = logging.getLogger(__name__)

_RAG_K = 15
_TOP_FOR_VOTE = 10


def _pick_primary_source(
    records: list[tuple[str, dict[str, Any], float]],
) -> tuple[str, list[tuple[str, dict[str, Any], float]]]:
    """Weight sources by inverse distance in top hits; prefer best-matching work."""
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


def run_four_agent_pipeline(
    news_text: str,
    retrieval_hint: str,
    domains: Sequence[str] | None,
) -> dict[str, Any]:
    """News → RAG (pick work) → story → audit → Q&A."""
    client = get_openai_client()
    model = get_model_name()
    news_raw = normalize_news_text(news_text)

    news_sys = (
        "Ты агент новостей. Сожми вход в JSON: summary (строка), "
        "themes (массив 2–5 строк), retrieval_keywords (одна строка "
        "для поиска похожих сказок, по-русски)."
    )
    news_user = f"Новость:\n{news_raw}"
    news_json = chat_json_object(
        client, model, news_sys, news_user, temperature=0.2
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

    try:
        records = retrieve_plot_records(rag_query, k=_RAG_K, domains=domains)
    except Exception:
        logger.exception("RAG retrieve failed")
        raise RuntimeError(
            "Не удалось прочитать индекс сказок. "
            "Выполните: python -m rag --reset"
        ) from None

    if not records:
        raise RuntimeError(
            "Индекса нет или он пуст. Выполните: python -m rag --reset"
        )

    chosen_source, curated = _pick_primary_source(records)
    rag_block = _build_rag_block(curated)

    story_sys = (
        "Ты агент генерации сказки. Оригинальный русский текст в духе "
        "русской народной сказки; отрази идеи новости метафорически. "
        "Не копируй корпус дословно — мотивы и стиль."
    )
    story_user = (
        f"Новость (структурировано):\n{summary}\n"
        f"Темы: {', '.join(themes)}\n\n"
        f"Опорная сказка из RAG (источник: {chosen_source}):\n"
        f"{rag_block}\n\n"
        "Напиши цельную сказку примерно 600–1200 слов с завершённым финалом."
    )
    tale_draft = chat_text(
        client,
        model,
        story_sys,
        story_user,
        temperature=0.85,
        max_tokens=3500,
    )

    audit_sys = (
        "Ты агент аудита. Проверь связность, сказочный стиль, отсутствие "
        "прямой политической агитации. Верни JSON: approved (bool), "
        "notes (строка), tale (полный исправленный текст или пустая строка)."
    )
    audit_user = f"Сводка новости:\n{summary}\n\nСказка:\n{tale_draft}\n"
    audit_json = chat_json_object(
        client, model, audit_sys, audit_user, temperature=0.2
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
    qa_json = chat_json_object(
        client,
        model,
        qa_sys,
        qa_user,
        temperature=0.4,
        max_tokens=900,
    )
    question = str(qa_json.get("question", ""))
    ref_ans = str(qa_json.get("reference_answer", ""))

    return {
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
