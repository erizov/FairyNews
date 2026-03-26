"""Incremental updates and optional periodic re-ingest for tale RAG."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import yaml

from rag.config import (
    EMBEDDING_MODEL_NAME,
    HTTP_TIMEOUT,
    PIPELINE_STATE_PATH,
    SEEDS_YAML,
)
from rag.embeddings import TaleEmbedder
from rag.gutenberg import fetch_gutenberg_text
from rag.ingest import (
    iter_local_globs_dedup,
    records_from_gutenberg,
    records_from_local_file,
)
from rag.store import add_to_collection, delete_by_source, get_collection

logger = logging.getLogger(__name__)

_STATE_VERSION = 1


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state() -> dict[str, Any]:
    path = PIPELINE_STATE_PATH
    if not path.is_file():
        return {"version": _STATE_VERSION, "sources": {}}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "sources" not in data:
        data["sources"] = {}
    return data


def save_state(data: dict[str, Any]) -> None:
    PIPELINE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    path = PIPELINE_STATE_PATH
    data["version"] = _STATE_VERSION
    data["updated_utc"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_incremental_update() -> dict[str, int]:
    """Re-fetch sources whose SHA-256 changed; embed only those.

    Returns counters: updated_sources, skipped_sources, chunks_added.
    """
    cfg = _load_yaml(SEEDS_YAML)
    state = load_state()
    stored: dict[str, str] = state.get("sources", {})
    collection = get_collection(reset=False)
    embedder = TaleEmbedder(EMBEDDING_MODEL_NAME)

    updated = 0
    skipped = 0
    chunks_added = 0

    for item in cfg.get("gutenberg_epubs", []):
        gid = int(item["id"])
        source_key = f"gutenberg:{gid}"
        try:
            full = fetch_gutenberg_text(gid, HTTP_TIMEOUT)
        except Exception as exc:
            logger.error("Fetch %s failed: %s", source_key, exc)
            continue
        _sk, digest, recs = records_from_gutenberg(item, full)
        if stored.get(source_key) == digest:
            skipped += 1
            continue
        try:
            delete_by_source(collection, source_key)
        except Exception as exc:
            logger.debug("Delete %s: %s", source_key, exc)
        ids_ = [r[0] for r in recs]
        docs = [r[1] for r in recs]
        metas = [r[2] for r in recs]
        if not ids_:
            stored[source_key] = digest
            updated += 1
            continue
        embs = embedder.encode(docs)
        add_to_collection(collection, ids_, docs, embs, metas)
        stored[source_key] = digest
        chunks_added += len(ids_)
        updated += 1
        logger.info("Updated %s (%s chunks)", source_key, len(ids_))

    for rel_path, text, dom, auth, ctry, he, hr, clang in iter_local_globs_dedup(
        cfg.get("local_globs", []),
    ):
        source_key = f"file:{rel_path}"
        _sk, digest, recs = records_from_local_file(
            rel_path,
            text,
            dom,
            author=auth,
            country=ctry,
            heroes_en=he,
            heroes_ru=hr,
            content_lang=clang,
        )
        if stored.get(source_key) == digest:
            skipped += 1
            continue
        try:
            delete_by_source(collection, source_key)
        except Exception as exc:
            logger.debug("Delete %s: %s", source_key, exc)
        ids_ = [r[0] for r in recs]
        docs = [r[1] for r in recs]
        metas = [r[2] for r in recs]
        if not ids_:
            stored[source_key] = digest
            updated += 1
            continue
        embs = embedder.encode(docs)
        add_to_collection(collection, ids_, docs, embs, metas)
        stored[source_key] = digest
        chunks_added += len(ids_)
        updated += 1
        logger.info("Updated %s (%s chunks)", source_key, len(ids_))

    state["sources"] = stored
    save_state(state)
    return {
        "updated_sources": updated,
        "skipped_sources": skipped,
        "chunks_added": chunks_added,
    }


def run_daemon_loop(interval_hours: float) -> None:
    """Sleep between incremental passes (simple periodic pipeline)."""
    seconds = max(300.0, float(interval_hours) * 3600.0)
    logger.info("Daemon loop every %.1f h (%.0f s)", interval_hours, seconds)
    while True:
        stats = run_incremental_update()
        logger.info(
            "Cycle done: updated=%s skipped=%s chunks_added=%s",
            stats["updated_sources"],
            stats["skipped_sources"],
            stats["chunks_added"],
        )
        time.sleep(seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(
        description="Periodic / incremental fairy-tale RAG pipeline.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("update", help="Incremental ingest (hash per source).")

    pd = sub.add_parser(
        "daemon",
        help="Run incremental update every N hours (simple sleep loop).",
    )
    pd.add_argument(
        "--interval-hours",
        type=float,
        default=24.0,
        help="Hours between runs (default: 24).",
    )

    args = p.parse_args()
    if args.cmd == "update":
        stats = run_incremental_update()
        print(json.dumps(stats, indent=2))
    elif args.cmd == "daemon":
        run_daemon_loop(args.interval_hours)


if __name__ == "__main__":
    main()
