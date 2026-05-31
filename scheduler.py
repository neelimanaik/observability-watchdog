import logging
from apscheduler.schedulers.background import BackgroundScheduler

from config import settings
from database import SessionLocal
from services.anomaly import detect_anomalies
from services.notifier import dispatch

logger = logging.getLogger("watchdog.scheduler")
_scheduler = BackgroundScheduler()


def _run_detection() -> None:
    db = SessionLocal()
    try:
        alerts = detect_anomalies(db)
        for alert in alerts:
            dispatch(alert)
        if alerts:
            logger.info("Detection cycle complete — %d new alert(s)", len(alerts))
    except Exception as exc:  # noqa: BLE001
        logger.error("Detection cycle error: %s", exc)
    finally:
        db.close()


def start_scheduler() -> None:
    _scheduler.add_job(
        _run_detection,
        "interval",
        seconds=settings.scheduler_interval_seconds,
        id="anomaly_detection",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — detection every %ds", settings.scheduler_interval_seconds
    )


def stop_scheduler() -> None:
    _scheduler.shutdown(wait=False)
