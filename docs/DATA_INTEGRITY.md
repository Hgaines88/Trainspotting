# Canonical archive integrity

`data/archive.json` is Trainspotting's portable public-content authority. Data
quality work begins with a read-only audit and a reviewed correction plan; it
does not begin by editing the deployed MySQL database.

## Audit command

```bash
python -m scripts.audit_archive
```

The command emits deterministic JSON with record counts, controlled
vocabularies, optional-field completeness, and findings. It never writes to the
archive or database. Use `--fail-on-errors` in automation when structural
failures should produce a nonzero exit status.

Findings have three severities:

- `error`: mechanically invalid structure, such as broken references,
  duplicate identities, unsupported statuses, unsafe evidence URLs, or invalid
  credit ordering.
- `warning`: a demonstrable completeness gap, currently a missing collection
  evidence URL.
- `review`: a potentially intentional editorial choice that must not be
  normalized automatically, such as a year inside an event-style season or a
  primary owner that differs from the first ordered collaboration credit.

Missing collection titles, piece counts, videos, designer birth years, and
websites remain optional. The audit reports useful completeness counts without
mislabeling absence as false data.

## Correction policy

1. Verify factual changes against an authoritative or reputable public source.
2. Record the exact source URL with the corrected collection.
3. Preserve historically meaningful house names, markets, capsules, and special
   events until a reviewed taxonomy can represent them without information
   loss.
4. Correct `data/archive.json`, then validate a clean import. Never patch only a
   running database.
5. Review the before/after report before committing a batch of corrections.
6. Keep correction batches small enough to attribute and reverse.

The audit is intentionally diagnostic. Automated rewriting is outside its
scope because a syntactically consistent archive can still be historically
wrong.
