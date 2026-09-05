"""Validate or ingest a curated collection CSV into the moderation queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ingestion import ingest_collection_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--submitter-clerk-user-id", required=True)
    parser.add_argument("--source-name")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create durable ingestion rows and moderated submissions. Default is dry-run.",
    )
    args = parser.parse_args()
    summary = ingest_collection_csv(
        args.csv_path,
        submitter_clerk_user_id=args.submitter_clerk_user_id,
        source_name=args.source_name,
        dry_run=not args.apply,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
