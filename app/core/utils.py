from datetime import datetime, timezone


def _utcnow() -> datetime:
    """Naive UTC timestamp — drop-in for the deprecated stdlib utcnow().

    Keeps the existing naive-UTC `.isoformat()`/`.strftime()` output byte-for-byte
    so stored timestamps don't change format."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
