# Observability Watchdog

An intelligent, API-first event observability system with anomaly detection, alerting, and a real-time dashboard.

## Stack
- **Backend:** Python (FastAPI)
- **Database:** SQLite (via SQLAlchemy)
- **Dashboard:** Jinja2 + HTMX + Chart.js (served by FastAPI)
- **Scheduler:** APScheduler (background anomaly detection)
- **Alerting:** Configurable webhooks + console alerts

## Quick Start
```bash
pip install -r requirements.txt
python main.py
```
Then open http://localhost:8000

## Architecture
```
observability-watchdog/
├── main.py               # FastAPI app entry point
├── config.py             # Settings (env-driven)
├── database.py           # SQLAlchemy setup + migrations
├── models/
│   ├── event.py          # Event ORM model
│   ├── alert.py          # Alert ORM model
│   └── metric.py         # Metric snapshot ORM model
├── routers/
│   ├── events.py         # POST /events, GET /events
│   ├── alerts.py         # GET /alerts, PATCH /alerts/{id}
│   └── metrics.py        # GET /metrics
├── services/
│   ├── ingestion.py      # Event ingestion & validation
│   ├── anomaly.py        # Anomaly detection engine
│   └── notifier.py       # Alert dispatching
├── scheduler.py          # Background jobs (APScheduler)
├── templates/            # Jinja2 HTML templates
│   ├── base.html
│   ├── dashboard.html
│   └── events.html
└── static/               # CSS / JS assets
```
