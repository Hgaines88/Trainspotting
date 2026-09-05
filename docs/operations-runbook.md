# Operations, alerting, and recovery runbook

This runbook covers the Railway staging environment. Never place tokens,
database URLs, encryption keys, object-storage credentials, request bodies,
source URLs, or Clerk user IDs in tickets, logs, screenshots, or Git.

## Service signals

- `/ready` verifies API connectivity and the expected Alembic revision. The web
  proxy exposes it as `/api/ready`.
- Structured `trainspotting.operations` logs contain a request ID, method,
  normalized route template, status, and duration only.
- HTTP 5xx events log at `ERROR`; HTTP 429 and requests lasting at least 1,000 ms
  log at `WARNING`.
- `/operations/metrics` is admin-only and reports bounded request, database,
  transaction, connection-pool, and moderation aggregates. It is process-local
  and resets on deployment; use it for diagnosis, not durable history.
- The backup job emits one `mysql_backup_completed` JSON event only after local
  encryption verification, both remote uploads, and remote size/checksum
  metadata verification succeed. A nonzero exit means the backup failed.

## Initial alert thresholds

Use these conservative staging thresholds until at least seven days of traffic
establishes a baseline:

| Signal | Initial alert | First response |
| --- | --- | --- |
| Readiness | Two consecutive failures over five minutes | Check API deployment, then MySQL health and variables |
| HTTP 5xx | Any sustained cluster of 3 in five minutes | Group by route template and request ID; inspect API/MySQL logs |
| Latency | 5 requests at or above 1,000 ms in five minutes | Check pool saturation and database-operation latency |
| Rate limiting | 10 HTTP 429 responses in five minutes | Confirm abuse versus an undersized documented limit |
| Pool health | `checked_out >= size` for five minutes | Find slow transactions; do not raise pool size blindly |
| DB operations | Any repeated `CONNECT`, `COMMIT`, or query errors | Check MySQL health, credentials, capacity, and recent deploys |
| Moderation | Approval failures or rollbacks above the normal manual workflow | Inspect the audit trail; never bypass transactional promotion |
| Backup job | Any failed scheduled execution | Preserve logs, correct the cause, then run one manual job |
| Backup age | No verified off-platform backup newer than 26 hours | Treat as failed backup and run a verified replacement |

Threshold changes require a short note in this runbook or the OPS-01 issue so
alerts cannot be silently weakened.

## Recovery objectives

- **Staging RPO:** 24 hours after the daily schedule is enabled. The 26-hour age
  threshold allows normal scheduler variance without hiding a missed day.
- **Staging RTO:** 30 minutes to provision an isolated MySQL target, restore,
  verify, and redirect staging after an operator begins recovery.

The 2026-09-05 isolated drill restored the current small dataset in under five
minutes. The 30-minute RTO includes diagnosis, provisioning, verification, and
human review. Revisit both objectives as database size and product importance
grow.

## Dedicated backup service

After the OPS-01 branch is reviewed and merged, create a fourth Railway staging
service named `mysql-backup` from the Trainspotting repository:

- Dockerfile path: `Dockerfile.backup`
- No public domain, TCP proxy, volume, or health-check endpoint
- Cron schedule: `0 6 * * *` (06:00 UTC daily)
- The process must exit after every run; an active prior execution causes
  Railway to skip the next scheduled run.

Set these variables on `mysql-backup` only:

| Variable | Source |
| --- | --- |
| `DATABASE_URL` | Railway reference to MySQL's private `MYSQL_URL` |
| `MYSQL_BACKUP_ENCRYPTION_KEY` | Independently stored Fernet key |
| `BACKUP_S3_ENDPOINT` | Cloudflare R2 S3 endpoint |
| `BACKUP_S3_ACCESS_KEY_ID` | Bucket-scoped R2 credential |
| `BACKUP_S3_SECRET_ACCESS_KEY` | Bucket-scoped R2 credential |
| `BACKUP_S3_BUCKET` | `trainspotting-backups` |
| `BACKUP_S3_PREFIX` | `staging/mysql` |
| `BACKUP_S3_REGION` | `auto` |

Do not copy R2 credentials into `api` or `web`. Do not give the bucket a public
domain. The R2 token is restricted to this bucket, and a lifecycle rule expires
objects under `staging/mysql/` after 35 days.

## Failed backup response

1. Confirm no secret value appears in the failure log before sharing it.
2. Determine whether dump, encryption, upload, or remote verification failed.
3. Correct configuration or availability; never disable encryption or remote
   verification to make the job green.
4. Trigger one manual deployment of `mysql-backup`.
5. Confirm exactly one `mysql_backup_completed` event and both `.sql.enc` and
   `.sql.enc.json` objects in R2.
6. Run an independent backup-health check and record the recovered timestamp.

## Database recovery

Follow [Backup and restore](BACKUP_AND_RESTORE.md). Always download both the
encrypted artifact and manifest, verify them, and restore into a new empty
database. Never rehearse against staging. Promote a restored target only after
checking Alembic revision, representative canonical and moderation rows,
foreign-key behavior, and append-only audit triggers.
