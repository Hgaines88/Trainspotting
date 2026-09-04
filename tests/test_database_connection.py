import sqlite3

import pytest

from app import database


PROJECT_ROOT = database.PROJECT_ROOT


def test_connection_enables_and_verifies_sqlite_safety_settings(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "safety.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)

    connection = database.connect()
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5_000
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_connection_closes_if_wal_cannot_be_enabled(tmp_path, monkeypatch):
    connection = sqlite3.connect(":memory:")
    close_calls = 0

    class ConnectionWithoutWal:
        row_factory = None

        def execute(self, sql):
            return connection.execute(sql)

        def close(self):
            nonlocal close_calls
            close_calls += 1
            connection.close()

    with pytest.raises(RuntimeError, match="WAL mode unavailable"):
        database.configure_connection(ConnectionWithoutWal())

    assert close_calls == 1


def test_connection_honors_sqlite_database_url_override(tmp_path, monkeypatch):
    override_path = tmp_path / "override.db"
    ignored_default_path = tmp_path / "ignored-default.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{override_path}")
    monkeypatch.setattr(database, "DATABASE_PATH", ignored_default_path)

    connection = database.connect()
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS check_override (id INTEGER)")
        connection.commit()
    finally:
        connection.close()

    assert override_path.exists()
    assert not ignored_default_path.exists()


def test_public_read_succeeds_during_representative_moderation_write(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "concurrency.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    setup = database.connect()
    try:
        setup.executescript((PROJECT_ROOT / "sql" / "schema.sql").read_text())
        setup.executescript((PROJECT_ROOT / "sql" / "seed.sql").read_text())
        setup.execute(
            "INSERT INTO users (clerk_user_id, role) VALUES (?, ?)",
            ("user_concurrent_member", "member"),
        )
        setup.commit()
    finally:
        setup.close()

    writer = database.connect()
    reader = database.connect()
    try:
        submitter_id = writer.execute(
            "SELECT id FROM users WHERE clerk_user_id = ?",
            ("user_concurrent_member",),
        ).fetchone()[0]
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            """
            INSERT INTO submissions (
                submitter_user_id, record_type, submission_type,
                status, proposed_data, explanation
            ) VALUES (?, 'designer', 'addition', 'draft', ?, ?)
            """,
            (submitter_id, '{"full_name":"Concurrent Designer"}', "Concurrency test"),
        )

        designer_count = reader.execute("SELECT COUNT(*) FROM designers").fetchone()[0]

        assert designer_count > 0
        writer.commit()
    finally:
        writer.rollback()
        writer.close()
        reader.close()

    verification = database.connect()
    try:
        assert verification.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1
    finally:
        verification.close()
