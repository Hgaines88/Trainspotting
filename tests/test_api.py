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
    discovery_response = public_client.get(
        f"/designers?search=McQueen&page=2&archive_version={version}"
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
    assert discovery_response.headers["cache-control"] == (
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


def test_designer_alias_resolves_without_replacing_canonical_name(client):
    connection = database.connect()
    try:
        designer_id = connection.execute(
            "INSERT INTO designers (full_name) VALUES (?)", ("Nigo",)
        ).lastrowid
        connection.execute(
            """INSERT INTO designer_aliases (
                   designer_id, alias, normalized_alias, alias_type, source_url
               ) VALUES (?, ?, ?, ?, ?)""",
            (designer_id, "Tomoaki Nagao", "tomoaki nagao", "legal-name", "https://example.com/nigo"),
        )
        connection.commit()
    finally:
        connection.close()

    discovery = client.get("/designers?search=Tomoaki")
    options = client.get("/archive-options/designers?search=Nagao")
    detail = client.get(f"/designers/{designer_id}")
    punctuation_discovery = client.get("/designers?search=%2A%2A%2A")
    punctuation_options = client.get(
        "/archive-options/designers?search=%2A%2A%2A"
    )

    assert [item["full_name"] for item in discovery.json()["items"]] == ["Nigo"]
    assert [item["full_name"] for item in options.json()] == ["Nigo"]
    assert detail.json()["full_name"] == "Nigo"
    assert detail.json()["aliases"] == [{
        "alias": "Tomoaki Nagao",
        "alias_type": "legal-name",
        "source_url": "https://example.com/nigo",
    }]
    assert punctuation_discovery.json()["pagination"]["total"] == 0
    assert punctuation_options.json() == []


def test_discovery_equality_filters_are_case_insensitive_and_indexed(client):
    designers = client.get("/designers?nationality=japanese&page_size=50")
    collections = client.get(
        "/collections?label=alexander%20mcqueen&season=spring%2Fsummer"
    )

    assert designers.status_code == 200
    assert designers.json()["pagination"]["total"] > 0
    assert all(
        item["nationality"].lower() == "japanese"
        for item in designers.json()["items"]
    )
    assert collections.status_code == 200
    assert collections.json()["pagination"]["total"] >= 1

    connection = database.connect()
    try:
        plans = (
            connection.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM designers "
                "WHERE nationality COLLATE NOCASE = ?",
                ("japanese",),
            ).fetchall(),
            connection.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM collections "
                "WHERE label COLLATE NOCASE = ?",
                ("alexander mcqueen",),
            ).fetchall(),
            connection.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM collections "
                "WHERE season COLLATE NOCASE = ?",
                ("spring/summer",),
            ).fetchall(),
        )
    finally:
        connection.close()

    assert "idx_designers_nationality" in plans[0][0]["detail"]
    assert "idx_collections_label" in plans[1][0]["detail"]
    assert "idx_collections_season" in plans[2][0]["detail"]


def test_designer_newest_sort_defaults_to_descending(client):
    older = client.post(
        "/designers", json={"full_name": "Newest Default Test Older"}
    ).json()
    newer = client.post(
        "/designers", json={"full_name": "Newest Default Test Newer"}
    ).json()
    collection_payload = {
        "label": "Newest Default Test",
        "season": "Ready-to-wear",
        "status": "released",
    }
    assert client.post(
        "/collections",
        json={**collection_payload, "designer_id": older["id"], "release_year": 2001},
    ).status_code == 201
    assert client.post(
        "/collections",
        json={**collection_payload, "designer_id": newer["id"], "release_year": 2025},
    ).status_code == 201

    response = client.get("/designers?search=Newest%20Default%20Test&sort=newest")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        newer["id"],
        older["id"],
    ]


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
    assert collections.json()[0]["credits"] == [
        {
            "designer_id": collections.json()[0]["designer_id"],
            "designer_name": collections.json()[0]["lead_designer"],
            "role": "lead",
            "position": 1,
            "attribution_note": None,
        }
    ]
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
            "vimeo_video_id": "https://player.vimeo.com/video/76979871",
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
    assert detail_response.json()["vimeo_video_id"] == "76979871"

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
            "vimeo_video_id": "https://vimeo.com/channels/staffpicks/22439234",
        },
    )

    assert update_response.status_code == 200

    updated_detail = client.get(f"/collections/{collection_id}").json()

    assert updated_detail["source_url"] is None
    assert updated_detail["youtube_video_id"] == "dQw4w9WgXcQ"
    assert updated_detail["vimeo_video_id"] == "22439234"

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


def test_collection_rejects_non_vimeo_media_url(client):
    response = client.post(
        "/collections",
        json={
            "designer_id": 1,
            "label": "Invalid Vimeo Label",
            "season": "Resort",
            "release_year": 2027,
            "status": "concept",
            "vimeo_video_id": "https://example.com/video/76979871",
        },
    )

    assert response.status_code == 422
    assert "official Vimeo URL" in response.text


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


def test_related_collections_endpoint_is_public_explainable_and_bounded(client):
    target = client.get("/collections/1").json()

    response = client.get("/collections/1/related?limit=2")

    assert response.status_code == 200
    results = response.json()
    assert len(results) <= 2
    assert all(result["id"] != target["id"] for result in results)
    assert all(result["score"] > 0 for result in results)
    assert all(
        result["match_strength"] in {"Strong", "Notable", "Contextual"}
        for result in results
    )
    assert all(result["reasons"] for result in results)
    assert [result["score"] for result in results] == sorted(
        (result["score"] for result in results), reverse=True
    )


def test_related_collections_endpoint_validates_collection_and_limit(client):
    assert client.get("/collections/999999/related").status_code == 404
    assert client.get("/collections/1/related?limit=0").status_code == 422


def test_related_collection_batches_do_not_discard_older_strong_matches(client):
    target = client.get("/collections/1").json()
    connection = database.connect()
    try:
        weak_designer_id = connection.execute(
            "INSERT INTO designers (full_name) VALUES (?)",
            ("Recommendation Batch Designer",),
        ).lastrowid
        for index in range(205):
            weak_id = connection.execute(
                """INSERT INTO collections
                   (designer_id, label, season, release_year, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    weak_designer_id,
                    f"Recent Weak Match {index}",
                    target["season"],
                    2090,
                    "archived",
                ),
            ).lastrowid
            connection.execute(
                """INSERT INTO collection_credits
                   (collection_id, designer_id, credit_role, credit_order)
                   VALUES (?, ?, 'lead', 1)""",
                (weak_id, weak_designer_id),
            )
        strong_id = connection.execute(
            """INSERT INTO collections
               (designer_id, label, name, season, release_year, status, description)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                target["designer_id"],
                target["label"],
                target["name"],
                target["season"],
                1900,
                "archived",
                target["description"],
            ),
        ).lastrowid
        connection.execute(
            """INSERT INTO collection_credits
               (collection_id, designer_id, credit_role, credit_order)
               VALUES (?, ?, 'lead', 1)""",
            (strong_id, target["designer_id"]),
        )
        connection.commit()
    finally:
        connection.close()

    response = client.get("/collections/1/related?limit=1")

    assert response.status_code == 200
    assert response.json()[0]["id"] == strong_id
    assert f"Shared contributor: {target['lead_designer']}" in (
        response.json()[0]["reasons"]
    )


def test_collection_credits_are_ordered_queryable_and_compatibility_safe(client):
    guest = client.post(
        "/designers",
        json={"full_name": "Guest Credit Designer"},
    )
    assert guest.status_code == 201
    guest_id = guest.json()["id"]

    created = client.post(
        "/collections",
        json={
            "designer_id": 1,
            "label": "Collaborative Credit Label",
            "season": "Resort",
            "release_year": 2028,
            "status": "concept",
            "credits": [
                {
                    "designer_id": guest_id,
                    "role": "guest",
                    "position": 2,
                    "attribution_note": "Guest capsule contributor",
                },
                {"designer_id": 1, "role": "lead", "position": 1},
            ],
        },
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["designer_id"] == 1
    assert payload["lead_designer"]
    assert payload["credits"] == [
        {
            "designer_id": 1,
            "designer_name": payload["lead_designer"],
            "role": "lead",
            "position": 1,
            "attribution_note": None,
        },
        {
            "designer_id": guest_id,
            "designer_name": "Guest Credit Designer",
            "role": "guest",
            "position": 2,
            "attribution_note": "Guest capsule contributor",
        },
    ]

    collection_id = payload["id"]
    contributor_detail = client.get(
        f"/designers/{guest_id}/collections"
    ).json()
    assert [record["id"] for record in contributor_detail] == [collection_id]
    filtered = client.get(
        f"/collections?designer_id={guest_id}&page_size=10"
    ).json()
    assert [record["id"] for record in filtered["items"]] == [collection_id]

    legacy = client.post(
        "/collections",
        json={
            "designer_id": guest_id,
            "label": "Legacy Client Label",
            "season": "Resort",
            "release_year": 2029,
            "status": "concept",
        },
    )
    assert legacy.status_code == 201
    assert legacy.json()["credits"] == [
        {
            "designer_id": guest_id,
            "designer_name": "Guest Credit Designer",
            "role": "lead",
            "position": 1,
            "attribution_note": None,
        }
    ]

    updated = client.put(
        f"/collections/{collection_id}",
        json={
            "designer_id": guest_id,
            "label": "Collaborative Credit Label",
            "season": "Resort",
            "release_year": 2028,
            "status": "released",
            "credits": [
                {"designer_id": guest_id, "role": "lead", "position": 1},
                {
                    "designer_id": 1,
                    "role": "co-designer",
                    "position": 2,
                },
            ],
        },
    )
    assert updated.status_code == 200
    assert [credit["designer_id"] for credit in updated.json()["credits"]] == [
        guest_id,
        1,
    ]
    assert updated.json()["designer_id"] == guest_id


@pytest.mark.parametrize(
    "credits",
    [
        [],
        [
            {"designer_id": 1, "role": "lead", "position": 1},
            {"designer_id": 1, "role": "guest", "position": 2},
        ],
        [
            {"designer_id": 1, "role": "lead", "position": 1},
            {"designer_id": 2, "role": "guest", "position": 1},
        ],
        [{"designer_id": 2, "role": "lead", "position": 1}],
    ],
)
def test_collection_credit_validation_rejects_ambiguous_credits(client, credits):
    response = client.post(
        "/collections",
        json={
            "designer_id": 1,
            "label": "Invalid Credit Label",
            "season": "Resort",
            "release_year": 2030,
            "status": "concept",
            "credits": credits,
        },
    )
    assert response.status_code == 422


def test_unknown_secondary_credit_rolls_back_collection_create(client):
    response = client.post(
        "/collections",
        json={
            "designer_id": 1,
            "label": "Unknown Contributor Label",
            "season": "Resort",
            "release_year": 2030,
            "status": "concept",
            "credits": [
                {"designer_id": 1, "role": "lead", "position": 1},
                {"designer_id": 999999, "role": "guest", "position": 2},
            ],
        },
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Credited designer not found: 999999"}
    assert client.get(
        "/collections?search=Unknown%20Contributor%20Label"
    ).json()["pagination"]["total"] == 0
