"""Paths and hyperparameters for fairy-tale RAG."""

from pathlib import Path

# Project root: parent of ``rag/`` package directory.
ROOT = Path(__file__).resolve().parent.parent

CHROMA_PATH = ROOT / "data" / "chroma_fairy_tales"
COLLECTION_NAME = "fairy_tales_plots"

SEEDS_YAML = Path(__file__).resolve().parent / "sources" / "fairy_tale_seeds.yaml"

# Chunking tuned for plot retrieval (Russian + multilingual).
CHUNK_TARGET_CHARS = 900
CHUNK_OVERLAP_CHARS = 120

# sentence-transformers model (multilingual for Russian + European/Others in EN).
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# HTTP timeout for Gutenberg mirror fetches (seconds).
HTTP_TIMEOUT = 60.0

# Incremental pipeline: last-known hashes per source.
PIPELINE_STATE_PATH = ROOT / "data" / "rag_pipeline_state.json"
