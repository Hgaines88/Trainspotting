import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

from app import database
from app.database import PortableConnection
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
    assert set(response.json()) == {
        "requests",
        "request_latency_ms",
        "database_operations",
        "database_latency_ms",
        "transactions",
        "transaction_duration_ms",
        "moderation_events",
        "connection_pool",
    }


def test_portable_connection_records_bounded_database_metrics():
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=QueuePool)
    connection = PortableConnection(engine.connect(), engine, "mysql")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO example (id) VALUES (?)", (1,))
        connection.commit()
        assert connection.execute(
            "SELECT id FROM example WHERE id = ?",
            (1,),
        ).fetchone()[0] == 1
    finally:
        connection.close()
        engine.dispose()

    snapshot = service_metrics.snapshot()
    operations = {
        (item["operation"], item["outcome"]): item["count"]
        for item in snapshot["database_operations"]
    }
    assert operations[("CREATE", "success")] == 1
    assert operations[("INSERT", "success")] == 1
    assert operations[("COMMIT", "success")] == 1
    assert operations[("SELECT", "success")] == 1
    assert snapshot["transactions"] == [
        {"backend": "mysql", "outcome": "committed", "count": 1}
    ]
    assert snapshot["connection_pool"]["checked_out"] == 0
    assert "example" not in str(snapshot)


def test_database_errors_are_counted_without_sql_text():
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=QueuePool)
    connection = PortableConnection(engine.connect(), engine, "mysql")
    try:
        with pytest.raises(Exception):
            connection.execute("SELECT private_value FROM secret_table")
    finally:
        connection.close()
        engine.dispose()

    snapshot = service_metrics.snapshot()
    assert {
        (item["operation"], item["outcome"], item["count"])
        for item in snapshot["database_operations"]
    } == {("SELECT", "error", 1)}
    assert "private_value" not in str(snapshot)
    assert "secret_table" not in str(snapshot)


def test_implicit_write_transaction_is_timed():
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=QueuePool)
    connection = PortableConnection(engine.connect(), engine, "mysql")
    try:
        connection.execute("CREATE TABLE account (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()
        engine.dispose()

    assert service_metrics.snapshot()["transactions"] == [
        {"backend": "mysql", "outcome": "committed", "count": 1}
    ]
