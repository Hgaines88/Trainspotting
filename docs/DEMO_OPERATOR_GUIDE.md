# Trainspotting operator and architecture guide

This credential-free guide is designed to be printed or kept open locally when
AI assistance is unavailable. Never add real or hosted Clerk keys, Railway
tokens, database credentials, session tokens, or user IDs to this file. Values
explicitly labeled `local-development` are disposable defaults already defined
in `compose.yaml`; they must never be reused outside the local Docker stack.

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
   cd /path/to/Trainspotting
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
   `"revision":"0007"`.

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
cd /path/to/Trainspotting
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
cd /path/to/Trainspotting
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
cd /path/to/Trainspotting
docker compose stop mysql
```

The `.env` file must remain ignored by Git. If authentication is not needed,
the public archive can still be demonstrated without displaying or copying any
Clerk key.

## Safe ingestion dry run

Select an existing local member without printing the Clerk identifier:

```bash
export DEMOID="$(docker compose exec -T mysql \
  sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -N -B \
  -u"$MYSQL_USER" "$MYSQL_DATABASE" \
  -e "SELECT clerk_user_id FROM users WHERE role = \
  CHAR(109,101,109,98,101,114) ORDER BY id LIMIT 1;"')"
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
MySQL revision `0007`.

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
5. Copy the current public web domain from Railway into a temporary shell
   variable, then run the smoke check:

   ```bash
   export STAGING_BASE_URL='https://your-current-domain.up.railway.app'
   python -m scripts.smoke_staging \
     --base-url "$STAGING_BASE_URL"
   ```

6. Confirm the smoke report names MySQL and revision `0007` before presenting.

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

## Data engineering skills demonstrated

Trainspotting is not only a CRUD application. It demonstrates a controlled data
lifecycle from researched input through validation, review, publication,
serving, monitoring, backup, and recovery.

| Competency | Evidence in Trainspotting |
| --- | --- |
| Relational data modeling | Normalized designers, collections, sources, users, submissions, decisions, ingestion ledgers, and audit records; a many-to-many junction table represents ordered designer credits and roles without duplicating entities. |
| Schema evolution | Forward-only Alembic migrations upgrade both local and hosted MySQL. A Railway pre-deploy migration must pass before a new API deployment becomes active. |
| Batch ingestion | The curated CSV pipeline reads structured source rows, retains their raw form, normalizes supported values, validates the contract, and produces a reconciliation result. |
| Data quality | Deterministic checks identify invalid references, unsafe values, duplicate natural keys, taxonomy inconsistencies, and canonical/runtime drift instead of silently accepting questionable data. |
| Idempotency and deduplication | SHA-256 fingerprints classify repeated ingestion rows as duplicates. Approval and synchronization paths are designed so retries do not create duplicate canonical records. |
| Staging and promotion | Valid ingestion rows become reviewable submissions rather than direct writes. Member, moderator, and administrator boundaries separate proposed data from canonical publication. |
| Transactional integrity | Canonical promotion, ordered credits, decisions, and audit events are committed as controlled units; failed validation or conflicting rollback does not leave partial state. |
| Lineage and provenance | Source URLs, raw ingestion rows, batch records, proposer/reviewer actions, decisions, promotions, and append-only audit events show where data came from and how it changed. |
| Database portability and migration | The project migrated from SQLite to MySQL while retaining SQLite as an explicit compatibility and recovery path. Reconciliation tests compare counts, relationships, canonical digests, and operational history. |
| Query design and performance | Public discovery uses indexed filtering, stable sorting, API pagination, cache-aware versioning, and set-based aggregation for collection counts. |
| Serving and cache consistency | Public responses use archive-version-aware caching. Canonical mutations increment the version so clients and shared caches cannot continue serving stale archive data. |
| Orchestration and CI/CD | GitHub Actions runs application and database gates, validates immutable release tags, deploys services in dependency order, and executes post-deploy smoke checks. |
| Infrastructure and environments | Docker Compose provides reproducible local web, API, and MySQL services; Railway provides an independently configured hosted staging environment with private service networking. |
| Observability | Readiness and health endpoints expose database backend and migration revision; structured service metrics cover requests, database operations, connection pools, and moderation activity. |
| Backup and disaster recovery | A scheduled worker creates encrypted MySQL backups in a private off-platform R2 bucket. Restore procedures validate schema revision, canonical data, relationships, and operational history. |
| Security and governance | Least-public networking, scoped secrets, role-based authorization, append-only auditing, request limits, safe URL validation, and controlled rollback protect both data and operations. |

### Sixty-second explanation

> “Trainspotting demonstrates an end-to-end governed data pipeline. Researched
> CSV rows enter a staged ingestion process where I preserve the raw input,
> normalize and validate fields, reconcile references, and detect duplicate
> rows with deterministic fingerprints. Valid candidates become moderated
> submissions instead of writing directly to production tables. Approved data
> is promoted transactionally into a normalized MySQL model with ordered
> many-to-many credits, source provenance, and append-only audit history. I use
> Alembic for schema evolution, indexed and paginated queries for serving,
> archive-versioned cache invalidation for consistency, Docker for reproducible
> local infrastructure, and tag-gated CI/CD for Railway staging. The operational
> side includes health checks, database metrics, encrypted off-platform backups,
> and a tested local fallback.”

### What to show as proof

If an instructor asks for concrete evidence, show these in this order:

1. Prada Spring/Summer 2024 and its ordered junction-table credits.
2. `examples/collection_ingestion.csv` and the non-destructive reconciliation
   output: one valid, one invalid, and one duplicate.
3. The moderation queue and audit history to show staged promotion and lineage.
4. `alembic/versions/` and `/api/ready` to show controlled schema evolution.
5. `.github/workflows/deploy-staging.yml` to show release orchestration.
6. `Dockerfile.backup` and `docs/BACKUP_AND_RESTORE.md` to show recovery design.

## How the recommendation system is coded

The recommendation system is deterministic and explainable. It does not use a
machine-learning model, personal tracking, popularity, or a third-party
recommendation API. The implementation is in `app/recommendations.py`; the
FastAPI endpoint that retrieves candidates is in `app/main.py` at
`GET /collections/{collection_id}/related`.

### 1. Controlled editorial vocabulary

`EDITORIAL_FACETS` defines six categories and approved canonical descriptors:

- theme;
- motif;
- material;
- texture;
- color;
- silhouette.

Each canonical value has aliases. For example, `oversize` and `oversized`
normalize to the silhouette `oversized`; `transparent` and `transparency`
normalize to the texture `sheer`. This converts varied editorial language into
stable, comparable values.

`editorial_facets(collection)` combines two sources:

1. structured descriptors that passed the enrichment moderation workflow; and
2. deterministic whole-word matches inferred from the collection name and
   description.

Only values in the controlled vocabulary are accepted. Regex word boundaries
avoid substring matches. The color `black` has an additional context rule: it
must occur near clothing, material, or garment language. This prevents a phrase
such as “Black American history” from being incorrectly treated as a garment
color.

### 2. SQL candidate retrieval

The API does not load every collection and compare everything in memory. It
first asks MySQL for plausible candidates that share at least one retrieval
signal:

- label;
- season;
- release year within two years;
- a credited designer through the credit junction table;
- an editorial alias found in the name or description; or
- an approved structured descriptor.

`editorial_search_terms()` expands detected canonical facets back into their
known aliases for candidate retrieval. Results are read in stable ID order in
batches of 200. This bounds memory use while allowing the ranking layer to keep
the best results across batches.

### 3. Transparent weighted scoring

`rank_related_collections()` compares the target with each unique candidate.
Editorial overlap has the strongest weights:

| Signal | Points |
| --- | ---: |
| Each shared theme | 5 |
| Each shared motif | 5 |
| Each shared material | 5 |
| Each shared texture | 4 |
| Each shared color | 4 |
| Each shared silhouette | 3 |
| Each shared credited designer | 3 |
| Same label | 2 |
| Same season | 1 |
| Same year or within two years | 1 |
| Each shared meaningful editorial term, up to three | 1 |

This weighting lets a cross-label collection with strong material or thematic
overlap outrank a nearby collection from the same designer or house. Season and
year are only supporting signals: a candidate must also share an editorial
facet, contributor, or label before it can appear.

The target collection is excluded, repeated candidate IDs are ignored, and
designer names are removed from free-text terms so the same relationship is not
accidentally counted twice.

### 4. Reasons and match strength

Every scoring contribution creates a visitor-facing reason such as:

- `Shared material: denim, leather`;
- `Shared silhouette: sculptural`;
- `Shared contributor: Raf Simons`; or
- `Released 1 year apart`.

The integer score is translated into a stable label:

- `Strong`: 14 or more;
- `Notable`: 9–13;
- `Contextual`: below 9.

The API returns the numeric score, match-strength label, and reasons with each
recommended collection. The React interface renders these fields directly, so
the explanation shown to a visitor is produced by the same logic that produced
the ranking.

### 5. Diversity pass

Pure relevance can fill the result list with one house or designer. After the
initial ranking, `_diversify()` examines candidates within two points of the
current best score. Inside that near-equal relevance window, it prefers the
candidate that repeats the fewest already selected labels and credited
designers.

The algorithm never replaces a clearly stronger result merely for variety.
After selection, results remain displayed in descending score order with
release year and collection ID as deterministic tie-breakers.

### 6. Regression and editorial evaluation

`tests/test_recommendations.py` verifies exact scores and reasons, stable ties,
strength thresholds, alias normalization, sparse-result behavior, duplicate and
self exclusion, cross-label editorial ranking, diversity, and the contextual
handling of `black`.

`tests/test_recommendation_journeys.py` evaluates curated end-to-end journeys
defined in `docs/recommendation-evaluation.json`. The primary Mugler journey and
fallback Loewe journey specify expected collections, distinct-label diversity,
required explanation types, and prohibited inference outcomes. These fixtures
make the demo journey repeatable rather than dependent on a subjective visual
check.

### Sixty-second recommendation explanation

> “I built a deterministic, explainable recommendation system rather than a
> black-box model. A controlled vocabulary normalizes themes, motifs, materials,
> textures, colors, and silhouettes from reviewed descriptors and curated
> collection copy. MySQL first retrieves a bounded candidate set using indexed
> archive relationships and editorial search terms. Python then applies explicit
> weights, with editorial overlap weighted above designer, label, season, and
> year proximity. Every point produces a visible reason, and broad time signals
> cannot establish a match by themselves. A diversity pass can prefer another
> house or designer only when candidates are within two relevance points. Exact
> scores, explanations, exclusions, cultural-context safeguards, and two curated
> demo journeys are protected by deterministic regression tests.”

If asked why this is not machine learning, explain that the current archive is
small and editorial trust is more important than opaque personalization. The
rules provide a measurable baseline and labeled evaluation set that could later
support learning-to-rank experiments without discarding explainability.

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
- [ ] Local `/api/ready` reports MySQL revision `0007`.
- [ ] Railway is online only if the hosted demonstration will be used.
- [ ] Prada Spring/Summer 2024 shows Miuccia Prada and Raf Simons.
- [ ] Evidence and related-collection reasons load.
- [ ] Member and administrator accounts are available without exposing values.
- [ ] The ingestion dry-run terminal is prepared.
- [ ] Unrelated tabs and notifications are closed.
- [ ] [`DEMO_REHEARSAL.md`](DEMO_REHEARSAL.md) and its screenshots are available
      offline.
