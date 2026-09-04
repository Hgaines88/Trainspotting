# ADR 0001: MySQL as the production database

- Status: Accepted
- Date: 2026-09-04
- Decision owners: Trainspotting maintainers
- Related work: DB-01, ARCH-01, REL-04, OPS-01

## Context

Trainspotting began as a read-mostly SQLite archive and now includes Clerk
users, role enforcement, sourced submissions, moderation, transactional
promotion, append-only audit history, and rollback. The current implementation
uses Python's `sqlite3` driver and SQLite-specific SQL throughout the API,
scripts, migrations, and tests.

SQLite remains adequate for the current dataset and light write volume. It is
not the chosen production foundation for unpredictable concurrent member
writes, multiple application instances, background ingestion, connection
pooling, or managed recovery. DB-01 established WAL operation, bounded lock
waiting, concurrency regressions, and a verified private source snapshot so the
migration can proceed without weakening recovery.

## Decision

Trainspotting will use MySQL 8.4 LTS with InnoDB for production. MySQL 8.4 is
the stable long-term-support line; the implementation will pin an available
8.4 patch image and record its digest in CI or deployment configuration.

SQLAlchemy 2.x will become the database boundary, initially using SQLAlchemy
Core rather than an ORM rewrite. This limits behavioral change while replacing
driver-specific placeholders, row handling, connections, and transactions.
Alembic will own forward schema migrations. PyMySQL will be the initial MySQL
DBAPI driver because it is portable and does not require a local C toolchain.

Configuration will use one required `DATABASE_URL` contract:

- local compatibility and unit tests: `sqlite+pysqlite:///...`;
- local MySQL and integration tests: `mysql+pymysql://...`;
- production: a secret-managed MySQL URL with TLS requirements supplied by the
  selected host.

Credentials will never appear in tracked Compose, workflow, documentation, or
example files. Examples will contain placeholders only.

MySQL tables will use InnoDB, `utf8mb4`, UTC application timestamps, foreign
keys, unique constraints, and indexes equivalent to the verified SQLite
schema. Existing identifiers and API representations will remain stable during
the storage migration.

## Implementation sequence

1. Introduce SQLAlchemy and Alembic while SQLite remains the default and every
   existing test continues to pass.
2. Move connection and transaction ownership behind the database boundary.
3. Translate schema and queries incrementally; do not combine the migration
   with product-schema redesign.
4. Add an isolated MySQL 8.4 service for development and CI. No real account or
   archive data belongs in its image or tracked initialization files.
5. Run the permission, moderation, rollback, canonical-data, and browser suites
   against MySQL, including a workload equivalent to the DB-01 baseline.
6. Restore the verified SQLite snapshot to a disposable copy and migrate that
   copy into disposable MySQL.
7. Reconcile table counts, foreign-key relationships, canonical digest,
   submission sources, decisions, promotions, and ordered audit events.
8. Repeat the rehearsal before production cutover and require a human review
   checkpoint.

## Cutover and rollback

There will be no dual-write period. Dual writes would create two authorities
and introduce reconciliation failure modes that the current project does not
need.

For cutover:

1. Enter a short maintenance window and stop mutations.
2. Create and verify a final private SQLite snapshot.
3. Migrate from a restored copy into an empty MySQL database.
4. Run automated reconciliation and smoke tests.
5. Point the application at MySQL through `DATABASE_URL` and reopen writes.
6. Retain the final SQLite snapshot privately and unchanged through the agreed
   recovery period.

Before any post-cutover MySQL write is accepted, rollback may point the
application back to the final SQLite snapshot. After MySQL accepts writes,
rollback means restoring MySQL or running a deliberately tested reverse export;
silently returning to stale SQLite is forbidden.

## Rejected alternatives

- **Keep SQLite as the production architecture:** simplest today, but conflicts
  with the chosen multi-user deployment and future write-heavy roadmap.
- **Replace `sqlite3` directly with a MySQL connector:** leaves SQL dialect and
  transaction behavior spread throughout the application and makes testing a
  second engine unnecessarily difficult.
- **Rewrite everything as ORM models in one change:** combines storage
  migration with application redesign and creates too large a regression
  surface.
- **Maintain permanent SQLite/MySQL dual support:** useful during migration,
  but not a long-term product requirement. Compatibility code will be removed
  only after MySQL cutover and recovery are proven.
- **Dual-write during cutover:** rejected because partial failures could make
  either database stale without a robust distributed consistency mechanism.

## Consequences

The migration temporarily slows feature delivery and adds a database service,
driver, connection pooling, migrations, credentials, and CI integration. In
return, Trainspotting gains a conventional multi-instance production topology,
row-level write concurrency, managed-hosting compatibility, and clearer
database lifecycle controls.

REL-04 now depends on ARCH-01. OPS-01 must implement MySQL-specific monitoring,
encrypted backups, and restore drills. The SQLite snapshot and tooling remain
migration evidence, not the future production backup system.

## References

- [MySQL LTS and Innovation release model](https://dev.mysql.com/doc/refman/8.4/en/mysql-releases.html)
- [SQLAlchemy database dialects](https://docs.sqlalchemy.org/en/20/dialects/)
- [SQLAlchemy engine configuration](https://docs.sqlalchemy.org/en/20/core/engines.html)
- [Alembic documentation](https://alembic.sqlalchemy.org/en/latest/)
- [Official MySQL container image](https://hub.docker.com/_/mysql)
