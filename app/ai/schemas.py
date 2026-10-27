from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VacancyAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_score: int = Field(ge=0, le=100)
    recommendation: Literal["strong_apply", "apply", "maybe", "skip"]
    summary: str
    strengths: list[str]
    gaps: list[str]
    relevant_experience: list[str]
    cover_letter: str
