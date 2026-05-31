# Prompts Audit Log

## Turn 1 — 2026-05-31
**Prompt:**
> Lead Architect mode: ON. We are building a Python-based, API-first Intelligent Observability & Event Watchdog using a free database (SQLite) and a dashboard.
> Rules: No Manual Edits / Audit Log / Time-Check (MVP in 4–6h, max 16h).
> Also initialise a git repository in this folder so we can push to GitHub at the end.

**Actions:** Audited scaffold, installed deps, git init + initial commit, started server, seeded 300 events, verified all API endpoints and dashboard.

---

## Turn 2 — 2026-05-31
**Prompt:**
> Add the AI/LLM layer. When anomaly detector fires, call Groq LLM for root cause analysis. Store with alert, display on dashboard. Add groq to requirements.txt. Create .env for GROQ_API_KEY. Add .env to .gitignore.

**Actions:** groq added, .env + .gitignore created, `llm_analysis` column added to Alert model + SQLite migration, `services/llm_analyzer.py` created (SRE prompt → Groq → graceful fallback), anomaly.py wired, routers/alerts.py updated, dashboard + alerts templates updated with collapsible AI Analysis column, Jinja datetime bug fixed.

---

## Turn 3 — 2026-05-31
**Prompt:**
> Set GROQ_API_KEY in .env. Inject 20 error events to fire an alert. Verify LLM analysis appears on dashboard.

**Actions:** Key set in .env. 20 events injected to payment-service. Discovered llama3-8b-8192 decommissioned → updated default to `llama-3.1-8b-instant`. Detection fired, Groq returned HTTP 200, analysis stored and rendered in 2 dashboard HTML blocks. Committed.

---

## Turn 4 — 2026-05-31
**Prompt:**
> Commit the working tree changes with a sensible message.

**Actions:** Committed `.claude/settings.local.json` — tool allowlist additions accumulated during session.

---

## Turn 5 — 2026-05-31
**Prompt:**
> Add a pytest test suite with at least: 1) unit test for anomaly detection logic, 2) integration test for POST /events/, 3) test that verifies LLM analyser falls back gracefully when no API key is set. Put all tests in tests/ with a conftest.py. Run the tests and confirm they pass. Update prompts.md.

**Actions taken:**
- Installed pytest, pytest-asyncio, httpx
- Created `tests/__init__.py`
- Created `tests/conftest.py`:
  - `db_engine` fixture: in-memory SQLite with `StaticPool` (critical — prevents "no such table" from per-connection DB isolation)
  - `db_session` fixture: raw SQLAlchemy session against test DB
  - `client` fixture: FastAPI TestClient with `get_db` overridden to use test DB
- Created `tests/test_anomaly.py` — 9 tests across 3 classes:
  - `TestSpikeDetection`: threshold, no-dup, refires-after-ack, field values
  - `TestCriticalFloodDetection`: threshold, non-critical events ignored
  - `TestMetricSnapshots`: avg_value written correctly
- Created `tests/test_events_api.py` — 15 tests across 2 classes:
  - `TestCreateEvent`: 201 shape, level normalisation, invalid level/source, nullable fields, all valid levels
  - `TestListEvents`: empty, filter by level/source, limit, get-by-id, 404
- Created `tests/test_llm_analyser.py` — 10 tests across 3 classes:
  - `TestGracefulFallback`: no key, placeholder key, API error, network error → all return None
  - `TestSuccessPath`: mocked Groq response returned and stripped
  - `TestPromptConstruction`: prompt content, event window filtering, limit
- Fixed first-run failure: `StaticPool` added to conftest (SQLAlchemy in-memory SQLite creates a fresh DB per connection by default)
- Added pytest + pytest-asyncio to requirements.txt

**Result:** 34/34 tests passed in 8.06s. 1 deprecation warning (pydantic v2 config class — pre-existing, not introduced here).
