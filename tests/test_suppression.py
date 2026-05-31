"""
Tests for alert suppression logic (services/anomaly.py).

Verifies that a second identical alert within the 10-minute suppression
window is not written to the DB — instead, suppression_count is incremented
on the existing alert and the LLM is not called again.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from models.event import Event
from models.alert import Alert
from services.anomaly import detect_anomalies, SUPPRESSION_WINDOW_MINUTES


def _seed_spike_events(db, source, n=10):
    """Seed enough events to cross the spike threshold (baseline = 0, min = 10)."""
    for i in range(n):
        ev = Event(
            source=source,
            level="error",
            message=f"Error #{i}",
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=i * 5),
        )
        db.add(ev)
    db.commit()


class TestAlertSuppression:
    def test_second_detection_within_window_suppresses(self, db_session):
        """Two detection cycles within 10 min → 1 alert, suppression_count=1."""
        _seed_spike_events(db_session, "api-gateway")

        first = detect_anomalies(db_session)
        assert len(first) == 1, "First cycle should create one alert"

        second = detect_anomalies(db_session)
        assert len(second) == 0, "Second cycle within window should be suppressed"

        all_alerts = db_session.query(Alert).filter_by(source="api-gateway", rule="spike").all()
        assert len(all_alerts) == 1, "Only one DB record should exist"
        assert all_alerts[0].suppression_count == 1

    def test_suppression_count_increments_each_cycle(self, db_session):
        """Three cycles within window → suppression_count = 2."""
        _seed_spike_events(db_session, "auth-service")

        detect_anomalies(db_session)   # creates alert
        detect_anomalies(db_session)   # suppression_count → 1
        detect_anomalies(db_session)   # suppression_count → 2

        alert = db_session.query(Alert).filter_by(source="auth-service", rule="spike").one()
        assert alert.suppression_count == 2

    def test_llm_not_called_on_suppression(self, db_session):
        """LLM analyser must only be invoked for new alerts, not suppressed ones."""
        _seed_spike_events(db_session, "ml-pipeline")

        with patch("services.anomaly.analyse_alert") as mock_llm:
            mock_llm.return_value = "mock analysis"
            detect_anomalies(db_session)   # creates → LLM called once
            detect_anomalies(db_session)   # suppressed → LLM must NOT be called again

        assert mock_llm.call_count == 1, (
            f"LLM called {mock_llm.call_count} times; expected exactly 1"
        )

    def test_alert_fires_after_suppression_window_expires(self, db_session):
        """An alert older than the suppression window allows a new alert to be created."""
        _seed_spike_events(db_session, "db-proxy")

        # Create an alert that is artificially aged beyond the suppression window
        detect_anomalies(db_session)
        old_alert = db_session.query(Alert).filter_by(source="db-proxy", rule="spike").one()
        old_alert.created_at = (
            datetime.now(timezone.utc) - timedelta(minutes=SUPPRESSION_WINDOW_MINUTES + 1)
        )
        db_session.commit()

        new_alerts = detect_anomalies(db_session)
        assert len(new_alerts) == 1, "A new alert should fire after the suppression window expires"

        all_alerts = db_session.query(Alert).filter_by(source="db-proxy", rule="spike").all()
        assert len(all_alerts) == 2, "Two separate alert records should exist"

    def test_suppression_count_zero_on_new_alert(self, db_session):
        """A freshly created alert starts with suppression_count = 0."""
        _seed_spike_events(db_session, "payment-service")
        alerts = detect_anomalies(db_session)
        assert alerts[0].suppression_count == 0

    def test_suppression_is_per_rule(self, db_session):
        """Suppression is scoped to rule+source: spike and critical_flood are independent."""
        # Seed enough events to trigger both rules simultaneously
        for i in range(15):
            level = "critical" if i < 10 else "error"
            db_session.add(Event(
                source="mixed-svc",
                level=level,
                message=f"msg {i}",
                timestamp=datetime.now(timezone.utc) - timedelta(seconds=i),
            ))
        db_session.commit()

        first = detect_anomalies(db_session)
        rules_first = {a.rule for a in first}
        assert "spike" in rules_first
        assert "critical_flood" in rules_first

        second = detect_anomalies(db_session)
        assert len(second) == 0, "Both rules suppressed independently on second cycle"

        spike = db_session.query(Alert).filter_by(source="mixed-svc", rule="spike").one()
        flood = db_session.query(Alert).filter_by(source="mixed-svc", rule="critical_flood").one()
        assert spike.suppression_count == 1
        assert flood.suppression_count == 1

    def test_acknowledged_alert_does_not_suppress(self, db_session):
        """An acknowledged alert is not within the suppression window — new alert fires."""
        _seed_spike_events(db_session, "svc-x")

        detect_anomalies(db_session)
        alert = db_session.query(Alert).filter_by(source="svc-x", rule="spike").one()
        alert.acknowledged = True
        db_session.commit()

        new = detect_anomalies(db_session)
        assert len(new) == 1, "Acknowledged alert should not block a new one"
