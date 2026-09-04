import os
import sqlite3
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "archive.db"
MIGRATIONS_PATH = PROJECT_ROOT / "sql" / "migrations"
SQLITE_BUSY_TIMEOUT_MS = 5_000
DATABASE_INTEGRITY_ERRORS = (sqlite3.IntegrityError, SQLAlchemyIntegrityError)


def is_unique_violation(error: Exception) -> bool:
    message = str(error).lower()
    return "unique constraint failed" in message or "duplicate entry" in message


def select_for_update(connection, sql: str, parameters=()):
    """Lock selected rows on MySQL; SQLite's BEGIN IMMEDIATE already serializes."""
    if isinstance(connection, PortableConnection):
        sql = f"{sql.rstrip()} FOR UPDATE"
    return connection.execute(sql, parameters)


class PortableRow(Mapping):
    """Mapping row that retains sqlite3.Row's integer-index behavior."""

    def __init__(self, row):
        self._mapping = dict(row._mapping)
        self._values = tuple(row)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._mapping)

    def __len__(self):
        return len(self._mapping)


class PortableResult:
    def __init__(self, result):
        self._result = result
        self.lastrowid = result.lastrowid

    def fetchone(self):
        row = self._result.fetchone()
        return PortableRow(row) if row is not None else None

    def fetchall(self):
        return [PortableRow(row) for row in self._result.fetchall()]

    def __iter__(self):
        for row in self._result:
            yield PortableRow(row)


class PortableConnection:
    """Small DB-API compatibility facade over a SQLAlchemy connection."""

    def __init__(self, connection):
        self._connection = connection

    @staticmethod
    def _statement(sql: str, parameters):
        if not parameters:
            return sql, {}
        values = list(parameters)
        pieces = sql.split("?")
        if len(pieces) - 1 != len(values):
            raise ValueError("SQL placeholder count does not match parameters")
        names = [f"p{index}" for index in range(len(values))]
        statement = pieces[0]
        for name, piece in zip(names, pieces[1:], strict=True):
            statement += f":{name}{piece}"
        return statement, dict(zip(names, values, strict=True))

    def execute(self, sql: str, parameters=()):
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            self._connection.begin()
            return None
        statement, bindings = self._statement(sql, parameters)
        return PortableResult(self._connection.execute(text(statement), bindings))

    def executemany(self, sql: str, parameter_rows):
        rows = list(parameter_rows)
        if not rows:
            return None
        statement, _ = self._statement(sql, rows[0])
        bindings = [
            {f"p{index}": value for index, value in enumerate(row)}
            for row in rows
        ]
        return PortableResult(self._connection.execute(text(statement), bindings))

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


@lru_cache(maxsize=4)
def runtime_engine(database_url: str):
    from app.database_engine import build_engine

    return build_engine(database_url)


def configure_connection(connection: sqlite3.Connection) -> None:
    """Apply and verify the temporary SQLite safety settings."""
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        journal_mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if journal_mode.lower() != "wal":
            raise RuntimeError(
                f"SQLite WAL mode unavailable; received {journal_mode!r}."
            )
    except Exception:
        connection.close()
        raise


def connect():
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("mysql+"):
        return PortableConnection(runtime_engine(database_url).connect())

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000,
    )
    configure_connection(connection)
    return connection


def apply_migrations() -> list[str]:
    """Apply each pending SQL migration exactly once."""
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("mysql+"):
        configuration = Config(PROJECT_ROOT / "alembic.ini")
        configuration.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(configuration, "head")
        return []

    connection = connect()
    applied = []

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        completed = {
            row["filename"]
            for row in connection.execute(
                "SELECT filename FROM schema_migrations"
            ).fetchall()
        }

        for migration_path in sorted(MIGRATIONS_PATH.glob("*.sql")):
            if migration_path.name in completed:
                continue

            migration_sql = migration_path.read_text()
            quoted_filename = migration_path.name.replace("'", "''")

            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                f"{migration_sql}\n"
                "INSERT INTO schema_migrations (filename) "
                f"VALUES ('{quoted_filename}');\n"
                "COMMIT;"
            )
            applied.append(migration_path.name)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return applied
