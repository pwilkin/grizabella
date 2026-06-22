"""Cross-encoder reranker support for semantic search.

Loads sentence-transformers CrossEncoder models lazily with a process-wide
cache and exposes :func:`rerank` to re-score ``(query, doc)`` pairs after
an initial vector retrieval step.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from grizabella.core.exceptions import EmbeddingError

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[tuple[str, str], Any] = {}
_CACHE_LOCK = threading.Lock()


def get_reranker(model_name: str, use_gpu: bool = False) -> Any:
    """Load (and cache) a CrossEncoder for ``model_name``.

    The cache is keyed on ``(model_name, device)`` so CPU and CUDA variants
    of the same model coexist. ``sentence_transformers`` is imported lazily
    so environments without the extra still work for non-rerank paths.
    """
    device = "cuda" if use_gpu else "cpu"
    key = (model_name, device)
    with _CACHE_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            msg = (
                "sentence-transformers is required for reranker support "
                f"but could not be imported: {exc}"
            )
            raise EmbeddingError(msg) from exc
        try:
            model = CrossEncoder(model_name, device=device, trust_remote_code=True)
        except TypeError:
            model = CrossEncoder(model_name, device=device)
        except Exception as exc:  # pylint: disable=W0718
            msg = f"Failed to load reranker model '{model_name}': {exc}"
            raise EmbeddingError(msg) from exc
        _MODEL_CACHE[key] = model
        logger.info("Reranker model '%s' loaded on device '%s'.", model_name, device)
        return model


def rerank(
    model: Any,
    query_text: str,
    candidate_texts: list[str],
) -> list[float]:
    """Score ``(query_text, candidate_text)`` pairs with the given CrossEncoder.

    Returns a list of floats of the same length as ``candidate_texts``. Higher
    is more relevant. Missing or empty candidate texts receive ``-inf`` so
    they sink to the bottom of the ranking instead of crashing the model.
    """
    if not candidate_texts:
        return []
    pairs: list[tuple[str, str]] = []
    indices: list[int] = []
    scores: list[float] = [float("-inf")] * len(candidate_texts)
    for idx, text in enumerate(candidate_texts):
        if text is None or not str(text).strip():
            continue
        pairs.append((query_text, str(text)))
        indices.append(idx)
    if not pairs:
        return scores
    try:
        raw_scores = model.predict(pairs)
    except Exception as exc:  # pylint: disable=W0718
        msg = f"Reranker scoring failed: {exc}"
        raise EmbeddingError(msg) from exc
    for idx, score in zip(indices, raw_scores):
        scores[idx] = float(score)
    return scores


def clear_cache() -> None:
    """Drop all cached reranker models. Intended for tests."""
    with _CACHE_LOCK:
        _MODEL_CACHE.clear()


def resolve_reranker_config(
    embedding_definition_reranker: Optional[str],
    embedding_definition_multiplier: int,
    rerank: Optional[bool],
    rerank_model: Optional[str],
    rerank_candidates: Optional[int],
    limit: int,
) -> tuple[bool, Optional[str], int]:
    """Merge per-call rerank options with the EmbeddingDefinition defaults.

    Returns ``(enabled, model_name, candidate_count)``. ``enabled`` is False
    if no model is available or the caller explicitly disabled reranking.
    """
    effective_model = rerank_model or embedding_definition_reranker
    if rerank is False:
        enabled = False
    elif rerank is True:
        enabled = effective_model is not None
    else:
        enabled = effective_model is not None
    multiplier = max(1, embedding_definition_multiplier)
    candidates = rerank_candidates if rerank_candidates is not None else limit * multiplier
    candidates = max(candidates, limit)
    return enabled, effective_model, candidates
