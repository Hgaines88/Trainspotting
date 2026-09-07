# Curated collection ingestion

Trainspotting's ingestion pipeline demonstrates a controlled data-engineering
path into the existing moderation system. It accepts researched CSV data,
retains the original rows, normalizes and validates supported fields, detects
reruns using deterministic SHA-256 fingerprints, and creates ordinary audited
submissions. It never inserts or updates canonical archive records.

All source URLs remain subject to the
[`SOURCE_REGISTRY_AND_LICENSING.md`](SOURCE_REGISTRY_AND_LICENSING.md) policy.
Supplying or approving a citation never grants permission to scrape, copy, or
redistribute the source's text or media.

## CSV contract

The input must contain these columns:

- Required: `designer_name`, `label`, `season`, `release_year`, `status`,
  `source_url`
- Optional: `name`, `piece_count`, `description`, `source_title`,
  `source_notes`, `youtube_video_id`

Unknown columns are rejected so mapping errors cannot silently discard data.
Designers must already exist in Trainspotting. Supported statuses are
`concept`, `in-production`, `released`, and `archived`; `in production` is
normalized to `in-production`. The pipeline trims text, normalizes URLs through
the application's URL safety rules, and validates numeric ranges with the same
models used by canonical collection writes.

The tracked demonstration file is
`examples/collection_ingestion.csv`. It intentionally contains one valid
candidate, one unknown-designer failure, and one row matching an existing
canonical collection.

## Safe execution

Use the immutable Clerk ID of an existing local Trainspotting user. The default
is a dry run: it reads the database for reconciliation but writes nothing.

```bash
python -m scripts.ingest_collections \
  examples/collection_ingestion.csv \
  --submitter-clerk-user-id user_your_clerk_user_id
```

With Docker Compose running, the equivalent command is:

```bash
docker compose exec api python -m scripts.ingest_collections \
  examples/collection_ingestion.csv \
  --submitter-clerk-user-id user_your_clerk_user_id
```

Review the JSON reconciliation summary. Only add `--apply` when the counts and
row classifications are expected:

```bash
docker compose exec api python -m scripts.ingest_collections \
  examples/collection_ingestion.csv \
  --submitter-clerk-user-id user_your_clerk_user_id \
  --source-name "Demo Day curated research" \
  --apply
```

Applied runs create an `ingestion_batches` record and one `ingestion_rows`
record per CSV row. Raw payloads and validation errors remain inspectable.
Valid candidates become `submitted` collection additions linked back to their
ingestion rows and appear in the normal moderator queue. Duplicate and invalid
rows never create submissions. Reapplying the same normalized input produces a
duplicate classification instead of another submission.

Approval remains a separate moderator action. Therefore ingestion credentials
cannot bypass review or write directly to `designers`, `collections`,
`collection_credits`, or `collection_media`.
