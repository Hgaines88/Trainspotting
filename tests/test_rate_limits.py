import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main, submissions
from app.auth import ClerkIdentity, require_authenticated_user
from app.main import app
from app.rate_limits import ACCOUNT_SYNC_LIMIT, IdentityRateLimiter, identity_rate_limiter


def test_token_bucket_rejects_burst_and_reports_retry_time():
    now = [100.0]
    limiter = IdentityRateLimiter(clock=lambda: now[0])

    limiter.consume("submission", "user_1", limit=2, window_seconds=10)
    limiter.consume("submission", "user_1", limit=2, window_seconds=10)

    with pytest.raises(HTTPException) as error:
        limiter.consume("submission", "user_1", limit=2, window_seconds=10)

    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "5"}

    now[0] += 5
    limiter.consume("submission", "user_1", limit=2, window_seconds=10)


def test_rate_limits_are_isolated_by_bucket_and_identity():
    limiter = IdentityRateLimiter(clock=lambda: 100.0)

    limiter.consume("submission", "user_1", limit=1)
    limiter.consume("submission", "user_2", limit=1)
    limiter.consume("moderation", "user_1", limit=1)

    with pytest.raises(HTTPException) as error:
        limiter.consume("submission", "user_1", limit=1)

    assert error.value.status_code == 429


def test_rate_limiter_state_is_bounded():
    limiter = IdentityRateLimiter(clock=lambda: 100.0, max_identities=2)

    limiter.consume("submission", "user_1", limit=1)
    limiter.consume("submission", "user_2", limit=1)
    limiter.consume("submission", "user_3", limit=1)

    # user_1 was the least-recently-used identity and receives a fresh bucket.
    limiter.consume("submission", "user_1", limit=1)


def test_account_sync_is_rate_limited_by_verified_clerk_identity(monkeypatch):
    monkeypatch.setenv("AUTO_MIGRATE_DATABASE", "false")
    identity_rate_limiter.clear()
    app.dependency_overrides[require_authenticated_user] = lambda: ClerkIdentity(
        user_id="user_rate_limit_test",
        session_id="session_rate_limit_test",
    )
    monkeypatch.setattr(
        main,
        "sync_clerk_user_profile",
        lambda user_id: {"clerk_user_id": user_id, "role": "member"},
    )

    try:
        with TestClient(app) as client:
            for _ in range(ACCOUNT_SYNC_LIMIT):
                assert client.get("/me").status_code == 200
            response = client.get("/me")
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)
        identity_rate_limiter.clear()

    assert response.status_code == 429
    assert response.headers["retry-after"] == "5"
    assert response.json() == {
        "detail": "Too many requests. Please try again shortly."
    }


def test_submission_and_moderation_writes_use_separate_limits(monkeypatch):
    calls = []
    monkeypatch.setattr(
        submissions,
        "enforce_identity_rate_limit",
        lambda bucket, identity, *, limit: calls.append((bucket, identity, limit)),
    )
    user = {"clerk_user_id": "user_route_limit_test"}

    submissions.limit_submission_write(user)
    submissions.limit_moderation_write(user)
    submissions.limit_moderation_rollback(user)

    assert [call[:2] for call in calls] == [
        ("submission-write", "user_route_limit_test"),
        ("moderation-write", "user_route_limit_test"),
        ("moderation-rollback", "user_route_limit_test"),
    ]
    assert len({call[0] for call in calls}) == 3
