"""
Tests for services/llm_analyzer.py — focuses on graceful degradation
and prompt construction without making live API calls.
"""
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import pytest

from models.event import Event
from services.llm_analyzer import analyse_alert, _build_user_prompt, _fetch_recent_events


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


# ── Graceful fallback ─────────────────────────────────────────────────────────

class TestGracefulFallback:
    def test_returns_none_when_key_not_set(self, db_session):
        """No API key → None, no exception."""
        with patch("config.settings.groq_api_key", ""):
            result = analyse_alert(db_session, "svc", "spike detected", "spike")
        assert result is None

    def test_returns_none_when_key_is_placeholder(self, db_session):
        """Placeholder key → None, no exception."""
        with patch("config.settings.groq_api_key", "your_groq_api_key_here"):
            result = analyse_alert(db_session, "svc", "spike detected", "spike")
        assert result is None

    def test_returns_none_on_api_error(self, db_session):
        """Groq API raises → None returned, no exception propagated."""
        _seed_events(db_session, "payment-service")
        with patch("config.settings.groq_api_key", "sk-fake-key"), \
             patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.side_effect = RuntimeError("quota exceeded")
            result = analyse_alert(db_session, "payment-service", "spike detected", "spike")
        assert result is None

    def test_returns_none_on_network_error(self, db_session):
        """Network failure → None, not a crash."""
        _seed_events(db_session, "auth-service")
        with patch("config.settings.groq_api_key", "sk-fake-key"), \
             patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.side_effect = ConnectionError("unreachable")
            result = analyse_alert(db_session, "auth-service", "flood detected", "critical_flood")
        assert result is None


# ── Successful path (mocked API) ─────────────────────────────────────────────

class TestSuccessPath:
    def test_returns_llm_content_on_success(self, db_session):
        _seed_events(db_session, "ml-pipeline")
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Root cause: memory leak."

        with patch("config.settings.groq_api_key", "sk-real-key"), \
             patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.return_value = mock_response
            result = analyse_alert(db_session, "ml-pipeline", "spike detected", "spike")

        assert result == "Root cause: memory leak."

    def test_strips_whitespace_from_response(self, db_session):
        _seed_events(db_session, "db-proxy")
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "  Analysis here.  \n"

        with patch("config.settings.groq_api_key", "sk-real-key"), \
             patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.return_value = mock_response
            result = analyse_alert(db_session, "db-proxy", "flood detected", "critical_flood")

        assert result == "Analysis here."


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

    def test_fetch_returns_only_recent_events(self, db_session):
        # One fresh event, one old event outside the 30-min window
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
