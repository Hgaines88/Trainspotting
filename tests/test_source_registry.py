import copy
import json
from pathlib import Path

from scripts.check_source_registry import validate_registry


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = json.loads(
    (PROJECT_ROOT / "data" / "archive.json").read_text(encoding="utf-8")
)
REGISTRY = json.loads(
    (PROJECT_ROOT / "docs" / "source-registry.json").read_text(encoding="utf-8")
)


def test_source_registry_covers_every_canonical_evidence_host():
    report = validate_registry(ARCHIVE, REGISTRY)

    assert report["errors"] == []
    assert report["canonical_hosts"] == 46
    assert report["categories"] == 7


def test_source_registry_rejects_missing_governance_and_host_coverage():
    registry = copy.deepcopy(REGISTRY)
    registry["categories"]["rights-holder"].pop("licensing_position")
    registry["categories"]["editorial-publication"]["hosts"].remove(
        "www.vogue.com"
    )

    report = validate_registry(ARCHIVE, registry)

    assert any("licensing_position" in error for error in report["errors"])
    assert any("www.vogue.com" in error for error in report["errors"])
