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


def test_source_registry_reports_malformed_categories_without_crashing():
    registry = copy.deepcopy(REGISTRY)
    registry["categories"]["rights-holder"] = "not an object"

    report = validate_registry(ARCHIVE, registry)

    assert "category 'rights-holder' must be an object" in report["errors"]


def test_source_registry_reports_invalid_automation_status_actionably():
    registry = copy.deepcopy(REGISTRY)
    registry["categories"]["rights-holder"]["automation_status"] = "scrape-all"

    report = validate_registry(ARCHIVE, registry)

    assert any(
        "'scrape-all'" in error
        and "embed-only, manual-only, review-gated" in error
        for error in report["errors"]
    )


def test_source_registry_preserves_first_owner_and_ignores_invalid_hosts():
    expected_registered_hosts = validate_registry(
        ARCHIVE, REGISTRY
    )["registered_hosts"]
    registry = copy.deepcopy(REGISTRY)
    rights_holder_hosts = registry["categories"]["rights-holder"]["hosts"]
    cultural_hosts = registry["categories"]["cultural-institution"]["hosts"]
    cultural_hosts.append(cultural_hosts[0])
    rights_holder_hosts.extend([cultural_hosts[0], "", 42])

    report = validate_registry(ARCHIVE, registry)

    assert report["registered_hosts"] == expected_registered_hosts
    assert any("listed more than once" in error for error in report["errors"])
    assert any("belongs to both" in error for error in report["errors"])
    assert any("noncanonical host ''" in error for error in report["errors"])
    assert any("non-string host 42" in error for error in report["errors"])
