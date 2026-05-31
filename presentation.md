# Intelligent Observability & Event Watchdog
### Presentation · Neelima Naik · May 2026

---

## Slide 1 — Title

# ⚡ Intelligent Observability & Event Watchdog

**An AI-powered, API-first event monitoring platform with real-time anomaly detection and LLM root cause analysis**

---

| | |
|---|---|
| **Author** | Neelima Naik |
| **Date** | May 2026 |
| **Repository** | https://github.com/neelimanaik/observability-watchdog |
| **Stack** | Python · FastAPI · SQLite · Groq LLM · Chart.js |
| **Tests** | 45 automated tests · 0 manual code edits |

---

## Slide 2 — Problem Statement

# The Problem: Alert Fatigue & Black-Box Detection

### Three pain points every engineering team knows

---

### 🔔 Alert Fatigue
- Modern systems fire hundreds of alerts per day
- Duplicate alerts for the same ongoing incident pile up with no deduplication
- On-call engineers spend more time silencing alerts than fixing problems
- Teams start **ignoring** alerts — the exact opposite of the goal

### ⏱️ Cost of Late Detection
- A 5-minute delay in detecting a payment service failure at peak load can mean thousands in lost revenue
- Traditional threshold-based monitors fire **after** the damage is done
- Root cause investigation from scratch takes 30–60 minutes per incident
- Every minute of MTTR (Mean Time To Resolve) has a measurable business cost

### 🕳️ Black-Box AI Systems
- Existing observability tools use opaque ML models — you see the alert but not _why_
- Engineers can't trust a system they can't interrogate
- No category classification → alerts treated identically regardless of whether the cause is a DB issue, a memory leak, or a network fault
- LLM-assisted analysis is either locked behind expensive enterprise tiers or absent entirely

> **The gap:** A self-contained, transparent, AI-enriched observability system that any team can run for free.

---

## Slide 3 — Solution Architecture

# Solution Architecture: End-to-End Data Flow

```
Client / Service
      │
      ▼ POST /events/
┌─────────────────────┐
│  FastAPI Ingest API │  ← Validates level, source, tags; writes to SQLite
└─────────┬───────────┘
          │
          ▼ SQLAlchemy ORM
    ┌───────────┐
    │  SQLite   │  events · alerts · metrics · anomaly_logs
    └─────┬─────┘
          │
          ▼ APScheduler (every 60 s)
┌─────────────────────────────────────┐
│        Anomaly Detector             │
│  Spike rule:   count > 3× baseline  │
│  Flood rule:   critical events ≥ 10 │
│  Window:       last 5 minutes       │
└──────┬──────────────┬───────────────┘
       │ New alert    │ Duplicate within 10 min
       ▼              ▼
  ┌────────────┐  suppression_count++
  │ LLM Layer  │  (no DB write, no LLM call)
  │  Groq API  │
  │ JSON →     │  { "category": "Database",
  │  category  │    "analysis": "Connection pool..." }
  │  analysis  │
  └──────┬─────┘
         │
         ├──▶  Alert stored in SQLite (with category + analysis)
         │
         └──▶  Notifier → POST webhook payload
                          (Slack / Teams / webhook.site)
          │
          ▼
┌─────────────────────┐
│  Dashboard (Jinja2) │  Auto-refreshes every 15 s · IST timestamps
│  Chart.js · HTMX    │  4 charts · Anomaly Log · Acknowledge button
└─────────────────────┘
```

### Design Principles
- **API-first** — every feature reachable via REST; dashboard is a consumer of the same endpoints
- **Zero external infra** — SQLite, no Redis, no message queue, no cloud services required
- **Additive AI** — LLM enrichment is optional; system is fully functional without a Groq key
- **Transparent detection** — every threshold, every rule, every suppression is logged and visible

---

## Slide 4 — Tech Stack

# Tech Stack: Best-in-Class Free Tier

| Layer | Technology | Why |
|---|---|---|
| **API Framework** | FastAPI 0.115 | Async-ready, automatic OpenAPI docs, dependency injection |
| **Database** | SQLite + SQLAlchemy 2.0 | Zero-config, full ORM, production-capable for moderate loads |
| **Schema Validation** | Pydantic v2 | Fast validation, clear error messages, `.env` settings management |
| **Background Jobs** | APScheduler 3.10 | In-process cron, no external broker needed |
| **LLM Inference** | Groq API — `llama-3.1-8b-instant` | Free tier, ~100 ms latency, structured JSON output |
| **Dashboard Templating** | Jinja2 + HTMX | Server-rendered with partial updates — no JavaScript framework |
| **Charts** | Chart.js 4.4 + datalabels plugin | Rich pie/line charts with % labels and custom legend HTML |
| **ASGI Server** | Uvicorn | Production-grade, hot-reload in dev |
| **Test Suite** | pytest 8.3 | 45 tests, in-memory SQLite, mock-free happy paths |
| **Language** | Python 3.13 | Type annotations throughout, modern union syntax (`X \| Y`) |

### Key dependency choices
- **No Celery / Redis** — APScheduler runs detection in-process; acceptable for the observability use case
- **SQLite over PostgreSQL** — portable, zero-config, sufficient for thousands of events per hour; swap via `DB_URL` env var
- **Groq over OpenAI** — free tier, faster inference on Llama 3.1, identical SDK surface
- **HTMX over React** — alert acknowledgement, zero-JS bundle size, server owns all state

---

## Slide 5 — Key Features

# Key Features: What Ships Out of the Box

### 🚀 Core Platform
| Feature | Detail |
|---|---|
| **API-first design** | `POST /events/`, `GET /alerts/`, `GET /metrics/` — all dashboard data consumable via REST |
| **Real-time anomaly detection** | Spike rule (3× baseline) + Critical flood rule (≥10 criticals), configurable window |
| **15-second auto-refresh** | Dashboard reloads silently; "Last updated: HH:MM:SS IST" top-right |
| **IST timestamps** | All times displayed as UTC+5:30 with `IST` suffix across all three pages |
| **Health endpoint** | `GET /health` → status, version, uptime_seconds, total_events_24h, open_alerts |
| **Log generator script** | `scripts/generate_logs.py --spike` — fires a burst to trigger anomaly detection on demand |

### 🧠 AI Layer
| Feature | Detail |
|---|---|
| **LLM root cause analysis** | Groq `llama-3.1-8b-instant` — 2-3 sentence SRE-grade analysis per alert |
| **Root cause categorisation** | 6 categories: Database · Network · Authentication · Memory/Resource · Application · Unknown |
| **Unknown fallback badge** | Grey `Unknown` badge shown instead of a dash for any uncategorised alert |
| **Graceful degradation** | Missing API key, quota error, or network failure → alert created normally, analysis null |

### 🔔 Alert Management
| Feature | Detail |
|---|---|
| **Alert suppression** | 10-minute window — no duplicate DB records, no redundant LLM calls |
| **Suppression count badge** | Purple `+N` badge shows how many times an alert would have re-fired |
| **Colour-coded severity badges** | CRITICAL dark red · HIGH red · MEDIUM orange · LOW yellow |
| **One-click acknowledge** | HTMX `PATCH` — no page reload, re-arms detection for that source |
| **Webhook delivery** | POST alert payload to any HTTP endpoint on every new alert |

### 📊 Dashboard Panels
- Events by Level doughnut with % slice labels
- Event Volume Over Time line chart with index tooltip
- Root Cause Distribution pie chart with aligned HTML legend (Category / Count / Share%)
- Error · Warning · Request Volume Trends — three-series line chart
- Anomaly Detection Log — per-source, per-cycle: events, errors, error%, threshold, status

---

## Slide 6 — AI Innovation

# AI Innovation: Structured LLM Root Cause Analysis

### The Problem with Plain-Text Analysis
A system prompt asking "what's wrong?" returns free-form text that can't be indexed, filtered, or charted. This project forces the LLM to return **structured JSON** so the category becomes a first-class database field.

---

### Prompt Design: JSON-Mode SRE Agent

**System prompt (paraphrased):**
> _You are an expert SRE. Respond with ONLY a JSON object in this exact format — no markdown, no extra text:_
> ```json
> {"category": "<one of: Database|Network|Authentication|Memory/Resource|Application|Unknown>",
>  "analysis": "<2-3 sentences: root cause + one actionable recommendation>"}
> ```

**Context window per alert:**
```
Alert triggered on service: payment-service
Alert description: Event spike — 131 events in last 5m (baseline ~8.5/window)

Most recent events (20 shown):
  [16:08:42] [ERROR] DB connection pool exhausted [value=503.0]
  [16:08:41] [ERROR] Upstream timeout after 30s
  [16:08:40] [ERROR] Redis ECONNREFUSED on retry #3
  [16:08:39] [ERROR] SSL handshake failed
  ...
```

---

### Live Output Example — payment-service Spike

```json
{
  "category": "Network",
  "analysis": "The sudden spike in errors on payment-service is likely caused by a
               cascading network partition affecting upstream dependencies — the mix
               of SSL handshake failures, Redis ECONNREFUSED, and upstream timeouts
               all point to a routing or DNS resolution failure rather than
               application-level bugs. Recommendation: Check VPC routing tables and
               DNS health, and enable circuit-breaking on the payment processor
               client with a 30s fallback."
}
```

**Category stored as:** `badge-cat-network` → 🟡 **Network** badge on dashboard

---

### 6 Root Cause Categories

| Badge | Category | Typical signals |
|---|---|---|
| 🔵 **Database** | Connection pool exhaustion, deadlocks, OOM in DB proxy |
| 🟡 **Network** | Upstream timeouts, SSL failures, DNS errors, ECONNREFUSED |
| 🟣 **Authentication** | JWT failures, brute-force patterns, token rotation errors |
| 🔴 **Memory/Resource** | OOM kills, GC pressure, heap exhaustion, buffer eviction |
| 🟢 **Application** | NullPointerException, checksum mismatches, invalid payloads |
| ⚫ **Unknown** | Mixed signals, no dominant failure mode; or LLM not configured |

**Fallback chain:** invalid JSON → plain text treated as analysis with `Unknown` category → missing key → both fields `NULL`, alert fires normally.

---

## Slide 7 — Alert Suppression

# Alert Suppression: Solving Alert Fatigue at the Source

### The Problem
A spike alert fires. The scheduler runs again 60 seconds later. The spike is still happening. Without suppression:
- Second alert written to DB → **noise**
- Groq API called again → **cost**
- On-call engineer sees two identical alerts → **confusion**

Multiply by 5 sources × 2 rules = **10 identical alerts in 10 minutes** from a single incident.

---

### The Solution: 10-Minute Suppression Window

```
Detection cycle fires for source S, rule R
          │
          ▼
_find_recent_alert(db, rule=R, source=S)
          │
  ┌───────┴────────┐
  │                │
  ▼                ▼
Found unacked     Not found (or
alert within      acknowledged /
10 minutes        expired window)
  │                │
  ▼                ▼
suppression_    Create new alert
count += 1      + LLM analysis
  │              + webhook POST
  ▼
No new DB row
No Groq call
No webhook
```

**Query:**
```sql
SELECT * FROM alerts
WHERE rule = ? AND source = ?
  AND acknowledged = 0
  AND created_at >= (now - 10 minutes)
ORDER BY created_at DESC LIMIT 1
```

---

### Visible on Dashboard

Every alert row shows a **purple `+N` suppression badge** when `suppression_count > 0`:

```
[HIGH] spike | Network | payment-service | +3 | 16:08:42 IST
```

This means the alert would have fired 3 more times — without cluttering the alert list or wasting LLM quota.

---

### Suppression Rules Summary

| Condition | Behaviour |
|---|---|
| Same rule + source, within 10 min, unacknowledged | Suppressed — count incremented |
| Same rule + source, alert acknowledged | New alert fires (detection re-armed) |
| Same rule + source, 10 min elapsed | New alert fires (window expired) |
| Different rule on same source | Independent suppression per rule |
| Different source, same rule | Independent suppression per source |

---

## Slide 8 — Testing

# Testing: 45 Tests, Zero Flaky Fixtures

### Test Architecture

```
tests/
├── conftest.py           — Shared fixtures (StaticPool, db_session, client)
├── test_anomaly.py       — 9 tests
├── test_events_api.py    — 15 tests
├── test_llm_analyser.py  — 14 tests
└── test_suppression.py   — 7 tests
                          ──────────
                          45 total · ~35 s runtime
```

---

### The StaticPool Fix

SQLAlchemy's default connection pool opens a **new in-memory SQLite database per connection checkout** — meaning every test started with empty tables even though `create_all()` had just been called.

**Solution:**
```python
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,   # ← all checkouts share ONE connection
)
```
This pins every session to the same underlying connection, so the schema persists for the entire test function.

---

### Coverage Highlights

| File | What's tested |
|---|---|
| `test_anomaly.py` | Spike threshold at exactly 10 events · no alert below · dedup · re-fires after ack · critical flood threshold · non-critical events ignored · avg_value in metric snapshots |
| `test_events_api.py` | 201 response shape · level normalisation to lowercase · invalid level → 422 · empty source → 422 · nullable value/tags · filter by source/level · limit/offset pagination · 404 on missing ID |
| `test_llm_analyser.py` | No key → (None, None) · placeholder key → (None, None) · API error → (None, None) · network error → (None, None) · valid JSON → correct (analysis, category) · invalid category → "Unknown" · plain-text fallback · all 6 valid categories accepted · JSON instruction in prompt · event window filtering · limit respected |
| `test_suppression.py` | Second cycle suppressed · count = 1 · count = 2 after 3 cycles · LLM call_count == 1 across two cycles (mock) · new alert after window expires (backdated created_at) · count = 0 on fresh alert · spike and flood suppressed independently · acknowledged alert does not block new one |

---

### Key Testing Decisions

- **Happy paths are mock-free** — anomaly tests use real SQLAlchemy queries against in-memory DB
- **LLM tests mock the Groq client only** — `_fetch_recent_events`, `_build_user_prompt`, `_parse_llm_response` tested against real DB
- **FastAPI TestClient** with `get_db` dependency override — integration tests hit real route handlers
- **`raise_server_exceptions=True`** — ensures 500s surface as Python exceptions in tests, not silent failures

---

## Slide 9 — Vibe Coding Workflow

# Vibe Coding Workflow: Lead Architect Mode in Practice

### Rules of Engagement
The entire project was built under three strict constraints:
1. **No manual edits** — all code written and fixed by Claude Code
2. **Audit log** — `prompts.md` updated every turn with the exact prompt and actions taken
3. **Timer** — MVP target 4–6 hours (achieved in ~6h 20m across 17 turns)

---

### Key Architect Decisions Made

| Turn | Decision | Rationale |
|---|---|---|
| 1 | SQLite over PostgreSQL | Zero-config, portable, swap via env var later |
| 2 | Groq over OpenAI | Free tier, ~100ms Llama 3.1, same API surface |
| 3 | `llama3-8b-8192` → `llama-3.1-8b-instant` | Caught model decommission from Groq's error response |
| 5 | StaticPool for pytest | Diagnosed per-connection DB isolation issue |
| 9 | 10-min suppression window (not just "open alert") | Tighter dedup while still allowing re-arm after ack |
| 10 | JSON-mode LLM prompt | Makes category a DB column, not just a text string |
| 12 | HTML table legend for RCA chart | Canvas text rendering can't do tabular alignment; HTML can |
| 14 | `to_ist` as a Jinja2 filter | Centralised, reusable across all three template pages |

---

### Bugs Found and Fixed — Without a Single Manual Edit

| Bug | Root Cause | Fix Applied |
|---|---|---|
| `/ui/alerts` → 500 | `a.created_at[:19]` treated `datetime` as string | `.strftime()` → `\| to_ist` filter |
| Tests failing: `no such table: events` | SQLAlchemy opens fresh `:memory:` DB per connection | `StaticPool` in `conftest.py` |
| Groq returning 400 | `llama3-8b-8192` decommissioned by Groq | Updated default model in `config.py` |
| Dashboard → 500 after anomaly log added | `templates/events.html` still had bare `.strftime()` | Applied `\| to_ist` filter |
| GitHub push blocked | API key embedded in `prompts.md` in commit history | `git filter-branch --tree-filter` scrubbed all commits |
| 7 test failures after LLM return type change | Tests expected `str`, now `(str, str)` tuple | All assertions updated to unpack tuple |

---

### GitHub Secret Scanning — Handled Automatically

When the Groq API key was pasted in a prompt, it was faithfully logged to `prompts.md` and committed. GitHub's push protection caught it:

```
remote: GITHUB PUSH PROTECTION
remote: Push cannot contain secrets
remote: — Groq API Key —
remote:   commit: cdb6f208  path: prompts.md:49
```

**Resolution (no manual git commands needed):**
```bash
git filter-branch --force --tree-filter \
  'python -c "...re.sub(r\"gsk_[A-Za-z0-9]+\", \"[REDACTED]\", ...)"' \
  --tag-name-filter cat -- --all
```
Scrubbed all `gsk_*` patterns from every commit. Deleted `refs/original`, expired reflog, ran `gc --prune=now`. History verified clean, force-pushed.

---

### What Vibe Coding Enables
- **Faster iteration** — describe the feature, get working code with tests
- **Consistent style** — one architect voice, one set of patterns throughout
- **Automatic audit trail** — every decision recorded in `prompts.md` with exact prompts
- **No context switching** — bugs are diagnosed and fixed in the same turn they're found

---

## Slide 10 — GitHub & Submission

# GitHub & Submission

---

### Repository

```
https://github.com/neelimanaik/observability-watchdog
```

### Quick Start (30 seconds)
```bash
git clone https://github.com/neelimanaik/observability-watchdog.git
cd observability-watchdog
pip install -r requirements.txt
# Add GROQ_API_KEY to .env
uvicorn main:app --port 8000
# Open http://localhost:8000
```

---

### Project Stats

| Metric | Value |
|---|---|
| Automated tests | **45** (0 failures) |
| API endpoints | **12** |
| Dashboard panels | **8** |
| Git commits | **18** |
| Lines of Python | ~1,200 |
| Manual code edits | **0** |
| Session duration | ~6h 20m |

---

### Tagle.ai Submission

| Field | Value |
|---|---|
| **Tag** | The Catalyst with Connector edge |
| **Category** | AI-powered developer tooling / observability |
| **Core innovation** | LLM structured root cause analysis + alert suppression in a zero-infra Python stack |

---

### What's Next (Beyond MVP)

- **PostgreSQL migration** — swap `DB_URL` env var, schema already migration-ready
- **Multi-tenant support** — partition events by `tenant_id`, scoped anomaly detection
- **Streaming ingest** — Kafka consumer alongside HTTP endpoint for high-throughput sources
- **Alert routing rules** — configurable: route `critical` + `Database` category to PagerDuty, others to Slack
- **LLM fine-tuning** — collect analyst feedback on root cause accuracy, build training set
- **Grafana-compatible metrics** — expose `/metrics/prometheus` endpoint

---

### Thank You

> _Built with Python, FastAPI, Groq, and Claude Code — in a single Lead Architect session._

**Neelima Naik · May 2026**
**https://github.com/neelimanaik/observability-watchdog**
