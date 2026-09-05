import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import database
from app.auth import ClerkIdentity, require_authenticated_user
from app.main import app
from app.observability import logger, request_id, service_metrics


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def public_client(tmp_path, monkeypatch):
    database_path = tmp_path / "observability.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    connection = database.connect()
    try:
        connection.executescript(
            (PROJECT_ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
        )
        connection.executescript(
            (PROJECT_ROOT / "sql" / "seed.sql").read_text(encoding="utf-8")
        )
    finally:
        connection.close()

    with TestClient(app) as client:
        yield client


def test_request_ids_accept_safe_values_and_replace_unsafe_values():
    assert logger.level == logging.INFO
    assert request_id("trace_123.test") == "trace_123.test"
    generated = request_id("unsafe value with spaces")
    assert len(generated) == 32
    assert generated.isalnum()


def test_request_log_uses_route_template_without_query_or_identity(
    public_client,
    caplog,
):
    caplog.set_level(logging.INFO, logger="trainspotting.operations")

    response = public_client.get(
        "/designers/1?private=value",
        headers={
            "X-Request-ID": "safe-request-1",
            "Authorization": "Bearer secret-session-token",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "safe-request-1"
    payload = json.loads(caplog.records[-1].message)
    assert payload["route"] == "/designers/{designer_id}"
    assert payload["request_id"] == "safe-request-1"
    serialized = json.dumps(payload)
    assert "private=value" not in serialized
    assert "secret-session-token" not in serialized


def test_service_metrics_aggregate_status_and_latency_by_route_template(
    public_client,
):
    assert public_client.get("/designers/1").status_code == 200
    assert public_client.get("/designers/999999").status_code == 404

    snapshot = service_metrics.snapshot()
    matching = [
        item
        for item in snapshot["requests"]
        if item["route"] == "/designers/{designer_id}"
    ]

    assert {(item["status_code"], item["count"]) for item in matching} == {
        (200, 1),
        (404, 1),
    }
    latency = next(
        item
        for item in snapshot["request_latency_ms"]
        if item["route"] == "/designers/{designer_id}"
    )
    assert latency["sum_ms"] >= 0
    assert latency["buckets"]["+Inf"] == 2


def test_metrics_endpoint_requires_an_administrator(public_client):
    assert public_client.get("/operations/metrics").status_code == 401

    app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
        user_id="user_metrics_member",
        session_id="session_metrics_member",
    )
    connection = database.connect()
    try:
        connection.execute(
            "INSERT INTO users (clerk_user_id, role) VALUES (?, ?)",
            ("user_metrics_member", "member"),
        )
        connection.commit()
    finally:
        connection.close()

    try:
        assert public_client.get("/operations/metrics").status_code == 403
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)


def test_metrics_endpoint_returns_aggregates_to_an_administrator(
    public_client,
):
    app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
        user_id="user_metrics_admin",
        session_id="session_metrics_admin",
    )
    connection = database.connect()
    try:
        connection.execute(
            "INSERT INTO users (clerk_user_id, role) VALUES (?, ?)",
            ("user_metrics_admin", "admin"),
        )
        connection.commit()
    finally:
        connection.close()

    try:
        response = public_client.get("/operations/metrics")
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)

    assert response.status_code == 200
    assert set(response.json()) == {"requests", "request_latency_ms"}
