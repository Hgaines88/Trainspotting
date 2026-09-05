import json
import sqlite3
from pathlib import Path

from app import database
from scripts import init_db


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_fresh_initialization_uses_canonical_archive(tmp_path, monkeypatch):
    database_path = tmp_path / "archive.db"
    monkeypatch.setattr(init_db, "DATABASE_PATH", database_path)
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)

    assert not database_path.exists()
    assert init_db.initialize_database() is True
    assert init_db.initialize_database() is False
    assert database.apply_migrations() == []

    connection = sqlite3.connect(database_path)
    try:
        counts = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("designers", "collections", "users")
        )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        recorded_migrations = {
            row[0]
            for row in connection.execute(
                "SELECT filename FROM schema_migrations"
            ).fetchall()
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        connection.close()

    payload = json.loads(
        (PROJECT_ROOT / "data" / "archive.json").read_text(encoding="utf-8")
    )
    assert counts == (
        len(payload["designers"]),
        len(payload["collections"]),
        0,
    )
    assert {
        "designers",
        "collections",
        "collection_credits",
        "collection_media",
        "users",
        "submissions",
        "submission_sources",
        "submission_decisions",
        "submission_promotions",
        "submission_audit",
        "schema_migrations",
    } <= tables
    assert recorded_migrations == {
        path.name for path in (PROJECT_ROOT / "sql" / "migrations").glob("*.sql")
    }
    assert integrity == "ok"
    assert foreign_key_errors == []


def test_initialization_never_replaces_a_newer_existing_database(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "archive.db"
    init_db.import_archive(database_path, init_db.DEFAULT_ARCHIVE, replace=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "INSERT INTO designers (full_name) VALUES ('Approved Runtime Record')"
        )
        connection.commit()
    finally:
        connection.close()
    monkeypatch.setattr(init_db, "DATABASE_PATH", database_path)

    assert init_db.initialize_database() is False

    connection = sqlite3.connect(database_path)
    try:
        preserved = connection.execute(
            "SELECT 1 FROM designers WHERE full_name = 'Approved Runtime Record'"
        ).fetchone()
    finally:
        connection.close()
    assert preserved == (1,)
