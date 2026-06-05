"""Robust JSON extraction from LLM responses."""
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_llm_json(content: str) -> dict[str, Any]:
    """Parse JSON from raw LLM output, stripping markdown fences if present."""
    text = content.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as e:
                logger.warning("JSON brace extraction failed: %s", e)
        raise
