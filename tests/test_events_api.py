"""
Integration tests for the POST /events/ and GET /events/ endpoints.

Uses the FastAPI TestClient with an in-memory DB (no live server required).
"""
import pytest


VALID_PAYLOAD = {
    "source": "test-service",
    "level": "error",
    "message": "Something went wrong",
    "value": 42.5,
    "tags": {"env": "test"},
}


class TestCreateEvent:
    def test_create_returns_201(self, client):
        r = client.post("/events/", json=VALID_PAYLOAD)
        assert r.status_code == 201

    def test_create_response_shape(self, client):
        r = client.post("/events/", json=VALID_PAYLOAD)
        body = r.json()
        assert body["source"] == "test-service"
        assert body["level"] == "error"
        assert body["message"] == "Something went wrong"
        assert body["value"] == pytest.approx(42.5)
        assert body["tags"] == {"env": "test"}
        assert "id" in body
        assert "timestamp" in body

    def test_create_normalises_level_to_lowercase(self, client):
        r = client.post("/events/", json={**VALID_PAYLOAD, "level": "ERROR"})
        assert r.status_code == 201
        assert r.json()["level"] == "error"

    def test_create_rejects_invalid_level(self, client):
        r = client.post("/events/", json={**VALID_PAYLOAD, "level": "debug"})
        assert r.status_code == 422

    def test_create_rejects_empty_source(self, client):
        r = client.post("/events/", json={**VALID_PAYLOAD, "source": "   "})
        assert r.status_code == 422

    def test_create_optional_value_is_nullable(self, client):
        payload = {**VALID_PAYLOAD, "value": None}
        r = client.post("/events/", json=payload)
        assert r.status_code == 201
        assert r.json()["value"] is None

    def test_create_optional_tags_is_nullable(self, client):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "tags"}
        r = client.post("/events/", json=payload)
        assert r.status_code == 201
        assert r.json()["tags"] is None

    def test_all_valid_levels_accepted(self, client):
        for level in ("info", "warn", "error", "critical"):
            r = client.post("/events/", json={**VALID_PAYLOAD, "level": level})
            assert r.status_code == 201, f"Level {level!r} was rejected"


class TestListEvents:
    def test_list_empty_initially(self, client):
        r = client.get("/events/")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_returns_created_event(self, client):
        client.post("/events/", json=VALID_PAYLOAD)
        r = client.get("/events/")
        assert len(r.json()) == 1

    def test_list_filter_by_level(self, client):
        client.post("/events/", json={**VALID_PAYLOAD, "level": "info"})
        client.post("/events/", json={**VALID_PAYLOAD, "level": "error"})
        r = client.get("/events/?level=info")
        assert all(e["level"] == "info" for e in r.json())
        assert len(r.json()) == 1

    def test_list_filter_by_source(self, client):
        client.post("/events/", json={**VALID_PAYLOAD, "source": "svc-a"})
        client.post("/events/", json={**VALID_PAYLOAD, "source": "svc-b"})
        r = client.get("/events/?source=svc-a")
        assert all(e["source"] == "svc-a" for e in r.json())

    def test_list_respects_limit(self, client):
        for _ in range(10):
            client.post("/events/", json=VALID_PAYLOAD)
        r = client.get("/events/?limit=3")
        assert len(r.json()) == 3

    def test_get_single_event_by_id(self, client):
        created = client.post("/events/", json=VALID_PAYLOAD).json()
        r = client.get(f"/events/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_get_nonexistent_event_returns_404(self, client):
        r = client.get("/events/999999")
        assert r.status_code == 404
