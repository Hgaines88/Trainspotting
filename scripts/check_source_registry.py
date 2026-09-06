"""Validate governance coverage for canonical Trainspotting sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from scripts.archive_data import DEFAULT_ARCHIVE


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = PROJECT_ROOT / "docs" / "source-registry.json"
REQUIRED_FIELDS = {
    "description",
    "hosts",
    "attribution",
    "access_method",
    "licensing_position",
    "reliability",
    "rate_limits",
    "automation_status",
    "retention",
    "review_owner",
}
ALLOWED_AUTOMATION_STATUSES = {"manual-only", "embed-only", "review-gated"}


def canonical_source_hosts(archive: dict) -> set[str]:
    urls = [
        alias.get("source_url")
        for designer in archive.get("designers", [])
        for alias in designer.get("aliases", [])
    ] + [
        collection.get("source_url")
        for collection in archive.get("collections", [])
    ]
    return {
        urlsplit(url).hostname.lower()
        for url in urls
        if url and urlsplit(url).hostname
    }


def validate_registry(archive: dict, registry: dict) -> dict:
    errors: list[str] = []
    if registry.get("schema_version") != 1:
        errors.append("source registry schema_version must be 1")
    categories = registry.get("categories")
    if not isinstance(categories, dict) or not categories:
        return {"errors": errors + ["source registry needs categories"]}

    host_owners: dict[str, str] = {}
    for category_id, category in sorted(categories.items()):
        missing = sorted(REQUIRED_FIELDS - set(category))
        if missing:
            errors.append(
                f"category {category_id!r} is missing: {', '.join(missing)}"
            )
            continue
        if category["automation_status"] not in ALLOWED_AUTOMATION_STATUSES:
            errors.append(
                f"category {category_id!r} has an unsupported automation status"
            )
        for host in category["hosts"]:
            normalized_host = str(host).strip().lower()
            if not normalized_host or normalized_host != host:
                errors.append(
                    f"category {category_id!r} has a noncanonical host {host!r}"
                )
            if normalized_host in host_owners:
                errors.append(
                    f"host {normalized_host!r} belongs to both "
                    f"{host_owners[normalized_host]!r} and {category_id!r}"
                )
            host_owners[normalized_host] = category_id

    current_hosts = canonical_source_hosts(archive)
    for host in sorted(current_hosts - set(host_owners)):
        errors.append(f"canonical source host {host!r} is not classified")

    return {
        "errors": errors,
        "canonical_hosts": len(current_hosts),
        "registered_hosts": len(host_owners),
        "categories": len(categories),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()
    report = validate_registry(
        json.loads(args.archive.read_text(encoding="utf-8")),
        json.loads(args.registry.read_text(encoding="utf-8")),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
