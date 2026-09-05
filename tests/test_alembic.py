import sqlite3

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.test_portable_schema import EXPECTED_TABLES


def config_for(database_path):
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    return config


def test_alembic_upgrade_creates_schema_and_append_only_guards(tmp_path):
    database_path = tmp_path / "alembic.db"
    config = config_for(database_path)
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES | {"alembic_version"}
        with engine.begin() as connection:
            assert connection.execute(
                text("SELECT id, version FROM archive_state")
            ).one() == (1, 1)
            user_id = connection.execute(
                text("INSERT INTO users (clerk_user_id) VALUES ('user_alembic') RETURNING id")
            ).scalar_one()
            submission_id = connection.execute(text("""INSERT INTO submissions
                (submitter_user_id, record_type, submission_type, proposed_data)
                VALUES (:user_id, 'designer', 'addition', '{}') RETURNING id"""), {"user_id": user_id}).scalar_one()
            connection.execute(text("""INSERT INTO submission_audit
                (submission_id, actor_user_id, event_type, to_status, event_data)
                VALUES (:submission_id, :user_id, 'created', 'draft', '{}')"""), {"submission_id": submission_id, "user_id": user_id})
        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as connection:
                connection.execute(text("UPDATE submission_audit SET to_status = 'submitted'"))
    finally:
        engine.dispose()

    command.downgrade(config, "base")
    connection = sqlite3.connect(database_path)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        connection.close()
    assert not EXPECTED_TABLES & tables


def test_archive_version_migration_resumes_after_nontransactional_ddl(tmp_path):
    database_path = tmp_path / "partial-alembic.db"
    config = config_for(database_path)
    command.upgrade(config, "0001")

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """CREATE TABLE archive_state (
                        id INTEGER NOT NULL PRIMARY KEY,
                        version INTEGER NOT NULL DEFAULT 1,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT ck_archive_state_singleton CHECK (id = 1),
                        CONSTRAINT ck_archive_state_version_positive CHECK (version > 0)
                    )"""
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "0002"
            assert connection.execute(
                text("SELECT id, version FROM archive_state")
            ).one() == (1, 1)
    finally:
        engine.dispose()
