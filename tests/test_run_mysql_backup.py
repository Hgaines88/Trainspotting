from datetime import datetime, timezone

from scripts import run_mysql_backup


def test_job_creates_verifies_uploads_and_removes_temporary_artifact(
    monkeypatch,
):
    monkeypatch.setenv("DATABASE_URL", "mysql://database")
    monkeypatch.setenv("MYSQL_BACKUP_ENCRYPTION_KEY", "encryption-key")
    monkeypatch.setenv("BACKUP_S3_BUCKET", "private-backups")
    monkeypatch.setenv("BACKUP_S3_PREFIX", "staging/mysql")
    observed = {}

    def create(database_url, key, backup):
        observed["database_url"] = database_url
        observed["key"] = key
        observed["backup"] = backup
        backup.write_bytes(b"encrypted")
        return {"created_at": "2026-09-05T12:00:00+00:00"}

    monkeypatch.setattr(run_mysql_backup, "create_backup", create)
    monkeypatch.setattr(
        run_mysql_backup, "verify_backup", lambda key, backup: observed.update(verified=True)
    )
    monkeypatch.setattr(run_mysql_backup, "storage_client", lambda: "client")
    monkeypatch.setattr(
        run_mysql_backup,
        "upload_backup",
        lambda client, bucket, prefix, backup: {
            "bucket": bucket,
            "object_key": f"{prefix}/{backup.name}",
            "encrypted_bytes": 9,
            "encrypted_sha256": "digest",
        },
    )

    result = run_mysql_backup.run_backup(
        datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
    )

    assert result["event"] == "mysql_backup_completed"
    assert result["object_key"].endswith("trainspotting-20260905T120000Z.sql.enc")
    assert observed["verified"] is True
    assert not observed["backup"].exists()


def test_job_fails_before_database_access_when_configuration_is_missing(monkeypatch):
    for name in (
        "DATABASE_URL",
        "MYSQL_BACKUP_ENCRYPTION_KEY",
        "BACKUP_S3_BUCKET",
    ):
        monkeypatch.delenv(name, raising=False)

    try:
        run_mysql_backup.run_backup()
    except ValueError as error:
        message = str(error)
    else:
        raise AssertionError("Missing configuration should fail the backup job")
    assert "DATABASE_URL" in message
    assert "MYSQL_BACKUP_ENCRYPTION_KEY" in message
    assert "BACKUP_S3_BUCKET" in message
