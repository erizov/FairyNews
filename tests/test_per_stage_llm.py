"""Режим TEST 1: разные модели на этапах пайплайна."""

from __future__ import annotations

import os

import pytest

from app.llm_providers import build_llm_from_backend, resolve_pipeline_llm_providers


def _clear_fairynews_stage_env_from_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Убрать режимы LLM из .env: uniform, per-stage, принудительный backend."""
    monkeypatch.setenv("FAIRYNEWS_LLM_UNIFORM_STAGES", "")
    monkeypatch.setenv("FAIRYNEWS_LLM_PER_STAGE", "")
    monkeypatch.delenv("FAIRYNEWS_UNIFORM_BACKEND", raising=False)
    monkeypatch.delenv("FAIRYNEWS_UNIFORM_MODEL", raising=False)
    monkeypatch.delenv("FAIRYNEWS_LLM_BACKEND", raising=False)
    for key in tuple(os.environ.keys()):
        if key.startswith("FAIRYNEWS_STAGE_"):
            monkeypatch.delenv(key, raising=False)


def test_resolve_per_stage_reuses_one_stub_for_empty_backends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_fairynews_stage_env_from_dotenv(monkeypatch)
    monkeypatch.setenv("FAIRYNEWS_LLM_PER_STAGE", "1")
    monkeypatch.delenv("FAIRYNEWS_STAGE_NEWS_BACKEND", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GIGACHAT_API_KEY", raising=False)
    monkeypatch.setenv("FAIRYNEWS_LLM_MODE", "")
    on, stages = resolve_pipeline_llm_providers(llm=None)
    assert on is True
    p0 = stages["news"]
    assert p0 is stages["story"]
    assert p0 is stages["audit"]
    assert p0 is stages["qa"]


def test_resolve_per_stage_news_and_story_differ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_fairynews_stage_env_from_dotenv(monkeypatch)
    monkeypatch.setenv("FAIRYNEWS_LLM_PER_STAGE", "true")
    monkeypatch.setenv("FAIRYNEWS_STAGE_NEWS_BACKEND", "groq")
    monkeypatch.setenv("FAIRYNEWS_STAGE_NEWS_MODEL", "llama-4-maverick")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("FAIRYNEWS_STAGE_STORY_BACKEND", "openai")
    monkeypatch.setenv("FAIRYNEWS_STAGE_STORY_MODEL", "gpt-5.4-nano")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("GIGACHAT_API_KEY", raising=False)
    on, stages = resolve_pipeline_llm_providers(llm=None)
    assert on is True
    assert stages["news"].model_label == "llama-4-maverick"
    assert stages["story"].model_label == "gpt-5.4-nano"
    assert stages["news"] is not stages["story"]


def test_build_llm_deepseek_custom_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    p = build_llm_from_backend("deepseek", model="deepseek-v3.2")
    assert p.model_label == "deepseek-v3.2"


def test_build_llm_gigachat_pro_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIGACHAT_API_KEY", "x")
    p = build_llm_from_backend("gigachat", model="GigaChat2-Pro")
    assert p.model_label == "GigaChat2-Pro"


def test_uniform_stages_one_provider_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAIRYNEWS_LLM_UNIFORM_STAGES", "1")
    monkeypatch.setenv("FAIRYNEWS_UNIFORM_BACKEND", "openai")
    monkeypatch.setenv("FAIRYNEWS_UNIFORM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk")
    monkeypatch.delenv("GIGACHAT_API_KEY", raising=False)
    on, stages = resolve_pipeline_llm_providers(llm=None)
    assert on is True
    assert stages["news"] is stages["story"]
    assert stages["story"] is stages["qa"]


def test_report_includes_timing_stub_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_fairynews_stage_env_from_dotenv(monkeypatch)
    monkeypatch.setenv("FAIRYNEWS_LLM_MODE", "stub")
    monkeypatch.setenv("FAIRYNEWS_RAG_BACKEND", "snapshot")
    from app.agents_pipeline import run_four_agent_pipeline

    out = run_four_agent_pipeline(
        "В деревне осенью починили мост.",
        "русская сказка",
        ("russian",),
        rag_backend="snapshot",
        preset_id="russian_folk",
    )
    timing = out["report"].get("timing") or {}
    assert "pipeline_wall_sec" in timing
    assert "llm_total_sec" in timing
    assert timing["llm_total_sec"] >= 0
    rep = out["report"]
    assert "news_raw" in rep
    assert "agent_outputs" in rep
    assert "news_json" in rep["agent_outputs"]
