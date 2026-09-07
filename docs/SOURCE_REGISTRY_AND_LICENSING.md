# Source registry and licensing policy

Trainspotting is a citation-based, human-curated archive. A public URL can
support a factual claim without granting Trainspotting permission to scrape,
copy, redistribute, transform, or permanently store the page's text or media.
The machine-readable [`source-registry.json`](source-registry.json) records the
current technical and governance position for each source category.

This document is an engineering and editorial policy, not legal advice. Terms,
licenses, robots directives, APIs, and item-level rights statements can change;
the archive administrator must review the current primary policy before
approving any new automated access or content reuse.

## Current operating boundary

- Researchers select sources manually and write original archive descriptions.
- Canonical records retain citation URLs, source titles where available, and
  reviewed community evidence.
- Curated CSV ingestion accepts supplied URLs but does not fetch them.
- Trainspotting stores YouTube identifiers for platform-supported playback; it
  does not download or rehost video.
- Trainspotting does not currently scrape, crawl, mirror, or call a third-party
  content API.
- Images and long excerpts remain excluded until MEDIA-01 establishes an
  item-specific rights, attribution, deletion, accessibility, and recovery
  strategy.

## Reliability and attribution

Use the narrowest suitable claim and prefer this evidence order:

1. The designer, label, collaborator, or other relevant rights holder for its
   own credits and announcements.
2. A museum or cultural institution for cataloged objects and scholarship.
3. A reputable editorial publication for reporting and runway documentation.
4. Independent specialist research when its authorship and evidence are clear.
5. General references for discovery or identity disambiguation, followed by
   their stronger underlying citations when the claim matters.

No source category is automatically correct. Marketing pages are not
independent, publications can correct reporting, museum attributions can
change, and collaborative references are editable. Disputed dates, authorship,
or identity claims require corroboration and an explanatory note.

## Automation approval gate

Automation is denied by default. Before changing a registry entry to an
approved automated state, a pull request must document all of the following:

- the exact API, feed, dataset, or pages in scope and the business purpose;
- the current first-party terms, license, robots directives, and attribution
  requirements, with review date and durable links;
- whether storage, transformation, redistribution, commercial portfolio use,
  and deletion are permitted;
- authentication method, least-privilege secret ownership, rate and quota
  limits, retry/backoff behavior, and expected cost;
- retained raw fields, provenance, checksum or version behavior, and retention
  period;
- entity matching, duplicate handling, reconciliation, moderator review, and
  rollback behavior;
- takedown/contact procedure, monitoring owner, and a kill switch;
- tests proving reruns cannot overwrite canonical or operational history.

Approval changes only the named source and access method. It never grants
blanket permission to automate another host, endpoint, asset type, or use.

## Primary policy references for future review

These links are starting points and must be rechecked at the time of a proposed
integration:

- [Condé Nast user agreement](https://www.condenast.com/user-agreement)
- [YouTube Terms of Service](https://www.youtube.com/static?template=terms)
- [YouTube API Services Terms](https://developers.google.com/youtube/terms/api-services-terms-of-service)
- [Wikimedia Foundation Terms of Use](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)
- [Creative Commons license overview](https://creativecommons.org/share-your-work/cclicenses/)
- [The Met Terms and Conditions](https://www.metmuseum.org/policies/terms-and-conditions)

## Maintenance

Run the registry regression whenever canonical sources change:

```bash
python -m scripts.check_source_registry
```

The check fails if a canonical evidence host is unclassified, a host appears in
multiple categories, required governance fields are absent, or an unsupported
automation status is introduced. New source domains therefore require an
explicit registry decision in the same reviewed change.
