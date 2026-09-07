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

## Approved pre-freeze extensions

These P1 cards deepen the recommendation story without changing the protected
P0 demo baseline. Complete them in order and defer any unfinished card at the
September 16 feature-freeze boundary; they must never delay the release
candidate.

### DEMO-X04 — Editorial recommendation vocabulary and scoring

**Priority:** P1 · **Size:** S · **Dependency:** DEMO-02

- Define a small, transparent vocabulary for themes, motifs, materials,
  textures, colors, and silhouettes, including deterministic aliases.
- Infer descriptors only from existing curated public collection copy.
- Weight editorial overlap above designer, label, season, and year proximity.
- Keep archival attributes as useful fallback and supporting context.
- Return visitor-friendly match strength, numeric score, and specific reasons.
- Prove cross-label editorial matches can outrank same-house adjacency.

**Excluded from this slice:** machine learning, image analysis, personalization,
and claims that inferred descriptors are permanent canonical facts.

**Done when:** a visitor can follow an explainable cross-label recommendation
based primarily on editorial characteristics.

### DEMO-X05 — Moderator-reviewed collection enrichment

**Priority:** P1 · **Size:** M · **Dependency:** DEMO-X04

- Enrich only a curated demonstration set using the controlled vocabulary.
- Record descriptor category, canonical value, dominant/supporting strength,
  evidence note, source, proposer, reviewer, and timestamps.
- Reuse authenticated submission, review, decision, audit, and rollback
  boundaries wherever possible.
- Treat automated extraction as a suggestion that cannot publish itself.
- Give moderators review responsibility and reserve taxonomy changes and final
  canonical promotion for administrators.
- Report enrichment completeness as guidance, never an insertion constraint.

**Excluded from this slice:** bulk archive tagging, public free-form tags, a
general taxonomy-management console, and mandatory tag-count database rules.

**Done when:** an authorized reviewer can inspect evidence and approve or reject
one suggested enrichment without bypassing audit history or altering unrelated
collection data.

### DEMO-X06 — Curated recommendation journeys and diversity

**Priority:** P1 · **Size:** S · **Dependency:** DEMO-X05

- Define a small editorial evaluation set covering several designers, labels,
  decades, and relationship types.
- Record expected useful connections and prohibited/self/duplicate outcomes.
- Prefer a diverse result set when relevance is comparable so one label or
  designer does not monopolize the journey.
- Add deterministic relevance, explanation-integrity, diversity, and sparse-data
  regressions.
- Document one primary demo journey and one reliable fallback journey.

**Excluded from this slice:** behavioral analytics, popularity signals, A/B
testing infrastructure, and an organization-wide recommendation benchmark.

**Done when:** the selected demo journey is editorially defensible, varied,
repeatable, and protected by automated tests.

### DEMO-X07 — Designer aliases and normalized discovery

**Priority:** P1 · **Size:** S · **Parent roadmap card:** DATA-05

- Store sourced aliases as relational records without replacing preferred
  display names.
- Normalize aliases deterministically for accent- and punctuation-insensitive
  discovery.
- Resolve aliases through public search and administrator designer selection.
- Display documented aliases and their evidence on designer profiles.

**Excluded from this slice:** historical date precision, nationality modeling,
label aliases, and public alias submissions.

**Done when:** a legitimate alias resolves to the correct canonical designer,
ambiguous normalized aliases are rejected, and SQLite/MySQL paths agree.

### DEMO-X08 — Source registry and licensing policy

**Priority:** P1 · **Size:** S · **Parent roadmap card:** INGEST-01

- Inventory every source type currently used by curated archive and ingestion
  workflows.
- Record attribution expectations, access method, licensing considerations,
  reliability, rate limits, and automation status.
- Establish an explicit approval boundary before any source is automated.
- Keep this slice documentation-focused; do not add scraping or external jobs.

**Done when:** every automated or proposed source has a reviewable legal and
technical basis and the current curated workflow remains unchanged.

### DEMO-X11 — Archive image strategy decision

**Priority:** P2 · **Size:** Research · **Parent roadmap card:** MEDIA-01

- Compare platform embeds, hotlinks, open-license media, written permissions,
  and hosted copies without acquiring any new third-party asset.
- Define rights evidence, attribution, alt text, moderation, takedown, storage,
  caching, cost, and recovery requirements.
- Decide whether still-image implementation belongs before or after Demo Day.

**Excluded from this slice:** downloading, scraping, uploading, publishing, or
rendering any new third-party image and all schema, API, or UI changes.

**Done when:** an accepted decision record defines permitted media paths,
prohibited shortcuts, operational safeguards, and a clear go/no-go result.

### DEMO-X14 — Narrative workflow demonstration dataset

**Priority:** P1 · **Size:** M · **Dependencies:** DEMO-01, DEMO-03, DEMO-X05

- Use the verified Louis Vuitton Spring 2024 men's capsule by Tyler, The
  Creator as a production-eligible narrative anchor.
- Exercise realistic designer, collection, correction, enrichment, decision,
  promotion, rollback, audit, and ingestion records as one connected story.
- Keep constructed identities and workflow states in a guarded, disposable
  local Docker/MySQL environment.
- Make setup idempotent and make reset remove only the isolated demo volume.
- Document the exact instructor walkthrough without committing credentials or
  private identities.

**Excluded from this slice:** fabricated canonical facts, Railway demo fixtures,
new workflow states, and destructive cleanup inside an ordinary database.

**Done when:** every major workflow has convincing inspectable sample data, the
authentic collaboration reaches the public archive through existing governance,
repeat setup is harmless, and reset cannot affect ordinary local or hosted data.

### DEMO-X15 — Verified collection-video expansion

**Priority:** P1 · **Size:** M · **Dependencies:** DEMO-X01, DEMO-X13

- Audit canonical collections without video and prioritize demo-relevant records.
- Add only exact collection matches from the represented designer or fashion
  house's own YouTube channel.
- Record the verified title and publisher for every new mapping in a
  machine-checkable curation registry.
- Keep canonical video values as normalized 11-character YouTube IDs and test
  that registry mappings cannot drift from the archive.
- Evaluate Vimeo as a separate provider-aware follow-up; never place a Vimeo URL
  in the YouTube field.

**Done when:** the first verified tranche renders through the existing embed,
live YouTube metadata confirms every selected publisher and title, archive
auditing remains deterministic as coverage grows, and the full application
suite passes.

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
- DEMO-X04 through DEMO-X06 are optional P1 extensions and are deferred intact
  if they threaten the P0 baseline or cannot reach review before feature freeze.
- September 16 ends feature development regardless of unused ideas.

## Post-demo work

The following original cards remain open in the long-term roadmap but are not
part of the September release: DATA-01, DATA-02, full DATA-03, DATA-04, DATA-05,
full DISC-02, full DISC-03, STYLE-01, STYLE-02, full REC-01, USER-01, USER-02,
USER-03, INGEST-01, full INGEST-02, and MEDIA-01.
