"""Safely reconcile canonical archive JSON into MySQL without touching operations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sqlalchemy.engine import make_url

from app.database import bump_archive_version, connect, select_for_update
from app.database_url import normalize_database_url
from scripts.archive_data import DEFAULT_ARCHIVE, stable_key


DESIGNER_FIELDS = ("nationality", "birth_year", "website", "biography")
COLLECTION_FIELDS = ("label", "name", "season", "release_year", "status", "piece_count", "description")


def load_archive(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format_version") != 1:
        raise ValueError("Unsupported archive format_version")
    designers = payload.get("designers")
    collections = payload.get("collections")
    if not isinstance(designers, list) or not isinstance(collections, list):
        raise ValueError("Archive must contain designer and collection lists")

    keys: set[str] = set()
    names: set[str] = set()
    for designer in designers:
        key, name = designer.get("key"), designer.get("full_name")
        if not key or not name or key != stable_key(name):
            raise ValueError(f"Invalid designer identity: {key!r} / {name!r}")
        if key in keys or name in names:
            raise ValueError(f"Duplicate designer identity: {key!r} / {name!r}")
        keys.add(key)
        names.add(name)

    collection_keys: set[str] = set()
    identities: set[tuple] = set()
    for collection in collections:
        key = collection.get("key")
        designer_key = collection.get("designer_key")
        if not key or key in collection_keys or designer_key not in keys:
            raise ValueError(f"Invalid collection identity: {key!r}")
        identity = (designer_key, collection.get("label"), collection.get("season"), collection.get("release_year"))
        if None in identity or identity in identities:
            raise ValueError(f"Duplicate or incomplete collection identity: {key!r}")
        collection_keys.add(key)
        identities.add(identity)
        positions: set[int] = set()
        credited: set[str] = set()
        for credit in canonical_credits(collection):
            if credit.get("designer_key") not in keys:
                raise ValueError(f"Unknown credited designer in {key!r}")
            if credit.get("position") in positions or credit.get("designer_key") in credited:
                raise ValueError(f"Duplicate collection credit in {key!r}")
            positions.add(credit["position"])
            credited.add(credit["designer_key"])
    return payload


def canonical_credits(collection: dict) -> list[dict]:
    return collection.get("credits") or [{
        "designer_key": collection["designer_key"], "role": "lead",
        "position": 1, "attribution_note": None,
    }]


def _rows(connection, sql: str, parameters=()) -> list[dict]:
    return [dict(row) for row in connection.execute(sql, parameters).fetchall()]


def build_plan(connection, payload: dict) -> dict:
    db_designers = _rows(
        connection,
        "SELECT id, full_name, nationality, birth_year, website, biography "
        "FROM designers ORDER BY id",
    )
    by_name = {row["full_name"]: row for row in db_designers}
    designer_ids: dict[str, int | None] = {}
    designer_inserts, designer_updates = [], []
    for designer in payload["designers"]:
        current = by_name.get(designer["full_name"])
        designer_ids[designer["key"]] = current["id"] if current else None
        if current is None:
            designer_inserts.append(designer)
        else:
            changes = {field: designer.get(field) for field in DESIGNER_FIELDS if current[field] != designer.get(field)}
            if changes:
                designer_updates.append({"id": current["id"], "key": designer["key"], "changes": changes})

    db_collections = _rows(
        connection,
        "SELECT id, designer_id, label, name, season, release_year, status, "
        "piece_count, description FROM collections ORDER BY id",
    )
    exact = {(r["designer_id"], r["label"], r["season"], r["release_year"]): r for r in db_collections}
    fallback: dict[tuple, list[dict]] = {}
    for row in db_collections:
        fallback.setdefault((row["designer_id"], row["label"], row["release_year"]), []).append(row)
    reserved_exact_ids: set[int] = set()
    fallback_demands: dict[tuple, int] = {}
    for item in payload["collections"]:
        did = designer_ids[item["designer_key"]]
        if did is not None:
            identity = (did, item["label"], item["season"], item["release_year"])
            current = exact.get(identity)
            if current is not None:
                reserved_exact_ids.add(current["id"])
            else:
                key = (did, item["label"], item["release_year"])
                fallback_demands[key] = fallback_demands.get(key, 0) + 1

    inserts, updates, matched_ids, conflicts = [], [], set(), []
    for item in payload["collections"]:
        did = designer_ids[item["designer_key"]]
        if did is None:
            inserts.append(item)
            continue
        identity = (did, item["label"], item["season"], item["release_year"])
        current = exact.get(identity)
        if current is None:
            fallback_key = (did, item["label"], item["release_year"])
            candidates = [
                row
                for row in fallback.get(fallback_key, [])
                if row["id"] not in reserved_exact_ids
                and row["id"] not in matched_ids
            ]
            if len(candidates) == 1 and fallback_demands[fallback_key] == 1:
                current = candidates[0]
            elif candidates:
                conflicts.append({"key": item["key"], "candidate_ids": [row["id"] for row in candidates]})
                continue
            else:
                inserts.append(item)
                continue
        matched_ids.add(current["id"])
        changes = {field: item.get(field) for field in COLLECTION_FIELDS if current[field] != item.get(field)}
        desired_media = {k: item.get(v) for k, v in (("source", "source_url"), ("youtube", "youtube_video_id")) if item.get(v) is not None}
        media = {r["media_type"]: r["media_value"] for r in _rows(connection, "SELECT media_type, media_value FROM collection_media WHERE collection_id = ?", (current["id"],))}
        credits = _rows(connection, "SELECT designers.full_name, collection_credits.credit_role AS role, collection_credits.credit_order AS position, collection_credits.attribution_note FROM collection_credits JOIN designers ON designers.id = collection_credits.designer_id WHERE collection_id = ? ORDER BY credit_order", (current["id"],))
        desired_credits = [{"full_name": next(d["full_name"] for d in payload["designers"] if d["key"] == c["designer_key"]), "role": c["role"], "position": c["position"], "attribution_note": c.get("attribution_note")} for c in canonical_credits(item)]
        if changes or media != desired_media or credits != desired_credits:
            updates.append({"id": current["id"], "key": item["key"], "record": item, "changes": changes, "media_changed": media != desired_media, "credits_changed": credits != desired_credits})

    canonical_names = {d["full_name"] for d in payload["designers"]}
    return {
        "designer_inserts": designer_inserts, "designer_updates": designer_updates,
        "collection_inserts": inserts, "collection_updates": updates,
        "runtime_only_designers": [{"id": r["id"], "full_name": r["full_name"]} for r in db_designers if r["full_name"] not in canonical_names],
        "runtime_only_collections": [{"id": r["id"], "label": r["label"], "season": r["season"], "release_year": r["release_year"]} for r in db_collections if r["id"] not in matched_ids],
        "conflicts": conflicts,
    }


def has_changes(plan: dict) -> bool:
    return any(plan[name] for name in ("designer_inserts", "designer_updates", "collection_inserts", "collection_updates"))


def apply_plan(connection, payload: dict, plan: dict) -> dict:
    if plan["conflicts"]:
        raise RuntimeError("Canonical synchronization has ambiguous collection identities")
    # SQLAlchemy begins a transaction even for the preceding planning SELECTs.
    # End that read-only transaction before opening the atomic apply transaction.
    connection.rollback()
    try:
        connection.execute("BEGIN IMMEDIATE")
        select_for_update(connection, "SELECT id FROM designers")
        select_for_update(connection, "SELECT id FROM collections")
        locked_plan = build_plan(connection, payload)
        if locked_plan != plan:
            raise RuntimeError(
                "Database changed after the dry run; generate and review a new plan"
            )
        ids = {r["full_name"]: r["id"] for r in _rows(connection, "SELECT id, full_name FROM designers")}
        by_key = {d["key"]: d for d in payload["designers"]}
        for designer in plan["designer_inserts"]:
            result = connection.execute("INSERT INTO designers (full_name, nationality, birth_year, website, biography) VALUES (?, ?, ?, ?, ?)", (designer["full_name"], *(designer.get(f) for f in DESIGNER_FIELDS)))
            ids[designer["full_name"]] = result.lastrowid
        for update in plan["designer_updates"]:
            d = by_key[update["key"]]
            connection.execute("UPDATE designers SET nationality = ?, birth_year = ?, website = ?, biography = ? WHERE id = ?", (*(d.get(f) for f in DESIGNER_FIELDS), update["id"]))
        designer_ids = {key: ids[d["full_name"]] for key, d in by_key.items()}

        collection_work = [(None, item) for item in plan["collection_inserts"]] + [(item["id"], item["record"]) for item in plan["collection_updates"]]
        for collection_id, item in collection_work:
            values = (designer_ids[item["designer_key"]], *(item.get(f) for f in COLLECTION_FIELDS))
            if collection_id is None:
                result = connection.execute("INSERT INTO collections (designer_id, label, name, season, release_year, status, piece_count, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values)
                collection_id = result.lastrowid
            else:
                connection.execute("UPDATE collections SET designer_id = ?, label = ?, name = ?, season = ?, release_year = ?, status = ?, piece_count = ?, description = ? WHERE id = ?", (*values, collection_id))
            connection.execute("DELETE FROM collection_media WHERE collection_id = ?", (collection_id,))
            media = [(collection_id, kind, item.get(field)) for kind, field in (("source", "source_url"), ("youtube", "youtube_video_id")) if item.get(field) is not None]
            connection.executemany("INSERT INTO collection_media (collection_id, media_type, media_value) VALUES (?, ?, ?)", media)
            connection.execute("DELETE FROM collection_credits WHERE collection_id = ?", (collection_id,))
            connection.executemany("INSERT INTO collection_credits (collection_id, designer_id, credit_role, credit_order, attribution_note) VALUES (?, ?, ?, ?, ?)", [(collection_id, designer_ids[c["designer_key"]], c["role"], c["position"], c.get("attribution_note")) for c in canonical_credits(item)])
        if has_changes(plan):
            bump_archive_version(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return plan


def summary(plan: dict) -> dict:
    return {name: len(value) for name, value in plan.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--apply", action="store_true", help="Apply the displayed plan transactionally; default is dry-run.")
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL")
    if not url or make_url(normalize_database_url(url)).get_backend_name() != "mysql":
        raise SystemExit("DATABASE_URL must identify a MySQL database")
    payload = load_archive(args.archive)
    connection = connect()
    try:
        plan = build_plan(connection, payload)
        print(json.dumps({
            "mode": "apply" if args.apply else "dry-run",
            "counts": summary(plan),
            "plan": plan,
        }, indent=2))
        if plan["conflicts"]:
            print(json.dumps({"conflicts": plan["conflicts"]}, indent=2))
            raise SystemExit("Resolve ambiguous identities before synchronization")
        if args.apply:
            apply_plan(connection, payload, plan)
            print("Canonical MySQL synchronization committed.")
        else:
            print("Dry run only; no database changes were made.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
