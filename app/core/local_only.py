"""LOCAL_ONLY=1 keeps candidate data off third-party AI: no Tier-3 LLM, no voice interview."""
import os


def is_local_only() -> bool:
    return os.getenv("LOCAL_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}
