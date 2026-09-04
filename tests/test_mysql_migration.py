from datetime import datetime

import pytest

from scripts.migrate_sqlite_to_mysql import migrate, row_digest


def test_row_digest_is_deterministic_and_normalizes_datetimes():
    as_text = [{"id": 1, "created_at": "2026-09-04 12:30:45"}]
    as_datetime = [{"created_at": datetime(2026, 9, 4, 12, 30, 45), "id": 1}]

    assert row_digest(as_text) == row_digest(as_datetime)


def test_migration_requires_an_existing_source(tmp_path):
    with pytest.raises(FileNotFoundError, match="SQLite source does not exist"):
        migrate(tmp_path / "missing.db", "mysql+pymysql://example.invalid/archive")


def test_migration_requires_an_explicit_mysql_target(tmp_path):
    source = tmp_path / "source.db"
    source.touch()

    with pytest.raises(ValueError, match="explicit SQLAlchemy MySQL URL"):
        migrate(source, "sqlite+pysqlite:///:memory:")
