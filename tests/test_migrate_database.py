import os

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
