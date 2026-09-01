from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app, require_archive_admin


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        test_database_path,
    )

    connection = database.connect()

    try:
        schema_sql = (
            PROJECT_ROOT / "sql" / "schema.sql"
        ).read_text()

        seed_sql = (
            PROJECT_ROOT / "sql" / "seed.sql"
        ).read_text()

        connection.executescript(schema_sql)
        connection.executescript(seed_sql)
    finally:
        connection.close()

    app.dependency_overrides[require_archive_admin] = lambda: None

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(require_archive_admin, None)


@pytest.fixture
def public_client(tmp_path, monkeypatch):
    test_database_path = tmp_path / "public-test.db"

    monkeypatch.setattr(database, "DATABASE_PATH", test_database_path)
    connection = database.connect()

    try:
        connection.executescript(
            (PROJECT_ROOT / "sql" / "schema.sql").read_text()
        )
        connection.executescript(
            (PROJECT_ROOT / "sql" / "seed.sql").read_text()
        )
    finally:
        connection.close()

    app.dependency_overrides.pop(require_archive_admin, None)

    with TestClient(app) as test_client:
        yield test_client


DESIGNER_PAYLOAD = {"full_name": "Public Write Attempt"}
COLLECTION_PAYLOAD = {
    "designer_id": 1,
    "label": "Public Write Attempt",
    "season": "Resort",
    "release_year": 2030,
    "status": "concept",
}


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/designers", DESIGNER_PAYLOAD),
        ("put", "/designers/1", DESIGNER_PAYLOAD),
        ("delete", "/designers/1", None),
        ("post", "/collections", COLLECTION_PAYLOAD),
        ("put", "/collections/1", COLLECTION_PAYLOAD),
        ("delete", "/collections/1", None),
        (
            "post",
            "/designers/1/collections",
            COLLECTION_PAYLOAD,
        ),
    ],
)
def test_public_archive_mutations_require_admin(
    public_client,
    method,
    path,
    payload,
):
    response = public_client.request(method, path, json=payload)

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Archive changes require administrator access."
    }


def test_list_designers(client):
    response = client.get("/designers")

    assert response.status_code == 200

    designers = response.json()

    assert len(designers) == 30
    designer_names = {
        designer["full_name"]
        for designer in designers
    }
    assert {
        "Demna Gvasalia",
        "Grace Wales Bonner",
        "Junya Watanabe",
        "Jonathan Anderson",
        "Lee Alexander McQueen",
        "Miuccia Prada",
        "Rei Kawakubo",
        "Rick Owens",
        "Sarah Burton",
        "Shayne Oliver",
        "Telfar Clemens",
        "Virgil Abloh",
        "Tom Ford",
        "Jun Takahashi",
        "Thom Browne",
        "Yohji Yamamoto",
        "Willy Chavarria",
        "Olivier Rousteing",
        "Issey Miyake",
        "Jil Sander",
        "Craig Green",
        "John Elliott",
        "Haider Ackermann",
    } <= designer_names

def test_get_designer(client):
    response = client.get("/designers/1")

    assert response.status_code == 200
    assert response.json()["full_name"] == "Sarah Burton"


def test_missing_designer_returns_404(client):
    response = client.get("/designers/999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Designer not found"
    }


def test_designer_website_is_normalized(client):
    response = client.post(
        "/designers",
        json={
            "full_name": "Website Test Designer",
            "nationality": None,
            "birth_year": None,
            "website": "www.example.com",
            "biography": None,
        },
    )

    assert response.status_code == 201
    assert response.json()["website"] == "https://www.example.com"


def test_blank_and_unsafe_designer_websites(client):
    blank_response = client.post(
        "/designers",
        json={
            "full_name": "Blank Website Designer",
            "website": "   ",
        },
    )
    unsafe_response = client.post(
        "/designers",
        json={
            "full_name": "Unsafe Website Designer",
            "website": "javascript:alert(1)",
        },
    )

    assert blank_response.status_code == 201
    assert blank_response.json()["website"] is None
    assert unsafe_response.status_code == 422


def test_malformed_designer_domain_is_rejected(client):
    response = client.post(
        "/designers",
        json={
            "full_name": "Malformed Domain Designer",
            "website": "https://not a url at all !!",
        },
    )

    assert response.status_code == 422


def test_designer_without_collections_is_listed_with_zero_count(client):
    created = client.post(
        "/designers",
        json={"full_name": "Zero Collection Designer"},
    )
    assert created.status_code == 201

    designers = client.get("/designers").json()
    listed = next(
        designer
        for designer in designers
        if designer["id"] == created.json()["id"]
    )

    assert listed["collection_count"] == 0


def test_list_collections_for_designer(client):
    response = client.get("/designers/1/collections")

    assert response.status_code == 200

    collections = response.json()

    assert len(collections) == 2
    assert all(
        collection["designer_id"] == 1
        for collection in collections
    )
    assert {
        collection["label"]
        for collection in collections
    } == {"Alexander McQueen", "Givenchy"}


def test_every_seeded_designer_has_a_collection(client):
    designers_response = client.get("/designers")
    collections_response = client.get("/collections")

    assert designers_response.status_code == 200
    assert collections_response.status_code == 200

    designer_ids = {
        designer["id"]
        for designer in designers_response.json()
    }
    credited_designer_ids = {
        collection["designer_id"]
        for collection in collections_response.json()
    }

    assert designer_ids <= credited_designer_ids


def test_collection_media_is_normalized_and_updated(client):
    create_response = client.post(
        "/collections",
        json={
            "designer_id": 1,
            "label": "Media Test Label",
            "name": None,
            "season": "Resort",
            "release_year": 2027,
            "status": "concept",
            "piece_count": None,
            "description": None,
            "source_url": "https://example.com/runway-review",
            "youtube_video_id": (
                "https://www.youtube.com/watch?v=M7lc1UVf-VE"
            ),
        },
    )

    assert create_response.status_code == 201
    collection_id = create_response.json()["id"]

    detail_response = client.get(f"/collections/{collection_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["source_url"] == (
        "https://example.com/runway-review"
    )
    assert detail_response.json()["youtube_video_id"] == "M7lc1UVf-VE"

    update_response = client.put(
        f"/collections/{collection_id}",
        json={
            "designer_id": 1,
            "label": "Media Test Label",
            "name": None,
            "season": "Resort",
            "release_year": 2027,
            "status": "released",
            "piece_count": None,
            "description": None,
            "source_url": None,
            "youtube_video_id": "https://youtu.be/dQw4w9WgXcQ",
        },
    )

    assert update_response.status_code == 200

    updated_detail = client.get(f"/collections/{collection_id}").json()

    assert updated_detail["source_url"] is None
    assert updated_detail["youtube_video_id"] == "dQw4w9WgXcQ"

    delete_response = client.delete(f"/collections/{collection_id}")
    assert delete_response.status_code == 204

    connection = database.connect()
    try:
        remaining_media = connection.execute(
            """
            SELECT COUNT(*)
            FROM collection_media
            WHERE collection_id = ?
            """,
            (collection_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert remaining_media == 0


def test_deleting_designer_cascades_to_collections(client):
    designer_response = client.post(
        "/designers",
        json={
            "full_name": "Temporary Cascade Designer",
            "nationality": None,
            "birth_year": None,
            "website": None,
            "biography": None,
        },
    )

    assert designer_response.status_code == 201
    designer_id = designer_response.json()["id"]

    collection_response = client.post(
        "/collections",
        json={
            "designer_id": designer_id,
            "label": "Temporary Label",
            "name": None,
            "season": "Resort",
            "release_year": 2026,
            "status": "concept",
            "piece_count": None,
            "description": "Temporary cascade test.",
        },
    )

    assert collection_response.status_code == 201
    collection_id = collection_response.json()["id"]

    delete_response = client.delete(
        f"/designers/{designer_id}"
    )

    assert delete_response.status_code == 204

    missing_collection_response = client.get(
        f"/collections/{collection_id}"
    )

    assert missing_collection_response.status_code == 404


def test_designer_update_round_trip(client):
    created = client.post(
        "/designers",
        json={"full_name": "Update Round Trip Designer"},
    )
    assert created.status_code == 201
    designer_id = created.json()["id"]

    updated = client.put(
        f"/designers/{designer_id}",
        json={
            "full_name": "Update Round Trip Designer",
            "nationality": "Canadian",
            "birth_year": 1979,
            "website": "example.org",
            "biography": "Updated through the API.",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["nationality"] == "Canadian"
    assert updated.json()["birth_year"] == 1979
    assert updated.json()["website"] == "https://example.org"

    reread = client.get(f"/designers/{designer_id}")
    assert reread.json() == updated.json()


def test_updating_a_missing_designer_returns_404(client):
    response = client.put(
        "/designers/999999",
        json={"full_name": "Nobody"},
    )
    assert response.status_code == 404


def test_duplicate_designer_name_returns_409(client):
    existing = client.get("/designers").json()[0]["full_name"]

    response = client.post("/designers", json={"full_name": existing})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "A designer with this name already exists"
    }


def test_duplicate_collection_returns_409(client):
    designers = client.get("/designers").json()
    designer_id = designers[0]["id"]
    payload = {
        "designer_id": designer_id,
        "label": "Duplicate Guard Label",
        "season": "Resort",
        "release_year": 2029,
        "status": "concept",
    }

    first = client.post("/collections", json=payload)
    second = client.post("/collections", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "This collection already exists"}


def test_collection_for_unknown_designer_returns_404(client):
    response = client.post(
        "/collections",
        json={
            "designer_id": 999999,
            "label": "Orphan Label",
            "season": "Resort",
            "release_year": 2029,
            "status": "concept",
        },
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Designer not found"}


def test_nested_collection_create_uses_path_designer(client):
    designers = client.get("/designers").json()
    designer_id = designers[0]["id"]

    response = client.post(
        f"/designers/{designer_id}/collections",
        json={
            "designer_id": 999999,
            "label": "Nested Route Label",
            "season": "Resort",
            "release_year": 2029,
            "status": "concept",
        },
    )

    assert response.status_code == 201
    assert response.json()["designer_id"] == designer_id

    collections = client.get(
        f"/designers/{designer_id}/collections"
    ).json()
    assert response.json()["id"] in {
        collection["id"] for collection in collections
    }
