import json
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_PATH = PROJECT_ROOT / "data" / "archive.json"
CURATION_PATH = PROJECT_ROOT / "data" / "youtube_video_sources.json"
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_curated_youtube_sources_match_canonical_collections():
    archive = load_json(ARCHIVE_PATH)
    curation = load_json(CURATION_PATH)
    collections = {item["key"]: item for item in archive["collections"]}

    assert len(curation["videos"]) >= 15
    assert len({item["collection_key"] for item in curation["videos"]}) == len(
        curation["videos"]
    )
    assert len({item["video_id"] for item in curation["videos"]}) == len(
        curation["videos"]
    )
    for item in curation["videos"]:
        assert item["collection_key"] in collections
        assert VIDEO_ID_PATTERN.fullmatch(item["video_id"])
        assert collections[item["collection_key"]]["youtube_video_id"] == item["video_id"]
        assert item["title"].strip()
        assert item["channel"].strip()


def test_every_canonical_youtube_value_is_a_normalized_video_id():
    archive = load_json(ARCHIVE_PATH)

    for collection in archive["collections"]:
        video_id = collection.get("youtube_video_id")
        if video_id is not None:
            assert VIDEO_ID_PATTERN.fullmatch(video_id), collection["key"]
