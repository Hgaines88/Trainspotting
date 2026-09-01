# Trainspotting Product Direction

## Purpose

A public-facing fashion-history platform for discovering the relationships
among designers, labels, collections, seasons, and creative movements.

## Current user stories

- As a user, I can view all archived designers so I can discover who created fashion collections.
- As a user, I can view the collections credited to a designer across different labels and seasons.
- As a user, I can open a collection to see its label, season, year, status, piece count, and description.
- As a user, I can follow a curated source or watch an official embedded runway video when available.
- As a user, I can add, edit, and delete designer (& collection) records.
- Before public deployment both user authentication and an audit system must be encoded ensuring only verified users can make archival edits (v1.0.0).  

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

CRUD functionality for Designers & Collections by any/all users.

## Trainspotting roadmap

- Promote labels to first-class entities and record designer tenures by role and date.
- Support multiple designer credits and collective membership.
- Add weighted style tags and content-based collection recommendations.
- Add users, favorites, follows, and private or public profiles.
- Build a traceable ingestion and reconciliation pipeline from open sources.
- Add authentication, role-based editing, attribution, history, rollback, and moderation.
- Keep direct image hosting postponed while curated sources and official embeds
  meet the archive's needs.

---

*(h)gaines.*
