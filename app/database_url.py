"""Normalize portable database URLs at Trainspotting's configuration boundary."""

from __future__ import annotations

from sqlalchemy.engine import make_url


def normalize_database_url(database_url: str) -> str:
    """Select PyMySQL when a platform supplies SQLAlchemy's generic MySQL URL."""
    url = make_url(database_url)
    if url.drivername == "mysql":
        url = url.set(drivername="mysql+pymysql")
    return url.render_as_string(hide_password=False)
