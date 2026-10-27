from __future__ import annotations

import asyncio

from app.ai.analyzer import parse_analysis
from app.ai.codex import CodexClient
from app.config import get_settings


async def main() -> None:
    prompt = """Return only JSON for this schema: match_score integer 0-100,
recommendation one of strong_apply/apply/maybe/skip, summary string, strengths array,
gaps array, relevant_experience array, cover_letter string. Use score 0 and skip."""
    raw = await CodexClient(get_settings()).run(prompt)
    result = parse_analysis(raw)
    print(f"Codex OK: score={result.match_score} recommendation={result.recommendation}")


if __name__ == "__main__":
    asyncio.run(main())
