"""Sentence-transformers wrapper for multilingual embeddings."""

from __future__ import annotations

import logging
from typing import Sequence

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_BATCH = 32


class TaleEmbedder:
    """Lazy-loaded embedding model."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _ensure_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embeddings for *texts* (L2-normalized by ST by default)."""
        model = self._ensure_model()
        out: list[list[float]] = []
        batch: list[str] = []
        for t in texts:
            batch.append(t)
            if len(batch) >= _BATCH:
                vec = model.encode(
                    list(batch),
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )
                out.extend(vec.tolist())
                batch.clear()
        if batch:
            vec = model.encode(
                list(batch),
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            out.extend(vec.tolist())
        return out
