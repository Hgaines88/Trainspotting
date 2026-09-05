import sqlite3

import pytest

from app import database
from scripts.retire_user import (
    FORMER_MEMBER_DISPLAY_NAME,
    RetirementError,
    retire_user,
)


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
            """INSERT INTO users (clerk_user_id, email, display_name, role)
               VALUES (?, ?, ?, ?)""",
            [
                ("user_member", "member@example.com", "Member", "member"),
                ("user_moderator", "moderator@example.com", "Mod", "moderator"),
                ("user_admin", "admin@example.com", "Admin", "admin"),
            ],
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


def read_user(database_path, clerk_user_id):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM users WHERE clerk_user_id = ?",
            (clerk_user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def test_retirement_clears_profile_data_and_preserves_opaque_identity(users_database):
    assert retire_user("user_member") is True

    user = read_user(users_database, "user_member")
    assert user["clerk_user_id"] == "user_member"
    assert user["email"] is None
    assert user["display_name"] == FORMER_MEMBER_DISPLAY_NAME
    assert user["role"] == "member"


def test_retirement_removes_moderator_privilege(users_database):
    assert retire_user("user_moderator") is True
    assert read_user(users_database, "user_moderator")["role"] == "member"


def test_retirement_is_idempotent(users_database):
    assert retire_user("user_member") is True
    assert retire_user("user_member") is False


def test_retirement_refuses_administrators(users_database):
    with pytest.raises(RetirementError, match="controlled role recovery"):
        retire_user("user_admin")

    assert read_user(users_database, "user_admin")["role"] == "admin"


def test_retirement_requires_an_existing_synchronized_user(users_database):
    with pytest.raises(RetirementError, match="No synchronized user"):
        retire_user("user_missing")
