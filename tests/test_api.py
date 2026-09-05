from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import database
from app.auth import ClerkIdentity, require_authenticated_user
from app.database import current_archive_version
from app.main import app, require_archive_admin
from app.request_limits import MAX_MUTATION_BODY_BYTES


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


def archive_version(client):
    response = client.get("/archive-version")
    assert response.status_code == 200
    return response.json()["version"]


def test_only_anonymous_public_reads_are_shared_cacheable(public_client):
    version = archive_version(public_client)
    public_response = public_client.get(f"/designers?archive_version={version}")
    collections_response = public_client.get(
        f"/collections?archive_version={version}"
    )
    unversioned_response = public_client.get("/designers")
    stale_response = public_client.get(f"/designers?archive_version={version + 1}")
    authenticated_response = public_client.get(
        f"/designers?archive_version={version}",
        headers={"Authorization": "Bearer untrusted"},
    )
    version_response = public_client.get("/archive-version")

    assert public_response.headers["cache-control"] == (
        "public, max-age=0, s-maxage=30, stale-while-revalidate=60"
    )
    assert collections_response.headers["cache-control"] == (
        "public, max-age=0, s-maxage=30, stale-while-revalidate=60"
    )
    assert authenticated_response.headers["cache-control"] == "private, no-store"
    assert unversioned_response.headers["cache-control"] == "private, no-store"
    assert stale_response.headers["cache-control"] == "private, no-store"
    assert version_response.headers["cache-control"] == "private, no-store"


def test_public_cache_version_reads_run_outside_the_event_loop(
    public_client, monkeypatch
):
    version = archive_version(public_client)
    calls = []

    async def record_threadpool_call(function):
        calls.append(function)
        return function()

    monkeypatch.setattr("app.main.run_in_threadpool", record_threadpool_call)

    response = public_client.get(f"/designers?archive_version={version}")

    assert response.status_code == 200
    assert calls == [current_archive_version, current_archive_version]


def test_declared_oversized_mutation_is_rejected_before_authentication(public_client):
    response = public_client.post(
        "/submissions",
        content=b"{}",
        headers={"Content-Length": str(MAX_MUTATION_BODY_BYTES + 1)},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large."}
    assert response.headers["cache-control"] == "private, no-store"


def test_streamed_oversized_mutation_is_rejected(public_client):
    def oversized_body():
        yield b"x" * (MAX_MUTATION_BODY_BYTES // 2)
        yield b"x" * (MAX_MUTATION_BODY_BYTES // 2 + 1)

    response = public_client.post("/submissions", content=oversized_body())

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large."}


def test_small_mutation_continues_to_authentication(public_client):
    response = public_client.post("/submissions", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_large_get_is_not_subject_to_mutation_body_limit(public_client):
    response = public_client.request(
        "GET",
        "/designers",
        content=b"x" * (MAX_MUTATION_BODY_BYTES + 1),
    )

    assert response.status_code == 200


def test_canonical_admin_writes_increment_archive_version_transactionally(client):
    initial = archive_version(client)
    response = client.post("/designers", json={"full_name": "Versioned Designer"})
    assert response.status_code == 201
    designer_id = response.json()["id"]
    assert archive_version(client) == initial + 1

    duplicate = client.post("/designers", json={"full_name": "Versioned Designer"})
    assert duplicate.status_code == 409
    assert archive_version(client) == initial + 1

    assert client.delete(f"/designers/{designer_id}").status_code == 204
    assert archive_version(client) == initial + 2


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

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required."
    }


@pytest.mark.parametrize("role", ["member", "moderator"])
def test_authenticated_non_admin_cannot_mutate_the_archive(public_client, role):
    clerk_user_id = f"user_{role}123"
    if role == "moderator":
        connection = database.connect()
        try:
            connection.execute(
                "INSERT INTO users (clerk_user_id, role) VALUES (?, ?)",
                (clerk_user_id, role),
            )
            connection.commit()
        finally:
            connection.close()

    app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
        user_id=clerk_user_id,
        session_id=f"sess_{role}123",
    )

    try:
        response = public_client.post(
            "/designers",
            json={"full_name": "Member Write Attempt"},
        )
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)

    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator access required."}

    connection = database.connect()
    try:
        member = connection.execute(
            "SELECT role FROM users WHERE clerk_user_id = ?",
            (clerk_user_id,),
        ).fetchone()
    finally:
        connection.close()

    assert member["role"] == role


def test_authenticated_admin_can_mutate_the_archive(public_client):
    connection = database.connect()
    try:
        connection.execute(
            "INSERT INTO users (clerk_user_id, role) VALUES (?, 'admin')",
            ("user_admin123",),
        )
        connection.commit()
    finally:
        connection.close()

    app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
        user_id="user_admin123",
        session_id="sess_admin123",
    )

    try:
        response = public_client.post(
            "/designers",
            json={"full_name": "Administrator Created Designer"},
        )
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)

    assert response.status_code == 201
    assert response.json()["full_name"] == "Administrator Created Designer"


def test_list_designers(client):
    response = client.get("/designers?page_size=50")

    assert response.status_code == 200

    payload = response.json()
    designers = payload["items"]

    assert len(designers) == 30
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 50,
        "total": 30,
        "total_pages": 1,
    }
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


def test_designer_discovery_search_filters_and_paginates_stably(client):
    search = client.get("/designers?search=Afro-Atlantic")
    filtered = client.get(
        "/designers?nationality=Japanese&sort=name&page_size=1"
    )
    second_page = client.get(
        "/designers?nationality=Japanese&sort=name&page=2&page_size=1"
    )

    assert search.status_code == 200
    assert [item["full_name"] for item in search.json()["items"]] == [
        "Grace Wales Bonner"
    ]
    assert filtered.status_code == 200
    assert filtered.json()["pagination"]["total"] >= 2
    assert second_page.status_code == 200
    assert filtered.json()["items"][0]["id"] != second_page.json()["items"][0]["id"]


def test_collection_discovery_search_filters_and_paginates_stably(client):
    response = client.get(
        "/collections?search=No.%2013&status=archived&sort=label&page_size=5"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 5,
        "total": 1,
        "total_pages": 1,
    }
    assert payload["items"][0]["name"] == "No. 13"


@pytest.mark.parametrize(
    "path",
    [
        "/designers?page=0",
        "/designers?page_size=51",
        "/designers?year=1899",
        "/designers?status=unknown",
        "/designers?sort=unknown",
        "/collections?page_size=0",
        "/collections?designer_id=0",
        "/collections?direction=sideways",
    ],
)
def test_archive_discovery_rejects_invalid_query_values(client, path):
    assert client.get(path).status_code == 422


def test_archive_option_search_is_filtered_and_bounded(client):
    designers = client.get("/archive-options/designers?search=Wales&limit=5")
    collections = client.get("/archive-options/collections?search=No.%2013&limit=5")
    bounded = client.get("/archive-options/designers?limit=3")

    assert designers.status_code == 200
    assert [item["full_name"] for item in designers.json()] == ["Grace Wales Bonner"]
    assert collections.status_code == 200
    assert [item["name"] for item in collections.json()] == ["No. 13"]
    assert len(bounded.json()) == 3
    assert set(designers.json()[0]) == {"id", "full_name", "nationality"}


def test_archive_option_search_enforces_query_limits(client):
    assert client.get("/archive-options/designers?limit=51").status_code == 422
    assert client.get(f"/archive-options/collections?search={'x' * 121}").status_code == 422


def test_me_creates_one_member_for_the_verified_clerk_identity(client):
    app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
        user_id="user_first123",
        session_id="sess_first123",
    )

    try:
        first_response = client.get("/me")
        second_response = client.get("/me")
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["clerk_user_id"] == "user_first123"
    assert first_response.json()["role"] == "member"
    assert second_response.json()["id"] == first_response.json()["id"]

    connection = database.connect()
    try:
        user_count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE clerk_user_id = ?",
            ("user_first123",),
        ).fetchone()[0]
    finally:
        connection.close()

    assert user_count == 1


def test_me_synchronizes_trusted_clerk_profile_fields(client, monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-secret")

    class FakeClerk:
        def __init__(self, bearer_auth):
            assert bearer_auth == "test-secret"
            self.users = self

        def get(self, *, user_id):
            assert user_id == "user_profile123"
            return SimpleNamespace(
                first_name="Grace",
                last_name="Hopper",
                username="grace",
                primary_email_address_id="email_primary",
                email_addresses=[SimpleNamespace(
                    id="email_primary",
                    email_address="grace@example.com",
                )],
            )

    monkeypatch.setattr("app.users.Clerk", FakeClerk)
    app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
        user_id="user_profile123",
        session_id="sess_profile123",
    )
    try:
        response = client.get("/me")
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)

    assert response.status_code == 200
    assert response.json()["display_name"] == "Grace Hopper"
    assert response.json()["email"] == "grace@example.com"
    assert response.json()["role"] == "member"

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

    designers = client.get("/designers?page_size=50").json()["items"]
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


def test_every_seeded_collection_has_a_designer(client):
    designers_response = client.get("/designers?page_size=50")
    collections_response = client.get("/collections?page_size=100")

    assert designers_response.status_code == 200
    assert collections_response.status_code == 200

    designer_ids = {
        designer["id"]
        for designer in designers_response.json()["items"]
    }
    credited_designer_ids = {
        collection["designer_id"]
        for collection in collections_response.json()["items"]
    }

    assert credited_designer_ids <= designer_ids


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
    existing = client.get("/designers").json()["items"][0]["full_name"]

    response = client.post("/designers", json={"full_name": existing})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "A designer with this name already exists"
    }


def test_duplicate_collection_returns_409(client):
    designers = client.get("/designers").json()["items"]
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
    designers = client.get("/designers").json()["items"]
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
