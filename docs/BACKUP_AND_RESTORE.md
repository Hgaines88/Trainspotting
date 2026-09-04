# Backup, snapshot, and restore

Trainspotting has two complementary recovery artifacts:

- `data/archive.json` is the versioned public-content snapshot. It contains
  designers, collections, and collection media, and belongs in Git.
- A private SQLite backup contains the complete operational database, including
  users, submissions, sources, decisions, promotions, and append-only audit
  history. It must never be committed to Git or shared publicly.

The local backup and its manifest are written with owner-only permissions.
They still contain sensitive data at rest. Encrypted, scheduled, off-device
retention is intentionally tracked separately by OPS-01; until then, the
operator is responsible for storing private backups securely.

## Check canonical consistency

Run this before creating a release:

```bash
python3 -m scripts.archive_data check
```

Exit status `0` means the public database content matches
`data/archive.json`. Exit status `1` means approved runtime content has drifted
from the versioned snapshot. Do not release stale JSON.

CI creates a clean database from the committed JSON and verifies the round
trip. Because CI cannot access an operator's local production database, the
operator must run the local drift check after approved changes.

## Create one consistent snapshot

Stop write activity, then run:

```bash
python3 -m scripts.archive_backup snapshot backups/archive-YYYYMMDD.db
```

This command uses SQLite's online backup API, validates the backup, and exports
`data/archive.json` from that same database image. It writes an adjacent
manifest with a SHA-256 checksum, table counts, applied migrations, and the
canonical-content digest. Existing backup paths are never overwritten.

Review and commit only the expected `data/archive.json` change. Keep the `.db`
and `.db.manifest.json` files private and outside Git.

## Verify a private backup

```bash
python3 -m scripts.archive_backup verify backups/archive-YYYYMMDD.db
```

Verification checks the file checksum, SQLite integrity, foreign keys, required
tables, row counts, migrations, and canonical digest.

## Restore drill

Practice with a new target so the live database is untouched:

```bash
python3 -m scripts.archive_backup restore backups/archive-YYYYMMDD.db \
  --database data/restore-drill.db
```

Start the application against the drill database or inspect it directly. Check
the canonical record, its submission sources, decision, promotion, and ordered
audit events. Delete the drill copy after verification; it contains the same
sensitive data as the backup.

## Replace a lost or damaged runtime database

1. Stop FastAPI so no connection is writing to the target.
2. Preserve the damaged database separately if it still exists.
3. Verify the chosen backup.
4. Restore it with an explicit replacement:

```bash
python3 -m scripts.archive_backup restore backups/archive-YYYYMMDD.db \
  --database data/archive.db --replace
```

5. Run `python3 -m scripts.archive_data check`.
6. Start FastAPI and confirm public reads, reviewer history, and authorization.

Without `--replace`, the restore command refuses to overwrite any existing
database. Application startup also refuses to recreate or replace an existing
database, preventing a stale canonical snapshot from erasing newer runtime
records.
