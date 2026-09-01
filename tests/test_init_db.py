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

    assert init_db.initialize_database() is True
    assert init_db.initialize_database() is False
    assert database.apply_migrations() == []

    connection = sqlite3.connect(database_path)
    try:
        counts = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("designers", "collections", "users")
        )
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
