import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import ClerkIdentity, require_authenticated_user
from app.database import connect
from app.main import app


MYSQL_TEST_DATABASE_URL = os.getenv("MYSQL_TEST_DATABASE_URL")


@pytest.mark.skipif(
    not MYSQL_TEST_DATABASE_URL,
    reason="MYSQL_TEST_DATABASE_URL is required for the MySQL runtime test",
)
def test_mysql_submission_approval_audit_and_rollback(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", MYSQL_TEST_DATABASE_URL)
    tag = uuid.uuid4().hex[:12]
    member_identity = f"mysql-member-{tag}"
    admin_identity = f"mysql-admin-{tag}"

    connection = connect()
    try:
        connection.execute(
            "INSERT INTO users (clerk_user_id, display_name, role) VALUES (?, ?, ?)",
            (member_identity, "MySQL Member", "member"),
        )
        connection.execute(
            "INSERT INTO users (clerk_user_id, display_name, role) VALUES (?, ?, ?)",
            (admin_identity, "MySQL Admin", "admin"),
        )
        connection.commit()
    finally:
        connection.close()

    try:
        with TestClient(app) as client:
            initial_version = client.get("/archive-version").json()["version"]
            app.dependency_overrides.pop(require_authenticated_user, None)
            response = client.post(
                "/designers", json={"full_name": f"Anonymous MySQL {tag}"}
            )
            assert response.status_code == 401

            app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
                user_id=member_identity,
                session_id=f"member-session-{tag}",
            )
            response = client.post(
                "/designers", json={"full_name": f"Member MySQL {tag}"}
            )
            assert response.status_code == 403

            response = client.post(
                "/submissions",
                json={
                    "record_type": "designer",
                    "submission_type": "addition",
                    "proposed_data": {
                        "full_name": f"MySQL Runtime Designer {tag}",
                        "nationality": "American",
                    },
                    "explanation": "Automated MySQL runtime verification.",
                    "sources": [{"url": "https://example.com/mysql-runtime"}],
                },
            )
            assert response.status_code == 201
            submission_id = response.json()["id"]

            app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
                user_id=admin_identity,
                session_id=f"admin-session-{tag}",
            )
            direct_name = f"MySQL Direct CRUD {tag}"
            response = client.post("/designers", json={"full_name": direct_name})
            assert response.status_code == 201
            direct_designer_id = response.json()["id"]
            assert client.post(
                "/designers", json={"full_name": direct_name}
            ).status_code == 409
            assert client.delete(
                f"/designers/{direct_designer_id}"
            ).status_code == 204

            response = client.post(
                f"/moderation/submissions/{submission_id}/decisions",
                json={"decision": "approve", "notes": "Verified on MySQL."},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "approved"

            discovery = client.get(
                f"/designers?search={tag}&sort=collections&direction=desc"
                "&page=1&page_size=5"
            )
            assert discovery.status_code == 200
            assert discovery.json()["pagination"]["total"] == 1
            assert discovery.json()["items"][0]["full_name"] == (
                f"MySQL Runtime Designer {tag}"
            )

            response = client.post(
                f"/moderation/submissions/{submission_id}/rollback",
                json={"reason": "Automated MySQL verification complete."},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "rolled_back"

            response = client.get(f"/submissions/{submission_id}/audit")
            assert response.status_code == 200
            assert [event["event_type"] for event in response.json()] == [
                "submitted",
                "approved",
                "rolled_back",
            ]
            assert client.get("/archive-version").json()["version"] == (
                initial_version + 4
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)


@pytest.mark.skipif(
    not MYSQL_TEST_DATABASE_URL,
    reason="MYSQL_TEST_DATABASE_URL is required for the MySQL runtime test",
)
def test_mysql_multiple_collection_credits_round_trip(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", MYSQL_TEST_DATABASE_URL)
    tag = uuid.uuid4().hex[:12]
    admin_identity = f"mysql-credit-admin-{tag}"
    connection = connect()
    try:
        connection.execute(
            "INSERT INTO users (clerk_user_id, role) VALUES (?, 'admin')",
            (admin_identity,),
        )
        connection.commit()
    finally:
        connection.close()

    try:
        app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
            user_id=admin_identity,
            session_id=f"credit-session-{tag}",
        )
        with TestClient(app) as client:
            lead = client.post(
                "/designers", json={"full_name": f"MySQL Credit Lead {tag}"}
            ).json()
            guest = client.post(
                "/designers", json={"full_name": f"MySQL Credit Guest {tag}"}
            ).json()
            response = client.post(
                "/collections",
                json={
                    "designer_id": lead["id"],
                    "label": f"MySQL Credits {tag}",
                    "season": "Resort",
                    "release_year": 2028,
                    "status": "concept",
                    "credits": [
                        {
                            "designer_id": lead["id"],
                            "role": "lead",
                            "position": 1,
                        },
                        {
                            "designer_id": guest["id"],
                            "role": "guest",
                            "position": 2,
                            "attribution_note": "MySQL integration credit",
                        },
                    ],
                },
            )
            assert response.status_code == 201
            assert [
                (credit["designer_id"], credit["role"], credit["position"])
                for credit in response.json()["credits"]
            ] == [
                (lead["id"], "lead", 1),
                (guest["id"], "guest", 2),
            ]
            contributed = client.get(
                f"/designers/{guest['id']}/collections"
            )
            assert contributed.status_code == 200
            assert contributed.json()[0]["id"] == response.json()["id"]
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)
