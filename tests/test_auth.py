from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app


@pytest.fixture
def client():
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()


def test_session_endpoint_requires_a_bearer_token(client, monkeypatch):
    monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)

    response = client.get("/auth/session")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Authentication required."}


def test_default_authorized_parties_cover_localhost_and_loopback(monkeypatch):
    monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)

    assert auth.authorized_parties() == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


def test_session_endpoint_reports_missing_backend_configuration(
    client,
    monkeypatch,
):
    monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)

    response = client.get(
        "/auth/session",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is not configured."}


def test_session_endpoint_accepts_a_verified_clerk_identity(
    client,
    monkeypatch,
):
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-secret")
    monkeypatch.setenv(
        "CLERK_AUTHORIZED_PARTIES",
        "http://localhost:5173, https://trainspotting.example",
    )

    class FakeClerk:
        def __init__(self, bearer_auth):
            assert bearer_auth == "test-secret"

        def authenticate_request(self, request, options):
            assert request.headers["authorization"] == "Bearer test-token"
            assert options.authorized_parties == [
                "http://localhost:5173",
                "https://trainspotting.example",
            ]
            return SimpleNamespace(
                is_signed_in=True,
                payload={"sub": "user_test123", "sid": "sess_test123"},
            )

    monkeypatch.setattr(auth, "Clerk", FakeClerk)

    response = client.get(
        "/auth/session",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user_id": "user_test123",
    }


def test_session_endpoint_rejects_an_invalid_session(client, monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-secret")

    class FakeClerk:
        def __init__(self, bearer_auth):
            assert bearer_auth == "test-secret"

        def authenticate_request(self, request, options):
            return SimpleNamespace(is_signed_in=False, payload=None)

    monkeypatch.setattr(auth, "Clerk", FakeClerk)

    response = client.get(
        "/auth/session",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired session."}
