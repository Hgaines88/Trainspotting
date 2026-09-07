"""Deterministic curated CSV ingestion into Trainspotting moderation."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from app.database import connect
from app.schemas import CollectionCreate
from app.submission_schemas import submission_for_review_adapter
from app.submissions import create_submission_record


CSV_FIELDS = {
    "designer_name",
    "label",
    "name",
    "season",
    "release_year",
    "status",
    "piece_count",
    "description",
    "source_url",
    "source_title",
    "source_notes",
    "youtube_video_id",
    "vimeo_video_id",
}
REQUIRED_CSV_FIELDS = {
    "designer_name",
    "label",
    "season",
    "release_year",
    "status",
    "source_url",
}
MAX_INGESTION_ROWS = 10_000
STATUS_ALIASES = {
    "concept": "concept",
    "in production": "in-production",
    "in-production": "in-production",
    "released": "released",
    "archived": "archived",
}


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def validation_messages(error: ValidationError) -> list[dict[str, str]]:
    return [
        {
            "field": ".".join(str(part) for part in item["loc"]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        headers = set(fieldnames)
        if len(fieldnames) != len(headers):
            raise ValueError("Invalid CSV contract; duplicate column names")
        missing = REQUIRED_CSV_FIELDS - headers
        unknown = headers - CSV_FIELDS
        if missing or unknown:
            details = []
            if missing:
                details.append("missing columns: " + ", ".join(sorted(missing)))
            if unknown:
                details.append("unknown columns: " + ", ".join(sorted(unknown)))
            raise ValueError("Invalid CSV contract; " + "; ".join(details))
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError("Invalid CSV contract; one or more rows have extra values")
    if len(rows) > MAX_INGESTION_ROWS:
        raise ValueError(f"CSV exceeds the {MAX_INGESTION_ROWS}-row safety limit")
    return rows


def normalized_row(connection, raw: dict[str, str]) -> dict:
    cleaned = {key: (value or "").strip() for key, value in raw.items()}
    designer_name = cleaned["designer_name"]
    designer = connection.execute(
        "SELECT id, full_name FROM designers WHERE LOWER(full_name) = LOWER(?)",
        (designer_name,),
    ).fetchone()
    if designer is None:
        raise ValueError(f"Unknown designer: {designer_name or '[blank]'}")

    status = STATUS_ALIASES.get(cleaned["status"].casefold(), cleaned["status"].casefold())
    proposed = {
        "designer_id": designer["id"],
        "label": cleaned["label"],
        "name": cleaned.get("name") or None,
        "season": cleaned["season"],
        "release_year": cleaned["release_year"],
        "status": status,
        "piece_count": cleaned.get("piece_count") or None,
        "description": cleaned.get("description") or None,
        "source_url": cleaned["source_url"],
        "youtube_video_id": cleaned.get("youtube_video_id") or None,
        "vimeo_video_id": cleaned.get("vimeo_video_id") or None,
    }
    validated = CollectionCreate.model_validate(proposed)
    return {
        "designer_name": designer["full_name"],
        "proposed_data": validated.model_dump(exclude_none=True, exclude={"credits"}),
        "source": {
            "url": validated.source_url,
            "title": cleaned.get("source_title") or None,
            "notes": cleaned.get("source_notes") or None,
        },
    }


def fingerprint(normalized: dict) -> str:
    return hashlib.sha256(json_text(normalized).encode("utf-8")).hexdigest()


def is_duplicate(connection, normalized: dict, row_fingerprint: str) -> bool:
    prior = connection.execute(
        """SELECT 1 FROM ingestion_rows
           WHERE fingerprint = ? AND submission_id IS NOT NULL LIMIT 1""",
        (row_fingerprint,),
    ).fetchone()
    if prior is not None:
        return True
    proposed = normalized["proposed_data"]
    return connection.execute(
        """SELECT 1 FROM collections
           WHERE designer_id = ? AND LOWER(label) = LOWER(?)
             AND LOWER(season) = LOWER(?) AND release_year = ? LIMIT 1""",
        (
            proposed["designer_id"],
            proposed["label"],
            proposed["season"],
            proposed["release_year"],
        ),
    ).fetchone() is not None


def ingestion_payload(normalized: dict, source_name: str, row_number: int):
    return submission_for_review_adapter.validate_python(
        {
            "record_type": "collection",
            "submission_type": "addition",
            "target_id": None,
            "proposed_data": normalized["proposed_data"],
            "explanation": (
                f"Curated ingestion from {source_name}, source row {row_number}."
            ),
            "sources": [normalized["source"]],
        }
    )


def ingest_collection_csv(
    path: Path,
    *,
    submitter_clerk_user_id: str,
    source_name: str | None = None,
    dry_run: bool = True,
) -> dict:
    rows = read_csv_rows(path)
    source_name = (source_name or path.name).strip()
    if not source_name:
        raise ValueError("Source name must not be blank")
    if len(source_name) > 255:
        raise ValueError("Source name must be 255 characters or fewer")
    connection = connect()
    batch_id = None
    outcomes = []
    try:
        if not dry_run:
            connection.execute("BEGIN IMMEDIATE")
        user = connection.execute(
            "SELECT * FROM users WHERE clerk_user_id = ?",
            (submitter_clerk_user_id,),
        ).fetchone()
        if user is None:
            raise ValueError("Submitter must already exist in Trainspotting users")
        if not dry_run:
            batch_id = connection.execute(
                """INSERT INTO ingestion_batches
                   (submitter_user_id, source_name, input_format)
                   VALUES (?, ?, 'csv')""",
                (user["id"], source_name),
            ).lastrowid
        seen_fingerprints: set[str] = set()

        for row_number, raw in enumerate(rows, start=2):
            normalized = None
            row_fingerprint = None
            errors = None
            submission_id = None
            try:
                normalized = normalized_row(connection, raw)
                row_fingerprint = fingerprint(normalized)
                if row_fingerprint in seen_fingerprints or is_duplicate(
                    connection, normalized, row_fingerprint
                ):
                    outcome = "duplicate"
                elif dry_run:
                    ingestion_payload(normalized, source_name, row_number)
                    outcome = "valid"
                else:
                    payload = ingestion_payload(normalized, source_name, row_number)
                    submission_id = create_submission_record(
                        connection, payload, dict(user), "submitted"
                    )
                    outcome = "requiring_review"
                seen_fingerprints.add(row_fingerprint)
            except ValidationError as error:
                outcome = "invalid"
                errors = validation_messages(error)
            except ValueError as error:
                outcome = "invalid"
                errors = [{"field": "designer_name", "message": str(error), "type": "value_error"}]

            outcomes.append({"row_number": row_number, "status": outcome})
            if not dry_run:
                connection.execute(
                    """INSERT INTO ingestion_rows
                       (batch_id, source_row_number, raw_payload, normalized_payload,
                        fingerprint, status, validation_errors, submission_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        batch_id,
                        row_number,
                        json_text(raw),
                        json_text(normalized) if normalized else None,
                        row_fingerprint,
                        outcome,
                        json_text(errors) if errors else None,
                        submission_id,
                    ),
                )

        counts = Counter(item["status"] for item in outcomes)
        valid_count = counts["valid"] + counts["requiring_review"]
        summary = {
            "batch_id": batch_id,
            "dry_run": dry_run,
            "source_name": source_name,
            "total_rows": len(outcomes),
            "valid_rows": valid_count,
            "invalid_rows": counts["invalid"],
            "duplicate_rows": counts["duplicate"],
            "review_rows": counts["requiring_review"],
            "submissions_created": counts["requiring_review"],
            "rows": outcomes,
        }
        if not dry_run:
            connection.execute(
                """UPDATE ingestion_batches
                   SET status = 'completed', total_rows = ?, valid_rows = ?,
                       invalid_rows = ?, duplicate_rows = ?, review_rows = ?,
                       completed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (
                    len(outcomes),
                    valid_count,
                    counts["invalid"],
                    counts["duplicate"],
                    counts["requiring_review"],
                    batch_id,
                ),
            )
            connection.commit()
        return summary
    except Exception:
        if not dry_run:
            connection.rollback()
        raise
    finally:
        connection.close()
