# Trainspotting Product Direction

## Purpose

A public-facing fashion-history platform for discovering the relationships
among designers, labels, collections, seasons, and creative movements.

## Current user stories

- As a user, I can view all archived designers so I can discover who created fashion collections.
- As a user, I can view the collections credited to a designer across different labels and seasons.
- As a user, I can open a collection to see its label, season, year, status, piece count, and description.
- As a user, I can follow a curated source or watch an official embedded runway video when available.
- As a visitor, I can browse the archive without an account or the ability to
  change canonical records.

## Home page

For a small archive, the home page can initially show every designer.
Larger archive should show only recent or featured designers with a separate
"View All" page.

## Designer page

Full Name, Country/Nationality, Birth Year, Website. Background/Bio

## Collection page

Each collection page should show basic details about each collection:
Lead Designer
Label/Fashion House
Season
Release Year
Status (archived, released, concept, in-production, etc)
Piece Count
Description
Curated source link
Official YouTube runway video

## Current features

Public read access to designers, collections, sources, and runway media;
Clerk-backed accounts and application roles; administrator-only canonical
editing; sourced member submissions; moderator decisions; transactional,
idempotent approval; append-only audit history; and controlled rollback.

## Editorial policy

Trainspotting is an archive, not a public wiki. Canonical records are read-only
for visitors and ordinary members. Members may submit sourced additions or
corrections to a separate review queue, but submissions never write directly
to the archive. Moderators review proposals, while administrators retain
direct canonical editing and controlled rollback. Every approved change
retains its author, reviewer, sources, timestamp, and decision history.

## Trainspotting roadmap

- Promote labels to first-class entities and record designer tenures by role and date.
- Support multiple designer credits and collective membership.
- Add weighted style tags and content-based collection recommendations.
- Harden and deploy the completed authentication and moderation foundation.
- Add users, favorites, follows, and private or public profiles.
- Build a traceable ingestion and reconciliation pipeline from open sources.
- Expand field-level provenance and public source transparency.
- Keep direct image hosting postponed while curated sources and official embeds
  meet the archive's needs.

The ordered implementation board, dependencies, and acceptance criteria live
in [`docs/TRAINSPOTTING_KANBAN.md`](docs/TRAINSPOTTING_KANBAN.md).

---

*(h)gaines.*
