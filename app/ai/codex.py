from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from app.ai.schemas import VacancyAnalysis
from app.config import Settings


class CodexError(RuntimeError):
    pass


class CodexClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def binary_path(self) -> str | None:
        return shutil.which(self.settings.codex_binary)

    async def run(self, prompt: str) -> str:
        binary = self.binary_path()
        if not binary:
            raise CodexError(f"Codex CLI not found: {self.settings.codex_binary}")

        with tempfile.TemporaryDirectory(prefix="hh-copilot-codex-") as temp_dir:
            workspace = Path(temp_dir)
            schema_path = workspace / "analysis.schema.json"
            output_path = workspace / "analysis.json"
            schema_path.write_text(
                json.dumps(VacancyAnalysis.model_json_schema(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            command = [
                binary,
                "exec",
                "--cd",
                str(workspace),
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--color",
                "never",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-",
            ]
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._safe_environment(),
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(prompt.encode("utf-8")),
                    timeout=self.settings.codex_timeout_seconds,
                )
            except TimeoutError as exc:
                process.kill()
                await process.wait()
                raise CodexError(
                    f"Codex timed out after {self.settings.codex_timeout_seconds}s"
                ) from exc
            if process.returncode != 0:
                detail = stderr.decode("utf-8", errors="replace")[-2000:]
                raise CodexError(f"Codex exited with {process.returncode}: {detail}")
            if output_path.exists():
                result = output_path.read_text(encoding="utf-8").strip()
            else:
                result = stdout.decode("utf-8", errors="replace").strip()
            if not result:
                raise CodexError("Codex returned empty output")
            return result

    @staticmethod
    def _safe_environment() -> dict[str, str]:
        allowed = ("HOME", "PATH", "CODEX_HOME", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR")
        return {key: os.environ[key] for key in allowed if key in os.environ}
