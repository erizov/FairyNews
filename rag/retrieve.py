"""Retrieve tale-plot context for the story-generation agent."""

from __future__ import annotations

import logging
from typing import Sequence

from rag.config import EMBEDDING_MODEL_NAME
from rag.embeddings import TaleEmbedder
from rag.store import get_collection

logger = logging.getLogger(__name__)

_DEFAULT_K = 8


def retrieve_plot_context(
    query: str,
    *,
    k: int = _DEFAULT_K,
    domains: Sequence[str] | None = None,
) -> str:
    """Return a single string of retrieved passages for prompting.

    *domains*: optional filter, e.g. ``("russian", "european")``.
    Political news are **not** in this store.
    """
    collection = get_collection(reset=False)
    embedder = TaleEmbedder(EMBEDDING_MODEL_NAME)
    qvec = embedder.encode([query])[0]
    kwargs = {
        "query_embeddings": [qvec],
        "n_results": k,
        "include": ["documents", "metadatas", "distances"],
    }
    if domains:
        where: dict = {"domain": {"$in": list(domains)}}
        kwargs["where"] = where
    raw = collection.query(**kwargs)
    docs = raw.get("documents") or [[]]
    metas = raw.get("metadatas") or [[]]
    blocks: list[str] = []
    for doc, meta in zip(docs[0], metas[0]):
        header_parts = [
            str(meta.get("domain", "")),
            str(meta.get("source", "")),
            str(meta.get("content_lang", "")),
            str(meta.get("work_note", "")),
        ]
        header = " | ".join(p for p in header_parts if p)
        blocks.append(f"[{header}]\n{doc}")
    out = "\n\n---\n\n".join(blocks)
    logger.debug("Retrieved %s chunks", len(blocks))
    return out
