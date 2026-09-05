from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.database import SQLITE_BUSY_TIMEOUT_MS
from app.database_engine import build_engine, configured_database_url
from app.database_url import normalize_database_url


def test_database_url_defaults_to_the_requested_sqlite_path(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database_path = tmp_path / "default.db"

    assert configured_database_url(database_path) == (
        f"sqlite+pysqlite:///{database_path.resolve()}"
    )


def test_database_url_honors_environment_override(tmp_path, monkeypatch):
    expected = "mysql+pymysql://user:password@mysql/trainspotting"
    monkeypatch.setenv("DATABASE_URL", expected)

    assert configured_database_url(tmp_path / "ignored.db") == expected


def test_generic_mysql_url_selects_the_installed_pymysql_driver(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql://user:p%40ss@mysql.railway.internal:3306/trainspotting",
    )

    normalized = configured_database_url()

    assert normalized.startswith("mysql+pymysql://")
    assert make_url(normalized).password == "p@ss"
    assert normalize_database_url(normalized) == normalized


def test_sqlalchemy_sqlite_engine_preserves_safety_settings(tmp_path):
    database_path = tmp_path / "engine.db"
    engine = build_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == (
                SQLITE_BUSY_TIMEOUT_MS
            )
    finally:
        engine.dispose()


def test_mysql_engine_can_be_configured_without_opening_a_connection():
    engine = build_engine(
        "mysql+pymysql://trainspotting:placeholder@localhost/trainspotting"
    )
    try:
        assert engine.dialect.name == "mysql"
        assert engine.url.drivername == "mysql+pymysql"
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()
