import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, desc

from config import settings
from database import init_db, SessionLocal
from models.event import Event
from models.alert import Alert
from routers import events, alerts, metrics
from scheduler import start_scheduler, stop_scheduler

APP_VERSION = "1.0.0"
_start_time = datetime.now(timezone.utc)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

_IST_OFFSET = timedelta(hours=5, minutes=30)

templates = Jinja2Templates(directory="templates")


def _to_ist(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S IST") -> str:
    """Convert a UTC datetime to IST (UTC+5:30) and format it."""
    if dt is None:
        return "—"
    return (dt + _IST_OFFSET).strftime(fmt)


templates.env.filters["to_ist"] = _to_ist


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(events.router)
app.include_router(alerts.router)
app.include_router(metrics.router)


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    db = SessionLocal()
    try:
        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        total_events_24h = db.scalar(
            select(func.count(Event.id)).where(Event.timestamp >= since_24h)
        ) or 0
        open_alerts = db.scalar(
            select(func.count(Alert.id)).where(Alert.acknowledged == False)  # noqa: E712
        ) or 0
    finally:
        db.close()

    uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
    return JSONResponse({
        "status": "ok",
        "version": APP_VERSION,
        "uptime_seconds": round(uptime, 1),
        "total_events_24h": total_events_24h,
        "open_alerts_count": open_alerts,
    })


# ── Dashboard UI ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    db = SessionLocal()
    try:
        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

        total = db.scalar(select(func.count(Event.id)).where(Event.timestamp >= since_24h)) or 0
        errors = db.scalar(
            select(func.count(Event.id)).where(
                Event.timestamp >= since_24h,
                Event.level.in_(["error", "critical"]),
            )
        ) or 0
        open_alerts = db.scalar(
            select(func.count(Alert.id)).where(Alert.acknowledged == False)  # noqa: E712
        ) or 0
        sources = db.scalar(
            select(func.count(func.distinct(Event.source))).where(Event.timestamp >= since_24h)
        ) or 0

        # Level breakdown
        level_rows = db.execute(
            select(Event.level, func.count().label("cnt"))
            .where(Event.timestamp >= since_24h)
            .group_by(Event.level)
        ).all()
        level_map = {r.level: r.cnt for r in level_rows}
        level_data = {
            "labels": ["info", "warn", "error", "critical"],
            "values": [level_map.get(l, 0) for l in ["info", "warn", "error", "critical"]],
        }

        # Hourly buckets for last 24h (SQLite strftime)
        hourly_rows = db.execute(
            select(
                func.strftime("%H:00", func.datetime(Event.timestamp, "localtime")).label("hour"),
                func.count().label("cnt"),
            )
            .where(Event.timestamp >= since_24h)
            .group_by("hour")
            .order_by("hour")
        ).all()
        time_data = {
            "labels": [r.hour for r in hourly_rows],
            "values": [r.cnt for r in hourly_rows],
        }

        # Detector performance metrics
        total_alerts = db.scalar(select(func.count(Alert.id))) or 0
        total_suppressions = db.scalar(
            select(func.coalesce(func.sum(Alert.suppression_count), 0))
        ) or 0
        total_events_det = total_alerts + total_suppressions
        suppression_rate = round(total_suppressions / total_events_det * 100, 1) if total_events_det else 0.0
        sev_rows = db.execute(
            select(Alert.severity, func.count().label("cnt")).group_by(Alert.severity)
        ).all()
        by_severity = {r.severity: r.cnt for r in sev_rows}
        first_alert_ts = db.scalar(select(func.min(Alert.created_at)))
        if first_alert_ts:
            first_aware = first_alert_ts.replace(tzinfo=timezone.utc) if first_alert_ts.tzinfo is None else first_alert_ts
            days = max((datetime.now(timezone.utc) - first_aware).total_seconds() / 86400, 1)
            avg_per_day = round(total_alerts / days, 1)
        else:
            avg_per_day = 0.0
        perf = {
            "total_alerts_fired": total_alerts,
            "total_suppressions": total_suppressions,
            "suppression_rate_pct": suppression_rate,
            "by_severity": by_severity,
            "avg_alerts_per_day": avg_per_day,
        }

        recent_alerts = db.execute(
            select(Alert).order_by(func.datetime(Alert.created_at).desc()).limit(10)
        ).scalars().all()

        recent_events = db.execute(
            select(Event).order_by(desc(Event.timestamp)).limit(20)
        ).scalars().all()

        # Root cause distribution for pie chart
        from services.llm_analyzer import VALID_CATEGORIES
        cat_rows = db.execute(
            select(Alert.root_cause_category, func.count().label("cnt"))
            .group_by(Alert.root_cause_category)
        ).all()
        cat_map: dict[str, int] = {c: 0 for c in sorted(VALID_CATEGORIES)}
        for cat, cnt in cat_rows:
            key = cat if cat in VALID_CATEGORIES else "Unknown"
            cat_map[key] = cat_map.get(key, 0) + cnt
        rca_data = {
            "labels": list(cat_map.keys()),
            "values": list(cat_map.values()),
        }

        # Trends: hourly error / warning / total for the last 24h
        from models.event import Event as _Ev
        def _hourly_map(extra=None):
            q = (
                select(
                    func.strftime("%H:00", func.datetime(_Ev.timestamp, "localtime")).label("hr"),
                    func.count().label("cnt"),
                )
                .where(_Ev.timestamp >= since_24h)
                .group_by("hr").order_by("hr")
            )
            if extra is not None:
                q = q.where(extra)
            return {r.hr: r.cnt for r in db.execute(q).all()}

        total_map   = _hourly_map()
        error_map   = _hourly_map(_Ev.level.in_(["error", "critical"]))
        warning_map = _hourly_map(_Ev.level == "warn")
        trend_hours = sorted(total_map.keys())
        trends_data = {
            "labels":   trend_hours,
            "total":    [total_map.get(h, 0)   for h in trend_hours],
            "errors":   [error_map.get(h, 0)   for h in trend_hours],
            "warnings": [warning_map.get(h, 0) for h in trend_hours],
        }

        # Anomaly detection log — last 10 entries
        from models.anomaly_log import AnomalyLog
        log_rows = db.execute(
            select(AnomalyLog).order_by(desc(AnomalyLog.checked_at)).limit(10)
        ).scalars().all()
        anomaly_log_entries = [
            {
                "time": _to_ist(r.checked_at, "%H:%M:%S IST"),
                "source": r.source,
                "window_count": r.window_count,
                "error_count": r.error_count,
                "error_rate": round(r.error_count / r.window_count * 100, 1) if r.window_count else 0,
                "threshold": r.threshold,
                "status": "Anomaly" if r.is_anomaly else "Normal",
            }
            for r in log_rows
        ]

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "active": "dashboard",
                "stats": {
                    "total": total,
                    "errors": errors,
                    "open_alerts": open_alerts,
                    "sources": sources,
                },
                "level_data": level_data,
                "time_data": time_data,
                "rca_data": rca_data,
                "trends_data": trends_data,
                "anomaly_log": anomaly_log_entries,
                "perf": perf,
                "recent_alerts": recent_alerts,
                "recent_events": recent_events,
            },
        )
    finally:
        db.close()


@app.get("/ui/events", response_class=HTMLResponse)
def ui_events(
    request: Request,
    source: str | None = Query(None),
    level: str | None = Query(None),
):
    db = SessionLocal()
    try:
        q = select(Event).order_by(desc(Event.timestamp)).limit(200)
        if source:
            q = q.where(Event.source == source)
        if level:
            q = q.where(Event.level == level)
        evs = db.execute(q).scalars().all()
        total = db.scalar(select(func.count(Event.id))) or 0
        return templates.TemplateResponse(
            "events.html",
            {
                "request": request,
                "active": "events",
                "events": evs,
                "total": total,
                "filter_source": source,
                "filter_level": level,
            },
        )
    finally:
        db.close()


@app.get("/ui/alerts", response_class=HTMLResponse)
def ui_alerts(request: Request):
    db = SessionLocal()
    try:
        alts = db.execute(
            select(Alert).order_by(func.datetime(Alert.created_at).desc())
        ).scalars().all()
        return templates.TemplateResponse(
            "alerts.html",
            {"request": request, "active": "alerts", "alerts": alts},
        )
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
