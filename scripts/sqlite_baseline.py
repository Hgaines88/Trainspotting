"""Run a small disposable SQLite baseline before the MySQL migration."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.database import SQLITE_BUSY_TIMEOUT_MS, configure_connection
from scripts.archive_data import DEFAULT_ARCHIVE, import_archive


def connect_to(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        database_path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000,
    )
    configure_connection(connection)
    return connection


def run_baseline(*, reads: int = 100, writes: int = 20, workers: int = 8) -> dict:
    if reads < 1 or writes < 1 or workers < 2:
        raise ValueError("Baseline requires reads, writes, and at least two workers.")

    with tempfile.TemporaryDirectory(prefix="trainspotting-sqlite-baseline-") as temp:
        database_path = Path(temp) / "baseline.db"
        import_archive(database_path, DEFAULT_ARCHIVE, replace=True)
        setup = connect_to(database_path)
        try:
            setup.execute(
                "INSERT INTO users (clerk_user_id, role) VALUES (?, 'member')",
                ("user_sqlite_baseline",),
            )
            setup.commit()
            submitter_id = setup.execute(
                "SELECT id FROM users WHERE clerk_user_id = ?",
                ("user_sqlite_baseline",),
            ).fetchone()[0]
        finally:
            setup.close()

        def read_archive(_index: int) -> None:
            connection = connect_to(database_path)
            try:
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM collections
                    JOIN designers ON designers.id = collections.designer_id
                    """
                ).fetchone()
            finally:
                connection.close()

        def write_draft(index: int) -> None:
            connection = connect_to(database_path)
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO submissions (
                        submitter_user_id, record_type, submission_type,
                        status, proposed_data, explanation
                    ) VALUES (?, 'designer', 'addition', 'draft', ?, ?)
                    """,
                    (
                        submitter_id,
                        json.dumps({"full_name": f"Baseline Designer {index}"}),
                        "Disposable SQLite migration baseline.",
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        operations = []
        for index in range(max(reads, writes)):
            if index < reads:
                operations.append((read_archive, index))
            if index < writes:
                operations.append((write_draft, index))
        started = time.perf_counter()
        failures = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(operation, index)
                for operation, index in operations
            ]
            for future in futures:
                try:
                    future.result()
                except Exception as error:
                    failures.append(type(error).__name__)
        elapsed = time.perf_counter() - started

        verification = connect_to(database_path)
        try:
            persisted_writes = verification.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0]
            integrity = verification.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            verification.close()

    return {
        "reads": reads,
        "writes": writes,
        "workers": workers,
        "elapsed_seconds": round(elapsed, 4),
        "persisted_writes": persisted_writes,
        "failures": failures,
        "integrity": integrity,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reads", type=int, default=100)
    parser.add_argument("--writes", type=int, default=20)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    result = run_baseline(reads=args.reads, writes=args.writes, workers=args.workers)
    print(json.dumps(result, indent=2))
    return int(bool(result["failures"]) or result["integrity"] != "ok")


if __name__ == "__main__":
    raise SystemExit(main())
