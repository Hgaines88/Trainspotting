"""Copy and reconcile a verified Trainspotting SQLite database into MySQL."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


TABLES = (
    "users",
    "designers",
    "collections",
    "collection_media",
    "submissions",
    "submission_sources",
    "submission_decisions",
    "submission_promotions",
    "submission_audit",
)


def normalized_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat(sep=" ")
    return value


def row_digest(rows: list[dict]) -> str:
    normalized = [
        {key: normalized_value(value) for key, value in sorted(row.items())}
        for row in rows
    ]
    payload = json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sqlite_rows(connection: sqlite3.Connection, table_name: str) -> list[dict]:
    columns = [
        row[1]
        for row in connection.execute(f'PRAGMA table_info("{table_name}")')
    ]
    if not columns:
        raise ValueError(f"Source table is missing: {table_name}")
    records = connection.execute(
        f'SELECT * FROM "{table_name}" ORDER BY id'
    ).fetchall()
    return [dict(zip(columns, record, strict=True)) for record in records]


def target_rows(connection, table_name: str, columns: list[str]) -> list[dict]:
    selected = ", ".join(f"`{column}`" for column in columns)
    result = connection.execute(
        text(f"SELECT {selected} FROM `{table_name}` ORDER BY id")
    ).mappings()
    return [dict(row) for row in result]


def migrate(source_path: Path, target_url: str) -> dict[str, dict[str, object]]:
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite source does not exist: {source_path}")
    if not target_url.startswith("mysql+"):
        raise ValueError("The target must be an explicit SQLAlchemy MySQL URL.")

    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    target = create_engine(target_url, pool_pre_ping=True)
    report: dict[str, dict[str, object]] = {}

    try:
        source.execute("PRAGMA foreign_keys = ON")
        with target.begin() as connection:
            target_tables = set(inspect(connection).get_table_names())
            missing = set(TABLES) - target_tables
            if missing:
                raise ValueError(
                    "Target schema is incomplete; run Alembic first. Missing: "
                    + ", ".join(sorted(missing))
                )

            occupied = {
                table_name: connection.execute(
                    text(f"SELECT COUNT(*) FROM `{table_name}`")
                ).scalar_one()
                for table_name in TABLES
            }
            occupied = {name: count for name, count in occupied.items() if count}
            if occupied:
                details = ", ".join(
                    f"{name}={count}" for name, count in occupied.items()
                )
                raise ValueError(f"Target must be empty before migration: {details}")

            for table_name in TABLES:
                source_records = sqlite_rows(source, table_name)
                columns = list(source_records[0]) if source_records else [
                    column["name"]
                    for column in inspect(connection).get_columns(table_name)
                ]
                if source_records:
                    names = ", ".join(f"`{column}`" for column in columns)
                    parameters = ", ".join(f":{column}" for column in columns)
                    connection.execute(
                        text(
                            f"INSERT INTO `{table_name}` ({names}) "
                            f"VALUES ({parameters})"
                        ),
                        source_records,
                    )

                copied_records = target_rows(connection, table_name, columns)
                source_hash = row_digest(source_records)
                target_hash = row_digest(copied_records)
                if len(source_records) != len(copied_records):
                    raise RuntimeError(f"Row-count mismatch for {table_name}")
                if source_hash != target_hash:
                    raise RuntimeError(f"Content mismatch for {table_name}")
                report[table_name] = {
                    "rows": len(source_records),
                    "sha256": source_hash,
                }
    finally:
        source.close()
        target.dispose()

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--target-url",
        default=os.getenv("MYSQL_MIGRATION_DATABASE_URL"),
        help="SQLAlchemy MySQL URL; defaults to MYSQL_MIGRATION_DATABASE_URL.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Required acknowledgement that the empty target may be populated.",
    )
    args = parser.parse_args()

    if not args.apply:
        parser.error("--apply is required; no data was changed")
    if not args.target_url:
        parser.error("--target-url or MYSQL_MIGRATION_DATABASE_URL is required")

    report = migrate(args.source, args.target_url)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
