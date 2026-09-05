"""SQLAlchemy engine configuration shared by SQLite and MySQL migration paths."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url

from app.database import DATABASE_PATH, SQLITE_BUSY_TIMEOUT_MS
from app.database_url import normalize_database_url


def default_sqlite_url(database_path: Path = DATABASE_PATH) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve()}"


def configured_database_url(database_path: Path = DATABASE_PATH) -> str:
    configured = os.getenv("DATABASE_URL") or default_sqlite_url(database_path)
    return normalize_database_url(configured)


def build_engine(database_url: str | None = None) -> Engine:
    url = make_url(normalize_database_url(database_url or configured_database_url()))
    options: dict = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {
            "timeout": SQLITE_BUSY_TIMEOUT_MS / 1_000,
        }

    engine = create_engine(url, **options)
    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", configure_sqlite_connection)
    return engine


def configure_sqlite_connection(
    connection: sqlite3.Connection,
    _connection_record,
) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        cursor.execute("PRAGMA journal_mode = WAL")
        journal_mode = cursor.fetchone()[0]
        if journal_mode.lower() != "wal":
            raise RuntimeError(
                f"SQLite WAL mode unavailable; received {journal_mode!r}."
            )
    finally:
        cursor.close()
