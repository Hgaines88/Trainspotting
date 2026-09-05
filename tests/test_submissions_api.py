import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import database
from app.auth import ClerkIdentity, require_authenticated_user
from app.main import app
from app.observability import service_metrics


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE = {"url": "https://example.com/documented-source", "title": "Source"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "moderation.db")
    connection = database.connect()
    try:
        connection.executescript((PROJECT_ROOT / "sql" / "schema.sql").read_text())
        connection.executescript((PROJECT_ROOT / "sql" / "seed.sql").read_text())
    finally:
        connection.close()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(require_authenticated_user, None)


def authenticate(user_id, role="member"):
    connection = database.connect()
    try:
        connection.execute(
            "INSERT OR IGNORE INTO users (clerk_user_id, role) VALUES (?, ?)",
            (user_id, role),
        )
        connection.execute(
            "UPDATE users SET role = ? WHERE clerk_user_id = ?", (role, user_id)
        )
        connection.commit()
    finally:
        connection.close()
    app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
        user_id=user_id, session_id=f"session_{user_id}"
    )


def designer_submission(name="Documented Designer"):
    return {
        "record_type": "designer",
        "submission_type": "addition",
        "proposed_data": {"full_name": name, "nationality": "American"},
        "explanation": "This designer belongs in the archive.",
        "sources": [SOURCE],
    }


def count_rows(table):
    connection = database.connect()
    try:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        connection.close()


def archive_version(client):
    return client.get("/archive-version").json()["version"]


def test_only_canonical_promotion_and_rollback_increment_archive_version(client):
    authenticate("user_version_submitter")
    initial = archive_version(client)
    submission = client.post(
        "/submissions", json=designer_submission("Version Workflow Designer")
    ).json()
    assert archive_version(client) == initial

    authenticate("user_version_admin", "admin")
    approved = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve", "notes": "Version test."},
    )
    assert approved.status_code == 200
    assert archive_version(client) == initial + 1

    retry = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve", "notes": "Retry."},
    )
    assert retry.status_code == 200
    assert archive_version(client) == initial + 1

    rolled_back = client.post(
        f"/moderation/submissions/{submission['id']}/rollback",
        json={"reason": "Version test complete."},
    )
    assert rolled_back.status_code == 200
    assert archive_version(client) == initial + 2

    events = {
        (item["action"], item["outcome"]): item["count"]
        for item in service_metrics.snapshot()["moderation_events"]
    }
    assert events == {
        ("submission_created", "submitted"): 1,
        ("moderation_decision", "approved"): 1,
        ("moderation_decision", "approved_retry"): 1,
        ("moderation_rollback", "rolled_back"): 1,
    }


def test_failed_moderation_transition_is_not_counted_as_completed(client):
    authenticate("user_metrics_submitter")
    submission = client.post("/submissions", json=designer_submission()).json()
    authenticate("user_metrics_moderator", "moderator")
    assert client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "reject", "notes": "Insufficient evidence."},
    ).status_code == 200
    assert client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve"},
    ).status_code == 409

    assert service_metrics.snapshot()["moderation_events"] == [
        {
            "action": "moderation_decision",
            "outcome": "rejected",
            "count": 1,
        },
        {
            "action": "submission_created",
            "outcome": "submitted",
            "count": 1,
        },
    ]


def test_anonymous_users_cannot_create_submissions(client):
    response = client.post("/submissions", json=designer_submission())
    assert response.status_code == 401


def test_member_submission_records_sources_without_changing_archive(client):
    authenticate("user_member")
    connection = database.connect()
    try:
        connection.execute(
            "UPDATE users SET display_name = 'Archive Contributor' WHERE clerk_user_id = 'user_member'"
        )
        connection.commit()
    finally:
        connection.close()
    designers_before = count_rows("designers")

    response = client.post("/submissions", json=designer_submission())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "submitted"
    assert body["submitter_clerk_user_id"] == "user_member"
    assert body["submitter_display_name"] == "Archive Contributor"
    assert body["current_data"] is None
    assert body["audit"][0]["actor_display_name"] == "Archive Contributor"
    assert body["sources"][0]["url"] == SOURCE["url"]
    assert body["submitted_at"] is not None
    assert count_rows("designers") == designers_before
    assert count_rows("submission_audit") == 1


def test_member_cannot_view_moderation_queue_or_another_members_draft(client):
    authenticate("user_owner")
    draft = client.post(
        "/submission-drafts",
        json={
            "record_type": "designer",
            "submission_type": "addition",
            "proposed_data": {},
        },
    ).json()
    authenticate("user_other")

    assert client.get("/moderation/submissions").status_code == 403
    assert client.get(f"/submissions/{draft['id']}").status_code == 403
    assert client.put(
        f"/submission-drafts/{draft['id']}",
        json={
            "record_type": "designer",
            "submission_type": "addition",
            "proposed_data": {"full_name": "Stolen Draft"},
        },
    ).status_code == 403


def test_owner_can_save_and_retrieve_an_incomplete_draft(client):
    authenticate("user_draft_owner")
    created = client.post(
        "/submission-drafts",
        json={
            "record_type": "collection",
            "submission_type": "correction",
            "proposed_data": {"description": "Research in progress."},
            "explanation": "",
            "sources": [],
        },
    )

    assert created.status_code == 201
    submission_id = created.json()["id"]
    retrieved = client.get(f"/submissions/{submission_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["status"] == "draft"
    assert retrieved.json()["target_id"] is None
    assert retrieved.json()["sources"] == []

    submitted = client.post(f"/submissions/{submission_id}/submit")
    assert submitted.status_code == 422
    assert client.get(f"/submissions/{submission_id}").json()["status"] == "draft"


def test_request_changes_edit_and_resubmit_transition(client):
    authenticate("user_submitter")
    submission = client.post("/submissions", json=designer_submission()).json()
    authenticate("user_moderator", "moderator")
    queue = client.get("/moderation/submissions").json()
    assert [item["id"] for item in queue["items"]] == [submission["id"]]

    decision = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "request_changes", "notes": "Add a stronger source."},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "changes_requested"

    authenticate("user_submitter")
    updated = client.put(
        f"/submission-drafts/{submission['id']}",
        json={
            **designer_submission(),
            "sources": [SOURCE, {"url": "https://example.org/second-source"}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    resubmitted = client.post(f"/submissions/{submission['id']}/submit")
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "submitted"


def test_moderation_queue_includes_canonical_comparison_and_human_audit_identity(client):
    authenticate("user_comparison_submitter")
    connection = database.connect()
    try:
        connection.execute(
            "UPDATE users SET display_name = ? WHERE clerk_user_id = ?",
            ("Named Contributor", "user_comparison_submitter"),
        )
        original = connection.execute(
            "SELECT biography FROM designers WHERE id = 1"
        ).fetchone()["biography"]
        connection.commit()
    finally:
        connection.close()
    submission = client.post(
        "/submissions",
        json={
            "record_type": "designer",
            "submission_type": "correction",
            "target_id": 1,
            "proposed_data": {"biography": "A sourced replacement biography."},
            "explanation": "Correct the biography.",
            "sources": [SOURCE],
        },
    ).json()

    authenticate("user_comparison_moderator", "moderator")
    queue = client.get("/moderation/submissions").json()
    item = next(candidate for candidate in queue["items"] if candidate["id"] == submission["id"])

    assert item["submitter_display_name"] == "Named Contributor"
    assert item["current_data"]["biography"] == original
    assert item["proposed_data"] == {"biography": "A sourced replacement biography."}
    assert item["audit"][0]["event_type"] == "submitted"
    assert item["audit"][0]["actor_display_name"] == "Named Contributor"


def test_moderation_queue_is_counted_paginated_and_bounded(client):
    authenticate("user_pagination_submitter")
    submission_ids = [
        client.post(
            "/submissions", json=designer_submission(f"Paginated Designer {index}")
        ).json()["id"]
        for index in range(3)
    ]
    authenticate("user_pagination_moderator", "moderator")

    first = client.get("/moderation/submissions?page=1&page_size=2")
    second = client.get("/moderation/submissions?page=2&page_size=2")

    assert first.status_code == second.status_code == 200
    assert [item["id"] for item in first.json()["items"]] == submission_ids[:2]
    assert [item["id"] for item in second.json()["items"]] == submission_ids[2:]
    assert first.json()["counts"]["submitted"] == 3
    assert first.json()["counts"]["rejected"] == 0
    assert first.json()["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total": 3,
        "total_pages": 2,
    }
    assert client.get("/moderation/submissions?page=0").status_code == 422
    assert client.get("/moderation/submissions?page_size=51").status_code == 422


def test_approval_is_transactional_and_idempotent(client):
    authenticate("user_submitter")
    submission = client.post("/submissions", json=designer_submission()).json()
    authenticate("user_moderator", "moderator")

    first = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve", "notes": "Verified."},
    )
    second = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve", "notes": "Retry."},
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["promotion"] == second.json()["promotion"]
    connection = database.connect()
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM designers WHERE full_name = 'Documented Designer'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM submission_promotions WHERE submission_id = ?",
            (submission["id"],),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM submission_decisions WHERE submission_id = ?",
            (submission["id"],),
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_reviewer_cannot_decide_own_submission(client):
    authenticate("user_moderator", "moderator")
    submission = client.post("/submissions", json=designer_submission()).json()

    response = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve"},
    )

    assert response.status_code == 403
    assert count_rows("submission_promotions") == 0


def test_conflicting_approval_rolls_back_every_change(client):
    authenticate("user_submitter")
    submission = client.post(
        "/submissions", json=designer_submission("Existing Designer")
    ).json()
    connection = database.connect()
    try:
        connection.execute("INSERT INTO designers (full_name) VALUES ('Existing Designer')")
        connection.commit()
    finally:
        connection.close()
    authenticate("user_moderator", "moderator")

    response = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve"},
    )

    assert response.status_code == 409
    connection = database.connect()
    try:
        stored = connection.execute(
            "SELECT status FROM submissions WHERE id = ?", (submission["id"],)
        ).fetchone()
        assert stored["status"] == "submitted"
        assert connection.execute(
            "SELECT COUNT(*) FROM submission_promotions WHERE submission_id = ?",
            (submission["id"],),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM submission_decisions WHERE submission_id = ?",
            (submission["id"],),
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_correction_approval_and_admin_rollback_restore_original(client):
    authenticate("user_submitter")
    submission = client.post(
        "/submissions",
        json={
            "record_type": "designer",
            "submission_type": "correction",
            "target_id": 1,
            "proposed_data": {"biography": "Corrected documented biography."},
            "explanation": "Correct the biography.",
            "sources": [SOURCE],
        },
    ).json()
    connection = database.connect()
    try:
        original = connection.execute(
            "SELECT biography FROM designers WHERE id = 1"
        ).fetchone()["biography"]
    finally:
        connection.close()
    authenticate("user_moderator", "moderator")
    approved = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    assert client.post(
        f"/moderation/submissions/{submission['id']}/rollback",
        json={"reason": "Moderator must not roll back canonical data."},
    ).status_code == 403

    authenticate("user_admin", "admin")
    rolled_back = client.post(
        f"/moderation/submissions/{submission['id']}/rollback",
        json={"reason": "The source was later disproven."},
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["status"] == "rolled_back"
    connection = database.connect()
    try:
        restored = connection.execute(
            "SELECT biography FROM designers WHERE id = 1"
        ).fetchone()["biography"]
    finally:
        connection.close()
    assert restored == original


def test_audit_and_decisions_are_append_only(client):
    authenticate("user_submitter")
    submission = client.post("/submissions", json=designer_submission()).json()
    authenticate("user_moderator", "moderator")
    client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "reject", "notes": "Source does not support the claim."},
    )
    audit = client.get(f"/submissions/{submission['id']}/audit")
    assert audit.status_code == 200
    assert [event["event_type"] for event in audit.json()] == ["submitted", "rejected"]

    connection = database.connect()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE submission_audit SET event_type = 'created' WHERE submission_id = ?",
                (submission["id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM submission_decisions WHERE submission_id = ?",
                (submission["id"],),
            )
    finally:
        connection.close()


def test_collection_approval_promotes_media_in_same_transaction(client):
    authenticate("user_submitter")
    submission = client.post(
        "/submissions",
        json={
            "record_type": "collection",
            "submission_type": "addition",
            "proposed_data": {
                "designer_id": 1,
                "label": "Documented Label",
                "season": "Resort",
                "release_year": 2029,
                "status": "concept",
                "source_url": "https://example.com/collection-source",
                "youtube_video_id": "abcdefghijk",
            },
            "explanation": "Add this sourced collection.",
            "sources": [SOURCE],
        },
    ).json()
    authenticate("user_moderator", "moderator")

    response = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve"},
    )

    assert response.status_code == 200
    record_id = response.json()["promotion"]["canonical_record_id"]
    connection = database.connect()
    try:
        media = {
            row["media_type"]: row["media_value"]
            for row in connection.execute(
                "SELECT media_type, media_value FROM collection_media WHERE collection_id = ?",
                (record_id,),
            ).fetchall()
        }
    finally:
        connection.close()
    assert media == {
        "source": "https://example.com/collection-source",
        "youtube": "abcdefghijk",
    }


def test_admin_can_rollback_an_approved_addition(client):
    authenticate("user_submitter")
    submission = client.post(
        "/submissions", json=designer_submission("Temporary Approved Designer")
    ).json()
    authenticate("user_moderator", "moderator")
    approved = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve"},
    ).json()
    record_id = approved["promotion"]["canonical_record_id"]
    authenticate("user_admin", "admin")

    response = client.post(
        f"/moderation/submissions/{submission['id']}/rollback",
        json={"reason": "Approved as part of a rollback test."},
    )

    assert response.status_code == 200
    connection = database.connect()
    try:
        assert connection.execute(
            "SELECT 1 FROM designers WHERE id = ?", (record_id,)
        ).fetchone() is None
    finally:
        connection.close()


def test_rejected_submission_cannot_later_be_approved(client):
    authenticate("user_submitter")
    submission = client.post("/submissions", json=designer_submission()).json()
    authenticate("user_moderator", "moderator")
    client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "reject", "notes": "Insufficient evidence."},
    )

    response = client.post(
        f"/moderation/submissions/{submission['id']}/decisions",
        json={"decision": "approve"},
    )

    assert response.status_code == 409
    assert count_rows("submission_promotions") == 0
