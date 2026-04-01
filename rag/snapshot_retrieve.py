"""RAG retrieval from a checked-in JSON snapshot (no Chroma)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from rag.config import EMBEDDING_MODEL_NAME, ROOT
from rag.embeddings import TaleEmbedder

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_PATH = ROOT / "data" / "notebook_rag_snapshot.json"


def load_snapshot(path: Path | None = None) -> list[dict[str, Any]]:
    """Return list of {text, metadata} from snapshot file."""
    p = path or DEFAULT_SNAPSHOT_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    chunks = raw.get("chunks")
    if not isinstance(chunks, list):
        return []
    out: list[dict[str, Any]] = []
    for item in chunks:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        meta = item.get("metadata")
        if not text:
            continue
        out.append({"text": text, "metadata": dict(meta) if meta else {}})
    return out


def retrieve_plot_records_from_snapshot(
    query: str,
    *,
    k: int = 15,
    domains: Sequence[str] | None = None,
    snapshot_path: Path | None = None,
) -> list[tuple[str, dict[str, Any], float]]:
    """Same shape as ``rag.retrieve.retrieve_plot_records`` (L2 on embeddings)."""
    items = load_snapshot(snapshot_path)
    if domains:
        dom = set(domains)
        items = [
            it
            for it in items
            if str(it["metadata"].get("domain", "")) in dom
        ]
    if not items:
        logger.warning("Snapshot empty after filter")
        return []

    texts = [it["text"] for it in items]
    metas = [it["metadata"] for it in items]
    embedder = TaleEmbedder(EMBEDDING_MODEL_NAME)
    vectors = np.asarray(embedder.encode([query] + texts), dtype=np.float64)
    qv = vectors[0]
    doc_matrix = vectors[1:]
    dists = np.linalg.norm(doc_matrix - qv, axis=1)
    order = np.argsort(dists)[:k]

    out: list[tuple[str, dict[str, Any], float]] = []
    for idx in order:
        i = int(idx)
        out.append((texts[i], metas[i], float(dists[i])))
    return out
