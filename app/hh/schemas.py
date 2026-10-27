from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NormalizedVacancy(BaseModel):
    id: str
    title: str
    company_name: str | None = None
    description: str
    salary_from: float | None = None
    salary_to: float | None = None
    salary_currency: str | None = None
    area: str | None = None
    experience: str | None = None
    employment: str | None = None
    schedule: str | None = None
    key_skills: list[str] = Field(default_factory=list)
    professional_roles: list[str] = Field(default_factory=list)
    alternate_url: str | None = None
    published_at: datetime | None = None
