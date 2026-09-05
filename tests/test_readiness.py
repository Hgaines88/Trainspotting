import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app


def test_sqlite_readiness_is_read_only(tmp_path, monkeypatch):
    database_path = tmp_path / "ready.db"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE designers (id INTEGER PRIMARY KEY)")
    connection.execute(
        "CREATE TABLE archive_state (id INTEGER PRIMARY KEY, version INTEGER NOT NULL)"
    )
    connection.execute("INSERT INTO archive_state (id, version) VALUES (1, 1)")
    connection.commit()
    connection.close()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)

    assert database.database_readiness() == {
        "database": "sqlite",
        "revision": "legacy-current",
    }


@pytest.mark.parametrize(
    "ledger_sql",
    [
        None,
        "CREATE TABLE archive_state "
        "(id INTEGER PRIMARY KEY, version INTEGER NOT NULL)",
    ],
)
def test_sqlite_readiness_requires_initialized_archive_ledger(
    tmp_path, monkeypatch, ledger_sql
):
    database_path = tmp_path / "incomplete.db"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE designers (id INTEGER PRIMARY KEY)")
    if ledger_sql:
        connection.execute(ledger_sql)
    connection.commit()
    connection.close()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)

    with pytest.raises(RuntimeError, match="archive"):
        database.database_readiness()


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
