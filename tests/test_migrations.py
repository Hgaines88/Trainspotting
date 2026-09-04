import sqlite3
from pathlib import Path

import pytest

from app import database


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_database(database_path: Path, setup_sql: str) -> None:
    connection = sqlite3.connect(database_path)

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            (PROJECT_ROOT / "sql" / "schema.sql").read_text()
        )
        connection.executescript(setup_sql)
    finally:
        connection.close()


def test_migration_upgrades_legacy_data_and_preserves_user_records(
    tmp_path,
    monkeypatch,
):
    test_database_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DATABASE_PATH", test_database_path)

    create_database(
        test_database_path,
        """
        INSERT INTO designers (
            id, full_name, nationality, birth_year, website, biography
        )
        VALUES
            (2, 'Shayne Oliver', 'American', NULL, NULL, NULL),
            (3, 'Grace Wales Bonner', 'British-Jamaican', NULL, NULL, NULL),
            (5, 'Jonathan Anderson', 'Northern Irish', NULL, NULL, NULL),
            (6, 'Demna', 'Georgian', NULL, NULL, NULL),
            (7, 'Virgil Abloh', 'American', NULL, NULL, NULL),
            (8, 'Hussein Chalayan', 'Cypriot-British', NULL, NULL, NULL),
            (9, 'Miuccia Prada', 'Italian', NULL, NULL, NULL),
            (10, 'Rei Kawakubo', 'Japanese', NULL, NULL, NULL),
            (
                20,
                'User Added Designer',
                'Canadian',
                1980,
                NULL,
                'This record must survive the migration unchanged.'
            );

        INSERT INTO collections (
            id, designer_id, label, name, season, release_year,
            status, piece_count, description
        )
        VALUES
            (
                1, 3, 'Wales Bonner', NULL, 'Spring/Summer', 2024,
                'released', 45, 'Older description.'
            ),
            (
                2, 5, 'JW Anderson', NULL, 'Spring/Summer', 2024,
                'released', 55, 'Older description.'
            ),
            (
                3, 2, 'Hood By Air', 'Wench', 'Spring/Summer', 2017,
                'archived', NULL, 'Older description.'
            ),
            (
                20, 20, 'Control Label', NULL, 'Resort', 2026,
                'concept', NULL, 'This user collection must survive.'
            );
        """,
    )

    first_run = database.apply_migrations()
    second_run = database.apply_migrations()

    connection = database.connect()

    try:
        names = {
            row["full_name"]
            for row in connection.execute(
                "SELECT full_name FROM designers"
            ).fetchall()
        }
        control_designer = connection.execute(
            """
            SELECT nationality, birth_year, biography
            FROM designers
            WHERE full_name = 'User Added Designer'
            """
        ).fetchone()
        control_collection = connection.execute(
            """
            SELECT label, season, release_year, description
            FROM collections
            WHERE designer_id = 20
            """
        ).fetchone()
        migration_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM schema_migrations
            WHERE filename = '001_sync_archive_records.sql'
            """
        ).fetchone()[0]
        archive_pairs = {
            (row["full_name"], row["label"])
            for row in connection.execute(
                """
                SELECT designers.full_name, collections.label
                FROM designers
                JOIN collections
                    ON collections.designer_id = designers.id
                """
            ).fetchall()
        }
        curated_videos = {
            row["media_value"]
            for row in connection.execute(
                """
                SELECT media_value
                FROM collection_media
                WHERE media_type = 'youtube'
                """
            ).fetchall()
        }
        haider_profile = connection.execute(
            """
            SELECT nationality, birth_year, biography
            FROM designers
            WHERE full_name = 'Haider Ackermann'
            """
        ).fetchone()
        haider_collections = {
            (row["label"], row["release_year"])
            for row in connection.execute(
                """
                SELECT collections.label, collections.release_year
                FROM collections
                JOIN designers
                    ON designers.id = collections.designer_id
                WHERE designers.full_name = 'Haider Ackermann'
                """
            ).fetchall()
        }
        haider_sources = connection.execute(
            """
            SELECT COUNT(*)
            FROM collection_media
            JOIN collections
                ON collections.id = collection_media.collection_id
            JOIN designers
                ON designers.id = collections.designer_id
            WHERE designers.full_name = 'Haider Ackermann'
              AND collection_media.media_type = 'source'
            """
        ).fetchone()[0]
        archive_state = connection.execute(
            "SELECT id, version FROM archive_state"
        ).fetchone()
    finally:
        connection.close()

    assert first_run == [
        "001_sync_archive_records.sql",
        "002_create_collection_media.sql",
        "003_add_curated_runway_videos.sql",
        "004_add_demna_runway_video.sql",
        "005_preserve_curated_archive.sql",
        "006_add_haider_ackermann_profile.sql",
        "007_create_users.sql",
        "008_create_moderation_workflow.sql",
        "009_add_archive_version.sql",
    ]
    assert second_run == []
    assert tuple(archive_state) == (1, 1)
    assert migration_count == 1
    assert "Hussein Chalayan" not in names
    assert {"Junya Watanabe", "Rick Owens", "Telfar Clemens"} <= names
    assert tuple(control_designer) == (
        "Canadian",
        1980,
        "This record must survive the migration unchanged.",
    )
    assert tuple(control_collection) == (
        "Control Label",
        "Resort",
        2026,
        "This user collection must survive.",
    )
    assert {
            ("Demna Gvasalia", "Balenciaga"),
        ("Virgil Abloh", "Louis Vuitton"),
        ("Junya Watanabe", "Junya Watanabe MAN"),
        ("Miuccia Prada", "Prada"),
        ("Rei Kawakubo", "Comme des Garçons"),
        ("Shayne Oliver", "Anonymous Club"),
        ("Telfar Clemens", "Telfar"),
        ("Rick Owens", "Rick Owens"),
    } <= archive_pairs
    assert {
        "akJxFSRW03U",
        "oYtZVDZWCes",
        "Yh_1K9s6UV0",
    } <= curated_videos
    assert tuple(haider_profile[:2]) == ("French-Colombian", 1971)
    assert haider_profile["biography"]
    assert haider_collections == {
        ("Haider Ackermann", 2011),
        ("Berluti", 2017),
        ("Jean Paul Gaultier", 2023),
        ("Tom Ford", 2025),
    }
    assert haider_sources == 5


def test_failed_migration_rolls_back_and_is_not_recorded(
    tmp_path,
    monkeypatch,
):
    test_database_path = tmp_path / "failure.db"
    migrations_path = tmp_path / "migrations"
    migrations_path.mkdir()
    (migrations_path / "001_broken.sql").write_text(
        """
        INSERT INTO designers (full_name)
        VALUES ('Should Be Rolled Back');

        THIS IS NOT VALID SQL;
        """
    )

    monkeypatch.setattr(database, "DATABASE_PATH", test_database_path)
    monkeypatch.setattr(database, "MIGRATIONS_PATH", migrations_path)
    create_database(test_database_path, "")

    with pytest.raises(sqlite3.OperationalError):
        database.apply_migrations()

    connection = database.connect()

    try:
        inserted_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM designers
            WHERE full_name = 'Should Be Rolled Back'
            """
        ).fetchone()[0]
        recorded_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM schema_migrations
            WHERE filename = '001_broken.sql'
            """
        ).fetchone()[0]
    finally:
        connection.close()

    assert inserted_count == 0
    assert recorded_count == 0
