import pytest

from scripts import start_api


def test_mysql_startup_leaves_database_preparation_to_alembic(monkeypatch):
    initialize_calls = []
    monkeypatch.setattr(
        start_api,
        "initialize_database",
        lambda path: initialize_calls.append(path),
    )

    assert (
        start_api.prepare_runtime_database(
            "mysql+pymysql://user:password@mysql.internal/trainspotting"
        )
        is False
    )
    assert initialize_calls == []


def test_generic_railway_mysql_url_is_supported_at_startup(monkeypatch):
    initialize_calls = []
    monkeypatch.setattr(
        start_api,
        "initialize_database",
        lambda path: initialize_calls.append(path),
    )

    assert (
        start_api.prepare_runtime_database(
            "mysql://user:password@mysql.railway.internal/trainspotting"
        )
        is False
    )
    assert initialize_calls == []


def test_sqlite_startup_initializes_the_configured_path(tmp_path, monkeypatch):
    database_path = tmp_path / "configured.db"
    initialize_calls = []
    monkeypatch.setattr(
        start_api,
        "initialize_database",
        lambda path: initialize_calls.append(path) or True,
    )

    assert start_api.prepare_runtime_database(
        f"sqlite+pysqlite:///{database_path}"
    ) is True
    assert initialize_calls == [database_path]


@pytest.mark.parametrize("port", ["0", "65536", "not-a-port"])
def test_server_arguments_reject_invalid_ports(port):
    with pytest.raises(ValueError, match="PORT must be an integer"):
        start_api.server_arguments(port)


def test_server_arguments_use_the_platform_port():
    assert start_api.server_arguments("10000") == [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "10000",
    ]
