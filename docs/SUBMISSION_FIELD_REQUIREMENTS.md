# Submission field requirements

This contract separates saving an incomplete draft from submitting a proposal
for moderator review. It does not change canonical archive records.

## Submission-level fields

| Field | Draft | Submit for review | Meaning |
|---|---|---|---|
| Record type | Required | Required | `designer` or `collection` |
| Submission type | Required | Required | `addition` or `correction` |
| Target record | Optional | Required for corrections; forbidden for additions | Existing canonical record ID |
| Explanation | Optional | Required and non-blank | Why the archive should change |
| Sources | Optional | At least one valid HTTP(S) URL | Evidence for moderator review |
| Submitter | From authenticated session | From authenticated session | Never accepted from request data |

`proposal_kind` defaults to `archive_record`. The bounded `enrichment` kind is
valid only for a correction targeting an existing collection.

## Proposed designer data

| Field | Addition submitted for review | Correction submitted for review |
|---|---|---|
| Full name | Required | Optional, but cannot be cleared |
| Nationality | Optional | Optional; may be explicitly cleared |
| Birth year | Optional | Optional; may be explicitly cleared |
| Website | Optional | Optional; may be explicitly cleared |
| Biography | Optional | Optional; may be explicitly cleared |

## Proposed collection data

| Field | Addition submitted for review | Correction submitted for review |
|---|---|---|
| Designer | Required | Optional, but cannot be cleared |
| Label/fashion house | Required | Optional, but cannot be cleared |
| Season | Required | Optional, but cannot be cleared |
| Release year | Required | Optional, but cannot be cleared |
| Status | Required | Optional, but cannot be cleared |
| Collection name | Optional | Optional; may be explicitly cleared |
| Piece count | Optional | Optional; may be explicitly cleared |
| Description | Optional | Optional; may be explicitly cleared |
| Curated source URL | Optional | Optional; may be explicitly cleared |
| YouTube video | Optional | Optional; may be explicitly cleared |

## Patch semantics for corrections

- An omitted field means “leave the canonical value unchanged.”
- A field explicitly set to `null` means “request removal of this value.”
- Only nullable canonical fields may be cleared.
- An empty correction is invalid when submitted for review.
- Approval will apply the proposed patch transactionally; merely submitting a
proposal will never update the canonical archive.

## Proposed collection enrichment

An enrichment proposal contains exactly one controlled descriptor:

| Field | Requirement |
|---|---|
| Category | One of theme, motif, material, texture, color, or silhouette |
| Canonical value | Must already exist in the server-controlled vocabulary |
| Strength | `dominant` or `supporting` |
| Evidence note | Required, non-blank explanation of what the source supports |
| Target | Existing collection ID |
| Source | At least one valid HTTP(S) submission source |

Members may propose enrichment. Moderators may inspect evidence, request
changes, or reject. Final canonical enrichment approval and rollback are
administrator-only. Approval inserts only the normalized descriptor and never
rewrites unrelated collection fields. Completeness is guidance, not a database
insertion rule, and free-form taxonomy expansion is outside this workflow.

Drafts may be incomplete, but basic type, length, range, and URL checks still
apply to any values they contain. Promotion to the review queue applies all
submission-level and record-level requirements above.

## Status transitions

Only these transitions are valid:

```text
draft ───────────────→ submitted
                         ├──→ changes_requested ───→ submitted
                         ├──→ rejected
                         └──→ approved ────────────→ rolled_back
```

- The submitter owns and may edit only `draft` or `changes_requested` records.
- Members can submit, but only moderators and administrators can review.
- A reviewer cannot decide their own submission.
- Rejection is final; a contributor creates a new submission if new evidence
  later emerges.
- Approval and its canonical write occur in one database transaction.
- Each submission has at most one promotion record, so approval retries return
  the existing result instead of creating duplicates.
- Rollback is restricted to administrators and is refused if the promoted
  canonical record has subsequently changed or acquired dependent records.

Audit events and review decisions are append-only. The promotion record stores
the canonical before/after snapshots, reviewer, timestamps, and any controlled
rollback details.
