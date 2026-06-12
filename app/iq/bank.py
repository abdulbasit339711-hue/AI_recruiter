"""Built-in IQ question bank + server-side scoring.

The bank lives in code for now. Everything outside this module goes through
``get_bank()`` / ``sample_questions()`` / ``score_answers()`` so a future
per-job, DB-backed bank can replace the source without changing the endpoints.

Integrity: correct answers (``IqQuestion.answer``) must never be serialized to
the client. Use ``to_public()`` when shipping a question over the wire.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class IqQuestion:
    id: str
    prompt: str
    options: list[str]
    answer: int  # index into options — SERVER ONLY, never sent to the client

    def to_public(self) -> dict:
        """Client-safe shape: no correct answer."""
        return {"id": self.id, "prompt": self.prompt, "options": list(self.options)}


# A small, neutral aptitude set (number series, logic, verbal, spatial).
_BANK: list[IqQuestion] = [
    IqQuestion("seq-1", "What number comes next: 2, 4, 8, 16, ?", ["20", "24", "32", "30"], 2),
    IqQuestion("seq-2", "What number comes next: 1, 1, 2, 3, 5, 8, ?", ["11", "12", "13", "14"], 2),
    IqQuestion("seq-3", "What number comes next: 3, 6, 11, 18, ?", ["27", "25", "29", "24"], 0),
    IqQuestion("seq-4", "Odd one out: 3, 5, 11, 15, 17", ["5", "11", "15", "17"], 2),
    IqQuestion("seq-5", "What number comes next: 100, 50, 25, ?", ["10", "12", "12.5", "15"], 2),
    IqQuestion("ana-1", "Hand is to Glove as Foot is to ?", ["Sock", "Shoe", "Toe", "Leg"], 1),
    IqQuestion("ana-2", "Bird is to Sky as Fish is to ?", ["Net", "Water", "Scale", "Boat"], 1),
    IqQuestion("ana-3", "Doctor is to Patient as Teacher is to ?", ["School", "Book", "Student", "Lesson"], 2),
    IqQuestion("log-1", "If all Bloops are Razzies and all Razzies are Lazzies, then all Bloops are definitely:",
               ["Lazzies", "Not Lazzies", "Sometimes Lazzies", "Razzies only"], 0),
    IqQuestion("log-2", "A is taller than B. C is shorter than B. Who is tallest?", ["A", "B", "C", "Cannot tell"], 0),
    IqQuestion("log-3", "Which word does NOT belong: Apple, Banana, Carrot, Mango", ["Apple", "Banana", "Carrot", "Mango"], 2),
    IqQuestion("math-1", "If 5 machines make 5 widgets in 5 minutes, how long for 100 machines to make 100 widgets?",
               ["100 minutes", "5 minutes", "20 minutes", "1 minute"], 1),
    IqQuestion("math-2", "What is half of one quarter of 200?", ["25", "50", "100", "12.5"], 0),
    IqQuestion("math-3", "A shirt costs $40 after a 20% discount. What was the original price?",
               ["$48", "$50", "$60", "$45"], 1),
    IqQuestion("verb-1", "Which word is the opposite of 'Scarce'?", ["Rare", "Abundant", "Empty", "Limited"], 1),
    IqQuestion("spat-1", "How many faces does a cube have?", ["4", "6", "8", "12"], 1),
    IqQuestion("spat-2", "Which shape has no straight edges?", ["Triangle", "Square", "Circle", "Pentagon"], 2),
    IqQuestion("pat-1", "Complete the pattern: AZ, BY, CX, ?", ["DV", "DW", "EW", "DX"], 1),
]

_BANK_BY_ID = {q.id: q for q in _BANK}


def get_bank() -> list[IqQuestion]:
    """All questions (server-side; includes answers)."""
    return list(_BANK)


def sample_questions(n: int, *, rng: random.Random | None = None) -> list[IqQuestion]:
    """Pick ``n`` distinct questions in random order (clamped to bank size)."""
    r = rng or random
    n = max(1, min(n, len(_BANK)))
    return r.sample(_BANK, n)


def score_answers(answers: dict[str, int], served_ids: list[str]) -> tuple[int, int]:
    """Score ``{question_id: chosen_index}`` against the bank.

    Only the ``served_ids`` count toward the total (so missing/extra answers and
    unknown ids can't inflate or deflate the score). Returns ``(correct, total)``.
    """
    total = len(served_ids)
    correct = 0
    for qid in served_ids:
        q = _BANK_BY_ID.get(qid)
        if q is None:
            continue
        if answers.get(qid) == q.answer:
            correct += 1
    return correct, total
