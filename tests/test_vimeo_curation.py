import json
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_PATH = PROJECT_ROOT / "data" / "archive.json"
CURATION_PATH = PROJECT_ROOT / "data" / "vimeo_video_sources.json"
VIDEO_ID_PATTERN = re.compile(r"^[0-9]{6,12}$")
MATCH_TYPES = {
    "official-full-show",
    "official-collection-film",
    "official-campaign",
    "campaign",
    "collection-film",
    "collection-highlight",
    "official-backstage",
    "process-film",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_curated_vimeo_sources_match_canonical_collections():
    archive = load_json(ARCHIVE_PATH)
    curation = load_json(CURATION_PATH)
    collections = {item["key"]: item for item in archive["collections"]}

    assert len(curation["videos"]) >= 21
    assert len({item["collection_key"] for item in curation["videos"]}) == len(
        curation["videos"]
    )
    assert len({item["video_id"] for item in curation["videos"]}) == len(
        curation["videos"]
    )
    for item in curation["videos"]:
        assert item["collection_key"] in collections
        assert VIDEO_ID_PATTERN.fullmatch(item["video_id"])
        assert (
            collections[item["collection_key"]]["vimeo_video_id"]
            == item["video_id"]
        )
        assert item["title"].strip()
        assert item["publisher"].strip()
        assert item["match_type"] in MATCH_TYPES


def test_every_canonical_vimeo_value_is_curated_and_normalized():
    archive = load_json(ARCHIVE_PATH)
    curation = load_json(CURATION_PATH)
    curated = {
        item["collection_key"]: item["video_id"]
        for item in curation["videos"]
    }

    for collection in archive["collections"]:
        video_id = collection.get("vimeo_video_id")
        if video_id is not None:
            assert VIDEO_ID_PATTERN.fullmatch(video_id), collection["key"]
            assert curated.get(collection["key"]) == video_id
