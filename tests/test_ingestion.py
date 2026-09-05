import csv
from pathlib import Path

import pytest

from app import database
from app.ingestion import CSV_FIELDS, ingest_collection_csv, read_csv_rows


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBMITTER_ID = "user_ingestion_curator"


@pytest.fixture
def ingestion_database(tmp_path, monkeypatch):
    database_path = tmp_path / "ingestion.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    connection = database.connect()
    try:
        connection.executescript((PROJECT_ROOT / "sql" / "schema.sql").read_text())
        connection.executescript((PROJECT_ROOT / "sql" / "seed.sql").read_text())
        connection.execute(
            """INSERT INTO users (clerk_user_id, display_name, role)
               VALUES (?, ?, 'member')""",
            (SUBMITTER_ID, "Ingestion Curator"),
        )
        grace = connection.execute(
            "SELECT id FROM designers WHERE full_name = ?",
            ("Grace Wales Bonner",),
        ).fetchone()
        duplicate_id = connection.execute(
            """INSERT INTO collections
               (designer_id, label, name, season, release_year, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                grace["id"],
                "Wales Bonner",
                "Ebonics",
                "Spring/Summer Menswear",
                2015,
                "archived",
            ),
        ).lastrowid
        connection.execute(
            """INSERT INTO collection_credits
               (collection_id, designer_id, credit_role, credit_order)
               VALUES (?, ?, 'lead', 1)""",
            (duplicate_id, grace["id"]),
        )
        connection.commit()
    finally:
        connection.close()
    return database_path


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(CSV_FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def sample_rows():
    return [
        {
            "designer_name": "  Grace Wales Bonner ",
            "label": " Wales Bonner ",
            "name": "Ingestion Study",
            "season": "Resort",
            "release_year": "2029",
            "status": " In Production ",
            "piece_count": "24",
            "description": "A documented ingestion candidate.",
            "source_url": "https://www.vogue.com/fashion-shows",
            "source_title": "Vogue Runway",
        },
        {
            "designer_name": "Unknown Pipeline Designer",
            "label": "Unknown Label",
            "season": "Resort",
            "release_year": "2029",
            "status": "released",
            "source_url": "https://example.com/source",
        },
        {
            "designer_name": "Grace Wales Bonner",
            "label": "Wales Bonner",
            "name": "Ebonics",
            "season": "Spring/Summer Menswear",
            "release_year": "2015",
            "status": "archived",
            "source_url": "https://walesbonner.com/pages/archive",
        },
    ]


def test_dry_run_classifies_without_writing(ingestion_database, tmp_path):
    csv_path = tmp_path / "curated.csv"
    write_csv(csv_path, sample_rows())

    summary = ingest_collection_csv(
        csv_path,
        submitter_clerk_user_id=SUBMITTER_ID,
        dry_run=True,
    )

    assert summary | {"rows": []} == {
        "batch_id": None,
        "dry_run": True,
        "source_name": "curated.csv",
        "total_rows": 3,
        "valid_rows": 1,
        "invalid_rows": 1,
        "duplicate_rows": 1,
        "review_rows": 0,
        "submissions_created": 0,
        "rows": [],
    }
    connection = database.connect()
    try:
        assert connection.execute("SELECT COUNT(*) FROM ingestion_batches").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM ingestion_rows").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 0
    finally:
        connection.close()


def test_apply_retains_rows_and_creates_only_moderated_submissions(
    ingestion_database, tmp_path
):
    csv_path = tmp_path / "curated.csv"
    write_csv(csv_path, sample_rows())
    connection = database.connect()
    try:
        canonical_before = connection.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
    finally:
        connection.close()

    first = ingest_collection_csv(
        csv_path,
        submitter_clerk_user_id=SUBMITTER_ID,
        source_name="Instructor-curated runway research",
        dry_run=False,
    )
    second = ingest_collection_csv(
        csv_path,
        submitter_clerk_user_id=SUBMITTER_ID,
        source_name="Instructor-curated runway research rerun",
        dry_run=False,
    )

    assert (first["review_rows"], first["invalid_rows"], first["duplicate_rows"]) == (1, 1, 1)
    assert first["submissions_created"] == 1
    assert (second["review_rows"], second["invalid_rows"], second["duplicate_rows"]) == (0, 1, 2)
    assert second["submissions_created"] == 0

    connection = database.connect()
    try:
        assert connection.execute("SELECT COUNT(*) FROM collections").fetchone()[0] == canonical_before
        assert connection.execute("SELECT COUNT(*) FROM ingestion_batches").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM ingestion_rows").fetchone()[0] == 6
        retained = connection.execute(
            """SELECT raw_payload, normalized_payload, fingerprint, status,
                      validation_errors, submission_id
               FROM ingestion_rows WHERE batch_id = ? ORDER BY source_row_number""",
            (first["batch_id"],),
        ).fetchall()
        assert [row["status"] for row in retained] == [
            "requiring_review", "invalid", "duplicate"
        ]
        assert retained[0]["raw_payload"]
        assert retained[0]["normalized_payload"]
        assert len(retained[0]["fingerprint"]) == 64
        assert retained[0]["submission_id"] is not None
        assert retained[1]["validation_errors"]
        submission = connection.execute(
            "SELECT status, record_type, submission_type FROM submissions"
        ).fetchone()
        assert dict(submission) == {
            "status": "submitted",
            "record_type": "collection",
            "submission_type": "addition",
        }
        assert connection.execute("SELECT event_type FROM submission_audit").fetchone()[0] == "submitted"
        assert connection.execute("SELECT url FROM submission_sources").fetchone()[0] == (
            "https://www.vogue.com/fashion-shows"
        )
    finally:
        connection.close()


def test_csv_contract_rejects_unknown_or_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("designer_name,unexpected\nGrace Wales Bonner,value\n")

    with pytest.raises(ValueError, match="missing columns:.*unknown columns"):
        read_csv_rows(path)


def test_unknown_submitter_cannot_create_a_batch(ingestion_database, tmp_path):
    path = tmp_path / "curated.csv"
    write_csv(path, sample_rows()[:1])

    with pytest.raises(ValueError, match="Submitter must already exist"):
        ingest_collection_csv(
            path,
            submitter_clerk_user_id="user_unknown",
            dry_run=False,
        )

    connection = database.connect()
    try:
        assert connection.execute("SELECT COUNT(*) FROM ingestion_batches").fetchone()[0] == 0
    finally:
        connection.close()
