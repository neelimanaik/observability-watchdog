"""
LLM-powered root cause analysis via Groq API.

Called after anomaly detection creates an alert. Fetches the N most recent
events for the affected source, formats them as a structured prompt, and
returns a concise human-readable analysis string to be stored on the Alert.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from config import settings
from models.event import Event

logger = logging.getLogger("watchdog.llm_analyzer")

_SYSTEM_PROMPT = (
    "You are an expert SRE (Site Reliability Engineer) analyzing application logs. "
    "Given a set of recent error events from a service, provide a concise root cause "
    "analysis in 2-3 sentences. Focus on the most likely cause and one actionable "
    "recommendation. Be direct and technical. Do not repeat the event list back."
)


def _fetch_recent_events(db: Session, source: str, window_minutes: int = 30, limit: int = 20) -> list[Event]:
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    return db.execute(
        select(Event)
        .where(Event.source == source, Event.timestamp >= since)
        .order_by(desc(Event.timestamp))
        .limit(limit)
    ).scalars().all()


def _build_user_prompt(source: str, alert_message: str, events: list[Event]) -> str:
    lines = [
        f"Alert triggered on service: {source}",
        f"Alert description: {alert_message}",
        "",
        f"Most recent events ({len(events)} shown):",
    ]
    for ev in events:
        ts = ev.timestamp.strftime("%H:%M:%S") if ev.timestamp else "unknown"
        val = f" [value={ev.value}]" if ev.value is not None else ""
        lines.append(f"  [{ts}] [{ev.level.upper()}] {ev.message}{val}")
    lines += [
        "",
        "Provide a root cause analysis and one actionable recommendation.",
    ]
    return "\n".join(lines)


def analyse_alert(db: Session, source: str, alert_message: str, rule: str) -> str | None:
    """
    Returns an LLM-generated root cause analysis string, or None if analysis
    is unavailable (no API key, quota exceeded, network error, etc.).
    """
    if not settings.groq_api_key or settings.groq_api_key == "your_groq_api_key_here":
        logger.debug("Groq API key not configured — skipping LLM analysis")
        return None

    try:
        from groq import Groq  # lazy import so missing key doesn't crash startup
        client = Groq(api_key=settings.groq_api_key)

        events = _fetch_recent_events(db, source)
        user_prompt = _build_user_prompt(source, alert_message, events)

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=settings.groq_max_tokens,
            temperature=0.3,
        )
        analysis = response.choices[0].message.content.strip()
        logger.info("LLM analysis complete for alert on '%s' (%s)", source, rule)
        return analysis

    except Exception as exc:  # noqa: BLE001
        logger.error("LLM analysis failed for '%s': %s", source, exc)
        return None
