from sqlalchemy import Boolean, Column, Integer, String, Text

from ..database import Base


class IqQuestionRow(Base):
    """HR-authored IQ question. Served alongside the built-in bank; ids are ``hr-<id>``.

    Soft-deleted (``active=False``) so tests already in flight still score."""

    __tablename__ = "iq_questions"

    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(Text, nullable=False)
    options = Column(Text, nullable=False)  # JSON list[str]
    answer = Column(Integer, nullable=False)  # index into options
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(String, nullable=True)
