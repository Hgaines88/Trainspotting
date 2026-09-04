import json
import sqlite3
import stat
from pathlib import Path

import pytest

from scripts.archive_backup import (
    create_backup,
    create_snapshot,
    manifest_path,
    restore_backup,
    verify_backup,
)
from scripts.archive_data import archive_has_drift, import_archive


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = PROJECT_ROOT / "data" / "archive.json"


def create_operational_database(database_path: Path) -> int:
    import_archive(database_path, ARCHIVE, replace=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        migrations = [
            (path.name,)
            for path in sorted((PROJECT_ROOT / "sql" / "migrations").glob("*.sql"))
        ]
        connection.executemany(
            "INSERT INTO schema_migrations (filename) VALUES (?)", migrations
        )
        connection.executemany(
            "INSERT INTO users (clerk_user_id, display_name, role) VALUES (?, ?, ?)",
            [
                ("user_backup_member", "Backup Member", "member"),
                ("user_backup_moderator", "Backup Moderator", "moderator"),
            ],
        )
        member_id, moderator_id = [
            row[0]
            for row in connection.execute("SELECT id FROM users ORDER BY id").fetchall()
        ]
        designer_id = connection.execute(
            "INSERT INTO designers (full_name, nationality) VALUES (?, ?)",
            ("Approved Backup Designer", "American"),
        ).lastrowid
        submission_id = connection.execute(
            """
            INSERT INTO submissions (
                submitter_user_id, record_type, submission_type, status,
                proposed_data, explanation, submitted_at, reviewed_at
            ) VALUES (?, 'designer', 'addition', 'approved', ?, ?, CURRENT_TIMESTAMP,
                      CURRENT_TIMESTAMP)
            """,
            (
                member_id,
                json.dumps(
                    {"full_name": "Approved Backup Designer", "nationality": "American"}
                ),
                "Preserve this approved submission through database loss.",
            ),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO submission_sources (submission_id, url, title)
            VALUES (?, ?, ?)
            """,
            (submission_id, "https://example.test/backup-source", "Backup source"),
        )
        connection.execute(
            """
            INSERT INTO submission_decisions (
                submission_id, reviewer_user_id, decision, notes
            ) VALUES (?, ?, 'approve', ?)
            """,
            (submission_id, moderator_id, "Verified before backup."),
        )
        connection.execute(
            """
            INSERT INTO submission_promotions (
                submission_id, canonical_record_type, canonical_record_id,
                before_snapshot, after_snapshot, promoted_by_user_id
            ) VALUES (?, 'designer', ?, NULL, ?, ?)
            """,
            (
                submission_id,
                designer_id,
                json.dumps(
                    {"full_name": "Approved Backup Designer", "nationality": "American"}
                ),
                moderator_id,
            ),
        )
        connection.executemany(
            """
            INSERT INTO submission_audit (
                submission_id, actor_user_id, event_type, from_status, to_status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (submission_id, member_id, "submitted", None, "submitted"),
                (submission_id, moderator_id, "approved", "submitted", "approved"),
            ],
        )
        connection.commit()
        return submission_id
    finally:
        connection.close()


def test_snapshot_and_restore_preserve_approved_record_sources_and_audit(tmp_path):
    database = tmp_path / "archive.db"
    canonical = tmp_path / "archive.json"
    backup = tmp_path / "private-backup.db"
    submission_id = create_operational_database(database)

    payload = create_snapshot(database, canonical, backup)

    assert payload["counts"]["submissions"] == 1
    assert payload["counts"]["submission_sources"] == 1
    assert payload["counts"]["submission_audit"] == 2
    assert archive_has_drift(database, canonical) is False
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE(manifest_path(backup).stat().st_mode) == 0o600

    database.unlink()
    restore_backup(backup, database)

    connection = sqlite3.connect(database)
    try:
        designer = connection.execute(
            "SELECT nationality FROM designers WHERE full_name = ?",
            ("Approved Backup Designer",),
        ).fetchone()
        source = connection.execute(
            "SELECT url, title FROM submission_sources WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()
        decisions = connection.execute(
            "SELECT decision, notes FROM submission_decisions WHERE submission_id = ?",
            (submission_id,),
        ).fetchall()
        audit = connection.execute(
            "SELECT event_type FROM submission_audit WHERE submission_id = ? ORDER BY id",
            (submission_id,),
        ).fetchall()
        promotion = connection.execute(
            "SELECT canonical_record_id FROM submission_promotions WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()
    finally:
        connection.close()

    assert designer == ("American",)
    assert source == ("https://example.test/backup-source", "Backup source")
    assert decisions == [("approve", "Verified before backup.")]
    assert audit == [("submitted",), ("approved",)]
    assert promotion is not None
    assert verify_backup(backup) == payload


def test_restore_refuses_to_replace_database_without_explicit_flag(tmp_path):
    database = tmp_path / "archive.db"
    backup = tmp_path / "private-backup.db"
    create_operational_database(database)
    create_backup(database, backup)

    with pytest.raises(FileExistsError, match="Use --replace deliberately"):
        restore_backup(backup, database)


def test_verify_rejects_a_backup_with_a_mismatched_checksum(tmp_path):
    database = tmp_path / "archive.db"
    backup = tmp_path / "private-backup.db"
    create_operational_database(database)
    create_backup(database, backup)
    with backup.open("ab") as backup_file:
        backup_file.write(b"corruption")

    with pytest.raises(ValueError, match="checksum"):
        verify_backup(backup)
