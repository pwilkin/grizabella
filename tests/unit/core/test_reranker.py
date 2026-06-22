"""Unit tests for the reranker helper module.

These tests avoid loading real cross-encoder models — they either mock the
underlying CrossEncoder class or exercise configuration logic only.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from grizabella.core import reranker
from grizabella.core.exceptions import EmbeddingError


@pytest.fixture(autouse=True)
def _clear_reranker_cache():
    reranker.clear_cache()
    yield
    reranker.clear_cache()


class _FakeCrossEncoder:
    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.device = kwargs.get("device")
        self.predict_calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs):
        self.predict_calls.append(list(pairs))
        # Higher score = later doc in the list (lexicographic by document)
        return [float(len(doc)) for _, doc in pairs]


def _install_fake_cross_encoder(monkeypatch):
    fake_module = MagicMock()
    fake_module.CrossEncoder = _FakeCrossEncoder
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", fake_module)


def test_get_reranker_caches_by_model_and_device(monkeypatch):
    _install_fake_cross_encoder(monkeypatch)

    first = reranker.get_reranker("m1", use_gpu=False)
    second = reranker.get_reranker("m1", use_gpu=False)
    assert first is second, "same (model, device) must hit cache"

    gpu_model = reranker.get_reranker("m1", use_gpu=True)
    assert gpu_model is not first, "different device must not share cache entry"
    assert gpu_model.device == "cuda"
    assert first.device == "cpu"


def test_rerank_skips_empty_and_none_texts(monkeypatch):
    _install_fake_cross_encoder(monkeypatch)
    model = reranker.get_reranker("m1")

    scores = reranker.rerank(
        model,
        query_text="q",
        candidate_texts=["alpha", None, "", "bravo longer"],
    )
    assert len(scores) == 4
    assert scores[0] == float(len("alpha"))
    assert scores[1] == float("-inf")
    assert scores[2] == float("-inf")
    assert scores[3] == float(len("bravo longer"))
    # CrossEncoder.predict should only see non-empty pairs
    assert len(model.predict_calls) == 1
    assert [doc for _, doc in model.predict_calls[0]] == ["alpha", "bravo longer"]


def test_rerank_with_no_candidates_returns_empty():
    assert reranker.rerank(MagicMock(), "q", []) == []


def test_get_reranker_raises_wrapped_error_when_load_fails(monkeypatch):
    class _BrokenCE:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    fake_module = MagicMock()
    fake_module.CrossEncoder = _BrokenCE
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", fake_module)
    with pytest.raises(EmbeddingError, match="Failed to load reranker"):
        reranker.get_reranker("broken")


def test_resolve_reranker_config_enables_when_model_present():
    enabled, model, candidates = reranker.resolve_reranker_config(
        embedding_definition_reranker="ce-model",
        embedding_definition_multiplier=5,
        rerank=None,
        rerank_model=None,
        rerank_candidates=None,
        limit=10,
    )
    assert enabled is True
    assert model == "ce-model"
    assert candidates == 50


def test_resolve_reranker_config_respects_explicit_false():
    enabled, model, _ = reranker.resolve_reranker_config(
        embedding_definition_reranker="ce-model",
        embedding_definition_multiplier=5,
        rerank=False,
        rerank_model=None,
        rerank_candidates=None,
        limit=10,
    )
    assert enabled is False
    assert model == "ce-model"  # still resolved so callers can inspect


def test_resolve_reranker_config_per_call_override_wins():
    enabled, model, candidates = reranker.resolve_reranker_config(
        embedding_definition_reranker=None,
        embedding_definition_multiplier=5,
        rerank=True,
        rerank_model="call-specific",
        rerank_candidates=17,
        limit=3,
    )
    assert enabled is True
    assert model == "call-specific"
    assert candidates == 17


def test_resolve_reranker_config_candidates_never_below_limit():
    _, _, candidates = reranker.resolve_reranker_config(
        embedding_definition_reranker="m",
        embedding_definition_multiplier=5,
        rerank=None,
        rerank_model=None,
        rerank_candidates=2,
        limit=10,
    )
    assert candidates == 10
