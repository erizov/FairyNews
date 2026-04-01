"""E2E: news → RAG anchor → four-agent tale (HTTP API)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.run_database import load_run


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
def test_e2e_snapshot_stub_pipeline_saves_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Снимок JSON + stub LLM; без Chroma и без OpenAI. Сохраняется отчёт."""
    monkeypatch.setenv("FAIRYNEWS_LLM_UNIFORM_STAGES", "")
    monkeypatch.setenv("FAIRYNEWS_LLM_PER_STAGE", "")
    monkeypatch.delenv("FAIRYNEWS_UNIFORM_BACKEND", raising=False)
    monkeypatch.delenv("FAIRYNEWS_UNIFORM_MODEL", raising=False)
    monkeypatch.delenv("FAIRYNEWS_LLM_BACKEND", raising=False)
    for key in tuple(os.environ.keys()):
        if key.startswith("FAIRYNEWS_STAGE_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("FAIRYNEWS_RAG_BACKEND", "snapshot")
    monkeypatch.setenv("FAIRYNEWS_LLM_MODE", "stub")
    db_path = tmp_path / "runs_e2e.db"
    monkeypatch.setenv("FAIRYNEWS_REPORTS_DB_PATH", str(db_path))
    monkeypatch.setenv("FAIRYNEWS_PERSIST_STUB_REPORTS", "1")

    client = TestClient(app)
    response = client.post(
        "/api/generate",
        json={
            "news_text": "Кузнецы просят справедливой цены за труд.",
            "preset_id": "russian_folk",
            "run_by": "pytest",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data.get("run_id")
    assert "Жил-был" in data.get("tale", "")
    assert data.get("chosen_tale_source")
    assert data.get("rag_chunks_used", 0) >= 1
    assert data.get("qa", {}).get("question")

    saved = load_run(data["run_id"])
    assert saved is not None
    assert saved.get("run_by") == "pytest"
    assert saved.get("news_raw")
    assert saved.get("agent_outputs")
    ap = saved.get("agent_prompts") or {}
    assert ap.get("news", {}).get("system")
    assert ap.get("story", {}).get("user")
    assert saved.get("heuristics")
    assert saved.get("rag", {}).get("top_k")
    assert saved["tale"] == data["tale"]

    lst = client.get("/api/reports/runs")
    assert lst.status_code == 200
    ids = [x["run_id"] for x in lst.json().get("items", [])]
    assert data["run_id"] in ids

    log_r = client.get(f"/api/reports/llm-logs/{data['run_id']}")
    assert log_r.status_code == 200, log_r.text
    log_body = log_r.json()
    assert log_body.get("run_id") == data["run_id"]
    assert len(log_body.get("steps") or []) == 4


@pytest.mark.e2e
def test_pipeline_chroma_with_fixed_mock_llm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Прямой вызов пайплайна с Chroma и фиксированным mock LLM."""
    if not _chromadb_has_chunks():
        pytest.skip("Chroma empty — run: python -m rag --reset")

    from app.agents_pipeline import run_four_agent_pipeline
    class FixedLLM:
        """Три JSON-вызова и один текст; счётчик без глобалов снаружи."""

        def __init__(self) -> None:
            self._json_i = 0

        @property
        def model_label(self) -> str:
            return "mock"

        @property
        def provider_name(self) -> str:
            return "mock"

        def chat_json_object(self, system, user, **kwargs):
            del system, user, kwargs
            self._json_i += 1
            if self._json_i == 1:
                return {
                    "summary": "Кузнецы просят справедливой цены.",
                    "themes": ["труд", "народ"],
                    "retrieval_keywords": "кузнец",
                }
            if self._json_i == 2:
                return {"approved": True, "notes": "ok", "tale": ""}
            return {
                "question": "Кто на площади?",
                "reference_answer": "Ремесленники.",
            }

        def chat_text(self, system, user, **kwargs):
            del system, user, kwargs
            return (
                "Жил-был царь. Собрались кузнецы у терема и речь сказали."
            )

    out = run_four_agent_pipeline(
        "Новость о кузнецах.",
        "русская сказка",
        ("russian",),
        llm=FixedLLM(),
        rag_backend="chroma",
    )
    assert "кузнец" in out["tale"].lower()
    assert out["report"]["rag"]["backend"] == "chroma"


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
        json={
            "news_text": (
                "Ремесленники собрались у терема требовать справедливой цены."
            ),
            "preset_id": "russian_folk",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data.get("tale", "")) > 200
    assert data.get("chosen_tale_source")

    brief = data.get("news_brief") or {}
    assert brief.get("summary")
    assert isinstance(brief.get("themes"), list)

    audit = data.get("audit") or {}
    assert "approved" in audit

    qa = data.get("qa") or {}
    assert qa.get("question")
    assert qa.get("reference_answer")


@pytest.mark.e2e
def test_e2e_wrong_news_id_returns_400() -> None:
    client = TestClient(app)
    r = client.post(
        "/api/generate",
        json={"news_id": "nope", "preset_id": "default"},
    )
    assert r.status_code == 400
