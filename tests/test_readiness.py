import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app


def test_sqlite_readiness_is_read_only(tmp_path, monkeypatch):
    database_path = tmp_path / "ready.db"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE designers (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)

    assert database.database_readiness() == {
        "database": "sqlite",
        "revision": "legacy-current",
    }


def test_readiness_endpoint_fails_closed(monkeypatch):
    def unavailable():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.main.database_readiness", unavailable)
    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not ready."}


def test_replica_startup_can_disable_automatic_migrations(monkeypatch):
    migration_calls = []
    monkeypatch.setenv("AUTO_MIGRATE_DATABASE", "false")
    monkeypatch.setattr(
        "app.main.apply_migrations", lambda: migration_calls.append(True)
    )

    with TestClient(app):
        pass

    assert migration_calls == []
