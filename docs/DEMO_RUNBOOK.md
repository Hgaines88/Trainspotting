# Trainspotting demo runbook

This is the primary demo-day story. It uses reviewed canonical data and the
tracked ingestion sample; it contains no credentials, tokens, or private user
identifiers.

## Featured record

For the full workflow demonstration, use **Louis Vuitton — Spring 2024 Men's
Capsule by Tyler, The Creator** in the isolated DEMO-X14 environment documented
in [`DEMO_OPERATOR_GUIDE.md`](DEMO_OPERATOR_GUIDE.md). It begins outside the
canonical baseline and enters through a sourced designer proposal followed by a
sourced collection proposal. Tyler Okonma is the lead designer; Pharrell
Williams is credited second as Louis Vuitton men's artistic director and
creative collaborator.

This narrative shows the instructor realistic draft, submitted,
changes-requested, approved, rejected, and rolled-back records; evidence-backed
enrichment; ordered credits; ingestion reconciliation; and chronological audit
history. Use the approved sportswear descriptor to follow a recommendation into
the wider archive.

For the credential-free or canonical-only fallback, use the established Prada
record below.

Use **Prada — Spring/Summer 2024**. Its Vogue Runway source documents the
collection created under co-creative directors Miuccia Prada and Raf Simons.
The record connects four headline capabilities without requiring a disposable
demo record:

- ordered many-to-many designer credits;
- visible canonical evidence;
- explainable related-collection recommendations;
- durable designer and collection URLs.

Find the record through the interface instead of relying on a database ID:
search for `Prada`, open Raf Simons, then open the Spring/Summer 2024
collection.

Use **Dior Men — California Couture, Spring/Summer Menswear 2023** as the
secondary comparison. Its source documents a bounded guest-design project by
Eli Russell Linnetz with Dior Men artistic director Kim Jones. Together, the
two records show why credits are relational: Prada represents ongoing
co-design leadership, while California Couture represents a guest
collaboration.

## Primary walkthrough (about five minutes)

When the isolated narrative environment is prepared, begin with its moderation
queue and Tyler/Louis Vuitton anchor. When it is unavailable, follow the Prada
fallback steps exactly as written.

1. **Anonymous visitor:** Open the homepage. Point out the guided discovery
   paths, search for `Prada`, and open the Spring/Summer 2024 result.
2. **Data model:** Show Miuccia Prada and Raf Simons as ordered credits.
   Explain that the collection-to-designer relationship is a junction table,
   allowing collaboration without duplicating either canonical entity.
   If time permits, open California Couture to contrast its lead and
   collaborator roles with Prada's two co-designer roles.
3. **Trust:** Open the Evidence section and identify the labeled public source.
   Explain that approved community sources appear here without exposing private
   moderation notes or reviewer identity.
4. **Recommendations:** Follow one related collection and read one visible
   reason. Explain that editorial themes, motifs, materials, textures, colors,
   and silhouettes lead the ranking, while creative identity and archive
   context provide supporting signals—not an unexplained black box.
   For a focused recommendation journey, open **Mugler — 20th Anniversary,
   Fall/Winter Couture 1995**. Its theatricality, glamour, and tailoring lead
   into a deliberately varied set spanning Mugler, Jean Paul Gaultier, Gucci,
   and Vivienne Westwood. The deterministic evaluation fixture is recorded in
   `docs/recommendation-evaluation.json`.
5. **Ingestion:** In a prepared terminal, run the tracked CSV in dry-run mode:

   ```bash
   python -m scripts.ingest_collections \
     examples/collection_ingestion.csv \
     --submitter-clerk-user-id "$TRAINSPOTTING_DEMO_USER_ID"
   ```

   Show one valid candidate, one invalid unknown designer, and one duplicate.
   Emphasize that dry run writes nothing and apply mode creates moderation
   submissions rather than canonical records.
6. **Roles:** Briefly describe the tested path: authenticated members propose,
   moderators review, and administrators retain controlled canonical CRUD and
   rollback. If demonstrating a live write, use a disposable staging submission
   and end by rejecting or rolling it back.

## Optional enrichment walkthrough (about two minutes)

1. Sign in as a member, open a collection, and choose **Suggest enrichment**.
2. Select one controlled descriptor and its dominant or supporting strength.
   Add a concise evidence note and an HTTP(S) source, then submit it.
3. Open the review queue as a moderator. Inspect the proposed value, evidence,
   submitter, source, and audit event. Show that a moderator may request changes
   or reject, but cannot publish a canonical descriptor.
4. As an administrator, approve the proposal. Reopen the collection and show
   the reviewed descriptor and evidence. Point out that recommendations can now
   use the normalized value even when collection prose uses different wording.
5. If this is a disposable demonstration record, roll it back as the
   administrator and confirm the collection itself is unchanged.

Automated extraction may eventually suggest the same proposal shape, but it
never bypasses this review and promotion boundary.

## Pre-demo data check

- Confirm the featured record has two ordered credits and a visible source.
- Confirm related collections load and show reasons.
- Confirm the enrichment vocabulary loads for an authenticated member and that
  moderator-only accounts do not receive an approval control for enrichment.
- Run the ingestion sample in dry-run mode and confirm `1 valid`, `1 invalid`,
  and `1 duplicate` with no new batch or submission.
- Confirm the moderation queue contains no temporary workflow-test records.
- Confirm any prior disposable submissions are terminal and the canonical
  archive contains no names beginning with `Test`, `Temporary`, or `E2E`.
- Keep all identities and secrets in ignored environment files or the password
  manager; never paste them into this runbook, screenshots, or terminal history.

## Short fallback (about ninety seconds)

Open the featured collection directly from a prepared browser bookmark. Show
its two credits, Evidence section, and one explainable recommendation. Then show
the saved dry-run output or tracked sample CSV. This path remains effective if
authentication or staging writes are unavailable.

If the featured Prada recommendation path is sparse, use **Loewe — A New
Aesthetic, Spring/Summer 2022** as the recommendation fallback. Its material
and sculptural connections produce a tested four-label journey through Loewe,
JW Anderson, Thom Browne, and Tom Ford.
