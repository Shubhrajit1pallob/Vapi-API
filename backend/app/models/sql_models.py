"""
SQLAlchemy models for the survey system.

SurveyTemplate  - stores versioned question sets (JSONB).
PatientResponse - stores per-call answers collected by Vapi (JSONB).
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Integer, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.pg_database import Base


class SurveyTemplate(Base):
    """
    A versioned set of survey questions.

    questions JSONB example:
    [
        {"id": "q1", "type": "mcq", "Q": "How are you?", "A": ["Good", "Okay", "Bad"]},
        {"id": "q2", "type": "open", "Q": "Any concerns?", "A": []}
    ]
    """

    __tablename__ = "survey_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PatientResponse(Base):
    """
    Answers collected during a single Vapi phone/web call.

    answers JSONB example:
    [
        {"question_id": "q1", "answer": "Good"},
        {"question_id": "q2", "answer": "No concerns"}
    ]
    """

    __tablename__ = "patient_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    call_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    answers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
