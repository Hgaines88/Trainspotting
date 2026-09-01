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

Drafts may be incomplete, but basic type, length, range, and URL checks still
apply to any values they contain. Promotion to the review queue applies all
submission-level and record-level requirements above.
