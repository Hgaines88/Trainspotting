# Demo rehearsal and fallback sheet

Use this sheet for the September 24 demonstration. The detailed narrative lives
in [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md); this page is the operational checklist
that should remain open beside the presentation.

## Prepared endpoints

- Railway staging: <https://web-staging-9862.up.railway.app>
- Local Docker web: <http://localhost:5173>
- Local Docker readiness: <http://localhost:5173/api/ready>
- Tracked ingestion sample: `examples/collection_ingestion.csv`

Bookmark the staging and local web origins, not individual numeric collection
IDs. Reach the featured record by opening **Collections**, searching `Prada`,
selecting `Spring/Summer`, and opening **Spring/Summer 2024**.

## Credentials checklist

Keep all values in the password manager or ignored local environment files.
Never add emails, passwords, Clerk tokens, or user IDs to this document,
screenshots, issues, or shell history.

- [ ] Member account can sign in and open **Suggest enrichment**.
- [ ] Moderator account can inspect evidence and request changes or reject.
- [ ] Administrator account can approve, publish, and roll back.
- [ ] A fresh non-administrator Clerk session token is available only if the
      authenticated API smoke check will be demonstrated.
- [ ] `TRAINSPOTTING_DEMO_USER_ID` is set in the prepared terminal for the
      ingestion dry run; do not display its value.

## Five-minute primary rehearsal

Use the timed story in `DEMO_RUNBOOK.md`:

1. **0:00–0:45 — Discovery:** homepage to the filtered Prada collection.
2. **0:45–1:30 — Relational model:** Miuccia Prada and Raf Simons as ordered
   credits through a many-to-many junction table.
3. **1:30–2:10 — Trust:** open the public Evidence section and explain the
   private moderation boundary.
4. **2:10–3:20 — Recommendations:** show visible editorial reasons, then use
   Mugler's Fall/Winter Couture 1995 journey if time permits.
5. **3:20–4:20 — Pipeline:** run the prepared CSV dry run and explain valid,
   invalid, and duplicate reconciliation without canonical writes.
6. **4:20–5:00 — Governance:** summarize member proposal, moderator review,
   administrator publication, append-only audit, and rollback.

Do not perform an irreversible live edit. If a write demonstration is
requested, use a uniquely named disposable submission and leave it rejected or
rolled back before ending.

## Ninety-second fallback

If Railway or venue networking fails, switch to <http://localhost:5173> without
changing the story:

1. Search `Prada` and open **Spring/Summer 2024**.
2. Show its two ordered credits and Evidence section.
3. Open one related collection and read its editorial reason.
4. Show the saved Prada screenshot and tracked ingestion CSV if the terminal or
   authentication path is unavailable.

If the Prada recommendation set is unexpectedly sparse, use **Loewe — A New
Aesthetic, Spring/Summer 2022**. If all live services fail, use the release
screenshots below and explain the same data flow.

## Release evidence

- [`demo-release-homepage.png`](demo-release-homepage.png) — desktop homepage
- [`demo-release-prada.png`](demo-release-prada.png) — desktop filtered Prada
  collection result with ordered credits
- [`demo-release-mobile.png`](demo-release-mobile.png) — 390px collection
  explorer, filters, results, and pagination
- [`recommendation-evaluation.json`](recommendation-evaluation.json) —
  deterministic primary and fallback recommendation expectations

Release candidate `v0.1.5` points to commit
`b1cd054d5eab2a372fc3745ff78473c4b6f33227`. Its tag-triggered Railway deploy,
MySQL migration, readiness checks, and anonymous smoke checks passed. Both the
staging and local Docker APIs reported MySQL revision `0006` during the release
rehearsal. Restarting only the local API and web containers preserved archive
version `70` and all `60` designer profiles in the continuously running MySQL
service.

## Day-of preflight

Run this at least 30 minutes before presenting:

```bash
docker compose up -d
docker compose ps
curl --fail --silent http://localhost:5173/api/ready
```

The readiness response must report `"status":"ready"`, `"database":"mysql"`,
and `"revision":"0006"`. Then verify:

- [ ] staging and local homepage load;
- [ ] Prada credits, evidence, and recommendations render;
- [ ] the ingestion dry run reports one valid, one invalid, and one duplicate;
- [ ] no temporary submission remains non-terminal;
- [ ] browser zoom is 100%, notifications are muted, and unrelated tabs are
      closed;
- [ ] the local Docker fallback remains running throughout the presentation.

After the final rehearsal, Railway services may be suspended to conserve
credit. Resume them and repeat this preflight before the next hosted rehearsal
or Demo Day.
