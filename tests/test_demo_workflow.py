import pytest

from app import database, submissions
from scripts import demo_workflow
from scripts.archive_data import DEFAULT_ARCHIVE, import_archive


def test_demo_guard_refuses_missing_acknowledgement(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://user:password@mysql:3306/trainspotting_demo",
    )
    monkeypatch.delenv("TRAINSPOTTING_DEMO_FIXTURES", raising=False)

    with pytest.raises(RuntimeError, match="set TRAINSPOTTING_DEMO_FIXTURES"):
        demo_workflow.require_isolated_demo_database()


@pytest.mark.parametrize(
    "database_url, message",
    [
        (
            "mysql+pymysql://user:password@mysql84.railway.internal:3306/trainspotting_demo",
            "non-local MySQL host",
        ),
        (
            "mysql+pymysql://user:password@mysql:3306/trainspotting",
            "not named trainspotting_demo",
        ),
        ("sqlite:///data/demo.db", "require the disposable MySQL environment"),
    ],
)
def test_demo_guard_refuses_unsafe_database_targets(monkeypatch, database_url, message):
    monkeypatch.setenv("TRAINSPOTTING_DEMO_FIXTURES", demo_workflow.GUARD_VALUE)
    monkeypatch.setenv("DATABASE_URL", database_url)

    with pytest.raises(RuntimeError, match=message):
        demo_workflow.require_isolated_demo_database()


def test_narrative_setup_is_idempotent_and_preserves_workflow_states(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "demo-workflow.db"
    import_archive(database_path, DEFAULT_ARCHIVE, replace=True)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    monkeypatch.setattr(
        demo_workflow,
        "require_isolated_demo_database",
        lambda: "trainspotting_demo",
    )
    monkeypatch.setattr(submissions, "enforce_identity_rate_limit", lambda *_a, **_k: None)

    created = demo_workflow.setup("user_demo_operator")
    repeated = demo_workflow.setup("user_demo_operator")

    assert created["mode"] == "created"
    assert repeated == {
        "database": "trainspotting_demo",
        "mode": "already-configured",
        "designer_id": created["designer_id"],
        "collection_id": created["collection_id"],
        "submission_count": 12,
        "ingestion_batch_id": created["applied"]["batch_id"],
    }
    assert [row["status"] for row in created["dry_run"]["rows"]] == [
        "valid",
        "invalid",
        "duplicate",
    ]
    assert [row["status"] for row in created["applied"]["rows"]] == [
        "requiring_review",
        "invalid",
        "duplicate",
    ]

    connection = database.connect()
    try:
        statuses = {
            row["status"]: row["count"]
            for row in connection.execute(
                """SELECT status, COUNT(*) AS count FROM submissions
                   WHERE explanation LIKE '[DEMO-X14]%'
                   GROUP BY status"""
            ).fetchall()
        }
        assert set(statuses) == {
            "draft",
            "submitted",
            "changes_requested",
            "approved",
            "rejected",
            "rolled_back",
        }
        credits = connection.execute(
            """SELECT designers.full_name, collection_credits.credit_role,
                      collection_credits.credit_order
               FROM collection_credits JOIN designers
                 ON designers.id = collection_credits.designer_id
               WHERE collection_credits.collection_id = ?
               ORDER BY collection_credits.credit_order""",
            (created["collection_id"],),
        ).fetchall()
        assert [tuple(row) for row in credits] == [
            ("Tyler Okonma", "lead", 1),
            ("Pharrell Williams", "collaborator", 2),
        ]
        audit = connection.execute(
            """SELECT event_type FROM submission_audit
               WHERE submission_id IN (
                   SELECT id FROM submissions WHERE explanation LIKE '[DEMO-X14]%'
               ) ORDER BY id"""
        ).fetchall()
        assert {row["event_type"] for row in audit} >= {
            "created",
            "submitted",
            "changes_requested",
            "approved",
            "rejected",
            "rolled_back",
        }
        descriptor = connection.execute(
            """SELECT category, canonical_value FROM collection_descriptors
               WHERE collection_id = ?""",
            (created["collection_id"],),
        ).fetchall()
        assert [tuple(row) for row in descriptor] == [("theme", "sportswear")]
    finally:
        connection.close()
