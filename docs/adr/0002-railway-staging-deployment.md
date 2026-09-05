# ADR 0002: Railway staging deployment topology

- Status: Accepted for staging implementation
- Date: 2026-09-04
- Decision owners: Trainspotting maintainers
- Related work: REL-04, ARCH-01, SEC-01, OPS-01

## Context

Trainspotting needs a reproducible staging environment for its React client,
FastAPI service, and MySQL 8.4 database. The deployment must preserve the
authoritative database across application restarts, keep MySQL off the public
internet, support Clerk production-domain configuration, run Alembic exactly
once per release, expose meaningful health checks, cache only safe public
content, and permit a tested application rollback.

The project is a portfolio and early community application. Low operating cost
and low administrative overhead matter, but the platform must not pretend an
unmanaged database is a managed service.

## Options considered

### Railway

Railway provides an official MySQL template, persistent volumes, private
service networking, reference and sealed variables, health-gated deployments,
automatic TLS for platform and custom domains, deployment rollback, and an
optional edge CDN. Its Hobby plan has a USD 5 monthly minimum that includes the
first USD 5 of usage; compute, memory, storage, and egress remain usage based.

Railway's MySQL template is explicitly unmanaged. Railway volume backups can
be scheduled, but they remain within the same project and environment and are
deleted if the volume is wiped. An independent encrypted logical backup is
therefore still required under OPS-01.

### Render

Render offers a strong static-site CDN, FastAPI hosting, automatic TLS, health
checks, and deployment rollback. It does not offer managed MySQL as a native
datastore. Running MySQL requires a paid private service and persistent disk,
and Render warns against filesystem snapshot restoration for custom database
recovery. This creates more operational risk than Railway for this project.

### DigitalOcean App Platform and Managed MySQL

DigitalOcean offers a more conventionally managed MySQL product, trusted-source
network restrictions, automatic HTTPS, a static-site CDN, and revision
rollback. It is operationally stronger but materially more expensive for this
stage: application compute starts at USD 5 per month and the smallest managed
MySQL tier is approximately USD 15 per month. It remains the preferred upgrade
path if Trainspotting outgrows an unmanaged Railway database.

## Decision

Use Railway for the first staging environment with three services in one
private project/environment:

1. `web`: the Nginx-served React production build, publicly reachable over
   HTTPS and eligible for Railway's edge CDN.
2. `api`: the FastAPI container, reachable by the browser through `/api` on
   the web origin and by the web proxy over Railway private networking.
3. `mysql`: MySQL 8.4 with an attached persistent volume, no public TCP proxy,
   and scheduled Railway volume backups as the first recovery layer.

The browser uses a single public origin. Nginx proxies `/api/*` privately to
FastAPI, eliminating production CORS exposure and preventing direct browser
access to Railway's private database network. Clerk must allow only the exact
staging and eventual production web origins.

The initial cost ceiling is the Railway Hobby minimum plus explicitly reviewed
usage. A billing alert or usage limit must be configured before staging is left
running continuously. No production claim will be made until OPS-01 adds and
tests an encrypted off-platform MySQL logical backup.

## Release model

- Pull requests must pass the combined GitHub application check before merge.
- Staging releases originate from an annotated tag on a reviewed `main`
  commit; moving or reusing release tags is prohibited.
- The release workflow builds immutable API and web artifacts for that commit.
- A one-shot release command runs `alembic upgrade head` before application
  traffic moves to the new API deployment. API startup may verify the schema
  revision but must not race multiple replicas to perform migrations.
- `/health` proves process liveness. A separate `/ready` check must verify
  database connectivity and the expected Alembic revision without mutating
  state.
- A deployment is accepted only after public-read, authentication,
  authorization, moderation, audit, persistence-restart, and traffic-baseline
  smoke checks pass.

## Cache policy

- Hashed Vite assets: `public, max-age=31536000, immutable`.
- HTML shell: `no-cache` so new asset manifests are discovered promptly.
- Authentication, `/me`, submissions, moderation, and all mutation responses:
  `private, no-store`.
- Public archive GET responses initially use a short shared TTL with
  revalidation. Canonical mutations must trigger explicit purge or versioned
  invalidation before a longer TTL is allowed.
- Requests carrying `Authorization` must never be served from a shared cache.

## Rollback boundary

Railway deployment rollback restores an earlier image and its variables, but
does not reverse a database migration. Every migration used by REL-04 must
therefore be backward compatible with the immediately previous application
release. A destructive schema change requires a separate expand/migrate/contract
sequence and a verified database recovery point.

If staging validation fails, keep mutation traffic closed, roll the web/API
services back to the previous successful release, and leave the database at
the forward-compatible revision. Database restore is reserved for corruption
or irreversible data errors and follows the OPS-01 recovery procedure.

## Required implementation checkpoints

1. Make API startup MySQL-aware and honor Railway's dynamic port.
2. Parameterize the Nginx private API upstream and set explicit cache/security
   headers.
3. Add liveness/readiness endpoints and schema-revision checks.
4. Add a one-shot migration/release command and prevent replica migration races.
5. Define required staging variables without committing values.
6. Add tagged-release automation with environment approval and smoke tests.
7. Configure Clerk staging origins manually and document verification.
8. Rehearse deployment, restart persistence, traffic baseline, and application
   rollback before marking REL-04 complete.

## References

- Railway MySQL: https://docs.railway.com/databases/mysql
- Railway pricing: https://docs.railway.com/pricing
- Railway private networking and domains:
  https://docs.railway.com/networking/domains/working-with-domains
- Railway variables: https://docs.railway.com/variables
- Railway volume backups: https://docs.railway.com/volumes/backups
- Railway CDN/cache headers: https://docs.railway.com/guides/cache-headers-cdn
- Railway deployment rollback:
  https://docs.railway.com/deployments/deployment-actions
- Render persistent disks: https://render.com/docs/disks
- DigitalOcean App Platform pricing:
  https://www.digitalocean.com/pricing/app-platform
- DigitalOcean managed database pricing:
  https://www.digitalocean.com/pricing/managed-databases
