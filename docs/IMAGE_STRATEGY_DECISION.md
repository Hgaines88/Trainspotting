# Archive image strategy decision

**Status:** Accepted for pre-demo planning  
**Reviewed:** September 6, 2026  
**Decision owner:** Trainspotting administrator  
**Parent roadmap card:** MEDIA-01

This record defines the engineering and editorial boundary for still images and
hosted media. It complements the
[`SOURCE_REGISTRY_AND_LICENSING.md`](SOURCE_REGISTRY_AND_LICENSING.md) policy.
It is not legal advice, and an item-specific license or written permission must
be rechecked before a media asset is published.

## Decision

Do **not** add third-party runway photographs before Demo Day. Continue using
the existing YouTube player for selected runway videos, without downloading or
rehosting video or thumbnails. A later implementation may display still images
only when Trainspotting has one of these documented bases:

1. Trainspotting or the portfolio owner created the image and retains the
   necessary rights.
2. The rights holder granted written permission covering web display, portfolio
   use, storage, and any planned transformation.
3. The individual asset is public domain or carries a compatible open license,
   and every license condition is recorded and rendered.
4. An approved platform embed provides the media under that platform's current
   terms, without copying the underlying asset.

A citation URL, public webpage, user-supplied image URL, or editorial source is
not evidence of reuse permission. Hotlinking is not a licensing workaround.

## Pre-demo boundary

| Path | Decision | Reason |
| --- | --- | --- |
| Existing YouTube iframe | Keep, subject to player rules | Platform-supported embed; no local audiovisual copy |
| Original Trainspotting artwork | Allowed after ordinary review | Rights and accessibility can be controlled |
| Item-level public-domain or compatible Creative Commons file | Eligible later | Requires asset-by-asset rights and attribution review |
| Written rights-holder license | Eligible later | Permission must cover the intended storage and display |
| Editorial or runway-site photograph | Do not copy | A factual citation does not license the photograph |
| Remote image URL supplied by a user | Do not render automatically | Rights, safety, availability, and tracking are unverified |
| Hotlinked third-party image | Do not use by default | Still subject to license terms and creates reliability/privacy risk |
| Scraped image or extracted video frame | Prohibited | Outside approved automation and transformation boundaries |

The current collection pages add an `ARCHIVE FEED` pseudo-element over the
YouTube iframe. YouTube's current embedded-player policy prohibits overlays in
front of any part of its player. Remove or reposition that decoration in a
separate corrective card before the release candidate; do not hide YouTube
branding, controls, or advertising.

## Required media record

Before implementation, design a record that can retain at least:

- the canonical designer or collection relationship;
- media purpose and placement;
- original source page and direct asset identifier;
- creator or photographer credit exactly as required;
- rights holder, license identifier, license URL, and license-version text;
- permission evidence and the date it was reviewed;
- whether commercial display and transformations are permitted;
- original filename, MIME type, byte size, dimensions, and content checksum;
- alt text written for the image's actual context;
- ingestion actor, reviewer, approval state, and timestamps;
- storage key, public delivery URL, and derived-asset relationships;
- takedown state, reason, request date, completion date, and audit reference.

The source page and rights evidence must remain available even after an image is
withdrawn. A deleted public asset must not erase the moderation or takedown
record.

## Accessibility rule

Every informative image needs concise contextual alt text describing the useful
visual information rather than repeating the collection title. Decorative
images use an empty `alt` value. Linked or interactive images describe the
destination or action. Images containing essential text reproduce that text in
the alternative. Complex visual analysis belongs in adjacent prose, not an
overloaded alt attribute.

Approval must include a human alt-text review. Filename-derived or generic text
such as "fashion image" is not acceptable.

## Storage and delivery decision

If approved still-image hosting is implemented later:

- create a dedicated private-origin media bucket; never place public media in
  the `trainspotting-backups` bucket;
- issue a separate least-privilege credential and never expose it to the React
  client;
- use Cloudflare R2 **Standard** storage initially because only Standard
  receives the published free-tier allowance and it has no minimum retention;
- publish through an application-controlled or custom-domain path with explicit
  caching, content types, and security headers;
- keep the `r2.dev` development URL disabled for production delivery;
- permit only reviewed MIME types and enforce byte and dimension limits;
- generate derivatives only when the license permits modification;
- purge cached copies during takedown or replacement because deletion from R2
  does not immediately remove an already cached object;
- back up media metadata and permission evidence separately from object bytes;
  retain originals only while the license and retention policy permit it.

R2 cost is not the near-term blocker. Cloudflare currently includes 10 GB-month
of Standard storage, one million Class A operations, ten million Class B
operations, and direct R2 egress at no charge each month. A curated demo-scale
library would likely fit inside those allowances, but usage must still be
metered and budget alerts reviewed. Rights, takedown correctness, and editorial
work are the dominant costs.

R2 Data Catalog and R2 SQL are not needed for image delivery. They solve
analytical-table use cases rather than the application's object-serving need.

## Moderation and takedown workflow

1. A contributor proposes metadata and a source; no remote binary is fetched.
2. A reviewer verifies identity, item-level rights, attribution, permitted
   transformations, and alt text.
3. An administrator approves publication and initiates controlled ingestion.
4. The worker validates type and size, strips unnecessary metadata when
   permitted, computes a checksum, stores the original and approved derivatives,
   and records the immutable provenance.
5. Replacement creates a new version rather than silently overwriting evidence.
6. A takedown immediately disables application references, deletes public and
   derived objects as required, purges caches, and preserves an audit record.

The site must expose a contact path for rights or accessibility concerns before
public image submissions are enabled. Emergency disablement must work without a
database migration or frontend redeploy.

## Reliability and privacy

- Do not make page rendering depend on an untrusted third-party image host.
- Use width and height or an aspect ratio to prevent layout shift.
- Serve responsive sizes and lazy-load below-the-fold images.
- Retain the existing text-first page when media is absent, withdrawn, or
  temporarily unavailable.
- Do not proxy arbitrary URLs; that creates server-side request-forgery and
  content-safety risk.
- Treat embedded providers as third parties that may receive browser request
  data. Do not enable autoplay merely for visual impact.

## Go/no-go result

**No-go for third-party still-image implementation before Demo Day.** The
current text-first interface and selected YouTube embeds remain the release
path. After Demo Day, implement one vertical pilot using a small set of original
or individually verified open-license assets. Do not build general uploads,
scraping, remote URL rendering, or automated transformations until that pilot
passes rights, moderation, accessibility, deletion, cache-purge, and recovery
tests.

## Primary references

- [U.S. Copyright Office: How to Obtain Permission](https://copyright.gov/circs/circ16a.pdf)
- [U.S. Copyright Office: Copyright Registration of Photographs](https://www.copyright.gov/circs/circ42.pdf)
- [Wikimedia Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en)
- [W3C WAI Images Tutorial](https://www.w3.org/WAI/tutorials/images/)
- [YouTube embedded-player parameters](https://developers.google.com/youtube/player_parameters)
- [YouTube embedded-player minimum functionality](https://developers.google.com/youtube/terms/required-minimum-functionality)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Cloudflare R2 public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)
- [Cloudflare R2 consistency and caching](https://developers.cloudflare.com/r2/reference/consistency/)
- [Cloudflare R2 CORS](https://developers.cloudflare.com/r2/buckets/cors/)

