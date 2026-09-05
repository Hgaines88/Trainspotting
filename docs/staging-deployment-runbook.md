# Staging deployment runbook

This runbook turns the topology in ADR 0002 into an auditable Railway staging
environment. Values belong in Railway or GitHub secret storage. Never paste
real credentials into source files, commits, issues, workflow logs, or pull
request comments.

## 1. Create the environment and services

Create one Railway project with a `staging` environment and these services:

| Service | Source/build | Public network | Persistent state |
| --- | --- | --- | --- |
| `web` | `react-ui/Dockerfile` | One generated HTTPS domain | None |
| `api` | root `Dockerfile` | No public domain | None |
| `mysql` | Railway MySQL 8.4 template | No TCP proxy | Attached volume |

Keep the API and database private. The browser should reach FastAPI only through
the web service's `/api` proxy. Set a usage alert or limit before leaving the
environment continuously active.

## 2. Configure service settings

Configure `api` with:

- health check path `/ready`;
- pre-deploy command `python -m scripts.migrate_database`;
- one replica during the initial staging rehearsal;
- root `Dockerfile` as its Docker build;
- restart policy `ON_FAILURE` with a finite retry limit.

Configure `web` with:

- health check path `/`;
- `react-ui/Dockerfile` as its Docker build;
- one generated public domain;
- restart policy `ON_FAILURE` with a finite retry limit.

Railway pre-deploy commands run in a separate container with private-network
access. A failed migration therefore prevents the new API deployment from
starting. `AUTO_MIGRATE_DATABASE=false` ensures application replicas never race
to migrate during startup; the migration command also holds a MySQL advisory
lock as defense in depth.

## 3. Configure Railway variables

Use [the safe contract](../deploy/staging.env.example) as a checklist, not as a
source of real values.

On `api`:

- `DATABASE_URL`: use a Railway reference to the MySQL service's private
  `MYSQL_URL`. Trainspotting normalizes Railway's generic `mysql://` scheme to
  the installed `pymysql` driver at its configuration boundary;
- `AUTO_MIGRATE_DATABASE=false`;
- `CLERK_SECRET_KEY`: the Clerk staging instance secret key;
- `CLERK_AUTHORIZED_PARTIES`: the exact public HTTPS origin of `web`, with no
  wildcard and no trailing path.

On `web`:

- `API_UPSTREAM`: the API service's Railway private DNS name and listening port,
  without `http://` or a path;
- `VITE_CLERK_PUBLISHABLE_KEY`: the Clerk staging publishable key. This is a
  public build-time value, not a secret.

Do not expose `DATABASE_URL`, add a public MySQL TCP proxy, put
`CLERK_SECRET_KEY` in the web service, or enable automatic API migrations.

## 4. Configure Clerk

In the Clerk staging instance, add only the generated `web` HTTPS origin to the
allowed origins, redirects, and authorized parties required by the configured
Google and passwordless-email flows. Keep localhost entries in the development
instance rather than broadening staging with wildcards.

Verify sign-in and sign-out in a private browser window. Confirm `/api/me`
returns the expected immutable Clerk user identity and local role. Do not use a
production administrator account for routine smoke testing.

## 5. Configure the GitHub staging environment

Create a GitHub environment named `staging` and restrict its deployment policy
to release tags matching `v*`. Store only this environment secret:

- `RAILWAY_TOKEN`: a Railway project token scoped to the staging environment.

Set `STAGING_BASE_URL`, the public HTTPS origin of the web service, as an
environment variable. It is intentionally not secret.

Do not store a Clerk session token in GitHub: Clerk session tokens are
short-lived and would normally expire before a later deployment runs. Never
store an interactive user password, Clerk secret key, or MySQL credentials in
GitHub for deployment.

GitHub does not provide required-reviewer environment gates for a private
personal repository on GitHub Pro. Treat annotated tag creation as the explicit
human release action unless the repository plan or visibility changes.

## 6. Release and acceptance order

1. Merge a reviewed pull request to `main` after the required application check
   passes.
2. Create a new annotated tag on that exact `main` commit. Never move or reuse a
   release tag.
3. Deploy `api`; its pre-deploy migration must complete before readiness passes.
4. Deploy `web` from the same tag.
5. Let the workflow run its automated public, readiness, cache, and anonymous
   authorization smoke checks through the public web origin.
6. Sign in as the non-admin staging smoke user, obtain a fresh Clerk session
   token, and immediately run the authenticated checks locally:

   ```bash
   read -s -p "Clerk session token: " STAGING_SMOKE_BEARER_TOKEN; echo
   STAGING_BASE_URL=https://trainspotting-staging.example.com \
     STAGING_SMOKE_BEARER_TOKEN="$STAGING_SMOKE_BEARER_TOKEN" \
     python -m scripts.smoke_staging --require-token
   unset STAGING_SMOKE_BEARER_TOKEN
   ```

   Enter the token only in the current shell invocation. Do not save it in a
   file, shell history, GitHub secret, issue, or workflow log. Confirm the
   identity endpoint succeeds and canonical mutation is rejected with `403`.
7. Complete the manual moderation and audit-history walkthrough while signed in
   with the appropriate staging accounts.
8. Record the tag, commit SHA, Alembic revision, service deployment IDs, and
   smoke result in the release notes.

## 7. Persistence and rollback rehearsal

Create a uniquely named test submission, restart both stateless services, and
verify the submission and audit events remain. Do not restart or replace MySQL
during this check.

For an application rollback, select the previous successful `web` and `api`
deployments. Leave the database at its forward-compatible revision and rerun
readiness plus smoke tests. Database restoration is for corruption or
irreversible data loss and remains an OPS-01 procedure.

REL-04 is complete only when a tagged staging deployment passes this rehearsal
and its evidence is recorded.
