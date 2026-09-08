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
                "designer_aliases",
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


def test_canonical_aliases_round_trip_with_sources(tmp_path):
    database = tmp_path / "aliases.db"
    exported = tmp_path / "aliases.json"

    import_archive(database, ARCHIVE, replace=True)
    export_archive(database, exported)

    designers = {
        designer["key"]: designer
        for designer in json.loads(exported.read_text())["designers"]
    }
    assert designers["nigo"]["aliases"] == [{
        "alias": "Tomoaki Nagao",
        "alias_type": "legal-name",
        "source_url": "https://en.wikipedia.org/wiki/Nigo",
    }]


def test_demo_alias_enrichment_is_sourced_and_keeps_display_names(tmp_path):
    database = tmp_path / "demo-aliases.db"
    exported = tmp_path / "demo-aliases.json"

    import_archive(database, ARCHIVE, replace=True)
    export_archive(database, exported)

    payload = json.loads(exported.read_text(encoding="utf-8"))
    designers = {
        designer["key"]: designer for designer in payload["designers"]
    }
    expected = {
        "cristobal-balenciaga": (
            "Cristóbal Balenciaga",
            ["Cristóbal Balenciaga Eizaguirre"],
        ),
        "christian-dior": (
            "Christian Dior",
            ["Christian Ernest Dior"],
        ),
        "demna-gvasalia": (
            "Demna Gvasalia",
            ["Demna"],
        ),
        "jil-sander": (
            "Jil Sander",
            ["Heidemarie Jiline Sander"],
        ),
        "john-galliano": (
            "John Galliano",
            ["Juan Carlos Antonio Galliano-Guillén"],
        ),
        "lee-alexander-mcqueen": (
            "Lee Alexander McQueen",
            ["Alexander McQueen"],
        ),
        "miuccia-prada": (
            "Miuccia Prada",
            ["Maria Bianchi"],
        ),
        "rick-owens": (
            "Rick Owens",
            ["Richard Saturnino Owens"],
        ),
        "thierry-mugler": (
            "Thierry Mugler",
            ["Manfred Thierry Mugler"],
        ),
        "tom-ford": (
            "Tom Ford",
            ["Thomas Carlyle Ford"],
        ),
        "ye-kanye-west": (
            "Ye (Kanye West)",
            ["Kanye West", "Ye"],
        ),
        "yves-saint-laurent": (
            "Yves Saint Laurent",
            ["Yves Henri Donat Mathieu-Saint-Laurent"],
        ),
    }

    for key, (display_name, aliases) in expected.items():
        designer = designers[key]
        assert designer["full_name"] == display_name
        assert [item["alias"] for item in designer["aliases"]] == aliases
        assert all(
            item["source_url"].startswith("https://en.wikipedia.org/wiki/")
            for item in designer["aliases"]
        )

    ye_aliases = designers["ye-kanye-west"]["aliases"]
    assert [item["alias_type"] for item in ye_aliases] == [
        "former-name",
        "legal-name",
    ]
    assert "Yeezy" not in {item["alias"] for item in ye_aliases}


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


def test_final_source_batch_has_verified_taxonomy_sources_and_statuses():
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    collections = {
        collection["key"]: collection
        for collection in payload["collections"]
    }
    expected = {
        "rick-owens-rick-owens-spring-summer-ready-to-wear-2014": (
            "Spring/Summer Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/spring-2014-ready-to-wear/rick-owens",
        ),
        "sarah-burton-alexander-mcqueen-spring-summer-ready-to-wear-2024": (
            "Spring/Summer Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/spring-2024-ready-to-wear/alexander-mcqueen",
        ),
        "sarah-burton-givenchy-fall-winter-ready-to-wear-2025": (
            "Fall/Winter Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/fall-2025-ready-to-wear/givenchy",
        ),
        "virgil-abloh-louis-vuitton-spring-summer-menswear-2019": (
            "Spring/Summer Menswear",
            "https://www.vogue.com/fashion-shows/spring-2019-menswear/louis-vuitton",
        ),
        "ye-kanye-west-yeezy-spring-summer-ready-to-wear-2017": (
            "Spring/Summer Ready-to-Wear",
            "https://www.vogue.com/fashion-shows/spring-2017-ready-to-wear/kanye-west-adidas-originals",
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


def test_export_import_preserves_vimeo_collection_media(tmp_path):
    source = tmp_path / "vimeo-source.db"
    restored = tmp_path / "vimeo-restored.db"
    exported = tmp_path / "vimeo.json"
    reexported = tmp_path / "vimeo-restored.json"
    import_archive(source, ARCHIVE, replace=True)

    connection = sqlite3.connect(source)
    try:
        collection_id = connection.execute(
            "SELECT id FROM collections ORDER BY id LIMIT 1"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO collection_media
               (collection_id, media_type, media_value)
               VALUES (?, 'vimeo', '76979871')""",
            (collection_id,),
        )
        connection.commit()
    finally:
        connection.close()

    export_archive(source, exported)
    payload = json.loads(exported.read_text())
    assert any(
        collection.get("vimeo_video_id") == "76979871"
        for collection in payload["collections"]
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


def test_hedi_slimane_profile_spans_three_houses_with_sourced_media():
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    designers = {
        designer["key"]: designer
        for designer in payload["designers"]
    }
    collections = [
        collection
        for collection in payload["collections"]
        if collection["designer_key"] == "hedi-slimane"
    ]

    assert designers["hedi-slimane"]["nationality"] == "French"
    assert len(collections) == 6
    assert {collection["label"] for collection in collections} == {
        "Celine",
        "Celine Homme",
        "Dior Homme",
        "Saint Laurent",
    }
    assert all(collection["source_url"] for collection in collections)
    assert all(
        collection["youtube_video_id"] or collection["vimeo_video_id"]
        for collection in collections
    )
    for collection in collections:
        assert len(collection["credits"]) == 1
        credit = collection["credits"][0]
        assert credit["role"] == "lead"
        assert credit["position"] == 1
        assert credit["designer_key"] == "hedi-slimane"
        assert credit["attribution_note"].strip()


def test_demo_x03_expansion_has_sources_and_ordered_credits():
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    designer_keys = {
        "christian-dior",
        "cristobal-balenciaga",
        "dapper-dan",
        "elsa-schiaparelli",
        "helmut-lang",
        "iris-van-herpen",
        "jean-paul-gaultier",
        "nigo",
        "phoebe-philo",
        "thierry-mugler",
    }
    archive_designer_keys = {
        designer["key"] for designer in payload["designers"]
    }
    assert designer_keys <= archive_designer_keys

    expanded_collections = [
        collection
        for collection in payload["collections"]
        if collection["designer_key"] in designer_keys
    ]
    assert len(expanded_collections) == 50
    assert all(collection.get("credits") for collection in expanded_collections)
    assert all(collection["source_url"] for collection in expanded_collections)
    assert all(
        [credit["position"] for credit in collection["credits"]]
        == list(range(1, len(collection["credits"]) + 1))
        for collection in expanded_collections
    )

    lv2 = next(
        collection
        for collection in payload["collections"]
        if collection["key"] == "virgil-abloh-louis-vuitton-pre-fall-2020"
    )
    assert [
        (credit["designer_key"], credit["role"], credit["position"])
        for credit in lv2["credits"]
    ] == [
        ("virgil-abloh", "lead", 1),
        ("nigo", "collaborator", 2),
    ]

    expected_collaborations = {
        "dapper-dan-gucci-dapper-dan-pre-fall-2018": [
            ("dapper-dan", "lead", 1),
            ("alessandro-michele", "collaborator", 2),
        ],
        "pharrell-williams-louis-vuitton-fall-winter-menswear-2025": [
            ("pharrell-williams", "lead", 1),
            ("nigo", "co-designer", 2),
        ],
    }
    for collection_key, expected_credits in expected_collaborations.items():
        collection = next(
            item
            for item in payload["collections"]
            if item["key"] == collection_key
        )
        assert [
            (credit["designer_key"], credit["role"], credit["position"])
            for credit in collection["credits"]
        ] == expected_credits
