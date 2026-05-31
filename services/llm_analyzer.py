"""
LLM-powered root cause analysis via Groq API.

Returns a (analysis, category) tuple.  Both elements are None when the
API key is absent or the call fails, so callers must handle None gracefully.

Category is one of the VALID_CATEGORIES set; anything the model returns
outside that set is normalised to "Unknown".
"""
import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from config import settings
from models.event import Event

logger = logging.getLogger("watchdog.llm_analyzer")

VALID_CATEGORIES = {"Database", "Network", "Authentication", "Memory/Resource", "Application", "Unknown"}

_SYSTEM_PROMPT = (
    "You are an expert SRE (Site Reliability Engineer) analyzing application logs. "
    "Given a set of recent error events from a service, respond with ONLY a JSON object "
    "— no markdown, no code fences, no extra text — in this exact format:\n"
    '{"category": "<category>", "analysis": "<analysis>"}\n'
    "Where:\n"
    "  category: exactly one of: Database, Network, Authentication, Memory/Resource, Application, Unknown\n"
    "  analysis: 2-3 sentences identifying the most likely root cause and one actionable recommendation.\n"
    "Be direct and technical. Do not repeat the event list back."
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
        'Respond with ONLY the JSON object: {"category": "...", "analysis": "..."}',
    ]
    return "\n".join(lines)


def _parse_llm_response(raw: str) -> tuple[str | None, str | None]:
    """Parse raw LLM output into (analysis, category). Returns (None, None) on parse failure."""
    raw = raw.strip()
    # Strip markdown code fences if the model adds them despite instructions
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    try:
        data = json.loads(raw)
        analysis = str(data.get("analysis", "")).strip() or None
        category = str(data.get("category", "")).strip()
        if category not in VALID_CATEGORIES:
            category = "Unknown"
        return analysis, category
    except (json.JSONDecodeError, AttributeError):
        # Model ignored instructions and returned plain text — treat full text as analysis
        logger.warning("LLM returned non-JSON response; using as plain analysis text")
        return raw if raw else None, "Unknown"


def analyse_alert(
    db: Session, source: str, alert_message: str, rule: str
) -> tuple[str | None, str | None]:
    """
    Returns (analysis_text, category) from Groq, or (None, None) when
    the API key is absent, is the placeholder, or the call fails.
    """
    if not settings.groq_api_key or settings.groq_api_key == "your_groq_api_key_here":
        logger.debug("Groq API key not configured — skipping LLM analysis")
        return None, None

    try:
        from groq import Groq
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
        raw = response.choices[0].message.content
        analysis, category = _parse_llm_response(raw)
        logger.info(
            "LLM analysis complete for '%s' (%s): category=%s", source, rule, category
        )
        return analysis, category

    except Exception as exc:  # noqa: BLE001
        logger.error("LLM analysis failed for '%s': %s", source, exc)
        return None, None
