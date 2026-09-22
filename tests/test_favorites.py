from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app, authenticated_app_user


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "favorites.db")
    connection = database.connect()
    try:
        connection.executescript((PROJECT_ROOT / "sql" / "schema.sql").read_text())
        connection.executescript((PROJECT_ROOT / "sql" / "seed.sql").read_text())
        user_id = connection.execute(
            "INSERT INTO users (clerk_user_id) VALUES (?)", ("user_favorites",)
        ).lastrowid
        connection.commit()
    finally:
        connection.close()

    app.dependency_overrides[authenticated_app_user] = lambda: {
        "id": user_id,
        "clerk_user_id": "user_favorites",
        "role": "member",
    }
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(authenticated_app_user, None)


def test_user_can_save_list_and_remove_a_collection(client):
    collection_id = client.get("/collections").json()["items"][0]["id"]

    assert client.get(f"/favorites/{collection_id}").json() == {"favorited": False}
    assert client.put(f"/favorites/{collection_id}").json() == {"favorited": True}
    assert client.put(f"/favorites/{collection_id}").json() == {"favorited": True}

    favorites = client.get("/favorites").json()
    assert [item["id"] for item in favorites] == [collection_id]
    assert favorites[0]["lead_designer"]
    assert client.get(f"/favorites/{collection_id}").json() == {"favorited": True}

    assert client.delete(f"/favorites/{collection_id}").status_code == 204
    assert client.delete(f"/favorites/{collection_id}").status_code == 204
    assert client.get("/favorites").json() == []


def test_saving_a_missing_collection_returns_not_found(client):
    response = client.put("/favorites/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Collection not found"}
