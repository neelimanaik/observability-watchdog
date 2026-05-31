# Observability Watchdog

An API-first, intelligent observability platform that ingests application events, detects anomalies in real time, uses a large language model to generate structured root cause analysis, and surfaces everything through a live auto-refreshing dashboard — all backed by SQLite with zero external infrastructure dependencies.

Built as a full-stack Python project demonstrating event-driven architecture, automated anomaly detection with configurable thresholds, LLM-powered SRE workflows using the Groq free API tier, and a dark-theme dashboard with Chart.js visualisations.

---

## Architecture

```mermaid
flowchart TD
    A[Client / Service] -->|POST /events/| B[FastAPI Ingest Layer]
    B -->|SQLAlchemy ORM| C[(SQLite events)]

    subgraph Scheduler [APScheduler every 60s]
        D[Anomaly Detector]
        D -->|Spike rule / Critical flood rule| E{Alert?}
    end

    C -->|Query window| D
    E -->|Yes — new alert| F[(SQLite alerts)]
    E -->|Suppressed — within 10 min| G[Increment suppression_count]
    G --> F
    E -->|Yes| H[LLM Analyser]

    H -->|Fetch recent events| C
    H -->|JSON prompt: category + analysis| I[Groq API llama-3.1-8b-instant]
    I -->|{category, analysis}| H
    H -->|root_cause_category + llm_analysis| F

    E -->|Yes| J[Notifier]
    J -->|Optional webhook| K[Slack / Teams / Custom]

    F -->|Metric snapshots| L[(SQLite metrics)]

    M[Browser] -->|GET / auto-refresh 15s| N[Dashboard UI]
    M -->|GET /ui/events| O[Events UI]
    M -->|GET /ui/alerts| P[Alerts UI]

    N & O & P -->|Jinja2 + Chart.js + HTMX| M
    F & C & L -->|SQLAlchemy| N
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | [FastAPI](https://fastapi.tiangolo.com/) 0.115 |
| Database | SQLite via [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 |
| Schema validation | [Pydantic](https://docs.pydantic.dev/) v2 |
| Background jobs | [APScheduler](https://apscheduler.readthedocs.io/) 3.10 |
| LLM inference | [Groq](https://console.groq.com/) free API — `llama-3.1-8b-instant` |
| Dashboard | [Jinja2](https://jinja.palletsprojects.com/) + [HTMX](https://htmx.org/) + [Chart.js](https://www.chartjs.org/) 4.4 + [chartjs-plugin-datalabels](https://chartjs-plugin-datalabels.netlify.app/) |
| ASGI server | [Uvicorn](https://www.uvicorn.org/) |
| Test suite | [pytest](https://pytest.org/) — 45 tests, in-memory SQLite |

---

## Features

### Event Ingestion
- `POST /events/` accepts source, level (`info`/`warn`/`error`/`critical`), message, optional numeric value, and arbitrary JSON tags.
- Events are validated, normalised, and stored with a UTC timestamp.

### Anomaly Detection (automated, every 60 s)
- **Spike rule** — fires a `HIGH` alert when a source emits 3× its 30-minute baseline (minimum 10 events) in the current 5-minute window.
- **Critical flood rule** — fires a `CRITICAL` alert when a source produces ≥ 10 critical-level events in the window.
- **Alert suppression** — if an unacknowledged alert for the same rule + source was created within the last 10 minutes, no new DB record is created and the LLM is not called again; instead `suppression_count` is incremented on the existing alert.
- Deduplication resets when an alert is acknowledged via `PATCH /alerts/{id}/acknowledge`.

### LLM Root Cause Analysis
- When a new alert fires, `services/llm_analyzer.py` fetches the 20 most recent events for that source (last 30 minutes) and sends a structured SRE prompt to Groq.
- The model returns a JSON object `{"category": "...", "analysis": "..."}`.
- **Category** is one of: `Database`, `Network`, `Authentication`, `Memory/Resource`, `Application`, `Unknown`.
- Both fields are stored on the alert. The category appears as a colour-coded badge; the analysis expands as a collapsible panel.
- Graceful degradation: if the API key is absent or the call fails, the alert is still created with `NULL` analysis — no functionality is lost.

### Dashboard
- **Auto-refreshes every 15 seconds** — a "Last updated: HH:MM:SS" timestamp in the top-right shows the last reload time.
- **KPI cards**: Total events (24 h), errors/criticals, open alerts, active sources.
- **Events by Level** doughnut chart with percentage labels on slices and `Label (count — X%)` legend entries.
- **Event Volume Over Time** line chart (hourly buckets, last 24 h).
- **Root Cause Distribution** pie chart with the same percentage labels, powered by `GET /metrics/root-cause-distribution`.
- **Recent Alerts** table: severity badge (colour-coded), category badge, AI analysis panel, suppression count badge, acknowledge button (HTMX, no page reload).
- **Recent Events** table: level badge, source, message, value, timestamp.

### API
See [API Endpoints](#api-endpoints) below.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/neelimanaik/observability-watchdog.git
cd observability-watchdog
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Edit `.env` and set your Groq API key (free at [console.groq.com](https://console.groq.com)):

```ini
GROQ_API_KEY=gsk_your_key_here
ALERT_WEBHOOK_URL=          # optional — Slack/Teams incoming webhook
```

> **Note:** `.env` is git-ignored. Your API key is never committed.

### 5. Run the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** for the dashboard or **http://localhost:8000/docs** for the interactive API explorer.

### 6. Seed demo data (optional)

```bash
python seed.py
```

Injects 300 realistic events across 5 simulated services over the last 24 hours.

### 7. Run the test suite

```bash
pytest tests/ -v
```

---

## API Endpoints

### Events

| Method | Path | Description |
|---|---|---|
| `POST` | `/events/` | Ingest a new event |
| `GET` | `/events/` | List events — filter by `source`, `level`; paginate with `limit` / `offset` |
| `GET` | `/events/{id}` | Fetch a single event by ID |

**Example payload:**

```json
{
  "source": "payment-service",
  "level": "error",
  "message": "DB connection pool exhausted",
  "value": 503.0,
  "tags": { "env": "prod", "region": "us-east" }
}
```

Valid levels: `info` · `warn` · `error` · `critical`

### Alerts

| Method | Path | Description |
|---|---|---|
| `GET` | `/alerts/` | List alerts — filter by `acknowledged` |
| `PATCH` | `/alerts/{id}/acknowledge` | Mark an alert as acknowledged |

Each alert includes: `rule`, `source`, `message`, `severity`, `acknowledged`, `llm_analysis`, `root_cause_category`, `suppression_count`, `created_at`.

### Metrics

| Method | Path | Description |
|---|---|---|
| `GET` | `/metrics/` | List per-source window snapshots — filter by `source` |
| `GET` | `/metrics/root-cause-distribution` | Returns `{category: count}` for all 6 categories |

### System

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns `status`, `version`, `uptime_seconds`, `total_events_24h`, `open_alerts_count` |

### Dashboard UI

| Path | Description |
|---|---|
| `GET /` | Auto-refreshing dashboard (15 s) |
| `GET /ui/events` | Filterable event log |
| `GET /ui/alerts` | Full alert list with AI analysis and category badges |
| `GET /docs` | Interactive OpenAPI / Swagger UI |

---

## How Anomaly Detection Works

APScheduler runs a detection cycle every 60 seconds. Each cycle applies two rules against a sliding window (default: last 5 minutes).

### Rule 1 — Event Spike

```
threshold = max(baseline_avg_per_window x ANOMALY_SPIKE_MULTIPLIER, 10)
if current_count >= threshold  ->  fire HIGH alert
```

Baseline is the average per window over the preceding 30 minutes. Default multiplier: `3.0`.

### Rule 2 — Critical Flood

```
if critical_count_in_window >= 10  ->  fire CRITICAL alert
```

### Alert Suppression (10-minute window)

If an unacknowledged alert for the same rule + source was created within the last 10 minutes:
- No new DB record is inserted.
- No LLM call is made.
- `suppression_count` on the existing alert is incremented.

Visible as a purple `+N` badge on each alert row. Acknowledging an alert re-arms detection for that source.

### Metric Snapshots

After each cycle, a `Metric` row is written per active source capturing event count and average numeric value — queryable via `GET /metrics/`.

### Configuration

| Variable | Default | Description |
|---|---|---|
| `ANOMALY_WINDOW_MINUTES` | `5` | Detection window size |
| `ANOMALY_SPIKE_MULTIPLIER` | `3.0` | Spike threshold multiplier |
| `SCHEDULER_INTERVAL_SECONDS` | `60` | Cycle frequency |

---

## How LLM Analysis Works

When the detector fires a new alert, `services/llm_analyzer.py` is called immediately before the alert is written to the database.

**Steps:**

1. **Fetch context** — Retrieves the 20 most recent events for the affected source from the last 30 minutes.
2. **Build SRE prompt** — Formats the alert and event log. System prompt instructs the model to respond with only a JSON object.
3. **Call Groq** — Sends to `llama-3.1-8b-instant` (temperature 0.3, max 512 tokens).
4. **Parse response** — Extracts `category` (normalised to `Unknown` if outside the valid set) and `analysis` text. Handles plain-text fallback if the model ignores the JSON instruction.
5. **Store** — Both fields saved to `alerts.llm_analysis` and `alerts.root_cause_category`.
6. **Display** — Category badge + collapsible "View analysis" panel per alert row.

**Valid categories:** `Database` · `Network` · `Authentication` · `Memory/Resource` · `Application` · `Unknown`

**Graceful degradation:** Any failure (missing key, quota, network) results in `NULL` values — alerts still fire normally.

---

## Project Structure

```
observability-watchdog/
├── main.py                  # FastAPI app, health endpoint, UI routes
├── config.py                # Pydantic settings (reads .env)
├── database.py              # SQLAlchemy engine + session factory
├── scheduler.py             # APScheduler background job
├── seed.py                  # Demo data generator
├── models/
│   ├── event.py
│   ├── alert.py             # llm_analysis, root_cause_category, suppression_count
│   └── metric.py
├── routers/
│   ├── events.py
│   ├── alerts.py
│   └── metrics.py           # includes /root-cause-distribution
├── services/
│   ├── ingestion.py
│   ├── anomaly.py           # Spike + flood + suppression logic
│   ├── llm_analyzer.py      # JSON-mode Groq prompt, (analysis, category) return
│   └── notifier.py
├── templates/
│   ├── base.html            # Dark theme, severity/category badge CSS, datalabels CDN
│   ├── dashboard.html       # Auto-refresh, 3 charts with %, alerts + events tables
│   ├── events.html
│   └── alerts.html
├── tests/
│   ├── conftest.py          # StaticPool in-memory SQLite fixtures
│   ├── test_anomaly.py      # 9 tests
│   ├── test_events_api.py   # 15 tests
│   ├── test_llm_analyser.py # 14 tests (JSON parsing, category validation, fallbacks)
│   └── test_suppression.py  # 7 tests
├── .env                     # git-ignored
├── .gitignore
└── requirements.txt
```

---

## License

MIT


---

## Live Traffic Simulation

`scripts/generate_logs.py` streams realistic events to the watchdog API to simulate live traffic and trigger anomaly detection.

```bash
# Stream continuous realistic events (Ctrl-C to stop)
python scripts/generate_logs.py

# Send a spike of 20 consecutive errors to trigger an alert immediately
python scripts/generate_logs.py --spike

# Options
python scripts/generate_logs.py --help
#   --spike           Send burst then exit
#   --host URL        API base URL (default: http://localhost:8000)
#   --interval SECS   Delay between events (default: 0.5)
#   --source SVC      Fix the source service name
```

---

## Webhook Alerts

Set `ALERT_WEBHOOK_URL` in `.env` to receive a POST payload whenever an alert fires.

**Get a free test URL:**
1. Go to [https://webhook.site](https://webhook.site)
2. Copy your unique URL (e.g. `https://webhook.site/abc-123-...`)
3. Paste it in `.env`:

```ini
ALERT_WEBHOOK_URL=https://webhook.site/your-unique-id-here
```

The next anomaly cycle (within 60 s) will POST a payload like:

```json
{
  "text": "*[HIGH]* `spike` on `payment-service`\nEvent spike on 'payment-service': 42 events in last 5m (baseline ~3.2/window)"
}
```

The `text` field is formatted for Slack-compatible webhook receivers. For Teams or custom endpoints, update `services/notifier.py` to adjust the payload shape.
