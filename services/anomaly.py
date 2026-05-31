"""
Anomaly detection engine — spike detection + critical flood.
Each new alert is enriched with LLM root cause analysis via Groq.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from models.event import Event
from models.alert import Alert
from models.metric import Metric
from services.llm_analyzer import analyse_alert


def _window_bounds() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - timedelta(minutes=settings.anomaly_window_minutes), now


def _baseline_bounds(window_start: datetime) -> tuple[datetime, datetime]:
    width = timedelta(minutes=settings.anomaly_window_minutes)
    return window_start - width * 6, window_start


def _open_alert_exists(db: Session, rule: str, source: str) -> bool:
    return db.scalar(
        select(Alert).where(
            Alert.rule == rule,
            Alert.source == source,
            Alert.acknowledged == False,  # noqa: E712
        )
    ) is not None


def _create_alert(
    db: Session,
    rule: str,
    source: str,
    message: str,
    severity: str,
    llm_analysis: str | None = None,
) -> Alert:
    alert = Alert(
        rule=rule,
        source=source,
        message=message,
        severity=severity,
        llm_analysis=llm_analysis,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def detect_anomalies(db: Session) -> list[Alert]:
    window_start, window_end = _window_bounds()
    baseline_start, baseline_end = _baseline_bounds(window_start)
    created: list[Alert] = []

    current_q = (
        select(Event.source, func.count().label("cnt"))
        .where(Event.timestamp >= window_start, Event.timestamp < window_end)
        .group_by(Event.source)
    )
    current_rows = db.execute(current_q).all()

    for source, current_count in current_rows:
        baseline_count = db.scalar(
            select(func.count()).where(
                Event.source == source,
                Event.timestamp >= baseline_start,
                Event.timestamp < baseline_end,
            )
        ) or 0

        baseline_per_window = baseline_count / 6 if baseline_count else 0
        threshold = max(baseline_per_window * settings.anomaly_spike_multiplier, 10)

        if current_count >= threshold and not _open_alert_exists(db, "spike", source):
            msg = (
                f"Event spike on '{source}': {current_count} events in last "
                f"{settings.anomaly_window_minutes}m (baseline ~{baseline_per_window:.1f}/window)"
            )
            analysis = analyse_alert(db, source, msg, "spike")
            created.append(_create_alert(db, "spike", source, msg, "high", analysis))

        critical_count = db.scalar(
            select(func.count()).where(
                Event.source == source,
                Event.level == "critical",
                Event.timestamp >= window_start,
                Event.timestamp < window_end,
            )
        ) or 0

        if critical_count >= 10 and not _open_alert_exists(db, "critical_flood", source):
            msg = (
                f"Critical flood on '{source}': {critical_count} critical events "
                f"in {settings.anomaly_window_minutes}m"
            )
            analysis = analyse_alert(db, source, msg, "critical_flood")
            created.append(_create_alert(db, "critical_flood", source, msg, "critical", analysis))

    for source, current_count in current_rows:
        avg_val = db.scalar(
            select(func.avg(Event.value)).where(
                Event.source == source,
                Event.timestamp >= window_start,
                Event.timestamp < window_end,
                Event.value.is_not(None),
            )
        )
        snap = Metric(
            source=source,
            level="all",
            count=current_count,
            avg_value=avg_val,
            window_start=window_start,
            window_end=window_end,
        )
        db.add(snap)
    db.commit()

    return created
