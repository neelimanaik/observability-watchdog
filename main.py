import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, desc

from config import settings
from database import init_db, SessionLocal
from models.event import Event
from models.alert import Alert
from routers import events, alerts, metrics
from scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

templates = Jinja2Templates(directory="templates")


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

        recent_alerts = db.execute(
            select(Alert).order_by(desc(Alert.created_at)).limit(10)
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
            select(Alert).order_by(desc(Alert.created_at))
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
