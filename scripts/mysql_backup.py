"""Create and verify encrypted MySQL logical backups without exposing credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from cryptography.fernet import Fernet, InvalidToken


FORMAT_VERSION = 1


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
    generator = option_file(config)
    credentials = next(generator)
    try:
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
    finally:
        try:
            next(generator)
        except StopIteration:
            pass
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


def verify_backup(encryption_key: str, backup: Path) -> dict:
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
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("backup", type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("backup", type=Path)
    args = parser.parse_args()
    key = os.getenv("MYSQL_BACKUP_ENCRYPTION_KEY")
    if not key:
        parser.error("MYSQL_BACKUP_ENCRYPTION_KEY is required")
    if args.command == "create":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            parser.error("DATABASE_URL is required")
        result = create_backup(database_url, key, args.backup)
    else:
        result = verify_backup(key, args.backup)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
