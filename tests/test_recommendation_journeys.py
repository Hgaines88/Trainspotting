import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.recommendations import editorial_facets
from scripts.archive_data import import_archive


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALUATION_PATH = PROJECT_ROOT / "docs" / "recommendation-evaluation.json"


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_path = tmp_path / "journeys.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    import_archive(database_path, PROJECT_ROOT / "data" / "archive.json", replace=True)
    with TestClient(app) as test_client:
        yield test_client


def evaluation():
    return json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))


def collection_id_for_source(source_url):
    connection = database.connect()
    try:
        row = connection.execute(
            """SELECT collections.id
               FROM collections
               JOIN collection_media
                 ON collection_media.collection_id = collections.id
                AND collection_media.media_type = 'source'
               WHERE collection_media.media_value = ?""",
            (source_url,),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None, f"Evaluation source is absent from the archive: {source_url}"
    return row["id"]


def test_curated_recommendation_journeys_are_reproducible_and_diverse(client):
    fixture = evaluation()
    policy = fixture["policy"]
    for journey in fixture["journeys"]:
        target_id = collection_id_for_source(journey["target_source_url"])
        first = client.get(
            f"/collections/{target_id}/related?limit={policy['maximum_results']}"
        )
        second = client.get(
            f"/collections/{target_id}/related?limit={policy['maximum_results']}"
        )

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        results = first.json()
        result_ids = [result["id"] for result in results]
        result_sources = [result["source_url"] for result in results]
        assert len(results) == policy["maximum_results"]
        assert target_id not in result_ids
        assert len(result_ids) == len(set(result_ids))
        assert len({result["label"].casefold() for result in results}) >= policy[
            "minimum_distinct_labels"
        ]
        assert result_sources == journey["expected_source_urls"]
        reasons = [reason for result in results for reason in result["reasons"]]
        for prefix in journey["required_reason_prefixes"]:
            assert any(reason.startswith(prefix) for reason in reasons)


def test_curated_evaluation_blocks_known_editorial_false_positives(client):
    for prohibited in evaluation()["prohibited_inferences"]:
        collection_id = collection_id_for_source(prohibited["record_source_url"])
        response = client.get(f"/collections/{collection_id}")
        assert response.status_code == 200, response.text
        collection = response.json()

        facets = editorial_facets(collection)

        assert prohibited["canonical_value"] not in facets.get(
            prohibited["category"], set()
        ), prohibited["reason"]
