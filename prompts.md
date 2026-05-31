# Prompts Audit Log

## Turn 1 — 2026-05-31
**Prompt:**
> Lead Architect mode: ON. We are building a Python-based, API-first Intelligent Observability & Event Watchdog using a free database (SQLite) and a dashboard.
> Rules: No Manual Edits / Audit Log / Time-Check (MVP in 4-6h, max 16h).
> Also initialise a git repository in this folder so we can push to GitHub at the end.

**Actions:** Audited scaffold, installed deps, git init + initial commit, started server, seeded 300 events, verified all API endpoints and dashboard.

---

## Turn 2 — 2026-05-31
**Prompt:**
> Add the AI/LLM layer. When anomaly detector fires, call Groq LLM for root cause analysis. Store with alert, display on dashboard. Add groq to requirements.txt. Create .env for GROQ_API_KEY. Add .env to .gitignore.

**Actions:** groq added, .env + .gitignore created, llm_analysis column added to Alert model + SQLite migration, services/llm_analyzer.py created, anomaly.py wired, routers updated, dashboard + alerts templates updated with collapsible AI Analysis column, Jinja datetime bug fixed.

---

## Turn 3 — 2026-05-31
**Prompt:**
> Set GROQ_API_KEY in .env. Inject 20 error events to fire an alert. Verify LLM analysis appears on dashboard.

**Actions:** Key set in .env. 20 events injected to payment-service. Discovered llama3-8b-8192 decommissioned — updated default to llama-3.1-8b-instant. Detection fired, Groq returned HTTP 200, analysis stored and rendered in dashboard HTML. Committed.

---

## Turn 4 — 2026-05-31
**Prompt:**
> Commit the working tree changes with a sensible message.

**Actions:** Committed .claude/settings.local.json — tool allowlist additions.

---

## Turn 5 — 2026-05-31
**Prompt:**
> Add a pytest test suite with at least: 1) unit test for anomaly detection, 2) integration test for POST /events/, 3) test that verifies LLM analyser falls back gracefully when no API key is set. Put all tests in tests/ with a conftest.py. Run and confirm they pass.

**Actions:** Created tests/conftest.py (StaticPool in-memory fixture), test_anomaly.py (9 tests), test_events_api.py (15 tests), test_llm_analyser.py (10 tests). Fixed StaticPool issue. 34/34 pass in 8.06s.

---

## Turn 6 — 2026-05-31
**Prompt:**
> Commit the working tree changes with a sensible message.

**Actions:** Committed .claude/settings.local.json — added pytest to tool allowlist.

---

## Turn 7 — 2026-05-31
**Prompt:**
> Generate a professional README.md: project title + description, Mermaid architecture diagram, tech stack, setup instructions (clone/install/GROQ_API_KEY/.env/uvicorn), API endpoints table, how anomaly detection works, how LLM analysis works. Then push all committed changes to GitHub at https://github.com/neelimanaik/observability-watchdog using git remote add origin and git push. Update prompts.md.

**Actions:**
- Wrote full README.md via PowerShell (triple-backtick fences required here-string to avoid shell escaping issues)
- Sections: description, Mermaid flowchart, tech stack table, 7-step setup, API endpoint tables, anomaly detection explanation with threshold formulas, LLM analysis step-by-step, project structure tree, MIT licence
- Updated prompts.md
- Committed README.md + prompts.md
- git remote add origin https://github.com/neelimanaik/observability-watchdog.git
- git push -u origin master

---

## Turn 8 — 2026-05-31
**Prompt:**
> The /ui/alerts page is returning an Internal Server Error. Check the server logs, identify the root cause, and fix it. Do not ask me to edit any files manually — provide the complete fix. Update prompts.md.

**Root cause:** `templates/alerts.html` line 26 used `a.created_at[:19].replace("T"," ")`, treating the SQLAlchemy ORM `datetime` field as a string. The `/ui/alerts` route passes raw `Alert` ORM objects; only the API layer serialises through `AlertOut` (which converts to ISO string). The same bug was fixed on the dashboard in Turn 2 but alerts.html was missed.

**Fix:** Changed `a.created_at[:19].replace("T"," ")` → `a.created_at.strftime("%Y-%m-%d %H:%M:%S")` in `templates/alerts.html:26`.

**Verified:** `curl /ui/alerts` returns HTTP 200.
