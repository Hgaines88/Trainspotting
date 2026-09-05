"""Create and verify encrypted MySQL logical backups without exposing credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from cryptography.fernet import Fernet, InvalidToken


FORMAT_VERSION = 1
REQUIRED_TABLES = {
    "alembic_version",
    "archive_state",
    "collection_media",
    "collections",
    "designers",
    "submission_audit",
    "submission_decisions",
    "submission_promotions",
    "submission_sources",
    "submissions",
    "users",
}


def database_config(database_url: str) -> dict[str, object]:
    parsed = urlsplit(database_url.replace("mysql+pymysql://", "mysql://", 1))
    if parsed.scheme != "mysql" or not all(
        (parsed.hostname, parsed.username, parsed.password, parsed.path.lstrip("/"))
    ):
        raise ValueError("DATABASE_URL must be a complete MySQL URL")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username),
        "password": unquote(parsed.password),
        "database": unquote(parsed.path.lstrip("/")),
    }


@contextmanager
def option_file(config: dict[str, object]):
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
    try:
        handle.write(
            "[client]\n"
            f"host={config['host']}\nport={config['port']}\n"
            f"user={config['user']}\npassword={config['password']}\n"
            "ssl-mode=REQUIRED\n"
        )
        handle.close()
        os.chmod(handle.name, 0o600)
        yield Path(handle.name)
    finally:
        handle.close()
        Path(handle.name).unlink(missing_ok=True)


def dump_database(database_url: str) -> bytes:
    config = database_config(database_url)
    with option_file(config) as credentials:
        result = subprocess.run(
            [
                "mysqldump",
                f"--defaults-extra-file={credentials}",
                "--single-transaction",
                "--quick",
                "--routines",
                "--events",
                "--triggers",
                "--set-gtid-purged=OFF",
                "--no-tablespaces",
                "--hex-blob",
                "--default-character-set=utf8mb4",
                str(config["database"]),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    if b"CREATE TABLE" not in result.stdout:
        raise RuntimeError("MySQL dump contains no table definitions")
    return result.stdout


def create_backup(database_url: str, encryption_key: str, destination: Path) -> dict:
    if destination.exists() or destination.with_suffix(destination.suffix + ".json").exists():
        raise FileExistsError(f"Backup output already exists: {destination}")
    plaintext = dump_database(database_url)
    encrypted = Fernet(encryption_key.encode("ascii")).encrypt(plaintext)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(encrypted)
    os.chmod(destination, 0o600)
    manifest = {
        "format_version": FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "encrypted_sha256": hashlib.sha256(encrypted).hexdigest(),
        "encrypted_bytes": len(encrypted),
    }
    manifest_path = destination.with_suffix(destination.suffix + ".json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    os.chmod(manifest_path, 0o600)
    return manifest


def decrypt_backup(encryption_key: str, backup: Path) -> tuple[dict, bytes]:
    encrypted = backup.read_bytes()
    manifest = json.loads(backup.with_suffix(backup.suffix + ".json").read_text())
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError("Unsupported backup format version")
    if hashlib.sha256(encrypted).hexdigest() != manifest.get("encrypted_sha256"):
        raise ValueError("Encrypted backup checksum mismatch")
    try:
        plaintext = Fernet(encryption_key.encode("ascii")).decrypt(encrypted)
    except (InvalidToken, ValueError) as error:
        raise ValueError("Backup decryption or authentication failed") from error
    if b"CREATE TABLE" not in plaintext:
        raise ValueError("Decrypted backup contains no table definitions")
    return manifest, plaintext


def verify_backup(encryption_key: str, backup: Path) -> dict:
    manifest, _plaintext = decrypt_backup(encryption_key, backup)
    return manifest


def mysql_command(config: dict[str, object], credentials: Path) -> list[str]:
    return [
        "mysql",
        f"--defaults-extra-file={credentials}",
        "--batch",
        "--skip-column-names",
        "--default-character-set=utf8mb4",
        str(config["database"]),
    ]


def database_tables(config: dict[str, object], credentials: Path) -> set[str]:
    result = subprocess.run(
        [*mysql_command(config, credentials), "--execute=SHOW TABLES"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def restore_backup(database_url: str, encryption_key: str, backup: Path) -> dict:
    """Restore into an existing empty database and verify its required tables."""
    manifest, plaintext = decrypt_backup(encryption_key, backup)
    config = database_config(database_url)
    with option_file(config) as credentials:
        existing = database_tables(config, credentials)
        if existing:
            raise ValueError("Restore target must be an empty database")
        subprocess.run(
            mysql_command(config, credentials),
            check=True,
            input=plaintext,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        restored = database_tables(config, credentials)
    missing = REQUIRED_TABLES - restored
    if missing:
        raise RuntimeError(
            "Restored database is incomplete; missing: " + ", ".join(sorted(missing))
        )
    return {**manifest, "restored_table_count": len(restored)}


def backup_health(
    encryption_key: str,
    directory: Path,
    max_age_hours: float,
    *,
    now: datetime | None = None,
) -> dict:
    manifests = sorted(directory.glob("*.sql.enc.json"), key=lambda path: path.stat().st_mtime)
    if not manifests:
        raise FileNotFoundError("No encrypted MySQL backup manifest found")
    manifest_path = manifests[-1]
    backup = manifest_path.with_suffix("")
    manifest = verify_backup(encryption_key, backup)
    created_at = datetime.fromisoformat(manifest["created_at"])
    if created_at.tzinfo is None:
        raise ValueError("Backup manifest timestamp must include a timezone")
    current = now or datetime.now(timezone.utc)
    age_hours = (current - created_at).total_seconds() / 3600
    if age_hours < 0:
        raise ValueError("Backup manifest timestamp is in the future")
    if age_hours > max_age_hours:
        raise RuntimeError(
            f"Newest encrypted MySQL backup is stale ({age_hours:.1f} hours old)"
        )
    return {
        "status": "healthy",
        "backup": backup.name,
        "age_hours": round(age_hours, 2),
        "max_age_hours": max_age_hours,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("backup", type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("backup", type=Path)
    restore = subparsers.add_parser("restore")
    restore.add_argument("backup", type=Path)
    restore.add_argument(
        "--apply",
        action="store_true",
        help="Required acknowledgement that the empty target will be populated.",
    )
    health = subparsers.add_parser("health")
    health.add_argument("directory", type=Path)
    health.add_argument("--max-age-hours", type=float, default=26)
    args = parser.parse_args()
    key = os.getenv("MYSQL_BACKUP_ENCRYPTION_KEY")
    if not key:
        parser.error("MYSQL_BACKUP_ENCRYPTION_KEY is required")
    if args.command in {"create", "restore"}:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            parser.error("DATABASE_URL is required")
    if args.command == "create":
        result = create_backup(database_url, key, args.backup)
    elif args.command == "restore":
        if not args.apply:
            parser.error("--apply is required; no data was changed")
        result = restore_backup(database_url, key, args.backup)
    elif args.command == "verify":
        result = verify_backup(key, args.backup)
    else:
        result = backup_health(key, args.directory, args.max_age_hours)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
