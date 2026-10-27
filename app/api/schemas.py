from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.hh.normalizer import extract_vacancy_id


class VacancyRequest(BaseModel):
    vacancy_id: str
    source: str = "instant"

    @field_validator("vacancy_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return extract_vacancy_id(value)


class SyncRequest(BaseModel):
    vacancy_ids: list[str] = Field(max_length=5000)
    source: str = "chrome_sync"


class SyncResponse(BaseModel):
    received: int
    new: int
    existing: int
    queued: int
    pending: int = 0
    baseline: bool = False


class ProcessBaselineRequest(BaseModel):
    limit: Literal[5, 10] = 5


class ProcessBaselineResponse(BaseModel):
    queued: int
    vacancy_ids: list[str]


class StatusResponse(BaseModel):
    status: str = "running"
    queue_size: int
    processing: int
    processed_total: int
    known_total: int
    baseline_total: int
    last_sync_at: datetime | None = None
