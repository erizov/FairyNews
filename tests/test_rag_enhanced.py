"""Unit tests for hybrid / iterative RAG helpers."""

from __future__ import annotations

import pytest

from rag.rag_enhanced import (
    compress_chunk_for_prompt,
    rag_legacy_mode,
    run_retrieval,
)
from rag.rag_enhanced import _rrf_sort_orders


def test_rrf_sort_orders_merges_rankings() -> None:
    fused = _rrf_sort_orders(
        [
            [0, 2, 1],
            [1, 0, 2],
        ],
    )
    assert set(fused) == {0, 1, 2}
    assert fused[0] in (0, 1)


def test_compress_prefers_sentences_with_focus_terms() -> None:
    text = (
        "В лесу тихо. Царь выехал на поляну. Собака спит на крыльце."
    )
    out = compress_chunk_for_prompt(text, ["царь", "поляна"], max_chars=80)
    assert "царь" in out.lower()
    assert len(out) <= 80


def test_run_retrieval_legacy_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAIRYNEWS_RAG_LEGACY", "1")
    monkeypatch.setenv("FAIRYNEWS_RAG_BACKEND", "snapshot")
    rec, meta = run_retrieval(
        "русская сказка царь",
        k=5,
        backend="snapshot",
        domains=("russian",),
        snapshot_path=None,
        focus_phrases=(),
    )
    assert meta.get("mode") == "legacy_snapshot"
    assert meta.get("hybrid") is False
    assert len(rec) >= 1
    assert rag_legacy_mode() is True


def test_run_retrieval_enhanced_snapshot_smoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FAIRYNEWS_RAG_LEGACY", raising=False)
    monkeypatch.setenv("FAIRYNEWS_RAG_ITERATIVE", "0")
    rec, meta = run_retrieval(
        "царь справедливость народ",
        k=4,
        backend="snapshot",
        domains=("russian",),
        snapshot_path=None,
        focus_phrases=("царь", "народ"),
    )
    assert meta.get("hybrid_bm25_rrf") is True
    assert meta.get("iterative_rounds") == 1
    assert 1 <= len(rec) <= 4
    for doc, _m, dist in rec:
        assert isinstance(doc, str)
        assert dist >= 0
