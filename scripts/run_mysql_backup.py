"""Run one encrypted MySQL backup, upload it, report the result, and exit."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scripts.backup_storage import storage_client, upload_backup
from scripts.mysql_backup import create_backup, verify_backup


def run_backup(now: datetime | None = None) -> dict:
    required = {
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "MYSQL_BACKUP_ENCRYPTION_KEY": os.getenv("MYSQL_BACKUP_ENCRYPTION_KEY"),
        "BACKUP_S3_BUCKET": os.getenv("BACKUP_S3_BUCKET"),
        "BACKUP_S3_ENDPOINT": os.getenv("BACKUP_S3_ENDPOINT"),
        "BACKUP_S3_ACCESS_KEY_ID": os.getenv("BACKUP_S3_ACCESS_KEY_ID"),
        "BACKUP_S3_SECRET_ACCESS_KEY": os.getenv("BACKUP_S3_SECRET_ACCESS_KEY"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("Missing backup job configuration: " + ", ".join(missing))

    client = storage_client()
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    with tempfile.TemporaryDirectory(prefix="trainspotting-backup-") as directory:
        backup = Path(directory) / f"trainspotting-{timestamp}.sql.enc"
        manifest = create_backup(
            required["DATABASE_URL"],
            required["MYSQL_BACKUP_ENCRYPTION_KEY"],
            backup,
        )
        verify_backup(required["MYSQL_BACKUP_ENCRYPTION_KEY"], backup)
        uploaded = upload_backup(
            client,
            required["BACKUP_S3_BUCKET"],
            os.getenv("BACKUP_S3_PREFIX", "staging/mysql"),
            backup,
        )
    return {
        "event": "mysql_backup_completed",
        "created_at": manifest["created_at"],
        **uploaded,
    }


def main() -> None:
    print(json.dumps(run_backup(), separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
