import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from app.database import expected_alembic_revision


MYSQL_TEST_DATABASE_URL = os.getenv("MYSQL_TEST_DATABASE_URL")


@pytest.mark.skipif(
    not MYSQL_TEST_DATABASE_URL,
    reason="MYSQL_TEST_DATABASE_URL is required for the MySQL integration test",
)
def test_mysql_schema_and_append_only_audit_guards():
    engine = create_engine(MYSQL_TEST_DATABASE_URL, pool_pre_ping=True)
    identity = f"mysql-test-{uuid.uuid4()}"

    try:
        with engine.begin() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == expected_alembic_revision()
            assert connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() "
                    "AND table_name <> 'alembic_version'"
                )
            ).scalar_one() == 14
            assert connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.triggers "
                    "WHERE trigger_schema = DATABASE()"
                )
            ).scalar_one() == 4

            inspector = inspect(connection)
            assert "idx_designers_nationality" in {
                index["name"] for index in inspector.get_indexes("designers")
            }
            assert {
                "idx_collections_label",
                "idx_collections_season",
                "idx_collections_year_status",
            } <= {
                index["name"] for index in inspector.get_indexes("collections")
            }
            collections_without_credits = connection.execute(
                text(
                    "SELECT COUNT(*) FROM collections "
                    "WHERE NOT EXISTS ("
                    "SELECT 1 FROM collection_credits "
                    "WHERE collection_credits.collection_id = collections.id)"
                )
            ).scalar_one()
            assert collections_without_credits == 0
            assert {
                "idx_collection_credits_collection",
                "idx_collection_credits_designer",
            } <= {
                index["name"]
                for index in inspector.get_indexes("collection_credits")
            }

            user_id = connection.execute(
                text(
                    "INSERT INTO users (clerk_user_id, role) "
                    "VALUES (:identity, 'member')"
                ),
                {"identity": identity},
            ).lastrowid
            submission_id = connection.execute(
                text(
                    "INSERT INTO submissions "
                    "(submitter_user_id, record_type, submission_type, proposed_data) "
                    "VALUES (:user_id, 'designer', 'addition', '{}')"
                ),
                {"user_id": user_id},
            ).lastrowid
            audit_id = connection.execute(
                text(
                    "INSERT INTO submission_audit "
                    "(submission_id, actor_user_id, event_type, to_status, event_data) "
                    "VALUES (:submission_id, :user_id, 'created', 'draft', '{}')"
                ),
                {"submission_id": submission_id, "user_id": user_id},
            ).lastrowid

        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE submission_audit SET to_status = 'submitted' "
                        "WHERE id = :audit_id"
                    ),
                    {"audit_id": audit_id},
                )

        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM submission_audit WHERE id = :audit_id"),
                    {"audit_id": audit_id},
                )
    finally:
        engine.dispose()
