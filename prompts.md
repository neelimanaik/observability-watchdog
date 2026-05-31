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
- Created `services/llm_analyzer.py`:
  - Fetches last 20 events for the affected source (last 30 min)
  - Builds structured SRE-style prompt
  - Calls Groq API (llama3-8b-8192, temp=0.3, max_tokens=512)
  - Gracefully returns None if no key configured or API fails
- Updated `services/anomaly.py` to call `analyse_alert()` before `_create_alert()` for both spike and critical_flood rules
- Updated `_create_alert()` signature to accept and store `llm_analysis`
- Updated `routers/alerts.py` AlertOut schema + `_to_out()` to expose `llm_analysis`
- Updated `templates/dashboard.html`: added "AI Analysis" column with collapsible `<details>` panel per alert
- Updated `templates/alerts.html`: same AI Analysis column with expand-on-click design
- Added `.llm-analysis` CSS style to `base.html` (dark panel, blue left border)
- Created `.claude/launch.json` for preview panel integration
- Fixed Jinja2 TypeError: `datetime.datetime` not subscriptable — switched to `.strftime()`
- Verified: dashboard returns 200, "AI Analysis" header present, `llm_analysis` in API response

**Status:** LLM layer fully wired. Set GROQ_API_KEY in .env to activate live analysis.
