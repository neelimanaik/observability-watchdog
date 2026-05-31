"""
Anomaly detection engine — spike detection + critical flood.

Suppression logic (10-minute window):
  - If an unacknowledged alert for the same rule+source was created within
    the last SUPPRESSION_WINDOW_MINUTES, suppress the new alert: skip DB
    insert and LLM call, but increment suppression_count on the existing alert.
  - If no recent alert exists, create a new one (with LLM analysis).
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from models.event import Event
from models.alert import Alert
from models.metric import Metric
from services.llm_analyzer import analyse_alert

SUPPRESSION_WINDOW_MINUTES = 10


def _window_bounds() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - timedelta(minutes=settings.anomaly_window_minutes), now


def _baseline_bounds(window_start: datetime) -> tuple[datetime, datetime]:
    width = timedelta(minutes=settings.anomaly_window_minutes)
    return window_start - width * 6, window_start


def _find_recent_alert(db: Session, rule: str, source: str) -> Alert | None:
    """Return the most recent unacknowledged alert for rule+source if it was
    created within the suppression window, otherwise None."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=SUPPRESSION_WINDOW_MINUTES)
    return db.scalar(
        select(Alert)
        .where(
            Alert.rule == rule,
            Alert.source == source,
            Alert.acknowledged == False,  # noqa: E712
            Alert.created_at >= cutoff,
        )
        .order_by(Alert.created_at.desc())
        .limit(1)
    )


def _suppress_alert(db: Session, alert: Alert) -> None:
    """Increment suppression_count on an existing alert instead of creating a new one."""
    alert.suppression_count += 1
    db.commit()


def _create_alert(
    db: Session,
    rule: str,
    source: str,
    message: str,
    severity: str,
    llm_analysis: str | None = None,
    root_cause_category: str | None = None,
) -> Alert:
    alert = Alert(
        rule=rule,
        source=source,
        message=message,
        severity=severity,
        llm_analysis=llm_analysis,
        root_cause_category=root_cause_category,
        suppression_count=0,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def _handle_rule(
    db: Session,
    rule: str,
    source: str,
    message: str,
    severity: str,
    created: list[Alert],
) -> None:
    """Create a new alert or suppress into an existing one — shared by both rules."""
    existing = _find_recent_alert(db, rule, source)
    if existing:
        _suppress_alert(db, existing)
    else:
        analysis, category = analyse_alert(db, source, message, rule)
        created.append(_create_alert(db, rule, source, message, severity, analysis, category))


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

        if current_count >= threshold:
            msg = (
                f"Event spike on '{source}': {current_count} events in last "
                f"{settings.anomaly_window_minutes}m (baseline ~{baseline_per_window:.1f}/window)"
            )
            _handle_rule(db, "spike", source, msg, "high", created)

        critical_count = db.scalar(
            select(func.count()).where(
                Event.source == source,
                Event.level == "critical",
                Event.timestamp >= window_start,
                Event.timestamp < window_end,
            )
        ) or 0

        if critical_count >= 10:
            msg = (
                f"Critical flood on '{source}': {critical_count} critical events "
                f"in {settings.anomaly_window_minutes}m"
            )
            _handle_rule(db, "critical_flood", source, msg, "critical", created)

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
