# Trainspotting Product Kanban

The live, instructor-facing board is maintained in
[GitHub Projects](https://github.com/users/Hgaines88/projects/11). This document
preserves the planning rationale and recommended execution sequence in the
repository; GitHub Projects is the authoritative source for current card
status.

This board translates the product vision into an implementation order. Cards
move from **Backlog** to **Ready**, then **In progress**, **Validate**, and
**Done**. Only one major feature epic should be in progress at a time.

## Working agreements

- Public archive reads remain available without an account.
- FastAPI remains authoritative for authentication, roles, and every write.
- Canonical records change only through administrator CRUD or an approved,
  audited submission transaction.
- Schema changes use forward-only migrations and preserve existing records.
- Every card requires tests, documentation, migration verification when
  applicable, and a production build before completion.
- Accessibility, responsive behavior, empty/error/loading states, and privacy
  are acceptance criteria—not later cleanup.
- Direct image hosting remains postponed until licensing, attribution, storage,
  and moderation policies are settled.

## In progress

### WF-01 — Close the browser walkthrough

**Priority:** P0 · **Size:** S · **Dependencies:** Moderation foundation

- Review resubmitted submission `#1`.
- Confirm the contributor display name and two sources appear.
- Reject it with a clear note because it is intentionally test data.
- Confirm the temporary designer remains absent.
- Preserve the audit records as the first completed workflow example.

**Done when:** submissions `#1` and `#2` are in terminal test states, no test
designer exists, and the entire history is visible to authorized reviewers.

## Ready — release-quality foundation

Complete these cards in order before expanding the archive model.

### REL-01 — Automated browser workflow tests

**Priority:** P0 · **Size:** M · **Dependencies:** WF-01

- Add Playwright or an equivalent browser-testing layer.
- Cover anonymous browsing, member submission, request changes, resubmission,
  moderator approval, duplicate approval retry, and administrator rollback.
- Use isolated test identities and a disposable database.
- Verify unauthorized controls are absent and direct route access is denied.

**Done when:** the critical workflow runs unattended locally and in CI without
using development archive data.

### REL-02 — Canonical snapshot consistency

**Priority:** P0 · **Size:** M · **Dependencies:** REL-01

- Decide whether approved transactions automatically refresh
  `data/archive.json` or create an explicit export task.
- Detect drift between SQLite and the canonical JSON snapshot.
- Prevent deployments from silently replacing newer approved content with an
  older snapshot.
- Document backup and restore procedures for submissions and audit tables, not
  only designers and collections.

**Done when:** an approved change survives database loss and a full documented
restore, with its sources and audit history intact.

### REL-03 — Continuous integration

**Priority:** P0 · **Size:** S · **Dependencies:** REL-01

- Run Python tests, React tests, lint, production build, and migration checks on
  every pull request.
- Add a clean-database migration test from schema zero to current.
- Block merging when security or data-integrity tests fail.
- Scan tracked files for committed secrets.

**Done when:** GitHub reports one required, reproducible green check for the
entire application.

### REL-04 — Production deployment design

**Priority:** P0 · **Size:** M · **Dependencies:** REL-02, REL-03

- Select hosting for React, FastAPI, and persistent relational storage.
- Configure production Clerk domains, redirect URLs, authorized parties, and
  environment secrets.
- Replace local-only assumptions with production origins and HTTPS.
- Define deployment, migration, rollback, and health-check procedures.
- Establish development, staging, and production environments.

**Done when:** staging deploys from a tagged commit, runs migrations once,
passes smoke tests, and retains data across restarts.

### SEC-01 — Security and abuse review

**Priority:** P0 · **Size:** M · **Dependencies:** REL-04

- Rate-limit authentication-adjacent and submission endpoints.
- Add request-size, source-count, and text-length limits at proxy and API layers.
- Review stored and rendered text for injection and unsafe-link behavior.
- Define account suspension and submission-spam controls.
- Review role-promotion and emergency administrator recovery procedures.
- Document retention and deletion rules for account profile data.

**Done when:** abuse cases have automated tests, operational responses, and no
client-controlled path can alter roles or canonical data.

### OPS-01 — Monitoring, backups, and recovery

**Priority:** P0 · **Size:** M · **Dependencies:** REL-04

- Add structured request, authentication, moderation, and migration logs.
- Track error rate, latency, queue depth, approval failures, and backup health.
- Schedule encrypted backups with retention rules.
- Perform and record a restore drill.
- Create alerts that do not expose tokens or personal data.

Implementation and response thresholds are recorded in
[`operations-runbook.md`](operations-runbook.md).

**Done when:** a failed approval and unavailable database are detectable, and a
tested recovery point objective is documented.

### UX-01 — Moderation workspace refinement

**Priority:** P1 · **Size:** M · **Dependencies:** WF-01

- Replace browser prompts with accessible decision and rollback dialogs.
- Add submission detail pages with field-by-field proposed/current comparison.
- Display human-readable contributor and reviewer names with privacy-safe
  fallback labels.
- Show complete decision and audit timelines.
- Add queue counts, sorting, filters, pagination, and clear terminal states.
- Improve mobile layout and prevent oversized headings from crowding records.

**Done when:** a moderator can understand evidence, changes, identity, and
history without reading raw JSON or Clerk identifiers.

### UX-02 — Submission experience refinement

**Priority:** P1 · **Size:** M · **Dependencies:** UX-01

- Add explicit draft saving rather than combining save and submit.
- Add field-level “leave unchanged” and “clear this value” controls for
  corrections.
- Replace raw target and designer IDs with searchable record selectors.
- Support source ordering, removal, notes, and source-type labels.
- Show validation before submission and preserve form state after errors.
- Add submission detail pages and status notifications.

**Done when:** members can produce a valid addition or correction without
knowing database IDs or patch semantics.

## Backlog — archive discovery

### DISC-01 — Search, filter, and pagination

**Priority:** P1 · **Size:** L · **Dependencies:** REL-04

- Search designers, labels, collection names, seasons, years, and descriptions.
- Filter by nationality, label, season, year, and status.
- Add stable sorting and API pagination metadata.
- Preserve filters in shareable URLs.
- Add useful no-result suggestions.

**Done when:** the archive remains fast and navigable beyond several thousand
records, with indexed query plans and accessibility tests.

### DISC-02 — Homepage and browse information architecture

**Priority:** P1 · **Size:** M · **Dependencies:** DISC-01

- Separate featured/recent content from “View all designers.”
- Add label, season, and timeline browse entry points.
- Establish editorial feature selection and expiry rules.
- Preserve direct, durable URLs for every canonical record.

**Done when:** visitors can begin with a person, house, season, or editorial
feature without loading the entire archive.

### DISC-03 — Source transparency

**Priority:** P1 · **Size:** M · **Dependencies:** UX-01

- Associate multiple citations with canonical fields or records.
- Display provenance and last-reviewed dates publicly.
- Mark inaccessible, archived, disputed, or secondary sources.
- Decide how approved submission citations become canonical citations.

**Done when:** a visitor can understand why each important factual claim is in
the archive and moderators can replace dead sources without losing history.

## Backlog — expanded fashion-history model

Implement these as separate schema migrations and API/UI slices. Do not combine
them into one large migration.

### DATA-01 — Labels as first-class entities

**Priority:** P1 · **Size:** L · **Dependencies:** DISC-03

- Define label identity, aliases, founding/closure years, location, website,
  description, and source policy.
- Migrate collection label text into deduplicated label records.
- Preserve original display text and resolve naming collisions manually.
- Add label list/detail pages and label submissions.

**Done when:** collections reference a label ID, every migrated label is
reconciled, and no historical collection relationship is lost.

### DATA-02 — Designer tenures and roles

**Priority:** P1 · **Size:** L · **Dependencies:** DATA-01

- Model designer-to-label roles with start/end precision, role title, interim
  status, and citations.
- Support overlapping and uncertain dates without inventing precision.
- Present succession timelines on designer and label pages.
- Moderate tenure additions and corrections through the existing workflow.

**Done when:** Trainspotting can answer who led a house, in what role, and when,
with sources and honest date precision.

### DATA-03 — Multiple collection credits

**Priority:** P1 · **Size:** L · **Dependencies:** DATA-01, DATA-02

- Replace the single lead-designer assumption with credited contributors.
- Define lead, co-designer, guest, collaborator, and attribution-note roles.
- Preserve compatibility while migrating current `designer_id` values.
- Display ordered credits consistently on all collection views.

**Done when:** collaborative collections no longer require flattening or
duplicating people and every credit is sourced.

### DATA-04 — Collectives and membership

**Priority:** P2 · **Size:** L · **Dependencies:** DATA-03

- Decide whether people and collectives share an entity model or use explicit
  linked types.
- Track membership roles and date ranges.
- Credit both the collective and known individual contributors appropriately.
- Add collective list/detail and moderation support.

**Done when:** collective authorship is represented without erasing individuals
or falsely assigning undocumented credit.

### DATA-05 — Temporal and naming precision

**Priority:** P2 · **Size:** M · **Dependencies:** DATA-01

- Add aliases, former names, preferred display names, and normalized search
  values for designers and labels.
- Represent known year, month, day, approximate, and unknown dates explicitly.
- Normalize nationality/country terminology while retaining nuanced display
  values and corresponding flags.

**Done when:** search resolves legitimate aliases and the system never converts
an approximate historical date into a false exact date.

## Backlog — style graph and recommendations

### STYLE-01 — Controlled style taxonomy

**Priority:** P2 · **Size:** L · **Dependencies:** DATA-03

- Research and define tag categories, aliases, descriptions, and governance.
- Distinguish observable attributes from subjective interpretation.
- Require evidence or editorial notes for assigned tags.
- Add moderator merge/deprecate operations without deleting history.

**Done when:** tags are consistent enough for browsing and recommendations,
rather than an uncontrolled collection of synonyms.

### STYLE-02 — Weighted collection tagging

**Priority:** P2 · **Size:** L · **Dependencies:** STYLE-01

- Store tag strength, confidence, assigner, source, and timestamps.
- Add an accessible editorial tagging interface.
- Include tag changes in moderation and audit history.
- Display meaningful tags without presenting subjective scores as facts.

**Done when:** collection vectors can be reproduced from audited tag records.

### REC-01 — Explainable related collections

**Priority:** P2 · **Size:** L · **Dependencies:** STYLE-02

- Establish a deterministic content-similarity baseline.
- Exclude leakage from popularity or private user data initially.
- Show “why this is related” using shared tags and contextual metadata.
- Create offline relevance evaluation and editorial review sets.

**Done when:** recommendations are fast, testable, explainable, and demonstrably
more useful than simple same-label or same-year links.

## Backlog — member experience

### USER-01 — Profile and privacy model

**Priority:** P2 · **Size:** M · **Dependencies:** SEC-01

- Define public display name, avatar, biography, profile visibility, and handle
  rules separately from Clerk authentication data.
- Allow members to control public visibility without controlling roles.
- Add account export and deletion workflows.

**Done when:** public identity is intentional, privacy-safe, and independent of
the immutable Clerk ID.

### USER-02 — Favorites and personal archive

**Priority:** P2 · **Size:** M · **Dependencies:** USER-01, DATA-03

- Favorite designers, labels, and collections.
- Add private-by-default saved lists with optional public sharing.
- Prevent duplicate favorites and preserve referential integrity.
- Add pagination and account export coverage.

**Done when:** members can reliably return to saved research without affecting
canonical rankings or moderation.

### USER-03 — Follows and activity

**Priority:** P3 · **Size:** L · **Dependencies:** USER-01, USER-02

- Decide whether users follow people, labels, other members, or all three.
- Define privacy, blocking, notification, and abuse behavior first.
- Build an activity feed from audited archive events rather than mutable text.

**Done when:** follows add discovery value without leaking private activity or
creating an unmoderated social surface.

## Backlog — ingestion and reconciliation

### INGEST-01 — Source registry and licensing policy

**Priority:** P2 · **Size:** M · **Dependencies:** DISC-03

- Inventory permitted primary, institutional, editorial, and open-data sources.
- Record attribution, licensing, rate limits, access method, and reliability.
- Prohibit ingestion from sources without acceptable usage terms.

**Done when:** every automated source has a documented legal and technical
basis for use.

### INGEST-02 — Staging and reconciliation pipeline

**Priority:** P2 · **Size:** XL · **Dependencies:** INGEST-01, DATA-01

- Import external records into staging tables, never canonical tables.
- Normalize names and dates while retaining raw source payloads.
- Generate possible matches with confidence and human review.
- Convert accepted reconciliations into ordinary audited submissions.
- Make imports restartable, observable, and duplicate-safe.

**Done when:** rerunning an import creates neither duplicate canonical records
nor silent overwrites, and every promoted fact is traceable to raw input.

### MEDIA-01 — Image strategy decision

**Priority:** P3 · **Size:** Research · **Dependencies:** INGEST-01

- Evaluate licensed embeds, institution/open-license media, user-provided URLs,
  storage costs, transformations, takedowns, and accessibility requirements.
- Define attribution and rights metadata before storing any image asset.

**Done when:** a written decision covers rights, moderation, cost, performance,
alt text, deletion, and disaster recovery. Implementation is a later card.

## Done — current foundation

- **FOUND-01:** Trainspotting branding and repository separation.
- **FOUND-02:** Public read-only React and Vanilla archives.
- **AUTH-01:** Clerk Google/passwordless authentication and local users.
- **AUTH-02:** Member, moderator, and administrator authorization matrix.
- **ADMIN-01:** Administrator-only canonical CRUD.
- **MOD-01:** Drafts, sourced submissions, and field requirements.
- **MOD-02:** Moderator queue and valid state transitions.
- **MOD-03:** Transactional, idempotent canonical approval.
- **MOD-04:** Append-only decisions/audit and controlled rollback.
- **MOD-05:** Member revision/resubmission and multiple-source UI.
- **MOD-06:** Contributor display names and reviewer self-decision prevention.
- **DATA-00:** Canonical JSON archive, migrations, and SQLite runtime model.

## Recommended execution sequence

```text
WF-01
  → REL-01 → REL-02 → REL-03 → REL-04
  → SEC-01 → OPS-01
  → UX-01 → UX-02
  → DISC-01 → DISC-02 → DISC-03
  → DATA-01 → DATA-02 → DATA-03 → DATA-04/DATA-05
  → STYLE-01 → STYLE-02 → REC-01
  → USER-01 → USER-02 → USER-03
  → INGEST-01 → INGEST-02
  → MEDIA-01 research when product needs justify it
```

This sequence deliberately makes Trainspotting recoverable, observable, and
safe to deploy before substantially increasing data-model and community
complexity.
