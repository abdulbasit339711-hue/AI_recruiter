"""Singleton loaders for heavy ML models (spaCy, sentence-transformers)."""
import logging
import subprocess

logger = logging.getLogger(__name__)

_nlp = None
_embedding_model = None


def get_spacy_model(model_name: str = "en_core_web_sm"):
    global _nlp
    if _nlp is None:
        import spacy

        try:
            _nlp = spacy.load(model_name)
            logger.info("Loaded spaCy model: %s", model_name)
        except OSError:
            subprocess.run(
                ["python", "-m", "spacy", "download", model_name],
                capture_output=True,
                check=True,
            )
            import spacy

            _nlp = spacy.load(model_name)
            logger.info("Downloaded and loaded spaCy model: %s", model_name)
    return _nlp


def get_embedding_model(model_name: str = "all-MiniLM-L6-v2"):
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(model_name)
        logger.info("Loaded embedding model: %s", model_name)
    return _embedding_model


def models_loaded() -> dict:
    return {
        "spacy": _nlp is not None,
        "embeddings": _embedding_model is not None,
    }
