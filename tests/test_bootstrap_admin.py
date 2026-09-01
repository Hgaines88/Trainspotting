import sqlite3

import pytest

from app import database
from scripts.bootstrap_admin import BootstrapError, bootstrap_admin


def create_users_database(database_path):
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clerk_user_id TEXT NOT NULL UNIQUE,
                email TEXT,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'member'
                    CHECK (role IN ('member', 'moderator', 'admin')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.executemany(
            "INSERT INTO users (clerk_user_id) VALUES (?)",
            [("user_first",), ("user_second",)],
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def users_database(tmp_path, monkeypatch):
    database_path = tmp_path / "users.db"
    create_users_database(database_path)
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    return database_path


def read_roles(database_path):
    connection = sqlite3.connect(database_path)
    try:
        return dict(
            connection.execute(
                "SELECT clerk_user_id, role FROM users"
            ).fetchall()
        )
    finally:
        connection.close()


def test_bootstrap_promotes_only_the_selected_first_admin(users_database):
    assert bootstrap_admin("user_first") is True
    assert read_roles(users_database) == {
        "user_first": "admin",
        "user_second": "member",
    }


def test_bootstrap_is_idempotent_for_the_existing_admin(users_database):
    assert bootstrap_admin("user_first") is True
    assert bootstrap_admin("user_first") is False


def test_bootstrap_refuses_to_replace_an_existing_admin(users_database):
    assert bootstrap_admin("user_first") is True

    with pytest.raises(BootstrapError, match="administrator already exists"):
        bootstrap_admin("user_second")

    assert read_roles(users_database)["user_second"] == "member"


def test_bootstrap_requires_a_synchronized_user(users_database):
    with pytest.raises(BootstrapError, match="Sign in first"):
        bootstrap_admin("user_missing")

    assert set(read_roles(users_database).values()) == {"member"}
