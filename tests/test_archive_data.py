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
            for table in (
                "designers",
                "collections",
                "collection_credits",
                "collection_media",
            )
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


def test_demo_collaborations_have_ordered_credits_and_sources():
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    collections = {collection["key"]: collection for collection in payload["collections"]}

    prada = collections["raf-simons-prada-spring-summer-2024"]
    assert [
        (credit["designer_key"], credit["role"], credit["position"])
        for credit in prada["credits"]
    ] == [
        ("miuccia-prada", "co-designer", 1),
        ("raf-simons", "co-designer", 2),
    ]
    assert prada["source_url"] == (
        "https://www.vogue.com/fashion-shows/spring-2024-ready-to-wear/prada"
    )

    dior = collections["eli-russell-linnetz-dior-men-spring-summer-menswear-2023"]
    assert [
        (credit["designer_key"], credit["role"], credit["position"])
        for credit in dior["credits"]
    ] == [
        ("eli-russell-linnetz", "lead", 1),
        ("kim-jones", "collaborator", 2),
    ]
    assert dior["source_url"] == (
        "https://www.vogue.com/fashion-shows/spring-2023-menswear/dior-men"
    )


def test_first_integrity_batch_has_verified_taxonomy_sources_and_statuses():
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    collections = {collection["key"]: collection for collection in payload["collections"]}
    expected = {
        "chitose-abe-sacai-spring-summer-ready-to-wear-2019": (
            "Spring/Summer Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/spring-2019-ready-to-wear/sacai",
        ),
        "demna-gvasalia-balenciaga-spring-summer-ready-to-wear-2023": (
            "Spring/Summer Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/spring-2023-ready-to-wear/balenciaga",
        ),
        "demna-gvasalia-balenciaga-fall-winter-ready-to-wear-2024": (
            "Fall/Winter Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/fall-2024-ready-to-wear/balenciaga",
        ),
        "grace-wales-bonner-wales-bonner-spring-summer-menswear-2024": (
            "Spring/Summer Menswear",
            "https://www.vogue.com/fashion-shows/spring-2024-menswear/wales-bonner",
        ),
        "jonathan-anderson-jw-anderson-spring-summer-ready-to-wear-2024": (
            "Spring/Summer Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/spring-2024-ready-to-wear/j-w-anderson",
        ),
    }

    for key, (season, source_url) in expected.items():
        assert collections[key]["season"] == season
        assert collections[key]["source_url"] == source_url
        assert collections[key]["status"] == "archived"


def test_second_integrity_batch_has_verified_taxonomy_sources_and_statuses():
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    collections = {
        collection["key"]: collection
        for collection in payload["collections"]
    }
    expected = {
        "junya-watanabe-junya-watanabe-man-spring-summer-menswear-2025": (
            "Spring/Summer Menswear",
            "https://www.vogue.com/fashion-shows/spring-2025-menswear/junya-watanabe",
        ),
        "lee-alexander-mcqueen-alexander-mcqueen-spring-summer-ready-to-wear-1999": (
            "Spring/Summer Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/spring-1999-ready-to-wear/alexander-mcqueen",
        ),
        "miuccia-prada-prada-spring-summer-ready-to-wear-2012": (
            "Spring/Summer Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/spring-2012-ready-to-wear/prada",
        ),
        "rei-kawakubo-comme-des-garcons-spring-summer-ready-to-wear-1997": (
            "Spring/Summer Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/spring-1997-ready-to-wear/comme-des-garcons",
        ),
        "rei-kawakubo-comme-des-garcons-fall-winter-ready-to-wear-2024": (
            "Fall/Winter Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/fall-2024-ready-to-wear/comme-des-garcons",
        ),
    }

    for key, (season, source_url) in expected.items():
        assert collections[key]["season"] == season
        assert collections[key]["source_url"] == source_url
        assert collections[key]["status"] == "archived"


def test_export_import_preserves_non_default_collection_credits(tmp_path):
    source = tmp_path / "credits-source.db"
    restored = tmp_path / "credits-restored.db"
    exported = tmp_path / "credits.json"
    reexported = tmp_path / "credits-restored.json"
    import_archive(source, ARCHIVE, replace=True)

    connection = sqlite3.connect(source)
    try:
        guest_id = connection.execute(
            "INSERT INTO designers (full_name) VALUES ('Archive Credit Guest')"
        ).lastrowid
        collection_id = connection.execute(
            "SELECT id FROM collections ORDER BY id LIMIT 1"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO collection_credits
               (collection_id, designer_id, credit_role, credit_order, attribution_note)
               VALUES (?, ?, 'guest', 2, 'Archive round-trip credit')""",
            (collection_id, guest_id),
        )
        connection.commit()
    finally:
        connection.close()

    export_archive(source, exported)
    payload = json.loads(exported.read_text())
    credited = next(
        collection for collection in payload["collections"]
        if len(collection.get("credits", [])) == 2
    )
    assert credited["credits"][1]["attribution_note"] == (
        "Archive round-trip credit"
    )

    import_archive(restored, exported, replace=True)
    export_archive(restored, reexported)
    assert json.loads(exported.read_text()) == json.loads(reexported.read_text())


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
