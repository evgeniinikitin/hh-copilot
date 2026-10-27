from __future__ import annotations

from pathlib import Path


class CandidateProfile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> str:
        if not self.path.is_file():
            raise FileNotFoundError(f"Candidate profile not found: {self.path}")
        value = self.path.read_text(encoding="utf-8").strip()
        if not value:
            raise ValueError("Candidate profile is empty")
        return value
