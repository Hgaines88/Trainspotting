"""Create, verify, and atomically restore private SQLite archive backups."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scripts.archive_data import (
    DEFAULT_ARCHIVE,
    archive_digest,
    database_archive,
    export_archive,
    write_text_atomically,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "archive.db"
BACKUP_FORMAT_VERSION = 1
COUNTED_TABLES = (
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
)


def manifest_path(backup_path: Path) -> Path:
    return backup_path.with_name(f"{backup_path.name}.manifest.json")


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_database(database_path: Path) -> dict:
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("SQLite integrity check failed.")
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise ValueError("SQLite foreign-key check failed.")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing = set(COUNTED_TABLES) - tables
        if missing:
            raise ValueError(
                f"Backup is missing required tables: {', '.join(sorted(missing))}"
            )
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in COUNTED_TABLES
        }
        migrations = (
            [
                row[0]
                for row in connection.execute(
                    "SELECT filename FROM schema_migrations ORDER BY filename"
                ).fetchall()
            ]
            if "schema_migrations" in tables
            else []
        )
    finally:
        connection.close()
    return {
        "counts": counts,
        "migrations": migrations,
        "canonical_digest": archive_digest(database_archive(database_path)),
    }


def sqlite_backup(source_path: Path, destination_path: Path) -> None:
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    destination = sqlite3.connect(destination_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def create_backup(database_path: Path, backup_path: Path) -> dict:
    if backup_path.exists() or manifest_path(backup_path).exists():
        raise FileExistsError(f"Backup output already exists: {backup_path}")
    inspect_database(database_path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{backup_path.name}.", suffix=".tmp", dir=backup_path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    temporary_path.unlink()
    try:
        sqlite_backup(database_path, temporary_path)
        details = inspect_database(temporary_path)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, backup_path)
        payload = {
            "backup_format_version": BACKUP_FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_sha256": file_digest(backup_path),
            **details,
        }
        write_text_atomically(
            manifest_path(backup_path),
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        )
        os.chmod(manifest_path(backup_path), 0o600)
        return payload
    except Exception:
        temporary_path.unlink(missing_ok=True)
        backup_path.unlink(missing_ok=True)
        manifest_path(backup_path).unlink(missing_ok=True)
        raise


def verify_backup(backup_path: Path) -> dict:
    sidecar = manifest_path(backup_path)
    if not sidecar.is_file():
        raise FileNotFoundError(f"Backup manifest does not exist: {sidecar}")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    if payload.get("backup_format_version") != BACKUP_FORMAT_VERSION:
        raise ValueError("Unsupported backup format version.")
    if payload.get("database_sha256") != file_digest(backup_path):
        raise ValueError("Backup checksum does not match its manifest.")
    details = inspect_database(backup_path)
    for field in ("counts", "migrations", "canonical_digest"):
        if payload.get(field) != details[field]:
            raise ValueError(f"Backup manifest {field} does not match the database.")
    return payload


def create_snapshot(database_path: Path, archive_path: Path, backup_path: Path) -> dict:
    payload = create_backup(database_path, backup_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{archive_path.name}.", suffix=".tmp", dir=archive_path.parent
    )
    os.close(descriptor)
    temporary_archive = Path(temporary_name)
    try:
        exported = export_archive(backup_path, temporary_archive)
        if archive_digest(exported) != payload["canonical_digest"]:
            raise RuntimeError("Canonical export does not match the operational backup.")
        os.replace(temporary_archive, archive_path)
    finally:
        temporary_archive.unlink(missing_ok=True)
    return payload


def restore_backup(backup_path: Path, database_path: Path, *, replace: bool = False) -> dict:
    payload = verify_backup(backup_path)
    if database_path.exists() and not replace:
        raise FileExistsError(
            f"Restore target already exists: {database_path}. Use --replace deliberately."
        )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{database_path.name}.", suffix=".tmp", dir=database_path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    temporary_path.unlink()
    try:
        sqlite_backup(backup_path, temporary_path)
        restored = inspect_database(temporary_path)
        for field in ("counts", "migrations", "canonical_digest"):
            if restored[field] != payload[field]:
                raise ValueError(f"Restored database {field} failed verification.")
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, database_path)
        return payload
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("backup", type=Path)
    create_parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("backup", type=Path)
    snapshot_parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    snapshot_parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("backup", type=Path)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    restore_parser.add_argument("--replace", action="store_true")

    args = parser.parse_args()
    if args.command == "create":
        payload = create_backup(args.database, args.backup)
        print(f"Created and verified private backup: {args.backup}")
    elif args.command == "snapshot":
        payload = create_snapshot(args.database, args.archive, args.backup)
        print(f"Created and verified private backup: {args.backup}")
        print(f"Refreshed canonical archive from the same snapshot: {args.archive}")
    elif args.command == "verify":
        payload = verify_backup(args.backup)
        print(f"Backup verified: {args.backup}")
    else:
        payload = restore_backup(args.backup, args.database, replace=args.replace)
        print(f"Restored and verified database: {args.database}")
    print(
        f"Canonical digest: {payload['canonical_digest']} · "
        f"submissions: {payload['counts']['submissions']} · "
        f"audit events: {payload['counts']['submission_audit']}"
    )


if __name__ == "__main__":
    main()
