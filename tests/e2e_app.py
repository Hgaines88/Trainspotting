"""Disposable FastAPI application used only by browser workflow tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import Request


if os.getenv("TRAINSPOTTING_E2E_TEST") != "1":
    raise RuntimeError(
        "The synthetic-auth E2E server requires TRAINSPOTTING_E2E_TEST=1."
    )


from app import database  # noqa: E402
from app.auth import ClerkIdentity, authentication_error, require_authenticated_user  # noqa: E402
from scripts.archive_data import DEFAULT_ARCHIVE, import_archive  # noqa: E402


_temporary_directory = tempfile.TemporaryDirectory(prefix="trainspotting-e2e-")
database.DATABASE_PATH = Path(_temporary_directory.name) / "archive.db"
import_archive(database.DATABASE_PATH, DEFAULT_ARCHIVE, replace=True)

connection = database.connect()
try:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    migration_names = [path.name for path in sorted(database.MIGRATIONS_PATH.glob("*.sql"))]
    connection.executemany(
        "INSERT OR IGNORE INTO schema_migrations (filename) VALUES (?)",
        [(name,) for name in migration_names],
    )
    connection.executemany(
        """
        INSERT INTO users (clerk_user_id, email, display_name, role)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("user_e2e_member", "member@example.test", "E2E Member", "member"),
            ("user_e2e_moderator", "moderator@example.test", "E2E Moderator", "moderator"),
            ("user_e2e_admin", "admin@example.test", "E2E Administrator", "admin"),
        ],
    )
    connection.commit()
finally:
    connection.close()


from app import main as main_module, submissions as submissions_module  # noqa: E402
from app.users import get_or_create_user  # noqa: E402


TEST_IDENTITIES = {
    "e2e-member": "user_e2e_member",
    "e2e-moderator": "user_e2e_moderator",
    "e2e-admin": "user_e2e_admin",
}


def require_e2e_identity(request: Request) -> ClerkIdentity:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    user_id = TEST_IDENTITIES.get(token) if scheme == "Bearer" else None
    if user_id is None:
        raise authentication_error("Invalid or missing E2E identity.")
    return ClerkIdentity(user_id=user_id, session_id=f"session_{user_id}")


def sync_e2e_user_profile(clerk_user_id: str) -> dict:
    return get_or_create_user(clerk_user_id)


def skip_e2e_rate_limit(*_args, **_kwargs) -> None:
    """Keep the isolated workflow deterministic; limiter behavior has unit coverage."""


main_module.sync_clerk_user_profile = sync_e2e_user_profile
main_module.enforce_identity_rate_limit = skip_e2e_rate_limit
submissions_module.enforce_identity_rate_limit = skip_e2e_rate_limit
main_module.app.dependency_overrides[require_authenticated_user] = require_e2e_identity
app = main_module.app
