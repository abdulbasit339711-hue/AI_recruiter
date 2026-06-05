import json
import logging
import os
from typing import Any, Dict

from ..database import config
from .groq_client import get_groq_client
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

class NameModel(BaseModel):
    name: str

def extract_name_llm(resume_text: str, retries: int = 3) -> Dict[str, str]:
    """Extract candidate full name using the LLM.
    Returns a dict with a single key ``name``.
    Falls back to a simple heuristic if the LLM client is unavailable.
    """
    client = get_groq_client()
    if not client:
        # Simple fallback: first line with at least two capitalized words
        lines = resume_text.strip().split('\n')
        if lines:
            first_line = lines[0]
            parts = first_line.split()
            if len(parts) >= 2 and all(p and p[0].isupper() for p in parts):
                return {"name": first_line.strip()}
        return {"name": ""}

    system_prompt = (
        "You are a senior technical recruiter. Extract the candidate's full name from the resume text. "
        "Return ONLY a JSON object with a single key 'name'."
    )
    user_prompt = f"Resume Text:\n{resume_text}"

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=config.get("llm", {}).get("model", "llama-3.3-70b-versatile"),
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
            NameModel(**parsed)  # validate schema
            return parsed
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning(f"Attempt {attempt + 1}: Failed to parse name JSON: {e}")
            if attempt == retries - 1:
                return {"name": ""}
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}: LLM name extraction error: {e}")
            if attempt == retries - 1:
                return {"name": ""}
    return {"name": ""}
