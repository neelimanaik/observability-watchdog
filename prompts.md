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

---

## Turn 9 — 2026-05-31
**Prompt:**
> Add alert suppression to prevent duplicate alerts. Rules: 1) Same source+rule within last 10 minutes — suppress, no new DB record, no LLM call. 2) Add suppression_count column — increment on each suppression. 3) Show suppression_count on dashboard and alerts page. 4) Add pytest test verifying suppression and count increment. Run all tests and confirm they pass. Commit and push. Update prompts.md.

**Actions taken:**
- Added `suppression_count: Integer DEFAULT 0` to `models/alert.py`
- SQLite migration: `ALTER TABLE alerts ADD COLUMN suppression_count INTEGER NOT NULL DEFAULT 0`
- Rewrote `services/anomaly.py`:
  - Replaced `_open_alert_exists()` with `_find_recent_alert()` — queries for unacknowledged alert created within last 10 min
  - Added `_suppress_alert()` — increments suppression_count and commits
  - Added `_handle_rule()` — shared dispatch: suppress if recent alert exists, else create new (with LLM)
  - Exported `SUPPRESSION_WINDOW_MINUTES = 10` constant for tests to import
- Updated `routers/alerts.py` — `AlertOut` + `_to_out()` now include `suppression_count`
- Updated `templates/dashboard.html` — added "Suppressed" column (purple badge showing +N, or dash)
- Updated `templates/alerts.html` — same Suppressed column, colspan updated to 10
- Created `tests/test_suppression.py` — 7 tests:
  - second cycle suppressed, count=1
  - count increments each cycle (count=2 after 3 cycles)
  - LLM call_count==1 across two cycles (mock verified)
  - new alert fires after suppression window expires (created_at backdated beyond 10 min)
  - fresh alert starts at count=0
  - suppression is per-rule (spike and critical_flood tracked independently)
  - acknowledged alert does not block new one
- Restarted server to pick up model/router changes
- **Result: 41/41 tests pass** (37.55s); all three UI pages return 200; suppression_count in API response

---

## Turn 10 — 2026-05-31
**Prompt:**
> Two enhancements: 1) Root cause categorisation — update LLM prompt to return JSON {category, analysis}, add root_cause_category column, store it, display as coloured badge. 2) Root Cause Distribution pie chart + GET /metrics/root-cause-distribution endpoint. 3) Seed 15 demo alerts across all 6 categories. 4) Fix suppression count visibility — trigger two rapid spikes so suppression_count > 0 on dashboard. Run tests, fix failures, commit and push. Update prompts.md.

**Actions taken:**
- `models/alert.py`: added `root_cause_category: String(64) nullable`
- SQLite migration: `ALTER TABLE alerts ADD COLUMN root_cause_category TEXT`
- `services/llm_analyzer.py` rewritten:
  - JSON-mode system prompt (category + analysis fields, list of 6 valid categories)
  - `_parse_llm_response()`: strips markdown fences, parses JSON, normalises invalid categories to "Unknown", falls back plain-text to ("text", "Unknown")
  - `analyse_alert()` now returns `(analysis: str | None, category: str | None)` tuple
  - Exported `VALID_CATEGORIES` set
- `services/anomaly.py`: `_create_alert()` + `_handle_rule()` updated to accept/unpack category
- `routers/alerts.py`: `root_cause_category` added to `AlertOut` and `_to_out()`
- `routers/metrics.py`: new `GET /metrics/root-cause-distribution` endpoint — counts alerts per category, seeds all 6 with 0
- `main.py`: dashboard route computes `rca_data` dict from alert table, passes to template
- `templates/base.html`: `grid-3` CSS class + 6 `badge-cat-*` colour rules
- `templates/dashboard.html`: Category column in alerts table, RCA pie chart in grid-3 layout with per-category colours
- `templates/alerts.html`: Category column added, colspan updated to 11
- Seeded 15 demo alerts (3 Database, 3 Network, 2 Auth, 3 Memory/Resource, 2 Application, 2 Unknown) directly to SQLite
- Triggered suppression: injected 15 events × 2 cycles on api-gateway → suppression_count=1 confirmed on live alert
- Fixed 7 test failures caused by `analyse_alert` return type change (str → tuple):
  - `test_llm_analyser.py`: all assertions updated to unpack tuple; added 4 new tests (invalid category, plain text fallback, all valid categories, JSON prompt instruction)
  - `test_suppression.py`: mock return_value changed to `("mock analysis", "Application")`
- **Result: 45/45 tests pass** (27.89s)
- Verified: all 4 endpoints 200; `GET /metrics/root-cause-distribution` returns all 6 categories

---

## Turn 11 — 2026-05-31
**Prompt:**
> Four improvements: 1) Pie chart percentages — show % labels on slices + counts in legend. 2) Alert severity colour coding — HIGH red, MEDIUM orange, LOW yellow, CRITICAL dark red. 3) GET /health returning JSON: status, uptime_seconds, total_events_24h, open_alerts_count, version. 4) 15-second auto-refresh on dashboard with Last updated HH:MM:SS timestamp. Update README to reflect full feature set. Commit and push. Update prompts.md.

**Actions taken:**
- `templates/base.html`:
  - Added `chartjs-plugin-datalabels@2.2.0` CDN script
  - `.badge-critical` dark red (#991b1b), `.badge-low` yellow (#ca8a04)
- `templates/dashboard.html`:
  - Added "Last updated: HH:MM:SS" bar (top-right, updates on load)
  - `Chart.register(ChartDataLabels)` — plugin registered globally
  - `pctLegendLabels()` helper — generates "Label (count — X%)" legend entries
  - `datalabelOpts` — percentage labels on pie/doughnut slices
  - levelChart and rcaChart use both `generateLabels` and `datalabels` plugin
  - timeChart has `datalabels: {display: false}` to suppress labels on line chart
  - `setTimeout(() => location.reload(), 15000)` — 15-second auto-refresh
- `main.py`:
  - `APP_VERSION = "1.0.0"` and `_start_time` module-level constants
  - `GET /health` → `{status, version, uptime_seconds, total_events_24h, open_alerts_count}`
- `README.md`: full rewrite — added Features section, alert suppression, LLM categorisation, auto-refresh, /health, updated test count to 45, updated architecture Mermaid diagram to include suppression path

**Verified:** 7/7 dashboard checks pass; /health returns 200 with correct JSON; /ui/alerts 200
**Tests:** 45/45 still passing (no new tests this turn — all features are UI/API layer)

---

## Turn 12 — 2026-05-31
**Prompt:**
> Six improvements: 1) Line chart Y-axis labels and improved tooltips. 2) Fix RCA legend alignment. 3) New Trends line chart (Errors/Warnings/Total, last 24h) + GET /metrics/trends. 4) Anomaly Detection Log table + GET /metrics/anomaly-log. 5) Check/create scripts/generate_logs.py with --spike flag. 6) Webhook: update .env placeholder + README instructions + payload structure. Run all tests, commit and push. Update prompts.md.

**Actions taken:**
- `models/anomaly_log.py`: new `AnomalyLog` model (checked_at, source, window_count, error_count, threshold, is_anomaly)
- `database.py`: registered `anomaly_log` in `init_db()` imports
- SQLite: `anomaly_logs` table created via `init_db()`
- `services/anomaly.py`: writes one `AnomalyLog` row per source per detection cycle (with error_count, threshold, fired status)
- `routers/metrics.py`:
  - `GET /metrics/trends` — hourly buckets for total/errors/warnings last 24h
  - `GET /metrics/anomaly-log` — last N detection log entries with error_rate computed
- `main.py`: dashboard route computes `trends_data` and `anomaly_log_entries` from DB; both passed to template
- `templates/dashboard.html` full rewrite:
  - Shared `commonScales` object reused across line charts
  - `timeChart`: `interaction.mode="index"`, custom tooltip callbacks, pointRadius
  - `rcaChart`: monospace legend font for alignment, padding=10
  - New `trendsChart`: 3-dataset line chart (Total/Errors/Warnings), full-width card
  - New "Anomaly Detection Log" table alongside Recent Alerts in grid-2 layout
  - All existing features preserved (datalabels, auto-refresh, last-updated)
- `scripts/generate_logs.py`: created — continuous realistic event streamer with argparse
  - `--spike`: sends 20 rapid errors to trigger anomaly, then exits
  - `--host`, `--interval`, `--source` options
  - Realistic LEVEL_WEIGHTS (info:60, warn:22, error:14, critical:4)
- `.env`: ALERT_WEBHOOK_URL updated to `https://webhook.site/your-unique-id-here` placeholder
- `README.md`: added "Live Traffic Simulation" section + "Webhook Alerts" section with payload structure
- Seeded anomaly_logs table with a detection cycle
- **Tests: 45/45 pass** (48.75s — no regressions from new model/service changes)

---

## Turn 13 — 2026-05-31
**Prompt:**
> Update the WEBHOOK_URL in .env to [https://webhook.site/4760ba7c-cc9a-4b4d-9bd2-82ca2fd54021]. Restart the app and trigger one spike using scripts/generate_logs.py --spike so we can verify the webhook payload fires to webhook.site. Update prompts.md.

**Actions taken:**
- Updated `ALERT_WEBHOOK_URL` in `.env`
- Killed and restarted uvicorn; confirmed `settings.alert_webhook_url` loaded correctly
- Ran `python scripts/generate_logs.py --spike` — 20/20 events returned 201
- Acknowledged existing open payment-service alert (suppression guard)
- Forced detection cycle via `detect_anomalies()` + `dispatch()`
- Results:
  - Groq LLM → `HTTP 200`, category = `Network`
  - Alert created: `[HIGH] spike on payment-service`
  - Webhook → `POST https://webhook.site/4760ba7c-cc9a-4b4d-9bd2-82ca2fd54021` → `HTTP 200 OK`
- Payload delivered to webhook.site (visible at https://webhook.site/#!/4760ba7c-cc9a-4b4d-9bd2-82ca2fd54021)

---

## Turn 14 — 2026-05-31
**Prompt:**
> Two fixes: 1) Fix RCA legend so labels/counts/percentages are perfectly column-aligned using fixed-width table layout. 2) Fix all timestamps on dashboard and alerts page to display in IST (UTC+5:30). Update prompts.md, commit and push.

**Actions taken:**
- `main.py`:
  - Added `_IST_OFFSET = timedelta(hours=5, minutes=30)` constant
  - Added `_to_ist(dt, fmt)` helper function (adds 5h30m, formats with strftime)
  - Registered as Jinja2 filter: `templates.env.filters["to_ist"] = _to_ist`
  - Fixed anomaly log dict `checked_at` to use `_to_ist(r.checked_at, "%H:%M:%S IST")`
- `templates/dashboard.html`:
  - `a.created_at.strftime(...)` → `a.created_at | to_ist("%H:%M:%S IST")`
  - `e.timestamp.strftime(...)` → `e.timestamp | to_ist` (uses default format "%Y-%m-%d %H:%M:%S IST")
  - Added `<div id="rcaLegend">` below canvas
  - Replaced built-in Chart.js legend (`legend: {display: false}`) with `buildRcaLegend()` HTML function:
    - Renders a `<table>` with three columns: Category (colour swatch + name), Count (right-aligned), Share % (right-aligned)
    - Uses `font-variant-numeric: tabular-nums` for number column alignment
    - No more reliance on canvas text rendering for legend
  - JS "Last updated": switched to `new Date().toLocaleTimeString("en-IN", {timeZone:"Asia/Kolkata",...}) + " IST"`
- `templates/alerts.html`:
  - `a.created_at.strftime(...)` → `a.created_at | to_ist`
- **Verified:** 6/6 checks pass; 25 IST timestamps on /ui/alerts (sample: 2026-05-31 16:37:28 IST)
- **Tests: 45/45 pass** (33.89s)

---

## Turn 15 — 2026-05-31
**Prompt:**
> The Events page (/ui/events) still shows timestamps in UTC. Apply the same IST fix — use the to_ist() Jinja2 filter on all timestamp fields in the events template. Verify timestamps show "IST" suffix. Commit and push. Update prompts.md.

**Root cause:** `templates/events.html` line 26 used `e.timestamp.strftime("%Y-%m-%d %H:%M:%S")` — the same raw UTC strftime pattern missed in Turn 14 (only dashboard and alerts were fixed then).

**Fix:** `e.timestamp.strftime("%Y-%m-%d %H:%M:%S")` → `e.timestamp | to_ist` in `templates/events.html:26`. Also added `white-space:nowrap` to prevent the "IST" suffix wrapping.

**Verified:** `/ui/events` returns 200; 200 IST timestamps found (sample: 2026-05-31 18:36:18 IST); 0 raw UTC timestamps remaining.

---

## Turn 16 — 2026-05-31
**Prompt:**
> In the alerts page and dashboard, replace the "&mdash;" placeholder for missing root_cause_category with the text "Unknown" styled with the same grey badge used for the Unknown category. Applies wherever category is None or empty. Commit and push. Update prompts.md.

**Fix:** Collapsed the `{% if a.root_cause_category %}...{% else %}&mdash;{% endif %}` block in both templates to a single expression using the `or` operator:
`{{ (a.root_cause_category or "Unknown") | replace(...) | lower | replace(...) }}` for the CSS class and `{{ a.root_cause_category or "Unknown" }}` for the text. The `badge-cat-unknown` CSS class (grey #475569) is already defined in `base.html`.

**Verified:** 25 category badge cells on /ui/alerts — all use `badge-cat-*`; 3 render as `badge-cat-unknown` (previously None); 0 dashes in category position.
