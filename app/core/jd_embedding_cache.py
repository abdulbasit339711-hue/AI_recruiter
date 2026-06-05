"""In-memory cache for job-description embeddings (per JD text hash)."""
import hashlib
import logging
import threading
from typing import Optional

import numpy as np

from .model_registry import get_embedding_model

logger = logging.getLogger(__name__)

_cache: dict[str, np.ndarray] = {}
_lock = threading.Lock()
_hits = 0
_misses = 0


def _jd_hash(jd_text: str) -> str:
    normalized = " ".join(jd_text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_jd_embedding(jd_text: str, job_id: Optional[int] = None) -> np.ndarray:
    """
    Return cached JD embedding vector, generating and storing on first use.
    job_id is logged for observability only; cache key is content hash.
    """
    global _hits, _misses
    key = _jd_hash(jd_text)

    with _lock:
        if key in _cache:
            _hits += 1
            return _cache[key]

    model = get_embedding_model()
    vector = model.encode(jd_text, show_progress_bar=False)
    if hasattr(vector, "numpy"):
        vector = vector.numpy()
    vector = np.asarray(vector, dtype=np.float32)

    with _lock:
        _cache[key] = vector
        _misses += 1
        logger.debug(
            "JD embedding cached (job_id=%s, cache_size=%d)",
            job_id,
            len(_cache),
        )
    return vector


def invalidate_job(jd_text: str) -> None:
    key = _jd_hash(jd_text)
    with _lock:
        _cache.pop(key, None)


def cache_stats() -> dict:
    with _lock:
        return {"size": len(_cache), "hits": _hits, "misses": _misses}
