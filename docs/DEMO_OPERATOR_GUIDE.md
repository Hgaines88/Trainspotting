# Trainspotting operator and architecture guide

This credential-free guide is designed to be printed or kept open locally when
AI assistance is unavailable. Never add real Clerk keys, Railway tokens,
database passwords, session tokens, or user IDs to this file.

## The thirty-second architecture explanation

Trainspotting has three runtime layers:

```text
Browser
  |
  v
React frontend / Nginx web service
  |  /api proxy
  v
FastAPI / Uvicorn API service
  |
  v
MySQL 8.4 / persistent volume
```

Clerk handles sign-in, but FastAPI remains authoritative for application roles
and every write. Public visitors can read the archive. Members submit proposed
changes, moderators review them, and administrators control canonical
publication and rollback.

## Recommended local startup: Docker Compose

Use this path for demonstrations. It most closely resembles Railway and needs
only one command window.

1. Start Docker Desktop and wait until Docker Engine reports that it is running.
2. Open Terminal and enter the repository:

   ```bash
   cd /Users/hakeem/Projects/Trainspotting
   ```

3. Confirm the branch and working tree:

   ```bash
   git status --short --branch
   ```

4. Build and start the web, API, and MySQL services:

   ```bash
   docker compose up -d --build
   ```

5. Confirm all three services are running and MySQL/API are healthy:

   ```bash
   docker compose ps
   ```

6. Confirm the web-to-API path and database migration:

   ```bash
   curl --fail --silent http://localhost:5173/api/ready
   ```

   The response must include `"status":"ready"`, `"database":"mysql"`, and
   `"revision":"0006"`.

7. Open <http://localhost:5173>.

If startup fails, inspect logs without changing data:

```bash
docker compose logs --tail=100 mysql api web
```

Stop application compute while retaining the local MySQL volume:

```bash
docker compose down
```

Never add `--volumes` during ordinary shutdown. That option deletes the local
MySQL volume and its data.

## Manual two-server startup

Use this only when an instructor specifically asks to see the frontend and API
development servers separately. MySQL still runs in Docker so the application
uses the same database engine as staging.

### Terminal 1: MySQL and FastAPI

```bash
cd /Users/hakeem/Projects/Trainspotting
docker compose up -d mysql
source .venv/bin/activate
set -a
source .env
set +a
export DATABASE_URL='mysql+pymysql://trainspotting:trainspotting_dev_only@127.0.0.1:3307/trainspotting?charset=utf8mb4'
export AUTO_MIGRATE_DATABASE=true
python -m scripts.migrate_database
python -m scripts.start_api
```

The API listens on <http://localhost:8000>. Leave this terminal running.

### Terminal 2: React/Vite

```bash
cd /Users/hakeem/Projects/Trainspotting
source .venv/bin/activate
set -a
source .env
set +a
export VITE_CLERK_PUBLISHABLE_KEY="$CLERK_PUBLISHABLE_KEY"
cd react-ui
npm run dev -- --host 127.0.0.1
```

The React client listens on <http://localhost:5173> and Vite proxies `/api` to
FastAPI. Leave this terminal running.

Stop each foreground server with `Control-C`, then stop MySQL with:

```bash
cd /Users/hakeem/Projects/Trainspotting
docker compose stop mysql
```

The `.env` file must remain ignored by Git. If authentication is not needed,
the public archive can still be demonstrated without displaying or copying any
Clerk key.

## Safe ingestion dry run

Select an existing local member without printing the Clerk identifier:

```bash
export DEMOID="$(docker compose exec -T mysql mysql -N -B \
  -utrainspotting -ptrainspotting_dev_only trainspotting \
  -e "SELECT clerk_user_id FROM users WHERE role = 'member' ORDER BY id LIMIT 1;")"
test -n "$DEMOID" && echo "Demo identity ready" || echo "Demo identity missing"
```

Then run the tracked sample without `--apply`:

```bash
docker compose exec api python -m scripts.ingest_collections \
  examples/collection_ingestion.csv \
  --submitter-clerk-user-id "$DEMOID"
```

Expected result: three input rows, one valid, one invalid, one duplicate,
`dry_run: true`, `batch_id: null`, and `submissions_created: 0`.

## What Railway does

Railway is the hosted staging environment. It proves that the application can
run outside the laptop with managed networking, HTTPS, secrets, deployment
history, health checks, a persistent MySQL volume, and repeatable deployment
automation. Local Docker remains the free development environment and Demo Day
fallback.

The staging topology is:

```text
Public HTTPS
  |
  v
web (Nginx + compiled React) ---- only public Railway domain
  |
  | private Railway DNS: api:8000
  v
api (FastAPI + Uvicorn) --------- no public domain
  |
  | private DATABASE_URL
  v
MySQL 8.4 ----------------------- no public TCP proxy
  |
  v
mysql-volume -------------------- persistent data

mysql-backup cron --> encrypted dump --> private Cloudflare R2 bucket
```

The browser never connects directly to MySQL or the private API. Nginx serves
the compiled React assets and proxies `/api` requests through Railway's private
network. This reduces exposed attack surface and avoids public database egress.

## How Railway was configured

### MySQL service

- Official MySQL 8.4 image and a volume mounted at `/var/lib/mysql`.
- Database name, application user, application password, and root password are
  Railway variables; none are committed.
- Private networking only: no generated public domain and no TCP proxy.
- One staging replica in the same region as the application.

### API service

- Source: Trainspotting repository root and root `Dockerfile`.
- Pre-deploy command: `python -m scripts.migrate_database`.
- Healthcheck: `/ready`.
- `AUTO_MIGRATE_DATABASE=false`, because migrations run once before deployment
  rather than racing inside application replicas.
- `DATABASE_URL` references MySQL's private Railway URL.
- Clerk secret key and the exact authorized web origin are private variables.
- No public domain; it is reached only through the web proxy.

### Web service

- Source: the same repository, with root directory `/react-ui`.
- Build: `react-ui/Dockerfile` compiles React and copies it into Nginx.
- Healthcheck: `/`; runtime port: `80`.
- `API_UPSTREAM` points to the API's private Railway DNS name and port.
- The Clerk publishable key is a frontend build variable; it is intentionally
  public, unlike the Clerk secret key.
- This is the only service with a generated public HTTPS domain.

### Backup service

- Source: root `Dockerfile.backup`.
- Runs as a Railway cron job and exits after one backup attempt.
- Receives private MySQL access plus bucket-scoped R2 credentials and an
  encryption key.
- The R2 bucket remains private and has lifecycle rules for retention.

## How tagged deployments work

Ordinary pushes and pull requests do not deploy staging. Deployment is an
explicit release action:

1. A reviewed pull request is merged into `main` after the full application
   check passes.
2. An annotated `v*` tag is created on that exact `main` commit.
3. GitHub Actions verifies that the tag is annotated and still equals current
   `main`.
4. The workflow uses the GitHub `staging` environment's scoped Railway token.
5. It deploys the API first; the pre-deploy Alembic migration must succeed.
6. It deploys the web service from the same commit.
7. It waits for readiness and runs public, cache-policy, MySQL, and anonymous
   authorization smoke checks.

Release candidate `v0.1.5` successfully exercised this entire path and reported
MySQL revision `0006`.

## Stop Railway without deleting configuration or data

In the `staging` environment, open each service's **Deployments** tab. For the
active `web`, `api`, and MySQL deployments, use the three-dot menu and choose
**Remove**. This stops compute while preserving each service configuration.

For `mysql-backup`, confirm no run is active and temporarily remove its cron
schedule if no scheduled backups should run. Do not delete a service, detach or
delete `mysql-volume`, delete the environment, or delete the project.

The persistent volume may continue to incur a small storage charge even while
compute is stopped.

## Resume Railway safely

1. Redeploy MySQL and wait until it is online.
2. Redeploy the API and confirm its pre-deploy migration and `/ready` health
   check pass.
3. Redeploy the web service and open its public HTTPS domain.
4. Restore the backup cron schedule if scheduled protection is desired.
5. Run:

   ```bash
   python -m scripts.smoke_staging \
     --base-url https://web-staging-9862.up.railway.app
   ```

6. Confirm the smoke report names MySQL and revision `0006` before presenting.

The first request after a restart can briefly return `502` while private
services become ready. Start or resume the environment well before a live demo.

Railway references:

- [Deployment actions](https://docs.railway.com/deployments/deployment-actions)
  explains removing and redeploying service deployments.
- [Serverless](https://docs.railway.com/deployments/serverless) explains idle
  sleeping, wake-up behavior, and possible cold-start responses.
- [Cron jobs](https://docs.railway.com/cron-jobs) explains scheduled services
  that run a task and exit.
- [Cost control](https://docs.railway.com/pricing/cost-control) explains usage
  limits, resource limits, private networking, and serverless cost controls.

## Instructor-ready answers

**Why Railway if Docker already works?**

Docker proves reproducible local development. Railway proves the same service
boundaries work on hosted infrastructure with HTTPS, private networking,
persistent storage, secrets, deployment history, and automated release checks.
Docker remains the fallback and avoids making development dependent on a paid
host.

**Why is only the web service public?**

Visitors need the website, not direct database or API infrastructure access.
Keeping the API and MySQL private reduces attack surface. Nginx provides the one
controlled public entry point.

**How is database persistence protected?**

MySQL stores data on an attached Railway volume, so replacing stateless web or
API containers does not replace the database. Alembic applies forward-only
schema revisions before a new API becomes active. Encrypted scheduled backups
are stored in a private off-platform R2 bucket.

**How are secrets protected?**

Secrets live in Railway service variables or the scoped GitHub `staging`
environment secret. They are excluded from source control, frontend bundles,
screenshots, logs, and documentation. The frontend receives only Clerk's
publishable key.

**How do you prevent a bad release?**

Pull requests run backend, frontend, MySQL, migration, security, and browser
checks. Only an annotated tag on current reviewed `main` can trigger staging.
The API migration must pass before deployment, health checks gate availability,
and the workflow finishes with non-destructive smoke tests.

**What happens if Railway fails on Demo Day?**

The same release runs locally through Docker Compose with persistent MySQL. The
primary story, tracked ingestion sample, and credential-free screenshots are
available offline in [`DEMO_REHEARSAL.md`](DEMO_REHEARSAL.md).

## Final five-minute preflight

- [ ] Docker Engine is running.
- [ ] `docker compose ps` shows MySQL and API healthy and web running.
- [ ] Local `/api/ready` reports MySQL revision `0006`.
- [ ] Railway is online only if the hosted demonstration will be used.
- [ ] Prada Spring/Summer 2024 shows Miuccia Prada and Raf Simons.
- [ ] Evidence and related-collection reasons load.
- [ ] Member and administrator accounts are available without exposing values.
- [ ] The ingestion dry-run terminal is prepared.
- [ ] Unrelated tabs and notifications are closed.
- [ ] [`DEMO_REHEARSAL.md`](DEMO_REHEARSAL.md) and its screenshots are available
      offline.
