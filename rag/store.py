"""ChromaDB persistence for fairy-tale chunks."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

import chromadb

from rag.config import CHROMA_PATH, COLLECTION_NAME

logger = logging.getLogger(__name__)

# Chroma Rust API caps add batch size (e.g. 5461); stay safely below.
_CHROMA_ADD_BATCH = 4000


def get_collection(*, reset: bool = False):
    """Return the fairy-tale Chroma collection."""
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info("Deleted collection %s", COLLECTION_NAME)
        except Exception:
            pass
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Fairy tale plots — no news"},
    )


def add_to_collection(
    collection,
    ids: Sequence[str],
    documents: Sequence[str],
    embeddings: Sequence[Sequence[float]],
    metadatas: Sequence[Mapping[str, Any]],
) -> None:
    """Add precomputed embeddings (split into Chroma-sized batches)."""
    ids_l = list(ids)
    docs_l = list(documents)
    embs_l = [list(map(float, e)) for e in embeddings]
    metas_l = [dict(m) for m in metadatas]
    n = len(ids_l)
    for start in range(0, n, _CHROMA_ADD_BATCH):
        end = start + _CHROMA_ADD_BATCH
        collection.add(
            ids=ids_l[start:end],
            documents=docs_l[start:end],
            embeddings=embs_l[start:end],
            metadatas=metas_l[start:end],
        )


def delete_by_source(collection, source_key: str) -> None:
    """Remove all chunks whose metadata ``source`` equals *source_key*."""
    collection.delete(where={"source": source_key})
    logger.info("Deleted chunks for source %s", source_key)
