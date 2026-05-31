"""
Tests for services/llm_analyzer.py — focuses on graceful degradation
and prompt construction without making live API calls.

analyse_alert() now returns (analysis: str | None, category: str | None).
"""
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import json

import pytest

from models.event import Event
from services.llm_analyzer import analyse_alert, _build_user_prompt, _fetch_recent_events, VALID_CATEGORIES


def _seed_events(db, source, n=5, level="error"):
    for i in range(n):
        ev = Event(
            source=source,
            level=level,
            message=f"Test error #{i}",
            value=float(i * 10),
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=i),
        )
        db.add(ev)
    db.commit()


def _mock_json_response(analysis: str, category: str = "Application") -> MagicMock:
    """Build a mock Groq response that returns valid JSON."""
    m = MagicMock()
    m.choices[0].message.content = json.dumps({"category": category, "analysis": analysis})
    return m


# ── Graceful fallback ─────────────────────────────────────────────────────────

class TestGracefulFallback:
    def test_returns_none_when_key_not_set(self, db_session):
        """No API key → (None, None), no exception."""
        with patch("config.settings.groq_api_key", ""):
            analysis, category = analyse_alert(db_session, "svc", "spike detected", "spike")
        assert analysis is None
        assert category is None

    def test_returns_none_when_key_is_placeholder(self, db_session):
        """Placeholder key → (None, None), no exception."""
        with patch("config.settings.groq_api_key", "your_groq_api_key_here"):
            analysis, category = analyse_alert(db_session, "svc", "spike detected", "spike")
        assert analysis is None
        assert category is None

    def test_returns_none_on_api_error(self, db_session):
        """Groq API raises → (None, None), no exception propagated."""
        _seed_events(db_session, "payment-service")
        with patch("config.settings.groq_api_key", "sk-fake-key"), \
             patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.side_effect = RuntimeError("quota exceeded")
            analysis, category = analyse_alert(db_session, "payment-service", "spike detected", "spike")
        assert analysis is None
        assert category is None

    def test_returns_none_on_network_error(self, db_session):
        """Network failure → (None, None), not a crash."""
        _seed_events(db_session, "auth-service")
        with patch("config.settings.groq_api_key", "sk-fake-key"), \
             patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.side_effect = ConnectionError("unreachable")
            analysis, category = analyse_alert(db_session, "auth-service", "flood detected", "critical_flood")
        assert analysis is None
        assert category is None


# ── Successful path (mocked API) ─────────────────────────────────────────────

class TestSuccessPath:
    def test_returns_llm_content_on_success(self, db_session):
        _seed_events(db_session, "ml-pipeline")

        with patch("config.settings.groq_api_key", "sk-real-key"), \
             patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.return_value = (
                _mock_json_response("Root cause: memory leak.", "Memory/Resource")
            )
            analysis, category = analyse_alert(db_session, "ml-pipeline", "spike detected", "spike")

        assert analysis == "Root cause: memory leak."
        assert category == "Memory/Resource"

    def test_strips_whitespace_from_analysis(self, db_session):
        _seed_events(db_session, "db-proxy")

        with patch("config.settings.groq_api_key", "sk-real-key"), \
             patch("groq.Groq") as MockGroq:
            m = MagicMock()
            m.choices[0].message.content = json.dumps({
                "category": "Database",
                "analysis": "  Analysis here.  "
            })
            MockGroq.return_value.chat.completions.create.return_value = m
            analysis, category = analyse_alert(db_session, "db-proxy", "flood detected", "critical_flood")

        assert analysis == "Analysis here."
        assert category == "Database"

    def test_invalid_category_falls_back_to_unknown(self, db_session):
        """Category value outside VALID_CATEGORIES is normalised to 'Unknown'."""
        _seed_events(db_session, "svc-z")

        with patch("config.settings.groq_api_key", "sk-real-key"), \
             patch("groq.Groq") as MockGroq:
            m = MagicMock()
            m.choices[0].message.content = json.dumps({
                "category": "Cosmic Ray",
                "analysis": "Some analysis."
            })
            MockGroq.return_value.chat.completions.create.return_value = m
            analysis, category = analyse_alert(db_session, "svc-z", "spike", "spike")

        assert category == "Unknown"
        assert analysis == "Some analysis."

    def test_plain_text_response_handled_gracefully(self, db_session):
        """If model ignores JSON instructions, plain text becomes analysis with Unknown category."""
        _seed_events(db_session, "svc-plain")

        with patch("config.settings.groq_api_key", "sk-real-key"), \
             patch("groq.Groq") as MockGroq:
            m = MagicMock()
            m.choices[0].message.content = "The DB is down."
            MockGroq.return_value.chat.completions.create.return_value = m
            analysis, category = analyse_alert(db_session, "svc-plain", "spike", "spike")

        assert analysis == "The DB is down."
        assert category == "Unknown"

    def test_all_valid_categories_accepted(self, db_session):
        """Every category in VALID_CATEGORIES is passed through unchanged."""
        _seed_events(db_session, "svc-cats")
        for cat in VALID_CATEGORIES:
            with patch("config.settings.groq_api_key", "sk-real-key"), \
                 patch("groq.Groq") as MockGroq:
                MockGroq.return_value.chat.completions.create.return_value = (
                    _mock_json_response("Analysis text.", cat)
                )
                _, returned_cat = analyse_alert(db_session, "svc-cats", "spike", "spike")
            assert returned_cat == cat, f"Category {cat!r} was not returned correctly"


# ── Prompt construction ───────────────────────────────────────────────────────

class TestPromptConstruction:
    def test_prompt_includes_source_and_alert_message(self, db_session):
        _seed_events(db_session, "api-gateway")
        events = _fetch_recent_events(db_session, "api-gateway")
        prompt = _build_user_prompt("api-gateway", "spike: 20 events", events)
        assert "api-gateway" in prompt
        assert "spike: 20 events" in prompt

    def test_prompt_includes_event_messages(self, db_session):
        _seed_events(db_session, "api-gateway")
        events = _fetch_recent_events(db_session, "api-gateway")
        prompt = _build_user_prompt("api-gateway", "spike", events)
        assert "Test error #0" in prompt

    def test_prompt_requests_json(self, db_session):
        """Prompt must include a JSON format instruction."""
        _seed_events(db_session, "svc-json")
        events = _fetch_recent_events(db_session, "svc-json")
        prompt = _build_user_prompt("svc-json", "spike", events)
        assert "JSON" in prompt or "json" in prompt

    def test_fetch_returns_only_recent_events(self, db_session):
        fresh = Event(
            source="svc-x", level="error", message="fresh",
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        old = Event(
            source="svc-x", level="error", message="old",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db_session.add_all([fresh, old])
        db_session.commit()

        events = _fetch_recent_events(db_session, "svc-x")
        messages = [e.message for e in events]
        assert "fresh" in messages
        assert "old" not in messages

    def test_fetch_respects_limit(self, db_session):
        _seed_events(db_session, "svc-y", n=25)
        events = _fetch_recent_events(db_session, "svc-y", limit=10)
        assert len(events) <= 10
