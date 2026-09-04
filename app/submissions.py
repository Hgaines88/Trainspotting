import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.auth import ClerkIdentity, require_authenticated_user
from app.database import DATABASE_INTEGRITY_ERRORS, connect, select_for_update
from app.schemas import CollectionCreate, DesignerCreate
from app.submission_schemas import (
    ReviewDecision,
    RollbackRequest,
    SubmissionDraft,
    SubmissionForReview,
    submission_for_review_adapter,
)
from app.users import get_or_create_user


router = APIRouter()
VALID_TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"changes_requested", "rejected", "approved"},
    "changes_requested": {"submitted"},
    "approved": {"rolled_back"},
    "rejected": set(),
    "rolled_back": set(),
}


def authenticated_app_user(
    identity: ClerkIdentity = Depends(require_authenticated_user),
) -> dict:
    return get_or_create_user(identity.user_id)


def require_moderator(user: dict = Depends(authenticated_app_user)) -> dict:
    if user["role"] not in {"moderator", "admin"}:
        raise HTTPException(status_code=403, detail="Moderator access required.")
    return user


def require_admin(user: dict = Depends(authenticated_app_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return user


def json_text(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def serialize_submission(connection, submission_id: int) -> dict:
    row = connection.execute(
        """
        SELECT submissions.*, users.clerk_user_id AS submitter_clerk_user_id,
               users.display_name AS submitter_display_name
        FROM submissions
        JOIN users ON users.id = submissions.submitter_user_id
        WHERE submissions.id = ?
        """,
        (submission_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    result = dict(row)
    result["proposed_data"] = json.loads(result["proposed_data"])
    result["sources"] = [
        dict(source)
        for source in connection.execute(
            """SELECT id, url, title, notes, created_at
               FROM submission_sources WHERE submission_id = ? ORDER BY id""",
            (submission_id,),
        ).fetchall()
    ]
    result["decisions"] = [
        dict(decision)
        for decision in connection.execute(
            """SELECT submission_decisions.id, submission_decisions.decision,
                      submission_decisions.notes, submission_decisions.created_at,
                      users.clerk_user_id AS reviewer_clerk_user_id
               FROM submission_decisions
               JOIN users ON users.id = submission_decisions.reviewer_user_id
               WHERE submission_id = ? ORDER BY submission_decisions.id""",
            (submission_id,),
        ).fetchall()
    ]
    promotion = connection.execute(
        """SELECT canonical_record_type, canonical_record_id, promoted_at,
                  rolled_back_at, rollback_reason
           FROM submission_promotions WHERE submission_id = ?""",
        (submission_id,),
    ).fetchone()
    result["promotion"] = dict(promotion) if promotion else None
    return result


def write_sources(connection, submission_id: int, sources) -> None:
    connection.execute(
        "DELETE FROM submission_sources WHERE submission_id = ?", (submission_id,)
    )
    connection.executemany(
        """INSERT INTO submission_sources (submission_id, url, title, notes)
           VALUES (?, ?, ?, ?)""",
        [(submission_id, source.url, source.title, source.notes) for source in sources],
    )


def append_audit(
    connection, submission_id, actor_id, event_type, from_status, to_status, data=None
):
    connection.execute(
        """INSERT INTO submission_audit
           (submission_id, actor_user_id, event_type, from_status, to_status, event_data)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (submission_id, actor_id, event_type, from_status, to_status, json_text(data or {})),
    )


def create_submission_record(connection, payload, user, initial_status):
    data = payload.proposed_data.model_dump(exclude_unset=True)
    cursor = connection.execute(
        """INSERT INTO submissions
           (submitter_user_id, record_type, submission_type, target_id, status,
            proposed_data, explanation, submitted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'submitted' THEN CURRENT_TIMESTAMP END)""",
        (
            user["id"], payload.record_type, payload.submission_type, payload.target_id,
            initial_status, json_text(data), payload.explanation, initial_status,
        ),
    )
    submission_id = cursor.lastrowid
    write_sources(connection, submission_id, payload.sources)
    append_audit(
        connection, submission_id, user["id"],
        "submitted" if initial_status == "submitted" else "created",
        None, initial_status,
    )
    return submission_id


def ensure_target_exists(connection, payload) -> None:
    if payload.submission_type != "correction":
        return
    table = "designers" if payload.record_type == "designer" else "collections"
    if connection.execute(
        f"SELECT 1 FROM {table} WHERE id = ?", (payload.target_id,)
    ).fetchone() is None:
        raise HTTPException(status_code=404, detail="Correction target not found")


@router.post("/submission-drafts", status_code=status.HTTP_201_CREATED)
def create_draft(
    payload: SubmissionDraft,
    user: dict = Depends(authenticated_app_user),
):
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        submission_id = create_submission_record(connection, payload, user, "draft")
        connection.commit()
        return serialize_submission(connection, submission_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.post("/submissions", status_code=status.HTTP_201_CREATED)
def create_ready_submission(
    payload: SubmissionForReview,
    user: dict = Depends(authenticated_app_user),
):
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        ensure_target_exists(connection, payload)
        submission_id = create_submission_record(connection, payload, user, "submitted")
        connection.commit()
        return serialize_submission(connection, submission_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.put("/submission-drafts/{submission_id}")
def update_draft(
    submission_id: int,
    payload: SubmissionDraft,
    user: dict = Depends(authenticated_app_user),
):
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = select_for_update(
            connection,
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        if row["submitter_user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Submission ownership required.")
        if row["status"] not in {"draft", "changes_requested"}:
            raise HTTPException(status_code=409, detail="Submission can no longer be edited")
        connection.execute(
            """UPDATE submissions SET record_type = ?, submission_type = ?, target_id = ?,
               proposed_data = ?, explanation = ?, version = version + 1,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (
                payload.record_type, payload.submission_type, payload.target_id,
                json_text(payload.proposed_data.model_dump(exclude_unset=True)),
                payload.explanation, submission_id,
            ),
        )
        write_sources(connection, submission_id, payload.sources)
        append_audit(
            connection, submission_id, user["id"], "draft_updated",
            row["status"], row["status"], {"version": row["version"] + 1},
        )
        connection.commit()
        return serialize_submission(connection, submission_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_payload_from_row(connection, row):
    sources = [
        dict(source)
        for source in connection.execute(
            "SELECT url, title, notes FROM submission_sources WHERE submission_id = ?",
            (row["id"],),
        ).fetchall()
    ]
    return submission_for_review_adapter.validate_python({
        "record_type": row["record_type"],
        "submission_type": row["submission_type"],
        "target_id": row["target_id"],
        "proposed_data": json.loads(row["proposed_data"]),
        "explanation": row["explanation"],
        "sources": sources,
    })


@router.post("/submissions/{submission_id}/submit")
def submit_draft(submission_id: int, user: dict = Depends(authenticated_app_user)):
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = select_for_update(
            connection,
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        if row["submitter_user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Submission ownership required.")
        if "submitted" not in VALID_TRANSITIONS[row["status"]]:
            raise HTTPException(status_code=409, detail="Invalid submission transition")
        try:
            payload = review_payload_from_row(connection, row)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=error.errors()) from error
        ensure_target_exists(connection, payload)
        connection.execute(
            """UPDATE submissions SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (submission_id,),
        )
        append_audit(connection, submission_id, user["id"], "submitted", row["status"], "submitted")
        connection.commit()
        return serialize_submission(connection, submission_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.get("/submissions/mine")
def list_my_submissions(user: dict = Depends(authenticated_app_user)):
    connection = connect()
    try:
        ids = connection.execute(
            "SELECT id FROM submissions WHERE submitter_user_id = ? ORDER BY id DESC",
            (user["id"],),
        ).fetchall()
        return [serialize_submission(connection, row["id"]) for row in ids]
    finally:
        connection.close()


@router.get("/moderation/submissions")
def moderation_queue(
    queue_status: str = "submitted",
    _reviewer: dict = Depends(require_moderator),
):
    if queue_status not in VALID_TRANSITIONS:
        raise HTTPException(status_code=422, detail="Unknown submission status")
    connection = connect()
    try:
        ids = connection.execute(
            "SELECT id FROM submissions WHERE status = ? ORDER BY submitted_at, id",
            (queue_status,),
        ).fetchall()
        return [serialize_submission(connection, row["id"]) for row in ids]
    finally:
        connection.close()


def designer_snapshot(connection, designer_id):
    row = connection.execute(
        "SELECT full_name, nationality, birth_year, website, biography FROM designers WHERE id = ?",
        (designer_id,),
    ).fetchone()
    return dict(row) if row else None


def collection_snapshot(connection, collection_id):
    row = connection.execute(
        """SELECT designer_id, label, name, season, release_year, status,
                  piece_count, description FROM collections WHERE id = ?""",
        (collection_id,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    media = {
        item["media_type"]: item["media_value"]
        for item in connection.execute(
            "SELECT media_type, media_value FROM collection_media WHERE collection_id = ?",
            (collection_id,),
        ).fetchall()
    }
    result["source_url"] = media.get("source")
    result["youtube_video_id"] = media.get("youtube")
    return result


def write_designer(connection, record_id, values):
    payload = DesignerCreate.model_validate(values)
    fields = payload.model_dump()
    if record_id is None:
        cursor = connection.execute(
            """INSERT INTO designers (full_name, nationality, birth_year, website, biography)
               VALUES (?, ?, ?, ?, ?)""",
            tuple(fields[name] for name in ("full_name", "nationality", "birth_year", "website", "biography")),
        )
        return cursor.lastrowid
    connection.execute(
        """UPDATE designers SET full_name = ?, nationality = ?, birth_year = ?,
           website = ?, biography = ? WHERE id = ?""",
        tuple(fields[name] for name in ("full_name", "nationality", "birth_year", "website", "biography")) + (record_id,),
    )
    return record_id


def write_collection(connection, record_id, values):
    payload = CollectionCreate.model_validate(values)
    fields = payload.model_dump()
    columns = ("designer_id", "label", "name", "season", "release_year", "status", "piece_count", "description")
    if connection.execute("SELECT 1 FROM designers WHERE id = ?", (payload.designer_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Designer not found")
    if record_id is None:
        cursor = connection.execute(
            f"INSERT INTO collections ({', '.join(columns)}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(fields[name] for name in columns),
        )
        record_id = cursor.lastrowid
    else:
        assignments = ", ".join(f"{name} = ?" for name in columns)
        connection.execute(
            f"UPDATE collections SET {assignments} WHERE id = ?",
            tuple(fields[name] for name in columns) + (record_id,),
        )
    connection.execute("DELETE FROM collection_media WHERE collection_id = ?", (record_id,))
    connection.executemany(
        "INSERT INTO collection_media (collection_id, media_type, media_value) VALUES (?, ?, ?)",
        [(record_id, kind, value) for kind, value in (("source", payload.source_url), ("youtube", payload.youtube_video_id)) if value],
    )
    return record_id


def promote_submission(connection, row, reviewer):
    existing = connection.execute(
        "SELECT canonical_record_id FROM submission_promotions WHERE submission_id = ?",
        (row["id"],),
    ).fetchone()
    if existing:
        return existing["canonical_record_id"]
    proposed = json.loads(row["proposed_data"])
    snapshot = designer_snapshot if row["record_type"] == "designer" else collection_snapshot
    writer = write_designer if row["record_type"] == "designer" else write_collection
    before = snapshot(connection, row["target_id"]) if row["submission_type"] == "correction" else None
    if row["submission_type"] == "correction" and before is None:
        raise HTTPException(status_code=409, detail="Correction target no longer exists")
    values = proposed if before is None else {**before, **proposed}
    record_id = writer(connection, row["target_id"], values)
    after = snapshot(connection, record_id)
    connection.execute(
        """INSERT INTO submission_promotions
           (submission_id, canonical_record_type, canonical_record_id, before_snapshot,
            after_snapshot, promoted_by_user_id) VALUES (?, ?, ?, ?, ?, ?)""",
        (row["id"], row["record_type"], record_id, json_text(before) if before else None, json_text(after), reviewer["id"]),
    )
    return record_id


@router.post("/moderation/submissions/{submission_id}/decisions")
def decide_submission(
    submission_id: int,
    payload: ReviewDecision,
    reviewer: dict = Depends(require_moderator),
):
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = select_for_update(
            connection, "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        if row["submitter_user_id"] == reviewer["id"]:
            raise HTTPException(status_code=403, detail="Reviewers cannot decide their own submissions.")
        if row["status"] == "approved" and payload.decision == "approve":
            connection.commit()
            return serialize_submission(connection, submission_id)
        target_status = {"approve": "approved", "reject": "rejected", "request_changes": "changes_requested"}[payload.decision]
        if target_status not in VALID_TRANSITIONS[row["status"]]:
            raise HTTPException(status_code=409, detail="Invalid review transition")
        if payload.decision == "approve":
            promote_submission(connection, row, reviewer)
        connection.execute(
            """INSERT INTO submission_decisions (submission_id, reviewer_user_id, decision, notes)
               VALUES (?, ?, ?, ?)""",
            (submission_id, reviewer["id"], payload.decision, payload.notes),
        )
        connection.execute(
            """UPDATE submissions SET status = ?, reviewed_at = CURRENT_TIMESTAMP,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (target_status, submission_id),
        )
        append_audit(connection, submission_id, reviewer["id"], target_status, row["status"], target_status, {"notes": payload.notes})
        connection.commit()
        return serialize_submission(connection, submission_id)
    except DATABASE_INTEGRITY_ERRORS as error:
        connection.rollback()
        raise HTTPException(status_code=409, detail="Approval conflicts with canonical archive data") from error
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.get("/submissions/{submission_id}/audit")
def submission_audit(submission_id: int, user: dict = Depends(authenticated_app_user)):
    connection = connect()
    try:
        submission = connection.execute("SELECT submitter_user_id FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        if submission["submitter_user_id"] != user["id"] and user["role"] not in {"moderator", "admin"}:
            raise HTTPException(status_code=403, detail="Submission access denied.")
        rows = connection.execute(
            """SELECT submission_audit.*, users.clerk_user_id AS actor_clerk_user_id
               FROM submission_audit JOIN users ON users.id = submission_audit.actor_user_id
               WHERE submission_id = ? ORDER BY submission_audit.id""",
            (submission_id,),
        ).fetchall()
        result = []
        for row in rows:
            event = dict(row)
            event["event_data"] = json.loads(event["event_data"])
            result.append(event)
        return result
    finally:
        connection.close()


@router.post("/moderation/submissions/{submission_id}/rollback")
def rollback_submission(
    submission_id: int,
    payload: RollbackRequest,
    admin: dict = Depends(require_admin),
):
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = select_for_update(
            connection, "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        promotion = select_for_update(
            connection,
            "SELECT * FROM submission_promotions WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()
        if row is None or promotion is None:
            raise HTTPException(status_code=404, detail="Approved submission not found")
        if row["status"] != "approved" or promotion["rolled_back_at"] is not None:
            raise HTTPException(status_code=409, detail="Submission cannot be rolled back")
        snapshot = designer_snapshot if row["record_type"] == "designer" else collection_snapshot
        writer = write_designer if row["record_type"] == "designer" else write_collection
        record_id = promotion["canonical_record_id"]
        current = snapshot(connection, record_id)
        if current != json.loads(promotion["after_snapshot"]):
            raise HTTPException(status_code=409, detail="Canonical record changed after approval")
        before = json.loads(promotion["before_snapshot"]) if promotion["before_snapshot"] else None
        if before is None:
            if row["record_type"] == "designer" and connection.execute(
                "SELECT 1 FROM collections WHERE designer_id = ? LIMIT 1", (record_id,)
            ).fetchone():
                raise HTTPException(status_code=409, detail="Created designer now has dependent collections")
            table = "designers" if row["record_type"] == "designer" else "collections"
            connection.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
        else:
            writer(connection, record_id, before)
        connection.execute(
            """UPDATE submission_promotions SET rolled_back_by_user_id = ?,
               rolled_back_at = CURRENT_TIMESTAMP, rollback_reason = ? WHERE submission_id = ?""",
            (admin["id"], payload.reason, submission_id),
        )
        connection.execute(
            "UPDATE submissions SET status = 'rolled_back', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (submission_id,),
        )
        append_audit(connection, submission_id, admin["id"], "rolled_back", "approved", "rolled_back", {"reason": payload.reason})
        connection.commit()
        return serialize_submission(connection, submission_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
