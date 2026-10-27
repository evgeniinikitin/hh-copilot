from __future__ import annotations

import argparse
import asyncio
import platform
import sys

import httpx
import uvicorn

from app.ai.codex import CodexClient
from app.api.server import build_container
from app.config import Settings, get_settings
from app.database.models import VacancyStatus
from app.database.repository import VacancyRepository
from app.database.session import create_database_engine, create_session_factory, initialize_database
from app.hh.normalizer import extract_vacancy_id
from app.logging_config import configure_logging


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.main", description="HH Copilot")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="Run the local backend")
    commands.add_parser("doctor", help="Check the local installation")
    analyze = commands.add_parser("analyze", help="Queue one vacancy by ID")
    analyze.add_argument("vacancy_id")
    analyze_url = commands.add_parser("analyze-url", help="Queue one vacancy URL")
    analyze_url.add_argument("url")
    baseline = commands.add_parser("process-baseline", help="Queue recent baseline vacancies")
    baseline.add_argument("--limit", type=int, choices=(5, 10), default=5)
    return parser


def _repository(settings: Settings) -> tuple[VacancyRepository, object]:
    engine = create_database_engine(settings)
    initialize_database(engine)
    return VacancyRepository(create_session_factory(engine)), engine


async def _doctor(settings: Settings) -> int:
    checks: list[tuple[str, str]] = []
    checks.append(("Python", "OK" if sys.version_info >= (3, 12) else "FAIL (3.12+ required)"))
    checks.append(("macOS", "OK" if platform.system() == "Darwin" else "WARN (designed for macOS)"))
    try:
        repository, engine = _repository(settings)
        repository.count()
        engine.dispose()  # type: ignore[attr-defined]
        checks.append(("Database", "OK"))
    except Exception as exc:
        checks.append(("Database", f"FAIL ({exc})"))
    checks.append(("Backend config", "OK"))
    checks.append(
        ("Candidate profile", "OK" if settings.candidate_profile_path.is_file() else "FAIL")
    )
    codex_path = CodexClient(settings).binary_path()
    checks.append(("Codex CLI", f"OK ({codex_path})" if codex_path else "FAIL"))
    if codex_path:
        try:
            process = await asyncio.create_subprocess_exec(
                codex_path,
                "login",
                "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            output = (stdout + stderr).decode("utf-8", errors="replace")
            auth_ok = process.returncode == 0 and "logged in" in output.lower()
            checks.append(("Codex auth", "OK" if auth_ok else "FAIL"))
        except (OSError, TimeoutError) as exc:
            checks.append(("Codex auth", f"FAIL ({exc})"))
    else:
        checks.append(("Codex auth", "SKIP"))
    telegram = (
        "OK" if settings.telegram_bot_token and settings.telegram_chat_id else "NOT CONFIGURED"
    )
    checks.append(("Telegram", telegram))
    if not settings.hh_user_agent_configured:
        checks.append(("HH public access", "NOT CONFIGURED (set HH_USER_AGENT)"))
    else:
        try:
            headers = {
                "User-Agent": settings.hh_user_agent,
                "HH-User-Agent": settings.hh_user_agent,
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as http:
                response = await http.get("https://api.hh.ru/vacancies", params={"per_page": 1})
                response.raise_for_status()
            checks.append(("HH public access", "OK"))
        except Exception as exc:
            try:
                browser_headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/140.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                }
                async with httpx.AsyncClient(
                    timeout=10.0, headers=browser_headers, follow_redirects=True
                ) as http:
                    fallback = await http.get("https://hh.ru/")
                    fallback.raise_for_status()
                checks.append(("HH public access", "OK (HTML fallback; API unavailable)"))
            except Exception:
                checks.append(("HH public access", f"FAIL ({exc})"))
    for label, result in checks:
        print(f"{label:.<24} {result}")
    return 1 if any(result.startswith("FAIL") for _, result in checks) else 0


async def _analyze(settings: Settings, vacancy_id: str) -> int:
    configure_logging(settings)
    container = build_container(settings)
    try:
        container.sync_service.enqueue_instant(vacancy_id, "cli")
        await container.queue.start()
        while True:
            row = container.repository.get(vacancy_id)
            if row and row.status in {VacancyStatus.NOTIFIED.value, VacancyStatus.FAILED.value}:
                print(f"{vacancy_id}: {row.status}")
                return 0 if row.status == VacancyStatus.NOTIFIED.value else 1
            if (
                row
                and row.status == VacancyStatus.ANALYZED.value
                and not container.notifier.configured
            ):
                print(f"{vacancy_id}: analyzed (Telegram is not configured)")
                return 0
            await asyncio.sleep(1)
    finally:
        await container.queue.stop()
        await container.hh_client.close()
        await container.notifier.close()
        container.engine.dispose()


def main() -> int:
    args = _parser().parse_args()
    settings = get_settings()
    if args.command == "run":
        uvicorn.run(
            "app.api.server:app",
            host=settings.backend_host,
            port=settings.backend_port,
            log_level=settings.log_level.lower(),
        )
        return 0
    if args.command == "doctor":
        return asyncio.run(_doctor(settings))
    if args.command in {"analyze", "analyze-url"}:
        value = args.vacancy_id if args.command == "analyze" else args.url
        return asyncio.run(_analyze(settings, extract_vacancy_id(value)))
    if args.command == "process-baseline":
        repository, engine = _repository(settings)
        ids = repository.process_baseline(args.limit)
        engine.dispose()  # type: ignore[attr-defined]
        print(f"Queued {len(ids)} baseline vacancies: {', '.join(ids) or 'none'}")
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
