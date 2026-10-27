from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class VacancyStatus(StrEnum):
    BASELINE = "baseline"
    DETECTED = "detected"
    QUEUED = "queued"
    PROCESSING = "processing"
    FETCHED = "fetched"
    ANALYZED = "analyzed"
    NOTIFIED = "notified"
    FAILED = "failed"


class Base(DeclarativeBase):
    pass


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hh_vacancy_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String(500))
    company_name: Mapped[str | None] = mapped_column(String(500))
    alternate_url: Mapped[str | None] = mapped_column(String(1000))

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VacancyStatus.DETECTED.value, index=True
    )

    match_score: Mapped[int | None] = mapped_column(Integer)
    recommendation: Mapped[str | None] = mapped_column(String(32))

    cover_letter: Mapped[str | None] = mapped_column(Text)
    analysis_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    raw_vacancy_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AppState(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
