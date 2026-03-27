"""E2E: news → RAG anchor → four-agent tale (HTTP API)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _chromadb_has_chunks() -> bool:
    try:
        from rag.store import get_collection

        col = get_collection(reset=False)
        return col.count() > 0
    except Exception:
        return False


live_openai = pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_OPENAI_E2E"),
    reason="set RUN_LIVE_OPENAI_E2E=1 and OPENAI_API_KEY for live API test",
)


@pytest.mark.e2e
def test_e2e_pipeline_mocked_llm() -> None:
    """Полный HTTP-флоу; LLM подменён — проверка RAG + четыре точки вызова."""
    if not _chromadb_has_chunks():
        pytest.skip("Chroma empty — run: python -m rag --reset")

    news_out = {
        "summary": "Кузнецы и мастеровые просят справедливой цены.",
        "themes": ["труд", "ярмарка", "народ"],
        "retrieval_keywords": "кузнец народная сказка",
    }
    audit_out = {"approved": True, "notes": "ок", "tale": ""}
    qa_out = {
        "question": "Кто собрался у терема?",
        "reference_answer": "Ремесленники.",
    }
    story_text = (
        "Жил-был царь Горох, а у него в подданных — кузнецы да ткачихи. "
        "Пришли они к терему не с мечом, а с наковальней да челноком, "
        "и сказали слово крепкое. Царь услышал и завесу поднял — стало "
        "на площади светло. Спорили они до третьего петуха, но вышло "
        "так, что каждому досталось зерно да уваженье. А кто не верит — "
        "пусть к молодцам снова сходить."
    )

    with patch(
        "app.agents_pipeline.chat_json_object",
        side_effect=[news_out, audit_out, qa_out],
    ):
        with patch(
            "app.agents_pipeline.chat_text",
            return_value=story_text,
        ):
            client = TestClient(app)
            response = client.post(
                "/api/generate",
                json={"news_id": "m3", "preset_id": "russian_folk"},
            )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["tale"] == story_text
    assert data["news_brief"]["summary"] == news_out["summary"]
    assert data["chosen_tale_source"]
    assert data["rag_chunks_used"] >= 1
    assert data["audit"]["approved"] is True
    assert data["qa"]["question"] == qa_out["question"]
    assert data["qa"]["reference_answer"] == qa_out["reference_answer"]

    tale_l = data["tale"].lower()
    brief_l = news_out["summary"].lower()
    assert any(t in tale_l for t in brief_l.split() if len(t) > 5)


@live_openai
@pytest.mark.e2e
def test_e2e_live_generate_russian_folk_preset() -> None:
    """Живой OpenAI + Chroma (только если регион API доступен)."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    if not _chromadb_has_chunks():
        pytest.skip("Chroma empty — run: python -m rag --reset")

    client = TestClient(app)
    response = client.post(
        "/api/generate",
        json={"news_id": "m3", "preset_id": "russian_folk"},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data.get("tale", "")) > 350
    assert data.get("chosen_tale_source")

    brief = data.get("news_brief") or {}
    assert brief.get("summary")
    assert isinstance(brief.get("themes"), list)

    audit = data.get("audit") or {}
    assert "approved" in audit

    qa = data.get("qa") or {}
    assert qa.get("question")
    assert qa.get("reference_answer")

    tale_l = data["tale"].lower()
    summary_l = brief["summary"].lower()
    themed_hit = any(
        str(t).lower() in tale_l
        for t in brief.get("themes", [])
        if len(str(t)) > 3
    )
    lexical_hit = any(
        w in tale_l
        for w in summary_l.split()
        if len(w) > 5 and w[:5].isalpha()
    )
    assert themed_hit or lexical_hit or "жил" in tale_l, (
        "сказка должна частично отзываться к новости или стилю сказки"
    )


@pytest.mark.e2e
def test_e2e_wrong_news_id_returns_400() -> None:
    client = TestClient(app)
    r = client.post(
        "/api/generate",
        json={"news_id": "nope", "preset_id": "default"},
    )
    assert r.status_code == 400
