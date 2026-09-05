"""Run Trainspotting database migrations as a serialized release operation."""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.database import apply_migrations
from app.database_engine import build_engine, configured_database_url
from app.database_url import normalize_database_url


LOCK_NAME = "trainspotting_alembic_migration"


def apply_to(database_url: str, alembic_connection=None) -> None:
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        apply_migrations(alembic_connection)
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url


def migrate(database_url: str | None = None) -> None:
    target_url = normalize_database_url(database_url or configured_database_url())
    if make_url(target_url).get_backend_name() != "mysql":
        apply_to(target_url)
        return

    engine = build_engine(target_url)
    try:
        with engine.connect() as connection:
            acquired = connection.execute(
                text("SELECT GET_LOCK(:name, 60)"), {"name": LOCK_NAME}
            ).scalar_one()
            if acquired != 1:
                raise RuntimeError("Could not acquire the database migration lock")
            try:
                apply_to(target_url, connection)
                # GET_LOCK starts SQLAlchemy's outer transaction before Alembic
                # receives this connection. Commit that transaction explicitly
                # so the revision ledger survives after the pre-deploy process
                # closes its connection.
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.execute(
                    text("SELECT RELEASE_LOCK(:name)"), {"name": LOCK_NAME}
                )
    finally:
        engine.dispose()


def main() -> None:
    migrate(os.getenv("DATABASE_URL"))


if __name__ == "__main__":
    main()
