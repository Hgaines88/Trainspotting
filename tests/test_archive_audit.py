import copy
import json
from pathlib import Path

from scripts.audit_archive import audit_archive


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = PROJECT_ROOT / "data" / "archive.json"


def canonical_payload():
    return json.loads(ARCHIVE.read_text(encoding="utf-8"))


def test_canonical_audit_is_deterministic_and_separates_optional_absence():
    report = audit_archive(canonical_payload())

    assert report == audit_archive(canonical_payload())
    assert report["counts"]["designers"] == 60
    assert report["counts"]["collections"] == 440
    assert report["counts"]["errors"] == 0
    assert report["counts"]["findings"] == (
        report["counts"]["warnings"] + report["counts"]["review"]
    )
    assert report["optional_missing"] == {
        "name": 211,
        "piece_count": 407,
        "youtube_video_id": 382,
    }


def test_audit_identifies_source_season_and_primary_credit_review_candidates():
    payload = canonical_payload()
    collection = payload["collections"][0]
    collection["source_url"] = None
    collection["season"] = f"Fall/Winter {collection['release_year']}"
    collection["credits"] = [
        {
            "designer_key": payload["designers"][1]["key"],
            "role": "co-designer",
            "position": 1,
            "attribution_note": None,
        },
        {
            "designer_key": collection["designer_key"],
            "role": "co-designer",
            "position": 2,
            "attribution_note": None,
        },
    ]
    report = audit_archive(payload)
    findings = {(item["code"], item["record"]) for item in report["findings"]}

    assert ("missing_source", collection["key"]) in findings
    assert ("year_embedded_in_season", collection["key"]) in findings
    assert ("primary_credit_mismatch", collection["key"]) in findings


def test_audit_reports_structural_errors_without_modifying_payload():
    payload = canonical_payload()
    payload["collections"][0]["designer_key"] = "missing-designer"
    payload["collections"][0]["status"] = "published"
    payload["collections"][0]["source_url"] = "http://example.com/source"
    payload["collections"][0]["credits"] = [{
        "designer_key": payload["designers"][1]["key"],
        "role": "lead",
        "position": 1,
        "attribution_note": None,
    }]
    before_audit = copy.deepcopy(payload)

    report = audit_archive(payload)
    codes = {item["code"] for item in report["findings"]}

    assert {
        "unknown_primary_designer",
        "unsupported_status",
        "invalid_source",
        "primary_designer_not_credited",
    } <= codes
    assert payload == before_audit
