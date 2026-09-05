# Backup, snapshot, and restore

Trainspotting has three complementary recovery artifacts:

- `data/archive.json` is the versioned public-content snapshot. It contains
  designers, collections, and collection media, and belongs in Git.
- An encrypted MySQL logical backup contains the complete operational database,
  including users, submissions, sources, decisions, promotions, and append-only
  audit history. It is the active recovery format.
- A private legacy SQLite backup contains the pre-migration operational database,
  including
  users, submissions, sources, decisions, promotions, and append-only audit
  history. It must never be committed to Git or shared publicly.

MySQL backup artifacts and manifests are written with owner-only permissions;
the database dump is encrypted and authenticated before it is saved. The
encryption key must be stored separately from the backup. Scheduled off-device
retention is the next OPS-01 checkpoint.

## Create and verify an encrypted MySQL backup

Install the MySQL 8.4 client so `mysqldump` and `mysql` match the server's major
version. Generate a Fernet key once and store it in a password manager or secret
store; losing it makes every backup encrypted with it unrecoverable:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set `DATABASE_URL` and `MYSQL_BACKUP_ENCRYPTION_KEY` only in the process
environment, then create and independently verify an artifact:

```bash
python -m scripts.mysql_backup create backups/trainspotting-YYYYMMDD.sql.enc
python -m scripts.mysql_backup verify backups/trainspotting-YYYYMMDD.sql.enc
```

Credentials are supplied to MySQL through a temporary owner-only option file,
not command arguments. Plaintext SQL is held in process memory and is never
written to disk. The current implementation is appropriate for the small
Trainspotting dataset; replace it with streaming authenticated encryption before
logical dumps regularly exceed 100 MiB.

## Restore an encrypted MySQL backup

Always restore into a newly created, isolated, empty database first. The command
refuses a target containing any table and requires the explicit `--apply`
acknowledgement:

```bash
DATABASE_URL='mysql+pymysql://USER:PASSWORD@HOST:PORT/EMPTY_DATABASE' \
  python -m scripts.mysql_backup restore \
  backups/trainspotting-YYYYMMDD.sql.enc --apply
```

The restore streams decrypted SQL directly into `mysql`, then verifies all 11
required Trainspotting tables. Before promoting a recovered database, also
confirm the Alembic revision, representative canonical and moderation rows,
foreign-key behavior, and the four append-only audit triggers.

## Recorded MySQL restore drill

On 2026-09-05, OPS-01 restored an encrypted dump made with MySQL client 8.4.11
into a separate empty schema inside a disposable MySQL 8.4.11 container. The
drill recovered the fixture row, Alembic revision `0002`, all 11 tables, and all
four audit-protection triggers. Staging and persistent local data were not
touched. The disposable container, key, and artifacts were removed afterward.

The observed hands-on restore took under five minutes for the current tiny
dataset. This is drill evidence, not yet the production recovery-time objective.
Once the daily off-platform backup schedule is enabled, the staging recovery-point
objective is 24 hours, with a 26-hour staleness threshold to allow scheduler variance.

## Legacy SQLite recovery material

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

### Create one consistent snapshot

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

### Verify a private backup

```bash
python3 -m scripts.archive_backup verify backups/archive-YYYYMMDD.db
```

Verification checks the file checksum, SQLite integrity, foreign keys, required
tables, row counts, migrations, and canonical digest.

### Restore drill

Practice with a new target so the live database is untouched:

```bash
python3 -m scripts.archive_backup restore backups/archive-YYYYMMDD.db \
  --database data/restore-drill.db
```

Start the application against the drill database or inspect it directly. Check
the canonical record, its submission sources, decision, promotion, and ordered
audit events. Delete the drill copy after verification; it contains the same
sensitive data as the backup.

### Replace a lost or damaged runtime database

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
