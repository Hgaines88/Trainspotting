# SQLite-to-MySQL migration runbook

This procedure migrates a verified SQLite snapshot into an empty MySQL schema.
It preserves primary keys and reconciles every copied table by row count and a
deterministic SHA-256 content digest.

## Safety requirements

- Keep the application in maintenance/read-only mode during the final snapshot
  and cutover.
- Verify the private SQLite backup and its manifest before proceeding.
- Use separate migration and application credentials in hosted environments.
- Grant the application account only the permissions needed at runtime.
- Never place database passwords in tracked files or command history. Prefer the
  ignored local environment file or the deployment platform's secret store.
- The target schema must be empty. The migration command refuses a populated
  target and has no replace mode.

## Local rehearsal

1. Start the isolated MySQL 8.4 service:

   ```shell
   docker compose up -d mysql
   ```

2. Set `DATABASE_URL` to the ignored local MySQL connection URL and apply the
   schema:

   ```shell
   .venv/bin/alembic upgrade head
   ```

3. Set `MYSQL_MIGRATION_DATABASE_URL` to that same target and migrate a verified
   snapshot:

   ```shell
   .venv/bin/python -m scripts.migrate_sqlite_to_mysql \
     --source /absolute/path/to/verified-snapshot.db \
     --apply
   ```

4. Retain the printed per-table counts and SHA-256 digests as rehearsal
   evidence. Run the MySQL integration test with `MYSQL_TEST_DATABASE_URL` set.

## Production cutover

1. Confirm a successful rehearsal against the same MySQL version and schema
   revision intended for production.
2. Enter maintenance/read-only mode and stop mutation traffic.
3. Create and verify a final SQLite snapshot.
4. Apply Alembic migrations to a new, empty MySQL database.
5. Run the migration command and retain its reconciliation report.
6. Run health, public-read, authentication, authorization, moderation, audit,
   and rollback smoke tests against MySQL.
7. Change the application secret `DATABASE_URL`, restart the application, and
   repeat the smoke tests before reopening mutation traffic.
8. Keep the final SQLite snapshot unchanged for the rollback-retention period.

## Rollback

If validation fails before reopening traffic, point `DATABASE_URL` back to the
unchanged SQLite database and restart the application. If writes have been
allowed on MySQL, do not switch databases blindly: re-enter maintenance mode,
preserve a MySQL snapshot, and reconcile post-cutover writes before deciding on
a recovery direction.
