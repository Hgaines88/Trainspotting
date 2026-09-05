"""Audit the canonical archive without modifying it."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from scripts.archive_data import DEFAULT_ARCHIVE, stable_key


ALLOWED_STATUSES = {"concept", "in-production", "released", "archived"}


def finding(code: str, severity: str, record: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "record": record,
        "message": message,
    }


def audit_archive(payload: dict) -> dict:
    """Return a deterministic report; absence is not treated as false data."""
    findings: list[dict[str, str]] = []
    designers = payload.get("designers", [])
    collections = payload.get("collections", [])
    designer_keys = {designer.get("key") for designer in designers}

    if payload.get("format_version") != 1:
        findings.append(finding(
            "unsupported_format", "error", "archive",
            "format_version must be 1.",
        ))

    identities: dict[tuple[str, str], list[str]] = defaultdict(list)
    for designer in designers:
        key = str(designer.get("key", ""))
        name = str(designer.get("full_name", ""))
        identities[("designer_key", key.casefold())].append(key)
        identities[("designer_name", name.casefold())].append(key)
        if stable_key(name) != key:
            findings.append(finding(
                "unstable_designer_key", "error", key,
                f"Designer key does not match the canonical form of {name!r}.",
            ))

    natural_collections: dict[tuple, list[str]] = defaultdict(list)
    collection_keys: dict[str, list[str]] = defaultdict(list)
    seasons = Counter()
    labels = Counter()
    optional_missing = Counter()
    for collection in collections:
        key = str(collection.get("key", ""))
        primary = collection.get("designer_key")
        label = str(collection.get("label", ""))
        season = str(collection.get("season", ""))
        year = collection.get("release_year")
        status = collection.get("status")
        collection_keys[key.casefold()].append(key)
        natural_collections[(primary, label.casefold(), season.casefold(), year)].append(key)
        labels[label] += 1
        seasons[season] += 1

        for field in ("name", "piece_count", "youtube_video_id"):
            if collection.get(field) in (None, ""):
                optional_missing[field] += 1

        if primary not in designer_keys:
            findings.append(finding(
                "unknown_primary_designer", "error", key,
                f"Primary designer {primary!r} does not exist.",
            ))
        if status not in ALLOWED_STATUSES:
            findings.append(finding(
                "unsupported_status", "error", key,
                f"Status {status!r} is not supported.",
            ))

        source = collection.get("source_url")
        if not source:
            findings.append(finding(
                "missing_source", "warning", key,
                "Collection has no public evidence URL.",
            ))
        else:
            parsed = urlparse(str(source))
            if parsed.scheme != "https" or not parsed.netloc:
                findings.append(finding(
                    "invalid_source", "error", key,
                    "Collection source must be an absolute HTTPS URL.",
                ))

        if re.search(r"\b(?:19|20)\d{2}\b", season):
            findings.append(finding(
                "year_embedded_in_season", "review", key,
                f"Season {season!r} contains a year already represented by release_year.",
            ))

        credits = collection.get("credits") or [{
            "designer_key": primary, "role": "lead", "position": 1,
        }]
        credited_keys = [credit.get("designer_key") for credit in credits]
        positions = [credit.get("position") for credit in credits]
        if any(credit_key not in designer_keys for credit_key in credited_keys):
            findings.append(finding(
                "unknown_credited_designer", "error", key,
                "At least one credited designer does not exist.",
            ))
        if len(credited_keys) != len(set(credited_keys)):
            findings.append(finding(
                "duplicate_credit", "error", key,
                "A designer is credited more than once.",
            ))
        if positions != list(range(1, len(positions) + 1)):
            findings.append(finding(
                "invalid_credit_order", "error", key,
                "Credit positions must be unique and contiguous from 1.",
            ))
        if primary not in credited_keys:
            findings.append(finding(
                "primary_designer_not_credited", "error", key,
                "The primary designer is absent from collection credits.",
            ))
        elif credits[0].get("designer_key") != primary:
            findings.append(finding(
                "primary_credit_mismatch", "review", key,
                "The primary designer differs from the first ordered credit.",
            ))

    for (kind, _), records in identities.items():
        if len(records) > 1:
            findings.append(finding(
                f"duplicate_{kind}", "error", ", ".join(sorted(records)),
                f"Multiple designers share the same normalized {kind}.",
            ))
    for records in collection_keys.values():
        if len(records) > 1:
            findings.append(finding(
                "duplicate_collection_key", "error", ", ".join(sorted(records)),
                "Multiple collections share the same normalized key.",
            ))
    for records in natural_collections.values():
        if len(records) > 1:
            findings.append(finding(
                "duplicate_natural_collection", "error", ", ".join(sorted(records)),
                "Collections share primary designer, label, season, and year.",
            ))

    findings.sort(key=lambda item: (
        {"error": 0, "warning": 1, "review": 2}[item["severity"]],
        item["code"], item["record"],
    ))
    severity_counts = Counter(item["severity"] for item in findings)
    return {
        "counts": {
            "designers": len(designers),
            "collections": len(collections),
            "findings": len(findings),
            "errors": severity_counts["error"],
            "warnings": severity_counts["warning"],
            "review": severity_counts["review"],
        },
        "optional_missing": dict(sorted(optional_missing.items())),
        "vocabularies": {
            "labels": dict(sorted(labels.items(), key=lambda item: item[0].casefold())),
            "seasons": dict(sorted(seasons.items(), key=lambda item: item[0].casefold())),
        },
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument(
        "--fail-on-errors", action="store_true",
        help="Exit unsuccessfully when structural errors are present.",
    )
    args = parser.parse_args()
    payload = json.loads(args.archive.read_text(encoding="utf-8"))
    report = audit_archive(payload)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    if args.fail_on_errors and report["counts"]["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
