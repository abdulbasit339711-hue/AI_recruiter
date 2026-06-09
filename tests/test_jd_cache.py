"""Tests for the bounded JD-embedding cache (app/core/jd_embedding_cache.py).

We stub the embedding model so no heavy ML import is needed, and exercise the
FIFO eviction bound that was added during the audit fixes.
"""

import numpy as np
import pytest

import app.core.jd_embedding_cache as cache


class _FakeModel:
    def encode(self, text, show_progress_bar=False):
        # deterministic small vector; content doesn't matter for cache tests
        return np.zeros(3, dtype=np.float32)


@pytest.fixture(autouse=True)
def stub_model_and_reset(monkeypatch):
    monkeypatch.setattr(cache, "get_embedding_model", lambda *a, **k: _FakeModel())
    cache._cache.clear()
    monkeypatch.setattr(cache, "_hits", 0, raising=False)
    monkeypatch.setattr(cache, "_misses", 0, raising=False)
    yield
    cache._cache.clear()


def test_caches_and_hits():
    cache.get_jd_embedding("some job description")
    assert cache.cache_stats()["size"] == 1
    cache.get_jd_embedding("some job description")  # same content -> hit, no new entry
    stats = cache.cache_stats()
    assert stats["size"] == 1
    assert stats["hits"] >= 1


def test_eviction_respects_max_entries(monkeypatch):
    monkeypatch.setattr(cache, "_MAX_ENTRIES", 5)
    for i in range(12):
        cache.get_jd_embedding(f"job description number {i}")
    assert cache.cache_stats()["size"] == 5  # bounded, never grows past the cap


def test_eviction_drops_oldest_first(monkeypatch):
    monkeypatch.setattr(cache, "_MAX_ENTRIES", 3)
    for i in range(3):
        cache.get_jd_embedding(f"jd {i}")
    # cache full with jd 0,1,2; adding jd 3 should evict jd 0 (oldest)
    cache.get_jd_embedding("jd 3")
    assert cache.cache_stats()["size"] == 3
    # re-requesting jd 0 should be a MISS (it was evicted) -> size stays 3, jd 1 evicted
    before = cache.cache_stats()["misses"]
    cache.get_jd_embedding("jd 0")
    assert cache.cache_stats()["misses"] == before + 1


def test_invalidate_removes_entry():
    cache.get_jd_embedding("removable jd")
    assert cache.cache_stats()["size"] == 1
    cache.invalidate_job("removable jd")
    assert cache.cache_stats()["size"] == 0
