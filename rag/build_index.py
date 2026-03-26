"""Build Chroma index from Gutenberg seeds and optional local .txt tales."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import yaml

from rag.config import (
    EMBEDDING_MODEL_NAME,
    HTTP_TIMEOUT,
    SEEDS_YAML,
)
from rag.embeddings import TaleEmbedder
from rag.gutenberg import fetch_gutenberg_text
from rag.ingest import (
    iter_local_globs_dedup,
    records_from_gutenberg,
    records_from_local_file,
)
from rag.store import add_to_collection, get_collection

logger = logging.getLogger(__name__)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build(*, reset: bool) -> int:
    """Fetch, chunk, embed, and persist. Returns total chunk count."""
    cfg = _load_yaml(SEEDS_YAML)
    collection = get_collection(reset=reset)
    embedder = TaleEmbedder(EMBEDDING_MODEL_NAME)

    id_docs_meta: list[tuple[str, str, dict[str, Any]]] = []

    for item in cfg.get("gutenberg_epubs", []):
        gid = int(item["id"])
        try:
            full = fetch_gutenberg_text(gid, HTTP_TIMEOUT)
        except Exception as exc:
            logger.error("Gutenberg %s failed: %s", gid, exc)
            continue
        _, _digest, recs = records_from_gutenberg(item, full)
        id_docs_meta.extend(recs)

    for rel_path, text, dom, auth, ctry, he, hr, clang in iter_local_globs_dedup(
        cfg.get("local_globs", []),
    ):
        _, _digest, recs = records_from_local_file(
            rel_path,
            text,
            dom,
            author=auth,
            country=ctry,
            heroes_en=he,
            heroes_ru=hr,
            content_lang=clang,
        )
        id_docs_meta.extend(recs)

    if not id_docs_meta:
        logger.warning("No chunks produced — check seeds and network.")
        return 0

    ids_ = [t[0] for t in id_docs_meta]
    docs = [t[1] for t in id_docs_meta]
    metas = [t[2] for t in id_docs_meta]
    logger.info("Embedding %s chunks...", len(docs))
    embs = embedder.encode(docs)
    add_to_collection(collection, ids_, docs, embs, metas)
    logger.info("Indexed %s chunks into %s", len(ids_), collection.name)
    return len(ids_)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Build fairy-tale RAG (no news).")
    p.add_argument(
        "--reset",
        action="store_true",
        help="Wipe Chroma collection before indexing.",
    )
    args = p.parse_args()
    n = build(reset=args.reset)
    print(f"Done. Total chunks: {n}")


if __name__ == "__main__":
    main()
