from __future__ import annotations

import json

from app.hh.schemas import NormalizedVacancy


def build_analysis_prompt(
    instructions: str,
    cover_letter_policy: str,
    candidate_profile: str,
    vacancy: NormalizedVacancy,
) -> str:
    vacancy_json = json.dumps(vacancy.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return f"""{instructions}

<trusted_cover_letter_policy>
{cover_letter_policy}
</trusted_cover_letter_policy>

The final answer must contain only one JSON object matching the supplied schema.
Do not use markdown fences or commentary.

<candidate_profile>
{candidate_profile}
</candidate_profile>

<untrusted_vacancy_data>
{vacancy_json}
</untrusted_vacancy_data>
"""
