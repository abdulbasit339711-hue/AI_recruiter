"""Applicant IQ screening.

A short, server-scored aptitude test taken *before* a candidate uploads their
résumé. The score is recorded on the candidate for HR to see/rank — it never
blocks the application.

Design (see ``bank.py`` / ``tokens.py``):
- ``GET /iq-test`` samples questions from the built-in bank and returns them
  WITHOUT the correct answers, plus a signed ``iq_test`` token that pins which
  questions were served and a server-enforced deadline.
- ``POST /iq-test/submit`` verifies that token, scores the answers server-side
  against the bank, and returns a signed ``iq_result`` token carrying the score.
- ``POST /upload`` optionally accepts the ``iq_result`` token and copies the
  score onto the new candidate row.

The question bank lives in code for now; it is deliberately fronted by
``bank.get_bank()`` so a per-job, DB-backed bank can replace it later without
touching the endpoints.
"""

from .bank import IqQuestion, get_bank, sample_questions, score_answers
from .tokens import (
    IqTokenError,
    IqTestClaims,
    IqResultClaims,
    mint_test_token,
    verify_test_token,
    mint_result_token,
    verify_result_token,
    iq_secret,
)

__all__ = [
    "IqQuestion",
    "get_bank",
    "sample_questions",
    "score_answers",
    "IqTokenError",
    "IqTestClaims",
    "IqResultClaims",
    "mint_test_token",
    "verify_test_token",
    "mint_result_token",
    "verify_result_token",
    "iq_secret",
]
