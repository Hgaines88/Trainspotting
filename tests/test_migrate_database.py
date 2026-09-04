import os

from scripts import migrate_database


def test_sqlite_migration_uses_explicit_url_and_restores_environment(monkeypatch):
    calls = []
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///original.db")
    monkeypatch.setattr(
        migrate_database,
        "apply_migrations",
        lambda: calls.append(os.environ["DATABASE_URL"]),
    )

    migrate_database.migrate("sqlite+pysqlite:///data/archive.db")

    assert calls == ["sqlite+pysqlite:///data/archive.db"]
    assert os.environ["DATABASE_URL"] == "sqlite+pysqlite:///original.db"
