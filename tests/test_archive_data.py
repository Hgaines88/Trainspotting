import json
import sqlite3
from pathlib import Path

from scripts.archive_data import archive_has_drift, export_archive, import_archive


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = PROJECT_ROOT / "data" / "archive.json"


def archive_counts(database_path):
    connection = sqlite3.connect(database_path)
    try:
        return tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("designers", "collections", "collection_media")
        )
    finally:
        connection.close()


def test_export_import_round_trip_preserves_content(tmp_path):
    source = tmp_path / "source.db"
    restored = tmp_path / "restored.db"
    first_json = tmp_path / "first.json"
    second_json = tmp_path / "second.json"

    import_archive(source, ARCHIVE, replace=True)
    export_archive(source, first_json)
    import_archive(restored, first_json, replace=True)
    export_archive(restored, second_json)

    assert json.loads(first_json.read_text()) == json.loads(second_json.read_text())
    assert archive_counts(source) == archive_counts(restored)


def test_merge_import_is_idempotent(tmp_path):
    database = tmp_path / "archive.db"
    archive = ARCHIVE

    import_archive(database, archive)
    initial_counts = archive_counts(database)
    import_archive(database, archive)

    assert archive_counts(database) == initial_counts


def test_drift_check_detects_and_export_resolves_canonical_changes(tmp_path):
    database = tmp_path / "archive.db"
    archive = tmp_path / "archive.json"
    archive.write_text(ARCHIVE.read_text(encoding="utf-8"), encoding="utf-8")
    import_archive(database, archive, replace=True)

    assert archive_has_drift(database, archive) is False

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO designers (full_name, nationality) VALUES (?, ?)",
            ("Approved Snapshot Designer", "American"),
        )
        connection.commit()
    finally:
        connection.close()

    assert archive_has_drift(database, archive) is True
    export_archive(database, archive)
    assert archive_has_drift(database, archive) is False


def test_new_designer_profiles_have_expected_career_records():
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    designers = {
        designer["key"]: designer
        for designer in payload["designers"]
    }
    collections = payload["collections"]

    assert designers["gosha-rubchinskiy"]["nationality"] == "Russian"
    assert designers["luka-sabbat"]["nationality"] == "French-American"
    assert designers["haider-ackermann"]["nationality"] == (
        "French-Colombian"
    )

    gosha_collections = [
        collection
        for collection in collections
        if collection["designer_key"] == "gosha-rubchinskiy"
    ]
    luka_collections = [
        collection
        for collection in collections
        if collection["designer_key"] == "luka-sabbat"
    ]
    haider_collections = [
        collection
        for collection in collections
        if collection["designer_key"] == "haider-ackermann"
    ]

    assert len(gosha_collections) == 7
    assert {collection["release_year"] for collection in gosha_collections} == {
        2009,
        2015,
        2016,
        2017,
        2018,
    }
    assert len(luka_collections) == 9
    assert any(
        collection["release_year"] == 2027
        and collection["status"] == "in-production"
        for collection in luka_collections
    )
    assert len(haider_collections) == 5
    assert all(
        collection["source_url"]
        for collection in gosha_collections
        + luka_collections
        + haider_collections
    )
