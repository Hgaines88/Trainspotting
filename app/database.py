import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "archive.db"
MIGRATIONS_PATH = PROJECT_ROOT / "sql" / "migrations"
SQLITE_BUSY_TIMEOUT_MS = 5_000


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


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000,
    )
    configure_connection(connection)
    return connection


def apply_migrations() -> list[str]:
    """Apply each pending SQL migration exactly once."""
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
