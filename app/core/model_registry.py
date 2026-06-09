"""Singleton loaders for heavy ML models (spaCy, sentence-transformers).

Both getters are called from request threads AND the background worker thread, so
loading is guarded by a lock with double-checked locking to avoid loading the same
heavy model twice concurrently.
"""
import logging
import subprocess
import threading

logger = logging.getLogger(__name__)

_nlp = None
_embedding_model = None
_nlp_lock = threading.Lock()
_embedding_lock = threading.Lock()


def get_spacy_model(model_name: str = "en_core_web_sm"):
    global _nlp
    if _nlp is None:
        with _nlp_lock:
            if _nlp is None:  # re-check inside the lock
                import spacy

                try:
                    _nlp = spacy.load(model_name)
                    logger.info("Loaded spaCy model: %s", model_name)
                except OSError:
                    try:
                        subprocess.run(
                            ["python", "-m", "spacy", "download", model_name],
                            capture_output=True,
                            check=True,
                        )
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        logger.error("spaCy model download failed for %s: %s", model_name, e)
                        raise RuntimeError(
                            f"spaCy model '{model_name}' is not installed and could not be "
                            "downloaded. Pre-install it during deployment."
                        ) from e
                    _nlp = spacy.load(model_name)
                    logger.info("Downloaded and loaded spaCy model: %s", model_name)
    return _nlp


def get_embedding_model(model_name: str = "all-MiniLM-L6-v2"):
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:  # re-check inside the lock
                from sentence_transformers import SentenceTransformer

                _embedding_model = SentenceTransformer(model_name)
                logger.info("Loaded embedding model: %s", model_name)
    return _embedding_model


def models_loaded() -> dict:
    return {
        "spacy": _nlp is not None,
        "embeddings": _embedding_model is not None,
    }
