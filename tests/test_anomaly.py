"""
Unit tests for the anomaly detection engine (services/anomaly.py).

All tests run against an in-memory SQLite DB seeded directly — no HTTP layer.
"""
from datetime import datetime, timezone, timedelta

import pytest

from models.event import Event
from models.alert import Alert
from services.anomaly import detect_anomalies
from config import settings


def _make_event(db, source, level="error", message="test", minutes_ago=1, value=None):
    ev = Event(
        source=source,
        level=level,
        message=message,
        value=value,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db.add(ev)
    db.commit()
    return ev


# ── Spike detection ───────────────────────────────────────────────────────────

class TestSpikeDetection:
    def test_no_alert_below_threshold(self, db_session):
        """Fewer than 10 events in window → no spike alert."""
        for _ in range(5):
            _make_event(db_session, "api-gateway")
        alerts = detect_anomalies(db_session)
        spike_alerts = [a for a in alerts if a.rule == "spike"]
        assert len(spike_alerts) == 0

    def test_spike_alert_fires_at_threshold(self, db_session):
        """Exactly 10 events with zero baseline → spike alert created."""
        for _ in range(10):
            _make_event(db_session, "api-gateway")
        alerts = detect_anomalies(db_session)
        spike_alerts = [a for a in alerts if a.rule == "spike" and a.source == "api-gateway"]
        assert len(spike_alerts) == 1
        assert spike_alerts[0].severity == "high"
        assert "api-gateway" in spike_alerts[0].message

    def test_spike_alert_not_duplicated(self, db_session):
        """A second detection cycle does not create a duplicate open alert."""
        for _ in range(10):
            _make_event(db_session, "api-gateway")
        first = detect_anomalies(db_session)
        second = detect_anomalies(db_session)
        spike_alerts_second = [a for a in second if a.rule == "spike" and a.source == "api-gateway"]
        assert len(spike_alerts_second) == 0

    def test_spike_alert_refires_after_acknowledge(self, db_session):
        """After acknowledging the open alert a new one can be created."""
        for _ in range(10):
            _make_event(db_session, "auth-service")
        detect_anomalies(db_session)
        # Acknowledge the alert
        alert = db_session.query(Alert).filter_by(source="auth-service", rule="spike").first()
        alert.acknowledged = True
        db_session.commit()
        # More events — should fire again
        for _ in range(10):
            _make_event(db_session, "auth-service")
        new_alerts = detect_anomalies(db_session)
        new_spikes = [a for a in new_alerts if a.rule == "spike" and a.source == "auth-service"]
        assert len(new_spikes) == 1

    def test_spike_stores_source_and_rule(self, db_session):
        for _ in range(10):
            _make_event(db_session, "ml-pipeline")
        alerts = detect_anomalies(db_session)
        a = next(x for x in alerts if x.rule == "spike")
        assert a.source == "ml-pipeline"
        assert a.rule == "spike"


# ── Critical flood detection ──────────────────────────────────────────────────

class TestCriticalFloodDetection:
    def test_no_flood_below_threshold(self, db_session):
        for _ in range(9):
            _make_event(db_session, "db-proxy", level="critical")
        alerts = detect_anomalies(db_session)
        floods = [a for a in alerts if a.rule == "critical_flood"]
        assert len(floods) == 0

    def test_flood_alert_fires_at_ten_criticals(self, db_session):
        for _ in range(10):
            _make_event(db_session, "db-proxy", level="critical")
        alerts = detect_anomalies(db_session)
        floods = [a for a in alerts if a.rule == "critical_flood" and a.source == "db-proxy"]
        assert len(floods) == 1
        assert floods[0].severity == "critical"

    def test_non_critical_events_do_not_trigger_flood(self, db_session):
        for _ in range(15):
            _make_event(db_session, "db-proxy", level="error")
        alerts = detect_anomalies(db_session)
        floods = [a for a in alerts if a.rule == "critical_flood"]
        assert len(floods) == 0


# ── Metric snapshots ──────────────────────────────────────────────────────────

class TestMetricSnapshots:
    def test_metrics_written_for_active_sources(self, db_session):
        from models.metric import Metric
        _make_event(db_session, "payment-service", value=200.0)
        _make_event(db_session, "payment-service", value=400.0)
        detect_anomalies(db_session)
        snaps = db_session.query(Metric).filter_by(source="payment-service").all()
        assert len(snaps) >= 1
        assert snaps[0].avg_value == pytest.approx(300.0)
