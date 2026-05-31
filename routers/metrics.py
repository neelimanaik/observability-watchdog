from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from database import get_db
from models.metric import Metric
from models.alert import Alert
from models.event import Event
from models.anomaly_log import AnomalyLog
from services.llm_analyzer import VALID_CATEGORIES

router = APIRouter(prefix="/metrics", tags=["metrics"])


class MetricOut(BaseModel):
    id: int
    source: str
    level: str
    count: int
    avg_value: float | None
    window_start: str
    window_end: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[MetricOut])
def list_metrics(
    source: str | None = Query(None),
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
):
    q = select(Metric).order_by(desc(Metric.window_end)).limit(limit)
    if source:
        q = q.where(Metric.source == source)
    rows = db.execute(q).scalars().all()
    return [
        MetricOut(
            id=r.id,
            source=r.source,
            level=r.level,
            count=r.count,
            avg_value=r.avg_value,
            window_start=r.window_start.isoformat(),
            window_end=r.window_end.isoformat(),
        )
        for r in rows
    ]


@router.get("/trends")
def trends(db: Session = Depends(get_db)) -> dict:
    """
    Hourly bucketed counts for the last 24 hours split into three series:
    total, errors (error+critical), and warnings.
    """
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    def _hourly(extra_filters=()):
        q = (
            select(
                func.strftime("%H:00", func.datetime(Event.timestamp, "localtime")).label("hour"),
                func.count().label("cnt"),
            )
            .where(Event.timestamp >= since_24h)
            .group_by("hour")
            .order_by("hour")
        )
        for f in extra_filters:
            q = q.where(f)
        return {r.hour: r.cnt for r in db.execute(q).all()}

    total_map   = _hourly()
    error_map   = _hourly([Event.level.in_(["error", "critical"])])
    warning_map = _hourly([Event.level == "warn"])

    hours = sorted(total_map.keys())
    return {
        "labels":   hours,
        "total":    [total_map.get(h, 0) for h in hours],
        "errors":   [error_map.get(h, 0) for h in hours],
        "warnings": [warning_map.get(h, 0) for h in hours],
    }


@router.get("/anomaly-log")
def anomaly_log(
    limit: int = Query(10, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Returns the last N anomaly detection log entries across all sources."""
    rows = db.execute(
        select(AnomalyLog)
        .order_by(desc(AnomalyLog.checked_at))
        .limit(limit)
    ).scalars().all()
    return [
        {
            "time": r.checked_at.strftime("%H:%M:%S"),
            "source": r.source,
            "window_count": r.window_count,
            "error_count": r.error_count,
            "error_rate": (
                round(r.error_count / r.window_count * 100, 1)
                if r.window_count > 0 else 0.0
            ),
            "threshold": r.threshold,
            "status": "Anomaly" if r.is_anomaly else "Normal",
        }
        for r in rows
    ]


@router.get("/root-cause-distribution")
def root_cause_distribution(db: Session = Depends(get_db)) -> dict[str, int]:
    """Returns count of alerts per root_cause_category across all alerts."""
    rows = db.execute(
        select(Alert.root_cause_category, func.count().label("cnt"))
        .group_by(Alert.root_cause_category)
    ).all()
    # Seed all valid categories with 0, then fill from DB
    dist: dict[str, int] = {cat: 0 for cat in sorted(VALID_CATEGORIES)}
    for category, count in rows:
        key = category if category in VALID_CATEGORIES else "Unknown"
        dist[key] = dist.get(key, 0) + count
    return dist
