# Prompts Audit Log

## Turn 1 — 2026-05-31
**Prompt:**
> Lead Architect mode: ON. We are building a Python-based, API-first Intelligent Observability & Event Watchdog using a free database (SQLite) and a dashboard.
> Rules:
> - No Manual Edits: You provide all logic and fixes. I will not edit any code.
> - Audit Log: You must maintain a file named prompts.md. After every turn, update that file with the prompt I just used.
> - Time-Check: Start a timer. Goal is an MVP in 4-6 hours (Max window: 16h). Report 'Elapsed Time' at the end of every response. Acknowledge and let's start.
> Also initialise a git repository in this folder so we can push to GitHub at the end.

**Actions taken:**
- Audited all existing project files (main.py, models, routers, services, templates, scheduler, seed)
- Installed dependencies — all imports verified OK
- Initialized git repository, made initial commit (25 files, d78cefd)
- Started uvicorn server on port 8000 — startup confirmed clean
- Ran seed.py — 300 demo events ingested successfully
- Verified all API endpoints: GET /events/, GET /alerts/, GET /metrics/ all returning correct JSON
- Dashboard at http://localhost:8000 renders with charts and tables

**Status:** MVP scaffold is complete and running. All core features functional.

---

## Turn 2 — 2026-05-31
**Prompt:**
> Now add the AI/LLM layer for intelligent anomaly analysis. When the anomaly detector fires an alert, it should also call an LLM to analyse the recent error logs and provide a human-readable root cause suggestion. Use the Groq free API for this — add groq to requirements.txt. The LLM analysis should be stored with the alert in the database and displayed on the dashboard alongside the alert in the Recent Alerts section. Also create a .env file for the GROQ_API_KEY and add .env to .gitignore so the API key is never committed to GitHub. Update prompts.md with this prompt.

**Actions taken:**
- Added `groq==0.13.1` to requirements.txt; installed via pip
- Created `.env` with `GROQ_API_KEY` placeholder
- Created `.gitignore` (excludes .env, *.db, __pycache__, logs, venv)
- Added `groq_api_key`, `groq_model`, `groq_max_tokens` to `config.py` Settings
- Added `llm_analysis: Text` nullable column to `models/alert.py`
- Applied SQLite migration: `ALTER TABLE alerts ADD COLUMN llm_analysis TEXT`
- Created `services/llm_analyzer.py` — SRE prompt builder + Groq API call with graceful fallback
- Updated `services/anomaly.py` to call `analyse_alert()` before persisting each alert
- Updated `routers/alerts.py` AlertOut schema to expose `llm_analysis`
- Updated `templates/dashboard.html` and `alerts.html`: collapsible AI Analysis column
- Added `.llm-analysis` CSS style to `base.html`
- Fixed Jinja2 TypeError: datetime not subscriptable — switched to `.strftime()`

**Status:** LLM layer wired. Groq API key not yet set — analysis returns None gracefully.

---

## Turn 3 — 2026-05-31
**Prompt:**
> Update the .env file to set GROQ_API_KEY to [[REDACTED]]. Then trigger a test anomaly by injecting 20 consecutive error events via the API to fire an alert and verify the LLM analysis appears on the dashboard. Update prompts.md.

**Actions taken:**
- Set `GROQ_API_KEY` in `.env`
- Injected 20 events (15 error + 5 critical) to `payment-service` via `POST /events/`
- Discovered model `llama3-8b-8192` was decommissioned by Groq — updated default to `llama-3.1-8b-instant` in `config.py`
- Acknowledged existing open alert to clear the deduplication guard
- Re-ran anomaly detection — spike alert fired, Groq API returned `HTTP 200`
- LLM analysis produced (excerpt): *"Root Cause Analysis: The sudden spike in error events on payment-service is likely caused by resource exhaustion — a memory leak or high memory allocation rate leading to OOM errors and cascading failures..."*
- Verified dashboard HTML: 2 `llm-analysis` div blocks rendering, "AI Analysis" column present, "View analysis" expand button working
- Committed: `config.py` model update

**Status:** End-to-end LLM analysis verified live against Groq API. Analysis displays correctly on dashboard.
