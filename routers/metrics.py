from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from database import get_db
from models.metric import Metric
from models.alert import Alert
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
