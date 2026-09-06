import copy
import json
import os
import sqlite3
import uuid

import pytest
from sqlalchemy import create_engine

from app.schema import metadata
from app.database import connect
from scripts.archive_data import DEFAULT_ARCHIVE, import_archive
from scripts.sync_canonical_mysql import apply_plan, build_plan, has_changes, load_archive
from tests.test_mysql_runtime import require_disposable_mysql_test_database


MYSQL_TEST_DATABASE_URL = os.getenv("MYSQL_TEST_DATABASE_URL")


OPERATIONAL_TABLES = (
    "users", "submissions", "submission_sources", "submission_decisions",
    "submission_promotions", "submission_audit", "ingestion_batches",
)


def database(tmp_path):
    target = tmp_path / "sync.db"
    engine = create_engine(f"sqlite:///{target}")
    metadata.create_all(engine)
    engine.dispose()
    import_archive(target, DEFAULT_ARCHIVE)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("INSERT INTO archive_state (id, version) VALUES (1, 1)")
    connection.commit()
    return connection


def table_snapshots(connection):
    return {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
        for table in OPERATIONAL_TABLES
    }


def test_sync_is_idempotent_and_preserves_operational_history(tmp_path):
    connection = database(tmp_path)
    payload = load_archive(DEFAULT_ARCHIVE)
    before = table_snapshots(connection)

    first = build_plan(connection, payload)
    apply_plan(connection, payload, first)
    second = build_plan(connection, payload)

    assert not has_changes(second)
    assert table_snapshots(connection) == before
    connection.close()


def test_archive_rejects_duplicate_normalized_designer_aliases(tmp_path):
    payload = copy.deepcopy(load_archive(DEFAULT_ARCHIVE))
    payload["designers"][0]["aliases"] = [{
        "alias": "Shared Name",
        "alias_type": "alternate-name",
        "source_url": "https://example.com/one",
    }]
    payload["designers"][1]["aliases"] = [{
        "alias": "SHARED—NAME",
        "alias_type": "former-name",
        "source_url": "https://example.com/two",
    }]
    archive = tmp_path / "duplicate-aliases.json"
    archive.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate or empty normalized"):
        load_archive(archive)


def test_sync_updates_in_place_and_bumps_version_once(tmp_path):
    connection = database(tmp_path)
    payload = load_archive(DEFAULT_ARCHIVE)
    payload = copy.deepcopy(payload)
    payload["designers"][0]["biography"] = "Corrected canonical biography."
    collection = payload["collections"][0]
    collection["description"] = "Corrected canonical collection."
    row = connection.execute(
        "SELECT id FROM collections WHERE label = ? AND season = ? AND release_year = ?",
        (collection["label"], collection["season"], collection["release_year"]),
    ).fetchone()
    original_id = row[0]
    version = connection.execute("SELECT version FROM archive_state WHERE id = 1").fetchone()[0]

    plan = build_plan(connection, payload)
    apply_plan(connection, payload, plan)

    assert connection.execute("SELECT biography FROM designers WHERE full_name = ?", (payload["designers"][0]["full_name"],)).fetchone()[0] == "Corrected canonical biography."
    assert connection.execute("SELECT id FROM collections WHERE description = ?", ("Corrected canonical collection.",)).fetchone()[0] == original_id
    assert connection.execute("SELECT version FROM archive_state WHERE id = 1").fetchone()[0] == version + 1
    connection.close()


def test_sync_rolls_back_every_change_on_constraint_failure(tmp_path):
    connection = database(tmp_path)
    payload = copy.deepcopy(load_archive(DEFAULT_ARCHIVE))
    payload["designers"][0]["biography"] = "Must roll back"
    collection = payload["collections"][0]
    collection["credits"] = [{
        "designer_key": collection["designer_key"], "role": "invalid",
        "position": 1, "attribution_note": None,
    }]
    before = connection.execute("SELECT biography FROM designers WHERE full_name = ?", (payload["designers"][0]["full_name"],)).fetchone()[0]
    plan = build_plan(connection, payload)

    with pytest.raises(sqlite3.IntegrityError):
        apply_plan(connection, payload, plan)

    assert connection.execute("SELECT biography FROM designers WHERE full_name = ?", (payload["designers"][0]["full_name"],)).fetchone()[0] == before
    connection.close()


def test_sync_rejects_stale_plan(tmp_path):
    connection = database(tmp_path)
    payload = load_archive(DEFAULT_ARCHIVE)
    plan = build_plan(connection, payload)
    connection.execute("UPDATE designers SET biography = ? WHERE id = 1", ("Concurrent edit",))
    connection.commit()

    with pytest.raises(RuntimeError, match="changed after the dry run"):
        apply_plan(connection, payload, plan)
    connection.close()


def test_plan_runtime_only_records_have_deterministic_id_order(tmp_path):
    connection = database(tmp_path)
    connection.execute(
        "INSERT INTO designers (full_name) VALUES (?)",
        ("Runtime-only second",),
    )
    second_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO designers (full_name) VALUES (?)",
        ("Runtime-only third",),
    )
    third_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.commit()

    plan = build_plan(connection, load_archive(DEFAULT_ARCHIVE))

    runtime_ids = [record["id"] for record in plan["runtime_only_designers"]]
    assert runtime_ids[-2:] == [second_id, third_id]
    assert runtime_ids == sorted(runtime_ids)
    connection.close()


def test_sync_reports_ambiguous_fallback_without_writing(tmp_path):
    connection = database(tmp_path)
    payload = copy.deepcopy(load_archive(DEFAULT_ARCHIVE))
    collection = payload["collections"][0]
    collection["season"] = "Corrected season"
    designer = next(d for d in payload["designers"] if d["key"] == collection["designer_key"])
    designer_id = connection.execute("SELECT id FROM designers WHERE full_name = ?", (designer["full_name"],)).fetchone()[0]
    connection.execute(
        "INSERT INTO collections (designer_id, label, season, release_year, status) VALUES (?, ?, ?, ?, ?)",
        (designer_id, collection["label"], "Ambiguous season", collection["release_year"], "released"),
    )
    connection.commit()

    plan = build_plan(connection, payload)

    assert plan["conflicts"]
    with pytest.raises(RuntimeError, match="ambiguous"):
        apply_plan(connection, payload, plan)
    connection.close()


def test_sync_reserves_exact_rows_before_matching_same_year_fallbacks(tmp_path):
    connection = database(tmp_path)
    payload = copy.deepcopy(load_archive(DEFAULT_ARCHIVE))
    existing = payload["collections"][0]
    additional = copy.deepcopy(existing)
    additional["key"] = f"{existing['key']}-additional-season"
    additional["season"] = "Additional season"
    payload["collections"].append(additional)

    plan = build_plan(connection, payload)

    assert not plan["conflicts"]
    assert [item["key"] for item in plan["collection_inserts"]] == [
        additional["key"]
    ]
    assert not plan["collection_updates"]
    connection.close()


def test_archive_validation_happens_before_database_changes(tmp_path):
    archive = tmp_path / "bad.json"
    payload = json.loads(DEFAULT_ARCHIVE.read_text())
    payload["designers"].append(copy.deepcopy(payload["designers"][0]))
    archive.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="Duplicate designer identity"):
        load_archive(archive)


@pytest.mark.skipif(
    not MYSQL_TEST_DATABASE_URL,
    reason="MYSQL_TEST_DATABASE_URL is required for the MySQL sync test",
)
def test_sync_runs_transactionally_and_idempotently_on_mysql(monkeypatch):
    require_disposable_mysql_test_database(MYSQL_TEST_DATABASE_URL)
    monkeypatch.setenv("DATABASE_URL", MYSQL_TEST_DATABASE_URL)
    tag = uuid.uuid4().hex[:12]
    payload = {
        "format_version": 1,
        "designers": [{
            "key": f"sync-{tag}", "full_name": f"Sync {tag}",
            "nationality": "Test", "birth_year": None, "website": None,
            "biography": "MySQL synchronization test.",
        }],
        "collections": [{
            "key": f"sync-{tag}-test-label-test-season-2026",
            "designer_key": f"sync-{tag}", "label": "Test label",
            "name": None, "season": "Test season", "release_year": 2026,
            "status": "concept", "piece_count": None,
            "description": "MySQL synchronization test.",
            "source_url": "https://example.test/sync",
            "youtube_video_id": None,
        }],
    }
    connection = connect()
    try:
        plan = build_plan(connection, payload)
        apply_plan(connection, payload, plan)
        assert not has_changes(build_plan(connection, payload))
        assert connection.execute(
            "SELECT COUNT(*) FROM designers WHERE full_name = ?",
            (f"Sync {tag}",),
        ).fetchone()[0] == 1
    finally:
        connection.close()
