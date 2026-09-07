"""Export and restore the curated archive as deterministic, reviewable JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import unicodedata
from pathlib import Path

from app.naming import normalized_search_name
from app.url_safety import normalize_public_http_url


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "archive.db"
DEFAULT_ARCHIVE = PROJECT_ROOT / "data" / "archive.json"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"


def stable_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return "-".join(
        part for part in "".join(
            character.lower() if character.isalnum() else " "
            for character in ascii_value
        ).split()
    )


def database_archive(database_path: Path) -> dict:
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row

    try:
        designer_rows = connection.execute(
            """
            SELECT full_name, nationality, birth_year, website, biography
            FROM designers
            ORDER BY full_name COLLATE NOCASE
            """
        ).fetchall()
        alias_rows = connection.execute(
            """SELECT designers.full_name, designer_aliases.alias,
                      designer_aliases.alias_type, designer_aliases.source_url
               FROM designer_aliases
               JOIN designers ON designers.id = designer_aliases.designer_id
               ORDER BY designers.full_name COLLATE NOCASE,
                        designer_aliases.alias COLLATE NOCASE"""
        ).fetchall()
        collection_rows = connection.execute(
            """
            SELECT
                collections.id AS collection_id,
                designers.full_name AS designer_name,
                collections.label,
                collections.name,
                collections.season,
                collections.release_year,
                collections.status,
                collections.piece_count,
                collections.description,
                MAX(CASE WHEN collection_media.media_type = 'source'
                    THEN collection_media.media_value END) AS source_url,
                MAX(CASE WHEN collection_media.media_type = 'youtube'
                    THEN collection_media.media_value END) AS youtube_video_id,
                MAX(CASE WHEN collection_media.media_type = 'vimeo'
                    THEN collection_media.media_value END) AS vimeo_video_id
            FROM collections
            JOIN designers ON designers.id = collections.designer_id
            LEFT JOIN collection_media
                ON collection_media.collection_id = collections.id
            GROUP BY collections.id
            ORDER BY
                designers.full_name COLLATE NOCASE,
                collections.release_year,
                collections.season COLLATE NOCASE,
                collections.label COLLATE NOCASE
            """
        ).fetchall()
        credit_rows = connection.execute(
            """
            SELECT
                collection_credits.collection_id,
                designers.full_name AS designer_name,
                collection_credits.credit_role AS role,
                collection_credits.credit_order AS position,
                collection_credits.attribution_note
            FROM collection_credits
            JOIN designers ON designers.id = collection_credits.designer_id
            ORDER BY collection_credits.collection_id, collection_credits.credit_order
            """
        ).fetchall()
    finally:
        connection.close()

    designers = []
    designer_keys = {}
    aliases_by_designer = {}
    for row in alias_rows:
        alias = dict(row)
        aliases_by_designer.setdefault(alias.pop("full_name"), []).append(alias)
    for row in designer_rows:
        record = dict(row)
        key = stable_key(record["full_name"])
        if key in designer_keys.values():
            raise ValueError(f"Duplicate stable designer key: {key}")
        designer_keys[record["full_name"]] = key
        designer = {"key": key, **record}
        if aliases_by_designer.get(record["full_name"]):
            designer["aliases"] = aliases_by_designer[record["full_name"]]
        designers.append(designer)

    collections = []
    seen_collection_keys = set()
    credits_by_collection = {}
    for row in credit_rows:
        credit = dict(row)
        collection_id = credit.pop("collection_id")
        credit["designer_key"] = designer_keys[credit.pop("designer_name")]
        credits_by_collection.setdefault(collection_id, []).append(credit)
    for row in collection_rows:
        record = dict(row)
        if record.get("vimeo_video_id") is None:
            record.pop("vimeo_video_id", None)
        collection_id = record.pop("collection_id")
        designer_key = designer_keys[record.pop("designer_name")]
        key = stable_key(
            f"{designer_key} {record['label']} {record['season']} "
            f"{record['release_year']}"
        )
        if key in seen_collection_keys:
            raise ValueError(f"Duplicate stable collection key: {key}")
        seen_collection_keys.add(key)
        collection = {"key": key, "designer_key": designer_key, **record}
        credits = credits_by_collection.get(collection_id, [])
        default_credit = [
            {
                "designer_key": designer_key,
                "role": "lead",
                "position": 1,
                "attribution_note": None,
            }
        ]
        if credits != default_credit:
            collection["credits"] = credits
        collections.append(collection)

    return {
        "format_version": 1,
        "designers": designers,
        "collections": collections,
    }


def archive_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def archive_digest(payload: dict) -> str:
    return hashlib.sha256(archive_text(payload).encode("utf-8")).hexdigest()


def write_text_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def export_archive(database_path: Path, archive_path: Path) -> dict:
    payload = database_archive(database_path)
    write_text_atomically(archive_path, archive_text(payload))
    return payload


def archive_has_drift(database_path: Path, archive_path: Path) -> bool:
    database_payload = database_archive(database_path)
    file_payload = json.loads(archive_path.read_text(encoding="utf-8"))
    return database_payload != file_payload


def import_archive(
    database_path: Path,
    archive_path: Path,
    *,
    replace: bool = False,
) -> dict[str, int]:
    payload = json.loads(archive_path.read_text(encoding="utf-8"))
    if payload.get("format_version") != 1:
        raise ValueError("Unsupported archive format_version")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='designers'"
        ).fetchone():
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        connection.execute("BEGIN IMMEDIATE")
        if replace:
            connection.execute("DELETE FROM designers")

        designer_ids = {}
        for designer in payload["designers"]:
            connection.execute(
                """
                INSERT INTO designers (
                    full_name, nationality, birth_year, website, biography
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(full_name) DO UPDATE SET
                    nationality = excluded.nationality,
                    birth_year = excluded.birth_year,
                    website = excluded.website,
                    biography = excluded.biography
                """,
                tuple(designer.get(field) for field in (
                    "full_name", "nationality", "birth_year", "website", "biography"
                )),
            )
            designer_ids[designer["key"]] = connection.execute(
                "SELECT id FROM designers WHERE full_name = ?",
                (designer["full_name"],),
            ).fetchone()[0]
            connection.execute(
                "DELETE FROM designer_aliases WHERE designer_id = ?",
                (designer_ids[designer["key"]],),
            )
            connection.executemany(
                """INSERT INTO designer_aliases (
                       designer_id, alias, normalized_alias, alias_type, source_url
                   ) VALUES (?, ?, ?, ?, ?)""",
                [
                    (
                        designer_ids[designer["key"]],
                        alias["alias"],
                        normalized_search_name(alias["alias"]),
                        alias["alias_type"],
                        normalize_public_http_url(
                            alias["source_url"], "Alias source URL"
                        ),
                    )
                    for alias in designer.get("aliases", [])
                ],
            )

        for collection in payload["collections"]:
            designer_id = designer_ids[collection["designer_key"]]
            values = (
                designer_id,
                collection["label"],
                collection.get("name"),
                collection["season"],
                collection["release_year"],
                collection["status"],
                collection.get("piece_count"),
                collection.get("description"),
            )
            connection.execute(
                """
                INSERT INTO collections (
                    designer_id, label, name, season, release_year,
                    status, piece_count, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(designer_id, label, season, release_year) DO UPDATE SET
                    name = excluded.name,
                    status = excluded.status,
                    piece_count = excluded.piece_count,
                    description = excluded.description
                """,
                values,
            )
            collection_id = connection.execute(
                """
                SELECT id FROM collections
                WHERE designer_id = ? AND label = ? AND season = ?
                  AND release_year = ?
                """,
                (designer_id, collection["label"], collection["season"],
                 collection["release_year"]),
            ).fetchone()[0]
            connection.execute(
                "DELETE FROM collection_media WHERE collection_id = ?",
                (collection_id,),
            )
            media = [
                (collection_id, "source", collection.get("source_url")),
                (collection_id, "youtube", collection.get("youtube_video_id")),
                (collection_id, "vimeo", collection.get("vimeo_video_id")),
            ]
            connection.executemany(
                """
                INSERT INTO collection_media (collection_id, media_type, media_value)
                VALUES (?, ?, ?)
                """,
                [item for item in media if item[2] is not None],
            )
            connection.execute(
                "DELETE FROM collection_credits WHERE collection_id = ?",
                (collection_id,),
            )
            credits = collection.get("credits") or [
                {
                    "designer_key": collection["designer_key"],
                    "role": "lead",
                    "position": 1,
                    "attribution_note": None,
                }
            ]
            connection.executemany(
                """
                INSERT INTO collection_credits (
                    collection_id, designer_id, credit_role, credit_order,
                    attribution_note
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        collection_id,
                        designer_ids[credit["designer_key"]],
                        credit["role"],
                        credit["position"],
                        credit.get("attribution_note"),
                    )
                    for credit in credits
                ],
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return {
        "designers": len(payload["designers"]),
        "collections": len(payload["collections"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "export", "import"))
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="On import, remove existing archive records first.",
    )
    args = parser.parse_args()

    if args.command == "check":
        if archive_has_drift(args.database, args.archive):
            print(
                "Canonical archive drift detected: SQLite and JSON differ. "
                "Review approved changes before exporting."
            )
            raise SystemExit(1)
        print("Canonical archive is synchronized with SQLite.")
    elif args.command == "export":
        payload = export_archive(args.database, args.archive)
        print(
            f"Exported {len(payload['designers'])} designers and "
            f"{len(payload['collections'])} collections to {args.archive}"
        )
    else:
        counts = import_archive(args.database, args.archive, replace=args.replace)
        print(
            f"Imported {counts['designers']} designers and "
            f"{counts['collections']} collections into {args.database}"
        )


if __name__ == "__main__":
    main()
