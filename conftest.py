"""Shared pytest configuration and process-global state isolation."""

import pytest

from app.rate_limits import identity_rate_limiter


@pytest.fixture(autouse=True)
def reset_identity_rate_limiter():
    identity_rate_limiter.clear()
    yield
    identity_rate_limiter.clear()
