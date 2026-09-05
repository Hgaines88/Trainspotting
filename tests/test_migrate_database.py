import os

import pytest
from sqlalchemy import text

from scripts import migrate_database


def test_sqlite_migration_uses_explicit_url_and_restores_environment(monkeypatch):
    calls = []
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///original.db")
    monkeypatch.setattr(
        migrate_database,
        "apply_migrations",
        lambda connection=None: calls.append(
            (os.environ["DATABASE_URL"], connection)
        ),
    )

    migrate_database.migrate("sqlite+pysqlite:///data/archive.db")

    assert calls == [("sqlite+pysqlite:///data/archive.db", None)]
    assert os.environ["DATABASE_URL"] == "sqlite+pysqlite:///original.db"


def test_mysql_migration_runs_alembic_on_the_advisory_lock_connection(
    monkeypatch,
):
    statements = []
    migrations = []
    transaction_events = []

    class ScalarResult:
        def scalar_one(self):
            return 1

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement, parameters):
            statements.append((str(statement), parameters))
            return ScalarResult()

        def commit(self):
            transaction_events.append("commit")

        def rollback(self):
            transaction_events.append("rollback")

    connection = Connection()

    class Engine:
        def connect(self):
            return connection

        def dispose(self):
            return None

    monkeypatch.setattr(migrate_database, "build_engine", lambda _url: Engine())
    monkeypatch.setattr(
        migrate_database,
        "apply_to",
        lambda database_url, alembic_connection=None: migrations.append(
            (database_url, alembic_connection)
        ),
    )

    migrate_database.migrate("mysql://user:password@mysql/archive")

    assert migrations == [
        ("mysql+pymysql://user:password@mysql/archive", connection)
    ]
    assert statements == [
        (
            str(text("SELECT GET_LOCK(:name, 60)")),
            {"name": migrate_database.LOCK_NAME},
        ),
        (
            str(text("SELECT RELEASE_LOCK(:name)")),
            {"name": migrate_database.LOCK_NAME},
        ),
    ]
    assert transaction_events == ["commit"]


def test_mysql_migration_rolls_back_before_releasing_lock_on_failure(monkeypatch):
    events = []

    class ScalarResult:
        def scalar_one(self):
            return 1

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement, _parameters):
            sql = str(statement)
            events.append(sql)
            return ScalarResult()

        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            return None

    monkeypatch.setattr(migrate_database, "build_engine", lambda _url: Engine())
    def apply_to_failure(*_args, **_kwargs):
        raise RuntimeError("failed")

    monkeypatch.setattr(migrate_database, "apply_to", apply_to_failure)

    with pytest.raises(RuntimeError, match="failed"):
        migrate_database.migrate("mysql://user:password@mysql/archive")

    assert events == [
        str(text("SELECT GET_LOCK(:name, 60)")),
        "rollback",
        str(text("SELECT RELEASE_LOCK(:name)")),
    ]
