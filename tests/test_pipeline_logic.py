"""Unit tests for status resolution and JSON parsing (no ML models)."""
import pytest

from app.core import status as S
from app.scoring.engine import _resolve_final_status
from app.llm.json_parser import parse_llm_json
from app.scoring.heuristics import extract_name_heuristic


def test_resolve_final_status_shortlisted():
    assert _resolve_final_status(80.0, "Reviewed") == S.SHORTLISTED


def test_resolve_final_status_reviewed():
    assert _resolve_final_status(65.0, "Rejected") == S.REVIEWED


def test_resolve_final_status_rejected():
    assert _resolve_final_status(40.0, "Rejected") == S.REJECTED


def test_parse_llm_json_strips_fences():
    raw = '```json\n{"name": "Jane", "tier3_score": 10}\n```'
    data = parse_llm_json(raw)
    assert data["name"] == "Jane"
    assert data["tier3_score"] == 10


def test_heuristic_name_extraction():
    text = "Jane Smith\nSoftware Engineer\njane@example.com\nExperience\n..."
    assert extract_name_heuristic(text) == "Jane Smith"
