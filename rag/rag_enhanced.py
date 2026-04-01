"""Гибридный RAG: dense + BM25 (RRF), итеративное уточнение, сжатие чанков."""

from __future__ import annotations

import logging
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from rag.config import EMBEDDING_MODEL_NAME
from rag.embeddings import TaleEmbedder
from rag.retrieve import retrieve_plot_records
from rag.snapshot_retrieve import (
    DEFAULT_SNAPSHOT_PATH,
    load_snapshot,
)
from rag.store import get_collection

logger = logging.getLogger(__name__)

_K1 = 1.5
_B = 0.75
_EPS = 1e-9


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def rag_legacy_mode() -> bool:
    """Полностью старый путь (только dense, один проход, без сжатия)."""
    return _env_flag("FAIRYNEWS_RAG_LEGACY", False)


def rag_iterative_enabled() -> bool:
    return _env_flag("FAIRYNEWS_RAG_ITERATIVE", True)


def chunk_max_chars() -> int:
    raw = os.environ.get("FAIRYNEWS_RAG_CHUNK_MAX_CHARS", "").strip()
    try:
        n = int(raw)
    except ValueError:
        return 900
    return max(200, min(n, 4000))


def chroma_pool_cap() -> int:
    raw = os.environ.get("FAIRYNEWS_RAG_CHROMA_POOL", "").strip()
    try:
        n = int(raw)
    except ValueError:
        return 120
    return max(24, min(n, 400))


def rrf_k() -> int:
    """Параметр k в RRF: 1/(k+rank); выше — мягче сглаживание."""
    raw = os.environ.get("FAIRYNEWS_RAG_RRF_K", "").strip()
    try:
        n = int(raw)
    except ValueError:
        return 60
    return max(10, min(n, 200))


def _tokenize(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[\wёЁ]+", text.lower())
        if len(t) > 1
    ]


class _BM25:
    """Okapi BM25 по корпусу токенов (без внешних зависимостей)."""

    def __init__(self, tokenized: list[list[str]]) -> None:
        self._docs = tokenized
        self._n = len(tokenized)
        dl_sum = sum(len(d) for d in tokenized)
        self._avgdl = dl_sum / max(self._n, 1)
        self._df = Counter()
        for doc in tokenized:
            for w in set(doc):
                self._df[w] += 1

    def scores(self, query_tokens: list[str]) -> list[float]:
        out = [0.0] * self._n
        if self._n == 0:
            return out
        for i, doc in enumerate(self._docs):
            dl = len(doc)
            tf = Counter(doc)
            s = 0.0
            for w in query_tokens:
                if w not in tf:
                    continue
                df_w = self._df.get(w, 0)
                idf = math.log(
                    (self._n - df_w + 0.5) / (df_w + 0.5) + 1.0,
                )
                f = tf[w]
                denom = f + _K1 * (1 - _B + _B * dl / (self._avgdl + _EPS))
                s += idf * (f * (_K1 + 1)) / (denom + _EPS)
            out[i] = s
        return out


def _rrf_sort_orders(
    order_lists: list[list[int]],
    k_rrf: int | None = None,
) -> list[int]:
    """order_lists: списки индексов от лучшего к худшему."""
    kk = k_rrf if k_rrf is not None else rrf_k()
    scores: dict[int, float] = defaultdict(float)
    for ordering in order_lists:
        for pos, idx in enumerate(ordering):
            scores[idx] += 1.0 / (kk + pos + 1)
    return sorted(scores.keys(), key=lambda i: scores[i], reverse=True)


def _record_key(doc: str, meta: dict[str, Any]) -> str:
    src = str(meta.get("source", ""))
    return f"{src}|{doc[:96]}"


def _dist_for_fused_rank(rank: int) -> float:
    """Монотонная «дистанция»: лучший ранг → меньшее значение."""
    return float(rank) * 0.01


def _merge_chroma_iterative_rows(
    rows1: list[tuple[str, dict[str, Any], float]],
    rows2: list[tuple[str, dict[str, Any], float]],
    *,
    k: int,
) -> list[tuple[str, dict[str, Any], float]]:
    """Слияние двух проходов: RRF по позициям, лучший dist на ключ."""
    kk = rrf_k()
    ranks1 = {_record_key(r[0], r[1]): i for i, r in enumerate(rows1)}
    ranks2 = {_record_key(r[0], r[1]): i for i, r in enumerate(rows2)}
    best: dict[str, tuple[str, dict[str, Any], float]] = {}
    for row in rows1 + rows2:
        key = _record_key(row[0], row[1])
        if key not in best or row[2] < best[key][2]:
            best[key] = row
    scores: dict[str, float] = {}
    for key in set(ranks1) | set(ranks2):
        s = 0.0
        if key in ranks1:
            s += 1.0 / (kk + ranks1[key] + 1)
        if key in ranks2:
            s += 1.0 / (kk + ranks2[key] + 1)
        scores[key] = s
    ordered = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    out: list[tuple[str, dict[str, Any], float]] = []
    for pos, key in enumerate(ordered[:k]):
        d, meta, _ = best[key]
        out.append((d, meta, _dist_for_fused_rank(pos)))
    return out


def compress_chunk_for_prompt(
    text: str,
    focus_phrases: Sequence[str],
    max_chars: int,
) -> str:
    """Выжимка: сначала релевантные предложения в порядке текста, затем остальные.

    Так сохраняется читаемость (без перемешивания абзаца по «весу»).
    """
    t = (text or "").strip()
    if not t or len(t) <= max_chars:
        return t
    terms = set()
    for ph in focus_phrases:
        for part in re.split(r"[\s,;]+", ph.lower()):
            if len(part) > 2:
                terms.add(part)
    if not terms:
        return t[: max_chars - 1].rstrip() + "…"
    parts = re.split(r"(?<=[.!?])\s+", t)
    indexed: list[tuple[int, int, str]] = []
    for i, p in enumerate(parts):
        p = p.strip()
        if not p:
            continue
        low = p.lower()
        sc = sum(1 for term in terms if term in low)
        indexed.append((i, sc, p))
    if not indexed:
        return t[: max_chars - 1].rstrip() + "…"
    pos_hits = [(i, sc, s) for i, sc, s in indexed if sc > 0]
    pos_rest = [(i, sc, s) for i, sc, s in indexed if sc == 0]
    pos_hits.sort(key=lambda x: x[0])
    pos_rest.sort(key=lambda x: x[0])
    ordered = pos_hits + pos_rest
    out_parts: list[str] = []
    total = 0
    for _i, _sc, sent in ordered:
        if total + len(sent) + 1 > max_chars:
            break
        out_parts.append(sent)
        total += len(sent) + 1
    if not out_parts:
        return t[: max_chars - 1].rstrip() + "…"
    return " ".join(out_parts)


def _apply_compression_to_records(
    records: list[tuple[str, dict[str, Any], float]],
    focus: Sequence[str],
    max_chars: int,
) -> list[tuple[str, dict[str, Any], float]]:
    out: list[tuple[str, dict[str, Any], float]] = []
    for doc, meta, dist in records:
        compressed = compress_chunk_for_prompt(doc, focus, max_chars)
        out.append((compressed, meta, dist))
    return out


def _hybrid_snapshot_indices(
    texts: list[str],
    q_vec: np.ndarray,
    doc_matrix: np.ndarray,
    query_text: str,
) -> list[int]:
    dists = np.linalg.norm(doc_matrix - q_vec, axis=1)
    dense_order = np.argsort(dists).tolist()
    tokenized = [_tokenize(tx) for tx in texts]
    bm = _BM25(tokenized)
    q_tok = _tokenize(query_text)
    bm_scores = np.asarray(bm.scores(q_tok), dtype=np.float64)
    bm25_order = np.argsort(-bm_scores).tolist()
    return _rrf_sort_orders([dense_order, bm25_order])


def retrieve_snapshot_enhanced(
    base_query: str,
    *,
    k: int,
    domains: Sequence[str] | None,
    snapshot_path: Path | None,
    focus_phrases: Sequence[str],
    iterative: bool,
) -> tuple[list[tuple[str, dict[str, Any], float]], dict[str, Any]]:
    """Snapshot: один encode документов, гибрид + опционально 2-й проход RRF."""
    path = snapshot_path or DEFAULT_SNAPSHOT_PATH
    items = load_snapshot(path)
    if domains:
        dom = set(domains)
        items = [it for it in items if str(it["metadata"].get("domain", "")) in dom]
    meta_trace: dict[str, Any] = {
        "mode": "snapshot_enhanced",
        "hybrid_bm25_rrf": True,
        "iterative": iterative,
        "snapshot_path": str(path),
        "chunk_compression": "ordered_relevance",
        "rrf_k": rrf_k(),
    }
    if not items:
        return [], meta_trace

    texts = [it["text"] for it in items]
    metas = [it["metadata"] for it in items]
    embedder = TaleEmbedder(EMBEDDING_MODEL_NAME)
    doc_matrix = np.asarray(embedder.encode(texts), dtype=np.float64)
    q1 = np.asarray(embedder.encode([base_query])[0], dtype=np.float64)

    order1 = _hybrid_snapshot_indices(texts, q1, doc_matrix, base_query)
    if not iterative:
        picked = order1[:k]
        raw_recs = [
            (texts[i], metas[i], _dist_for_fused_rank(r))
            for r, i in enumerate(picked)
        ]
        meta_trace["iterative_rounds"] = 1
        comp = _apply_compression_to_records(
            raw_recs,
            focus_phrases,
            chunk_max_chars(),
        )
        return comp, meta_trace

    snippets: list[str] = []
    for idx in order1[:3]:
        snippets.append(texts[int(idx)][:220].replace("\n", " "))
    refined = base_query + "\n" + " … ".join(snippets)
    q2 = np.asarray(embedder.encode([refined])[0], dtype=np.float64)
    order2 = _hybrid_snapshot_indices(texts, q2, doc_matrix, refined)
    fused = _rrf_sort_orders([order1, order2])[:k]
    raw_recs = [
        (texts[i], metas[i], _dist_for_fused_rank(r))
        for r, i in enumerate(fused)
    ]
    meta_trace["iterative_rounds"] = 2
    meta_trace["iterative_merge"] = "rrf_orders"
    meta_trace["refined_query_prefix_len"] = min(len(refined), 400)
    comp = _apply_compression_to_records(
        raw_recs,
        focus_phrases,
        chunk_max_chars(),
    )
    return comp, meta_trace


def retrieve_chroma_enhanced(
    base_query: str,
    *,
    k: int,
    domains: Sequence[str] | None,
    focus_phrases: Sequence[str],
    iterative: bool,
) -> tuple[list[tuple[str, dict[str, Any], float]], dict[str, Any]]:
    """Chroma: широкий пул + BM25/RRF на пуле; итерация — второй запрос и слияние."""
    pool = max(k * 4, 24)
    pool = min(pool, chroma_pool_cap())
    meta_trace: dict[str, Any] = {
        "mode": "chroma_enhanced",
        "hybrid_bm25_rrf": True,
        "iterative": iterative,
        "pool": pool,
        "chunk_compression": "ordered_relevance",
        "rrf_k": rrf_k(),
    }
    collection = get_collection(reset=False)
    embedder = TaleEmbedder(EMBEDDING_MODEL_NAME)
    q1 = embedder.encode([base_query])[0]
    kwargs: dict[str, Any] = {
        "query_embeddings": [q1],
        "n_results": pool,
        "include": ["documents", "metadatas", "distances"],
    }
    if domains:
        kwargs["where"] = {"domain": {"$in": list(domains)}}
    raw = collection.query(**kwargs)
    docs_l = (raw.get("documents") or [[]])[0]
    metas_l = (raw.get("metadatas") or [[]])[0]
    dists_l = (raw.get("distances") or [[]])[0]
    if not docs_l:
        return [], meta_trace
    n = len(docs_l)
    dists = np.asarray([float(d or 0.0) for d in dists_l], dtype=np.float64)
    dense_order = np.argsort(dists).tolist()
    tokenized = [_tokenize(str(d or "")) for d in docs_l]
    bm = _BM25(tokenized)
    q_tok = _tokenize(base_query)
    bm_scores = np.asarray(bm.scores(q_tok), dtype=np.float64)
    bm25_order = np.argsort(-bm_scores).tolist()
    fused_local = _rrf_sort_orders([dense_order, bm25_order])

    def _rows_from_fused(fused_idx: list[int]) -> list[tuple[str, dict[str, Any], float]]:
        rows: list[tuple[str, dict[str, Any], float]] = []
        for r, li in enumerate(fused_idx[:k]):
            i = int(li)
            rows.append(
                (
                    str(docs_l[i] or ""),
                    dict(metas_l[i] or {}),
                    _dist_for_fused_rank(r),
                ),
            )
        return rows

    rows1 = _rows_from_fused(fused_local)
    if not iterative:
        meta_trace["iterative_rounds"] = 1
        return (
            _apply_compression_to_records(
                rows1,
                focus_phrases,
                chunk_max_chars(),
            ),
            meta_trace,
        )

    snips = [
        str(docs_l[i])[:200].replace("\n", " ")
        for i in fused_local[:3]
    ]
    q2_text = base_query + "\n" + " … ".join(snips)
    q2 = embedder.encode([q2_text])[0]
    kwargs2 = {**kwargs, "query_embeddings": [q2]}
    raw2 = collection.query(**kwargs2)
    d2 = (raw2.get("documents") or [[]])[0]
    m2 = (raw2.get("metadatas") or [[]])[0]
    dist2 = np.asarray(
        [float(x or 0.0) for x in (raw2.get("distances") or [[]])[0]],
        dtype=np.float64,
    )
    if not d2:
        meta_trace["iterative_rounds"] = 2
        return (
            _apply_compression_to_records(
                rows1,
                focus_phrases,
                chunk_max_chars(),
            ),
            meta_trace,
        )
    ord2_d = np.argsort(dist2).tolist()
    tok2 = [_tokenize(str(x or "")) for x in d2]
    bm_b = _BM25(tok2)
    b_sc = np.asarray(bm_b.scores(_tokenize(q2_text)), dtype=np.float64)
    ord2_b = np.argsort(-b_sc).tolist()
    fused2 = _rrf_sort_orders([ord2_d, ord2_b])
    rows2 = []
    for r, li in enumerate(fused2[:k]):
        j = int(li)
        rows2.append(
            (str(d2[j] or ""), dict(m2[j] or {}), _dist_for_fused_rank(r)),
        )

    final = _merge_chroma_iterative_rows(rows1, rows2, k=k)
    meta_trace["iterative_rounds"] = 2
    meta_trace["iterative_merge"] = "rrf_ranks"
    return (
        _apply_compression_to_records(
            final,
            focus_phrases,
            chunk_max_chars(),
        ),
        meta_trace,
    )


def run_retrieval(
    rag_query: str,
    *,
    k: int,
    backend: str,
    domains: Sequence[str] | None,
    snapshot_path: Path | None,
    focus_phrases: Sequence[str],
) -> tuple[list[tuple[str, dict[str, Any], float]], dict[str, Any]]:
    """Единая точка входа: legacy или enhanced."""
    if rag_legacy_mode():
        logger.info("RAG legacy mode (dense only)")
        if backend == "snapshot":
            from rag.snapshot_retrieve import retrieve_plot_records_from_snapshot

            rec = retrieve_plot_records_from_snapshot(
                rag_query,
                k=k,
                domains=domains,
                snapshot_path=snapshot_path,
            )
            return rec, {"mode": "legacy_snapshot", "hybrid": False}
        rec = retrieve_plot_records(rag_query, k=k, domains=domains)
        return rec, {"mode": "legacy_chroma", "hybrid": False}

    it = rag_iterative_enabled()
    if backend == "snapshot":
        return retrieve_snapshot_enhanced(
            rag_query,
            k=k,
            domains=domains,
            snapshot_path=snapshot_path,
            focus_phrases=focus_phrases,
            iterative=it,
        )
    return retrieve_chroma_enhanced(
        rag_query,
        k=k,
        domains=domains,
        focus_phrases=focus_phrases,
        iterative=it,
    )
