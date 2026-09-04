"""Prepare the configured database when needed and start the FastAPI server."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import make_url

from app.database_engine import default_sqlite_url
from scripts.init_db import initialize_database


def prepare_runtime_database(database_url: str | None = None) -> bool:
    """Initialize a missing SQLite archive; MySQL is prepared by Alembic."""
    parsed_url = make_url(database_url or default_sqlite_url())
    backend = parsed_url.get_backend_name()
    if backend == "mysql":
        return False
    if backend != "sqlite":
        raise ValueError(f"Unsupported database backend: {backend}")

    database_name = parsed_url.database
    if not database_name or database_name == ":memory:":
        raise ValueError("API startup requires a persistent SQLite database path")
    database_path = Path(database_name)
    if not database_path.is_absolute():
        database_path = Path.cwd() / database_path
    return initialize_database(database_path)


def server_arguments(port: str | None = None) -> list[str]:
    configured_port = port or os.getenv("PORT", "8000")
    if not configured_port.isdigit() or not 1 <= int(configured_port) <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535")
    return [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        configured_port,
    ]


def main() -> None:
    prepare_runtime_database(os.getenv("DATABASE_URL"))
    arguments = server_arguments()
    os.execvp(arguments[0], arguments)


if __name__ == "__main__":
    main()
