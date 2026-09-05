# Trainspotting Demo Day Kanban

**Demo date:** September 24, 2026  
**Internal feature freeze:** September 16, 2026  
**Release-candidate target:** September 20, 2026

This is the active delivery plan for Demo Day. The broader product roadmap is
preserved in [`TRAINSPOTTING_KANBAN.md`](TRAINSPOTTING_KANBAN.md); completing
that long-term roadmap is not a requirement for the September release.

## Product story

Trainspotting is a sourced fashion-history archive that connects discovery,
explainable relationships, and data-engineering workflows. Visitors can explore
the archive, members can propose sourced changes, and authorized reviewers can
promote or reverse those changes through an auditable workflow.

## Scope rules

- Deliver complete, tested vertical slices instead of partial broad features.
- Reuse the existing authentication, moderation, audit, MySQL, CI, backup, and
  deployment foundation.
- New ideas go to the long-term roadmap until after Demo Day.
- Do not add external scraping, machine-learning claims, social features, or a
  large data-model redesign before the release.
- After September 16, only release-blocking corrections may change behavior.

## Ordered demo cards

### DEMO-01 — Multiple collection credits

**Priority:** P0 · **Size:** M · **Target:** September 8

Implement a safe many-to-many credit model that demonstrates relational design.

- Add ordered collection-to-designer credits with lead, co-designer, guest,
  collaborator, and attribution-note roles.
- Migrate every current `designer_id` into a lead credit without losing the
  compatibility field.
- Display ordered credits on collection pages and API responses.
- Give administrators a controlled way to maintain credits.
- Prevent duplicate credits and preserve referential integrity.

**Excluded from this slice:** designer-to-label tenure timelines and complete
moderation support for credit edits.

**Done when:** existing collections retain their lead designer, one collection
can visibly credit multiple people in a stable order, and SQLite/MySQL migration
and regression tests pass.

### DEMO-02 — Explainable related collections

**Priority:** P0 · **Size:** M · **Dependency:** DEMO-01 · **Target:** September 10

Build a deterministic recommendation baseline using existing public metadata.

- Rank related collections using shared contributors, label, season, nearby
  release years, and meaningful name/description terms.
- Exclude the current collection and prevent duplicate results.
- Return a stable score and human-readable reasons.
- Display a concise “Related collections” section on collection pages.
- Test ranking, ties, sparse records, and explanation integrity.

**Excluded from this slice:** personalization, machine learning, weighted style
taxonomy, popularity signals, and private member data.

**Done when:** a visitor can open a collection, see useful related records, and
understand why each was recommended.

### DEMO-03 — Curated ingestion pipeline

**Priority:** P0 · **Size:** L · **Dependency:** DEMO-01 · **Target:** September 13

Demonstrate a real data-engineering path into the existing moderation workflow.

- Accept one documented, curated CSV or JSON input contract.
- Record ingestion batches and retain raw source rows.
- Normalize supported values and validate required fields.
- Generate deterministic fingerprints for rerun safety.
- Classify rows as valid, invalid, duplicate, or requiring review.
- Support a dry run and emit a reconciliation summary.
- Convert accepted candidates into ordinary audited submissions; never write
  directly to canonical archive tables.

**Excluded from this slice:** web scraping, scheduled third-party ingestion,
probabilistic entity matching, and a browser-based mapping designer.

**Done when:** the same sample can be run twice without duplicate canonical
records, failures remain inspectable, and a valid row reaches moderation.

### DEMO-04 — Demo browse and homepage

**Priority:** P0 · **Size:** S · **Dependencies:** DEMO-02 · **Target:** September 14

Turn the existing archive discovery tools into a clear demonstration entry point.

- Separate a small editorial/recent area from the full designer index.
- Add practical designer, label, season, and timeline entry points using the
  existing schema and shareable discovery URLs.
- Surface the related-collection journey without loading the entire archive.
- Preserve durable designer and collection URLs.

**Excluded from this slice:** first-class label entities, editorial scheduling,
and a content-management system.

**Done when:** a first-time visitor can begin a compelling discovery path from
the homepage without explanation.

### DEMO-05 — Essential public provenance

**Priority:** P0 · **Size:** S · **Target:** September 15

Make the archive's evidence visible without introducing the full provenance model.

- Display existing canonical source links with clear labels.
- Preserve appropriate sources from approved submissions.
- Show basic review timing or availability information where it is trustworthy.
- Handle missing and inaccessible sources without breaking record pages.

**Excluded from this slice:** field-level citations, source replacement history,
archival crawling, and a complete source-quality taxonomy.

**Done when:** the demo can trace an important displayed claim to visible
evidence and explain how community evidence reaches the canonical archive.

### DEMO-06 — Curated demonstration dataset and narrative

**Priority:** P0 · **Size:** S · **Dependencies:** DEMO-02, DEMO-03, DEMO-05 · **Target:** September 16

- Select a small, accurate group of records that demonstrate multiple credits,
  recommendations, provenance, and ingestion.
- Remove temporary test content from staging and canonical data.
- Document the exact anonymous, member, moderator, and administrator walkthrough.
- Keep demo identities and secrets outside version control.

**Done when:** the demonstration tells one coherent story using verified data.

### DEMO-REL-01 — Feature freeze and release candidate

**Priority:** P0 · **Size:** M · **Dependencies:** DEMO-01 through DEMO-06  
**Window:** September 17–20

- Run the complete backend, frontend, MySQL, Playwright, Docker, security, backup,
  and staging checks.
- Correct only release-blocking defects.
- Verify responsive behavior and critical accessibility paths.
- Confirm Railway configuration without leaving unnecessary services running.
- Tag the release candidate only after all required checks pass.

**Done when:** a clean checkout can reproduce the tested release and staging is
ready for a timed walkthrough.

### DEMO-REL-02 — Rehearsal and fallback readiness

**Priority:** P0 · **Size:** S · **Dependency:** DEMO-REL-01  
**Window:** September 21–23

- Rehearse a concise primary demo and a shorter fallback version.
- Confirm local Docker/MySQL can run the demonstration without Railway.
- Capture backup screenshots or video of the critical workflow.
- Prepare credentials, sample ingestion input, URLs, and talking points.
- Do not add features during this window.

**Done when:** the presentation can continue through a network or hosting failure.

## Delivery gates

- If DEMO-01 is not stable by September 9, omit administrator credit editing and
  retain read-only migrated credits.
- If DEMO-02 is not stable by September 11, reduce results to three deterministic
  recommendations and keep the explanation contract.
- If DEMO-03 is not stable by September 14, demonstrate the tested CLI dry run and
  reconciliation report; do not build ingestion UI.
- DEMO-04 and DEMO-05 must reuse current schemas unless a migration is essential.
- September 16 ends feature development regardless of unused ideas.

## Post-demo work

The following original cards remain open in the long-term roadmap but are not
part of the September release: DATA-01, DATA-02, full DATA-03, DATA-04, DATA-05,
full DISC-02, full DISC-03, STYLE-01, STYLE-02, full REC-01, USER-01, USER-02,
USER-03, INGEST-01, full INGEST-02, and MEDIA-01.
