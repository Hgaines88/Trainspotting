import os
import sqlite3
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError

from app.database_url import normalize_database_url
from app.observability import monotonic_time, service_metrics


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "archive.db"
MIGRATIONS_PATH = PROJECT_ROOT / "sql" / "migrations"
SQLITE_BUSY_TIMEOUT_MS = 5_000
DATABASE_INTEGRITY_ERRORS = (sqlite3.IntegrityError, SQLAlchemyIntegrityError)


@lru_cache(maxsize=1)
def expected_alembic_revision() -> str:
    configuration = Config(PROJECT_ROOT / "alembic.ini")
    revision = ScriptDirectory.from_config(configuration).get_current_head()
    if revision is None:
        raise RuntimeError("Alembic has no current head revision")
    return revision


def is_unique_violation(error: Exception) -> bool:
    message = str(error).lower()
    return "unique constraint failed" in message or "duplicate entry" in message


def select_for_update(connection, sql: str, parameters=()):
    """Lock selected rows on MySQL; SQLite's BEGIN IMMEDIATE already serializes."""
    if isinstance(connection, PortableConnection):
        sql = f"{sql.rstrip()} FOR UPDATE"
    return connection.execute(sql, parameters)


def current_archive_version(connection=None) -> int:
    owns_connection = connection is None
    connection = connection or connect()
    try:
        row = connection.execute(
            "SELECT version FROM archive_state WHERE id = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("Archive version ledger is missing")
        return row[0]
    finally:
        if owns_connection:
            connection.close()


def bump_archive_version(connection) -> int:
    connection.execute(
        "UPDATE archive_state SET version = version + 1, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = 1"
    )
    return current_archive_version(connection)


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

    def __init__(self, connection, engine, backend: str):
        self._connection = connection
        self._engine = engine
        self._backend = backend
        self._transaction_started_at = None

    @staticmethod
    def _operation(sql: str) -> str:
        operation = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else "OTHER"
        allowed = {"SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"}
        return operation if operation in allowed else "OTHER"

    def _observe_pool(self) -> None:
        pool = self._engine.pool

        def pool_value(name: str) -> int:
            value = getattr(pool, name, -1)
            value = value() if callable(value) else value
            return value if isinstance(value, int) else -1

        service_metrics.set_connection_pool(
            backend=self._backend,
            size=pool_value("size"),
            checked_out=pool_value("checkedout"),
            overflow=pool_value("overflow"),
        )

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
            self._transaction_started_at = monotonic_time()
            return None
        operation = self._operation(sql)
        started_at = monotonic_time()
        if operation in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"}:
            self._transaction_started_at = self._transaction_started_at or started_at
        try:
            statement, bindings = self._statement(sql, parameters)
            result = self._connection.execute(text(statement), bindings)
        except Exception:
            service_metrics.observe_database_operation(
                self._backend,
                operation,
                "error",
                (monotonic_time() - started_at) * 1_000,
            )
            raise
        service_metrics.observe_database_operation(
            self._backend,
            operation,
            "success",
            (monotonic_time() - started_at) * 1_000,
        )
        return PortableResult(result)

    def executemany(self, sql: str, parameter_rows):
        rows = list(parameter_rows)
        if not rows:
            return None
        operation = self._operation(sql)
        started_at = monotonic_time()
        if operation in {"INSERT", "UPDATE", "DELETE"}:
            self._transaction_started_at = self._transaction_started_at or started_at
        try:
            statement, _ = self._statement(sql, rows[0])
            bindings = [
                {f"p{index}": value for index, value in enumerate(row)}
                for row in rows
            ]
            result = self._connection.execute(text(statement), bindings)
        except Exception:
            service_metrics.observe_database_operation(
                self._backend,
                operation,
                "error",
                (monotonic_time() - started_at) * 1_000,
            )
            raise
        service_metrics.observe_database_operation(
            self._backend,
            operation,
            "success",
            (monotonic_time() - started_at) * 1_000,
        )
        return PortableResult(result)

    def commit(self):
        self._finish_transaction("committed", self._connection.commit)

    def rollback(self):
        self._finish_transaction("rolled_back", self._connection.rollback)

    def _finish_transaction(self, outcome, action):
        operation = "COMMIT" if outcome == "committed" else "ROLLBACK"
        started_at = monotonic_time()
        try:
            action()
        except Exception:
            service_metrics.observe_database_operation(
                self._backend,
                operation,
                "error",
                (monotonic_time() - started_at) * 1_000,
            )
            if self._transaction_started_at is not None:
                service_metrics.observe_transaction(
                    self._backend,
                    "failed",
                    (monotonic_time() - self._transaction_started_at) * 1_000,
                )
            self._transaction_started_at = None
            raise
        service_metrics.observe_database_operation(
            self._backend,
            operation,
            "success",
            (monotonic_time() - started_at) * 1_000,
        )
        if self._transaction_started_at is not None:
            service_metrics.observe_transaction(
                self._backend,
                outcome,
                (monotonic_time() - self._transaction_started_at) * 1_000,
            )
        self._transaction_started_at = None

    def close(self):
        self._connection.close()
        self._observe_pool()


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
    if database_url:
        database_url = normalize_database_url(database_url)
        parsed_url = make_url(database_url)
        backend = parsed_url.get_backend_name()
        if backend == "mysql":
            engine = runtime_engine(database_url)
            started_at = monotonic_time()
            try:
                connection = engine.connect()
            except Exception:
                service_metrics.observe_database_operation(
                    backend,
                    "CONNECT",
                    "error",
                    (monotonic_time() - started_at) * 1_000,
                )
                raise
            service_metrics.observe_database_operation(
                backend,
                "CONNECT",
                "success",
                (monotonic_time() - started_at) * 1_000,
            )
            portable = PortableConnection(connection, engine, backend)
            portable._observe_pool()
            return portable
        if backend == "sqlite" and parsed_url.database:
            connection = sqlite3.connect(
                parsed_url.database,
                timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000,
            )
            configure_connection(connection)
            return connection

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000,
    )
    configure_connection(connection)
    return connection


def database_readiness() -> dict[str, str]:
    """Verify connectivity and the schema ledger without changing database state."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        database_url = normalize_database_url(database_url)
    backend = make_url(database_url).get_backend_name() if database_url else "sqlite"
    connection = connect()
    try:
        connection.execute("SELECT 1").fetchone()
        if backend == "mysql":
            revision = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
            if revision is None or revision[0] != expected_alembic_revision():
                raise RuntimeError("Database schema revision is not ready")
            return {"database": "mysql", "revision": revision[0]}

        required_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name IN ('designers', 'archive_state')"
            ).fetchall()
        }
        if required_tables != {"designers", "archive_state"}:
            raise RuntimeError("SQLite archive schema is not ready")
        version = connection.execute(
            "SELECT version FROM archive_state WHERE id = 1"
        ).fetchone()
        if version is None or version[0] < 1:
            raise RuntimeError("SQLite archive version ledger is not ready")
        return {"database": "sqlite", "revision": "legacy-current"}
    finally:
        connection.close()


def apply_migrations(alembic_connection=None) -> list[str]:
    """Apply each pending SQL migration exactly once."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        database_url = normalize_database_url(database_url)
    if database_url and make_url(database_url).get_backend_name() == "mysql":
        configuration = Config(PROJECT_ROOT / "alembic.ini")
        configuration.set_main_option("sqlalchemy.url", database_url)
        if alembic_connection is not None:
            configuration.attributes["connection"] = alembic_connection
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
