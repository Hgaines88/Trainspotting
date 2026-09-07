"""Populate the isolated DEMO-X14 database with a coherent workflow story."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sqlalchemy.engine import make_url

from app.database import connect
from app.database_url import normalize_database_url
from app.main import sync_collection_credits
from app.ingestion import ingest_collection_csv
from app.naming import normalized_search_name
from app.schemas import CollectionCreate
from app.submission_schemas import (
    ReviewDecision,
    RollbackRequest,
    submission_draft_adapter,
    submission_for_review_adapter,
)
from app.submissions import (
    create_submission_record,
    decide_submission,
    rollback_submission,
)


GUARD_VALUE = "DEMO-X14-LOCAL-ONLY"
MARKER = "[DEMO-X14]"
ACTORS = (
    ("demo_x14_member", "member@demo.invalid", "Maya Chen — Demo Member", "member"),
    ("demo_x14_moderator", "moderator@demo.invalid", "Jordan Ellis — Demo Moderator", "moderator"),
)
LVMH_SOURCE = {
    "url": "https://www.lvmh.com/en/news-lvmh/louis-vuitton-and-pharrell-williams-tap-tyler-the-creator-for-spring-2024-mens-capsule-collection/",
    "title": "Louis Vuitton and Pharrell Williams tap Tyler, the Creator",
    "notes": "Primary corporate announcement for the Spring 2024 capsule.",
}
VOGUE_SOURCE = {
    "url": "https://www.vogue.com/article/louis-vuitton-pharrell-williams-tyler-the-creator-video-debut",
    "title": "Tyler, The Creator premieres his Louis Vuitton capsule",
    "notes": "Editorial reporting on the release and creative vocabulary.",
}
GQ_SOURCE = {
    "url": "https://www.gq.com/story/louis-vuitton-tyler-the-creator-pharrell-capsule-collection",
    "title": "First look at Tyler's Louis Vuitton capsule",
    "notes": "Editorial reporting with statements from both collaborators.",
}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INGESTION_SAMPLE = PROJECT_ROOT / "examples" / "demo_x14_ingestion.csv"


def require_isolated_demo_database() -> str:
    if os.getenv("TRAINSPOTTING_DEMO_FIXTURES") != GUARD_VALUE:
        raise RuntimeError(
            f"Refusing demo fixtures: set TRAINSPOTTING_DEMO_FIXTURES={GUARD_VALUE} "
            "inside the disposable demo container."
        )
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        raise RuntimeError("DATABASE_URL is required")
    url = make_url(normalize_database_url(raw_url))
    if url.get_backend_name() != "mysql":
        raise RuntimeError("DEMO-X14 fixtures require the disposable MySQL environment")
    if url.host not in {"mysql", "localhost", "127.0.0.1"}:
        raise RuntimeError("Refusing a non-local MySQL host")
    if url.database != "trainspotting_demo":
        raise RuntimeError("Refusing a database not named trainspotting_demo")
    return url.database


def rows(connection, sql: str, parameters=()) -> list[dict]:
    return [dict(row) for row in connection.execute(sql, parameters).fetchall()]


def one(connection, sql: str, parameters=()) -> dict | None:
    row = connection.execute(sql, parameters).fetchone()
    return dict(row) if row else None


def actor(connection, clerk_user_id: str) -> dict:
    result = one(
        connection,
        "SELECT * FROM users WHERE clerk_user_id = ?",
        (clerk_user_id,),
    )
    if result is None:
        raise RuntimeError(f"Missing demo actor: {clerk_user_id}")
    return result


def create_submission(payload: dict, submitter: dict, status: str = "submitted") -> int:
    adapter = submission_draft_adapter if status == "draft" else submission_for_review_adapter
    validated = adapter.validate_python(payload)
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        submission_id = create_submission_record(
            connection, validated, submitter, status
        )
        connection.commit()
        return submission_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def decide(submission_id: int, reviewer: dict, decision: str, notes: str) -> None:
    decide_submission(
        submission_id,
        ReviewDecision(decision=decision, notes=notes),
        reviewer,
    )


def proposal(
    *, record_type: str, submission_type: str, proposed_data: dict,
    explanation: str, sources: list[dict], target_id: int | None = None,
    proposal_kind: str = "archive_record",
) -> dict:
    return {
        "record_type": record_type,
        "proposal_kind": proposal_kind,
        "submission_type": submission_type,
        "target_id": target_id,
        "proposed_data": proposed_data,
        "explanation": f"{MARKER} {explanation}",
        "sources": sources,
    }


def enrichment(collection_id: int, category: str, value: str, strength: str,
               evidence: str) -> dict:
    return proposal(
        record_type="collection",
        proposal_kind="enrichment",
        submission_type="correction",
        target_id=collection_id,
        proposed_data={
            "category": category,
            "canonical_value": value,
            "strength": strength,
            "evidence_note": evidence,
        },
        explanation=f"Suggest {category} descriptor '{value}' for the capsule.",
        sources=[LVMH_SOURCE, VOGUE_SOURCE],
    )


def existing_summary(connection, admin_clerk_user_id: str | None = None) -> dict | None:
    actors = rows(
        connection,
        "SELECT clerk_user_id FROM users WHERE clerk_user_id LIKE 'demo_x14_%'",
    )
    if not actors:
        return None
    if {item[0] for item in ACTORS} != {item["clerk_user_id"] for item in actors}:
        raise RuntimeError(
            "Partial DEMO-X14 state detected; reset the disposable Compose project."
        )
    if admin_clerk_user_id:
        operator = one(
            connection,
            "SELECT role FROM users WHERE clerk_user_id = ?",
            (admin_clerk_user_id,),
        )
        if operator is None or operator["role"] != "admin":
            raise RuntimeError(
                "DEMO-X14 is configured for another operator; reset the disposable "
                "Compose project before changing identities."
            )
    submissions = one(
        connection,
        "SELECT COUNT(*) AS count FROM submissions WHERE explanation LIKE ?",
        (f"{MARKER}%",),
    )["count"]
    tyler = one(connection, "SELECT id FROM designers WHERE full_name = 'Tyler Okonma'")
    capsule = one(
        connection,
        """SELECT collections.id FROM collections JOIN designers
           ON designers.id = collections.designer_id
           WHERE designers.full_name = 'Tyler Okonma'
             AND collections.label = 'Louis Vuitton'
             AND collections.season = 'Spring'
             AND collections.release_year = 2024""",
    )
    batch = one(
        connection,
        "SELECT id FROM ingestion_batches WHERE source_name = 'DEMO-X14 narrative ingestion'",
    )
    if not all((submissions >= 10, tyler, capsule, batch)):
        raise RuntimeError(
            "Incomplete DEMO-X14 state detected; reset the disposable Compose project."
        )
    return {
        "mode": "already-configured",
        "designer_id": tyler["id"],
        "collection_id": capsule["id"],
        "submission_count": submissions,
        "ingestion_batch_id": batch["id"],
    }


def setup(admin_clerk_user_id: str) -> dict:
    database_name = require_isolated_demo_database()
    admin_clerk_user_id = admin_clerk_user_id.strip()
    if not admin_clerk_user_id:
        raise RuntimeError("A Clerk user ID is required for the demo operator")
    connection = connect()
    try:
        current = existing_summary(connection, admin_clerk_user_id)
        if current:
            return {"database": database_name, **current}
        pharrell = one(
            connection,
            "SELECT id FROM designers WHERE full_name = 'Pharrell Williams'",
        )
        if pharrell is None:
            raise RuntimeError(
                "Canonical archive is not loaded; run sync_canonical_mysql --apply first."
            )
        connection.rollback()
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            """INSERT INTO users (clerk_user_id, email, display_name, role)
               VALUES (?, ?, ?, ?)""",
            ACTORS,
        )
        connection.execute(
            """INSERT INTO users (clerk_user_id, display_name, role)
               VALUES (?, 'Demo Operator', 'admin')""",
            (admin_clerk_user_id,),
        )
        connection.commit()
        member = actor(connection, "demo_x14_member")
        moderator = actor(connection, "demo_x14_moderator")
        admin = actor(connection, admin_clerk_user_id)
    finally:
        connection.close()

    designer_id = create_submission(
        proposal(
            record_type="designer",
            submission_type="addition",
            proposed_data={
                "full_name": "Tyler Okonma",
                "biography": (
                    "Designer, musician, and creative director Tyler Okonma, known "
                    "professionally as Tyler, The Creator, brought his Golf le Fleur "
                    "design language to Louis Vuitton's Spring 2024 men's capsule."
                ),
            },
            explanation="Propose the capsule's lead designer as a sourced archive profile.",
            sources=[LVMH_SOURCE, GQ_SOURCE],
        ),
        member,
    )
    decide(designer_id, admin, "approve", "Identity and design work verified from supplied sources.")

    connection = connect()
    try:
        tyler = one(connection, "SELECT id FROM designers WHERE full_name = 'Tyler Okonma'")
        tyler_id = tyler["id"]
        connection.rollback()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """INSERT INTO designer_aliases
               (designer_id, alias, normalized_alias, alias_type, source_url)
               VALUES (?, ?, ?, 'alternate-name', ?)""",
            (
                tyler_id,
                "Tyler, The Creator",
                normalized_search_name("Tyler, The Creator"),
                GQ_SOURCE["url"],
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    collection_submission_id = create_submission(
        proposal(
            record_type="collection",
            submission_type="addition",
            proposed_data={
                "designer_id": tyler_id,
                "label": "Louis Vuitton",
                "name": "Spring 2024 Men's Capsule",
                "season": "Spring",
                "release_year": 2024,
                "status": "released",
                "piece_count": 17,
                "description": (
                    "A standalone capsule translating Tyler Okonma's preppy Golf "
                    "vocabulary into Louis Vuitton travel codes, Damier motifs, pastel "
                    "knitwear, tailoring, golf accessories, and playful objects."
                ),
                "source_url": LVMH_SOURCE["url"],
            },
            explanation="Propose the verified collaboration as the narrative collection anchor.",
            sources=[LVMH_SOURCE, VOGUE_SOURCE, GQ_SOURCE],
        ),
        member,
    )
    decide(collection_submission_id, admin, "approve", "Collection scope and release details verified.")

    connection = connect()
    try:
        capsule = one(
            connection,
            """SELECT id FROM collections WHERE designer_id = ? AND label = 'Louis Vuitton'
               AND season = 'Spring' AND release_year = 2024""",
            (tyler_id,),
        )
        collection_id = capsule["id"]
        credit_payload = CollectionCreate(
            designer_id=tyler_id,
            label="Louis Vuitton",
            name="Spring 2024 Men's Capsule",
            season="Spring",
            release_year=2024,
            status="released",
            piece_count=17,
            description="Credit validation payload.",
            credits=[
                {
                    "designer_id": tyler_id,
                    "role": "lead",
                    "position": 1,
                    "attribution_note": "Lead designer of the standalone capsule.",
                },
                {
                    "designer_id": pharrell["id"],
                    "role": "collaborator",
                    "position": 2,
                    "attribution_note": "Louis Vuitton men's artistic director and creative collaborator.",
                },
            ],
        )
        connection.rollback()
        connection.execute("BEGIN IMMEDIATE")
        sync_collection_credits(connection, collection_id, credit_payload)
        connection.commit()
    finally:
        connection.close()

    create_submission(
        proposal(
            record_type="designer", submission_type="correction", target_id=tyler_id,
            proposed_data={"biography": "Draft wording awaiting source reconciliation."},
            explanation="Draft a biography clarification without publishing it.", sources=[],
        ), member, "draft",
    )
    create_submission(
        proposal(
            record_type="collection", submission_type="correction", target_id=collection_id,
            proposed_data={"piece_count": 17},
            explanation="Submit the reported look count for independent review.", sources=[GQ_SOURCE],
        ), member,
    )
    changes_id = create_submission(
        proposal(
            record_type="designer", submission_type="correction", target_id=tyler_id,
            proposed_data={"website": "https://golfwang.com/"},
            explanation="Propose an additional official web reference.", sources=[GQ_SOURCE],
        ), member,
    )
    decide(changes_id, moderator, "request_changes", "Clarify whether this is the preferred profile website.")
    rejected_id = create_submission(
        proposal(
            record_type="collection", submission_type="correction", target_id=collection_id,
            proposed_data={"season": "Fall/Winter"},
            explanation="Demonstrate rejection of a season conflicting with the sources.", sources=[LVMH_SOURCE],
        ), member,
    )
    decide(rejected_id, moderator, "reject", "The official title identifies this as Spring 2024.")
    rollback_id = create_submission(
        proposal(
            record_type="collection", submission_type="correction", target_id=collection_id,
            proposed_data={"name": "Spring 2024 Golf Capsule"},
            explanation="Demonstrate a plausible title correction that is later reversed.", sources=[GQ_SOURCE],
        ), member,
    )
    decide(rollback_id, admin, "approve", "Initially accepted from editorial shorthand.")
    rollback_submission(
        rollback_id,
        RollbackRequest(reason="Restored the official collection title after source reconciliation."),
        admin,
    )

    enrichment_states = (
        ("theme", "sportswear", "dominant", "Golf clothing and varsity sportswear organize the capsule.", "approve"),
        ("color", "pink", "supporting", "Pastel pink appears throughout the documented knitwear.", None),
        ("texture", "quilted", "supporting", "Travel goods suggest quilting, but the evidence needs a closer citation.", "request_changes"),
        ("material", "fur", "dominant", "A deliberately unsupported material claim for rejection.", "reject"),
        ("motif", "logo", "dominant", "The Craggy Monogram and Damier remix make logos central.", "rollback"),
    )
    for category, value, strength, evidence, outcome in enrichment_states:
        submission_id = create_submission(
            enrichment(collection_id, category, value, strength, evidence), member
        )
        if outcome == "approve":
            decide(submission_id, admin, "approve", "Descriptor is supported by the supplied evidence.")
        elif outcome == "request_changes":
            decide(submission_id, moderator, "request_changes", "Add a source passage specific to garment construction.")
        elif outcome == "reject":
            decide(submission_id, moderator, "reject", "The supplied sources do not support this material claim.")
        elif outcome == "rollback":
            decide(submission_id, admin, "approve", "Descriptor initially met the evidence threshold.")
            rollback_submission(
                submission_id,
                RollbackRequest(reason="Rehearsal rollback demonstrating reversible enrichment."),
                admin,
            )

    dry_run = ingest_collection_csv(
        INGESTION_SAMPLE,
        submitter_clerk_user_id=member["clerk_user_id"],
        source_name="DEMO-X14 narrative ingestion",
        dry_run=True,
    )
    applied = ingest_collection_csv(
        INGESTION_SAMPLE,
        submitter_clerk_user_id=member["clerk_user_id"],
        source_name="DEMO-X14 narrative ingestion",
        dry_run=False,
    )
    return {
        "database": database_name,
        "mode": "created",
        "designer_id": tyler_id,
        "collection_id": collection_id,
        "anchor_submission_id": collection_submission_id,
        "dry_run": dry_run,
        "applied": applied,
    }


def status() -> dict:
    database_name = require_isolated_demo_database()
    connection = connect()
    try:
        summary = existing_summary(connection)
        return {"database": database_name, "configured": summary is not None, "summary": summary}
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "status"))
    parser.add_argument(
        "--admin-clerk-user-id",
        help="Existing Clerk identity that will operate admin controls in the demo database",
    )
    args = parser.parse_args()
    if args.command == "setup" and not args.admin_clerk_user_id:
        parser.error("setup requires --admin-clerk-user-id")
    result = (
        setup(args.admin_clerk_user_id)
        if args.command == "setup"
        else status()
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
