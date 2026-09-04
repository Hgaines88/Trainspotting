from pathlib import Path

import pytest

from scripts.check_secrets import scan_paths


def test_repository_tracked_files_pass_secret_scan():
    from scripts.check_secrets import tracked_paths

    assert scan_paths(tracked_paths()) == []


def test_secret_scan_reports_content_without_exposing_value(tmp_path: Path):
    secret_path = tmp_path / "settings.txt"
    fake_secret = "sk_test_" + "abcdefghijklmnopqrstuvwxyz"
    secret_path.write_text("CLERK_SECRET_KEY=" + fake_secret)

    findings = scan_paths([secret_path])

    assert [(finding.path, finding.rule) for finding in findings] == [
        (secret_path, "Clerk or Stripe secret key")
    ]
    assert fake_secret not in repr(findings)


def test_secret_scan_rejects_local_environment_filename(tmp_path: Path):
    environment_path = tmp_path / ".env.local"
    environment_path.write_text("SAFE_PLACEHOLDER=true")

    findings = scan_paths([environment_path])

    assert [(finding.path, finding.rule) for finding in findings] == [
        (environment_path, "sensitive filename")
    ]


@pytest.mark.parametrize(
    "filename",
    ["archive.db", "archive.sqlite", "archive.sqlite3", "archive.db.manifest.json"],
)
def test_secret_scan_rejects_database_backup_artifacts(
    tmp_path: Path, filename: str
):
    artifact_path = tmp_path / filename
    artifact_path.write_text("SAFE_PLACEHOLDER=true")

    findings = scan_paths([artifact_path])

    assert [(finding.path, finding.rule) for finding in findings] == [
        (artifact_path, "sensitive filename")
    ]


@pytest.mark.parametrize(
    "filename",
    [
        "archive.db-wal",
        "archive.db-shm",
        "archive.sqlite-wal",
        "archive.sqlite-shm",
        "archive.sqlite3-wal",
        "archive.sqlite3-shm",
    ],
)
def test_secret_scan_rejects_sqlite_wal_and_shared_memory_sidecars(
    tmp_path: Path, filename: str
):
    sidecar_path = tmp_path / filename
    sidecar_path.write_bytes(b"sqlite sidecar data")

    findings = scan_paths([sidecar_path])

    assert [(finding.path, finding.rule) for finding in findings] == [
        (sidecar_path, "sensitive filename")
    ]
