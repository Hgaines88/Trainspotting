# SQLite migration safety checkpoint

SQLite remains Trainspotting's authoritative database only until ARCH-01
completes the validated MySQL migration. These safeguards protect that source;
they are not a long-term SQLite scaling strategy.

## Temporary runtime settings

Every application connection verifies:

- write-ahead logging (`journal_mode=WAL`);
- a 5,000 ms busy timeout;
- foreign-key enforcement.

If WAL cannot be enabled, startup or connection creation fails instead of
silently running with unexpected concurrency behavior.

## Transaction audit

Application write paths were reviewed before migration. Multi-step submission,
moderation, approval, rollback, and administrator-bootstrap operations use
explicit transactions with rollback and `finally` cleanup. Other mutation paths
also close connections in `finally`, which rolls back any uncommitted SQLite
transaction. Clerk profile retrieval occurs before the profile-update connection
is opened, so a network call is not held inside a database transaction.

## Disposable baseline

Run the small mixed workload from the repository root:

```bash
python3 -m scripts.sqlite_baseline
```

It creates a temporary database from canonical JSON, performs concurrent public
reads and representative draft writes, verifies persisted write count and
SQLite integrity, prints JSON results, and deletes the database. It never uses
`data/archive.db`. Record the output in the ARCH-01 architecture decision and
repeat an equivalent workload against MySQL; elapsed time is meaningful only
when the machine and workload parameters are identical.

This is a regression baseline, not a promise about production user capacity.

## Pre-migration snapshot

Immediately before a migration rehearsal, stop writes and follow
[`BACKUP_AND_RESTORE.md`](BACKUP_AND_RESTORE.md) to create and verify a private
snapshot. Migrate from a restored copy, never from the sole authoritative file.
