# Trainspotting: Current Data Model

This document describes the schema implemented today. Trainspotting's planned
model adds labels, designer tenures, shared collection credits, collectives,
style tags, users, favorites, and connections; those additions will be
documented here as they are implemented.

## Designer

Represents an individual fashion designer.

| Field | Meaning | Required? |
|---|---|---|
| id | Internal unique identifier | Yes |
| full_name | Designer’s full name | Yes |
| nationality | Designer’s nationality | No |
| birth_year | Year the designer was born | No |
| website | Designer’s official website | No |
| biography | Background and career information | No |

## Collection

Represents a collection credited to one lead designer.

| Field | Meaning | Required? |
|---|---|---|
| id | Internal unique identifier | Yes |
| designer_id | Identifies the lead designer | Yes |
| label | Label or fashion house that released it | Yes |
| name | Collection’s given name, if it has one | No |
| season | Fashion season, such as Spring/Summer | Yes |
| release_year | Year it was released or planned | Yes |
| status | Concept, in production, released, or archived | Yes |
| piece_count | Number of looks or pieces | No |
| description | Collection notes and context | No |

A collection name is optional because many fashion collections are unnamed or eponymous and are instead identified by label, season, and year.

## Collection media

Represents a curated external resource associated with one collection. The
archive stores links and YouTube video IDs, not copyrighted media files.

| Field | Meaning | Required? |
|---|---|---|
| id | Internal unique identifier | Yes |
| collection_id | Identifies the collection | Yes |
| media_type | Curated source or YouTube video | Yes |
| media_value | Source URL or normalized YouTube video ID | Yes |

## Relationship rules

- One designer may have zero or many collections.
- Every collection must reference one existing designer.
- Deleting a designer deletes their collection records.
- One collection may have a source link and a YouTube video.
- Deleting a collection deletes its media records.

## Application user

Represents an authenticated Clerk identity and Trainspotting's authoritative
application role. New identities are always created as members; clients cannot
provide or change their own role.

| Field | Meaning | Required? |
|---|---|---|
| id | Internal unique identifier | Yes |
| clerk_user_id | Clerk's immutable external user identifier | Yes |
| email | Optional synchronized contact address | No |
| display_name | Optional synchronized public name | No |
| role | Member, moderator, or administrator | Yes |
| created_at | Local identity creation time | Yes |
| updated_at | Last administrative profile update time | Yes |

---

*(h)gaines.*
