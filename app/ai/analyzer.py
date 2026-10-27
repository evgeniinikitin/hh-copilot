from __future__ import annotations

import asyncio
import json
import logging
import re

from pydantic import ValidationError

from app.ai.codex import CodexClient, CodexError
from app.ai.cover_letter import validate_cover_letter
from app.ai.prompts import build_analysis_prompt
from app.ai.schemas import VacancyAnalysis
from app.candidate.profile import CandidateProfile
from app.config import Settings
from app.hh.schemas import NormalizedVacancy

logger = logging.getLogger("ai")
FENCE_PATTERN = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.I | re.S)


def parse_analysis(value: str) -> VacancyAnalysis:
    match = FENCE_PATTERN.match(value)
    if match:
        value = match.group(1)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Codex output is not valid JSON") from exc
    try:
        result = VacancyAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Codex JSON does not match analysis schema") from exc
    validate_cover_letter(result.cover_letter)
    return result


class VacancyAnalyzer:
    def __init__(self, settings: Settings, client: CodexClient | None = None) -> None:
        self.settings = settings
        self.client = client or CodexClient(settings)
        self.profile = CandidateProfile(settings.candidate_profile_path)

    async def analyze(self, vacancy: NormalizedVacancy) -> VacancyAnalysis:
        instructions = self.settings.analysis_prompt_path.read_text(encoding="utf-8")
        cover_letter_policy = self.settings.cover_letter_prompt_path.read_text(encoding="utf-8")
        prompt = build_analysis_prompt(
            instructions,
            cover_letter_policy,
            self.profile.load(),
            vacancy,
        )
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                logger.info("Analysis started id=%s attempt=%s", vacancy.id, attempt + 1)
                raw = await self.client.run(prompt)
                result = parse_analysis(raw)
                logger.info("Analysis completed id=%s score=%s", vacancy.id, result.match_score)
                return result
            except (CodexError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Analysis failed id=%s attempt=%s error=%s",
                    vacancy.id,
                    attempt + 1,
                    exc,
                )
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
        raise CodexError(f"Analysis failed after retries: {last_error}")
