# HH Copilot

I built HH Copilot to shorten the work between saving a vacancy and deciding whether to apply. Saving jobs on a phone is easy; returning later to compare requirements with a candidate profile and write a relevant letter is the slow part.

The product starts with a behavior people already have: marking a job as a favorite on HeadHunter. When Chrome is opened on hh.ru, the extension syncs saved vacancy IDs. A local Python service fetches vacancy details from the public HH API, asks a local Codex CLI to analyze fit against an editable profile, drafts a cover letter, and sends the result to Telegram.

## Decisions behind the flow

**No backlog flood on day one.** The first full sync establishes a baseline. Existing favorites are saved but not analyzed automatically. A user can choose to process a few older roles from the extension popup.

**One vacancy, one analysis.** Vacancy IDs are unique in SQLite, and queued work resumes after a restart. Stalled items return to the queue with bounded retries.

**A draft is not an application.** The assistant does not submit to employers. It prepares a fit review and letter for the candidate to check and edit.

**A local boundary for candidate facts.** The model is instructed to use only facts in `data/candidate_profile.md`. The repository includes an example template; copy and edit it before use.

The architecture is deliberately small: Chrome extension, local FastAPI backend, SQLite queue, Codex CLI, and Telegram notifier. There is no hosted service to configure.

## Run locally

Requirements: macOS, Python 3.12–3.14, Chrome, an authenticated Codex CLI, and a Telegram bot you control.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
cp data/candidate_profile.example.md data/candidate_profile.md
```

Fill in your bot token, chat ID, and contact email in `.env`; edit `data/candidate_profile.md`; then run:

```bash
python -m app.main doctor
python -m app.main run
```

Load `extension/` as an unpacked Chrome extension. The full setup, recovery behavior, and manual checks are in [`docs/setup.ru.md`](docs/setup.ru.md).

```bash
ruff check .
mypy app
pytest
node --test tests_js/*.test.js
```

## Current status

This is a local prototype for the saved-vacancy workflow. It does not use applicant OAuth or send applications.
