import os
import math
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from app.auth import ClerkIdentity, require_authenticated_user
from app.database import (
    DATABASE_INTEGRITY_ERRORS,
    apply_migrations,
    bump_archive_version,
    connect,
    current_archive_version,
    database_readiness,
    is_unique_violation,
)
from app.schemas import CollectionCreate, DesignerCreate
from app.naming import normalized_search_name
from app.request_limits import RequestSizeLimitMiddleware
from app.rate_limits import (
    ACCOUNT_SYNC_LIMIT,
    ADMIN_WRITE_LIMIT,
    enforce_identity_rate_limit,
)
from app.observability import (
    log_request,
    monotonic_time,
    request_id,
    route_template,
    service_metrics,
)
from app.users import get_or_create_user, sync_clerk_user_profile
from app.submissions import router as submissions_router
from app.recommendations import (
    editorial_search_terms,
    rank_related_collections,
)
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("AUTO_MIGRATE_DATABASE", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        apply_migrations()
    yield


app = FastAPI(
    title="Trainspotting API",
    description="Structured fashion-history data for designers, labels, and collections.",
    lifespan=lifespan,
)
app.add_middleware(RequestSizeLimitMiddleware)
app.include_router(submissions_router)


def is_public_archive_path(path: str) -> bool:
    return (
        path == "/designers"
        or path.startswith("/designers/")
        or path == "/collections"
        or path.startswith("/collections/")
        or path.startswith("/archive-options/")
    )


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    safe_request_id = request_id(request.headers.get("x-request-id"))
    started_at = monotonic_time()
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = safe_request_id
        return response
    finally:
        duration_ms = (monotonic_time() - started_at) * 1_000
        template = route_template(request.scope)
        service_metrics.observe_request(
            request.method,
            template,
            status_code,
            duration_ms,
        )
        log_request(
            request_id_value=safe_request_id,
            method=request.method,
            route=template,
            status_code=status_code,
            duration_ms=duration_ms,
        )


@app.middleware("http")
async def cache_policy(request, call_next):
    requested_version = request.query_params.get("archive_version")
    eligible_request = (
        request.method == "GET"
        and is_public_archive_path(request.url.path)
        and "authorization" not in request.headers
        and requested_version is not None
        and requested_version.isdigit()
    )
    version_matches_before = False
    if eligible_request:
        try:
            version_matches_before = (
                int(requested_version)
                == await run_in_threadpool(current_archive_version)
            )
        except Exception:
            version_matches_before = False

    response = await call_next(request)
    version_matches_after = False
    if version_matches_before and response.status_code == 200:
        try:
            version_matches_after = (
                int(requested_version)
                == await run_in_threadpool(current_archive_version)
            )
        except Exception:
            version_matches_after = False

    anonymous_public_read = (
        eligible_request
        and response.status_code == 200
        and version_matches_before
        and version_matches_after
    )
    if anonymous_public_read:
        response.headers["Cache-Control"] = (
            "public, max-age=0, s-maxage=30, stale-while-revalidate=60"
        )
    else:
        response.headers["Cache-Control"] = "private, no-store"
    return response


def require_archive_admin(
    identity: ClerkIdentity = Depends(require_authenticated_user),
) -> dict:
    """Require a verified Clerk identity with Trainspotting's admin role."""
    user = get_or_create_user(identity.user_id)
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    enforce_identity_rate_limit(
        "canonical-admin-write",
        user["clerk_user_id"],
        limit=ADMIN_WRITE_LIMIT,
    )
    return user


def require_operations_admin(
    identity: ClerkIdentity = Depends(require_authenticated_user),
) -> dict:
    user = get_or_create_user(identity.user_id)
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return user


COLLECTION_SELECT = """
    SELECT
        collections.id,
        collections.designer_id,
        designers.full_name AS lead_designer,
        collections.label,
        collections.name,
        collections.season,
        collections.release_year,
        collections.status,
        collections.piece_count,
        collections.description,
        (
            SELECT media_value
            FROM collection_media
            WHERE collection_id = collections.id
              AND media_type = 'source'
        ) AS source_url,
        (
            SELECT media_value
            FROM collection_media
            WHERE collection_id = collections.id
              AND media_type = 'youtube'
        ) AS youtube_video_id
    FROM collections
    JOIN designers
        ON designers.id = collections.designer_id
"""


def fetch_collection(
    connection,
    collection_id: int,
) -> dict:
    row = connection.execute(
        COLLECTION_SELECT + " WHERE collections.id = ?",
        (collection_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Collection not found",
        )

    payload = collection_payloads(connection, [row])[0]
    payload["provenance"] = public_provenance(
        connection, "collection", collection_id, payload.get("source_url")
    )
    return payload


def public_provenance(
    connection, record_type: str, record_id: int, canonical_source: str | None = None
) -> dict:
    """Return safe evidence from canonical data and active approved promotions."""
    sources = []
    seen_urls = set()
    if canonical_source:
        sources.append({"url": canonical_source, "title": "Curated archive source", "origin": "canonical", "reviewed_at": None})
        seen_urls.add(canonical_source)
    rows = connection.execute(
        """SELECT submission_sources.url, submission_sources.title,
                  submissions.reviewed_at
           FROM submission_promotions
           JOIN submissions ON submissions.id = submission_promotions.submission_id
           JOIN submission_sources ON submission_sources.submission_id = submissions.id
           WHERE submission_promotions.canonical_record_type = ?
             AND submission_promotions.canonical_record_id = ?
             AND submission_promotions.rolled_back_at IS NULL
             AND submissions.status = 'approved'
           ORDER BY submissions.reviewed_at DESC, submission_sources.id""",
        (record_type, record_id),
    ).fetchall()
    for row in rows:
        if row["url"] in seen_urls:
            continue
        seen_urls.add(row["url"])
        sources.append({"url": row["url"], "title": row["title"] or "Approved community source", "origin": "approved_submission", "reviewed_at": row["reviewed_at"]})
    reviewed = [source["reviewed_at"] for source in sources if source["reviewed_at"]]
    return {"sources": sources, "last_reviewed_at": max(reviewed) if reviewed else None}


def collection_payloads(connection, rows) -> list[dict]:
    """Attach ordered credits and reviewed descriptors in bounded queries."""
    payloads = [dict(row) for row in rows]
    if not payloads:
        return payloads

    collection_ids = [payload["id"] for payload in payloads]
    placeholders = ", ".join("?" for _ in collection_ids)
    credit_rows = connection.execute(
        f"""
        SELECT
            collection_credits.collection_id,
            collection_credits.designer_id,
            designers.full_name AS designer_name,
            collection_credits.credit_role AS role,
            collection_credits.credit_order AS position,
            collection_credits.attribution_note
        FROM collection_credits
        JOIN designers
            ON designers.id = collection_credits.designer_id
        WHERE collection_credits.collection_id IN ({placeholders})
        ORDER BY collection_credits.collection_id, collection_credits.credit_order
        """,
        collection_ids,
    ).fetchall()
    credits_by_collection = {collection_id: [] for collection_id in collection_ids}
    for credit in credit_rows:
        credit_payload = dict(credit)
        collection_id = credit_payload.pop("collection_id")
        credits_by_collection[collection_id].append(credit_payload)

    descriptor_rows = connection.execute(
        f"""
        SELECT
            collection_descriptors.collection_id,
            collection_descriptors.category,
            collection_descriptors.canonical_value,
            collection_descriptors.strength,
            collection_descriptors.evidence_note,
            collection_descriptors.source_submission_id AS submission_id,
            collection_descriptors.created_at,
            submissions.created_at AS proposed_at,
            submissions.reviewed_at
        FROM collection_descriptors
        JOIN submissions
            ON submissions.id = collection_descriptors.source_submission_id
        JOIN submission_promotions
            ON submission_promotions.submission_id = submissions.id
           AND submission_promotions.rolled_back_at IS NULL
        WHERE collection_descriptors.collection_id IN ({placeholders})
        ORDER BY collection_descriptors.collection_id,
                 collection_descriptors.category,
                 collection_descriptors.canonical_value
        """,
        collection_ids,
    ).fetchall()
    descriptors_by_collection = {collection_id: [] for collection_id in collection_ids}
    submission_ids = []
    for descriptor in descriptor_rows:
        descriptor_payload = dict(descriptor)
        collection_id = descriptor_payload.pop("collection_id")
        submission_ids.append(descriptor_payload["submission_id"])
        descriptor_payload["sources"] = []
        descriptors_by_collection[collection_id].append(descriptor_payload)

    sources_by_submission = {submission_id: [] for submission_id in submission_ids}
    if submission_ids:
        source_placeholders = ", ".join("?" for _ in submission_ids)
        source_rows = connection.execute(
            f"""SELECT submission_id, url, title
                FROM submission_sources
                WHERE submission_id IN ({source_placeholders})
                ORDER BY submission_id, id""",
            submission_ids,
        ).fetchall()
        for source in source_rows:
            sources_by_submission[source["submission_id"]].append(
                {"url": source["url"], "title": source["title"]}
            )
    for payload in payloads:
        payload["credits"] = credits_by_collection[payload["id"]]
        payload["descriptors"] = descriptors_by_collection[payload["id"]]
        for descriptor in payload["descriptors"]:
            descriptor["sources"] = sources_by_submission[descriptor["submission_id"]]
            descriptor.pop("submission_id")
    return payloads


def sync_collection_credits(
    connection,
    collection_id: int,
    payload: CollectionCreate,
) -> None:
    credits = payload.credits or [
        {
            "designer_id": payload.designer_id,
            "role": "lead",
            "position": 1,
            "attribution_note": None,
        }
    ]
    credit_values = [
        credit.model_dump() if hasattr(credit, "model_dump") else credit
        for credit in credits
    ]
    designer_ids = [credit["designer_id"] for credit in credit_values]
    placeholders = ", ".join("?" for _ in designer_ids)
    existing_ids = {
        row[0]
        for row in connection.execute(
            f"SELECT id FROM designers WHERE id IN ({placeholders})",
            designer_ids,
        ).fetchall()
    }
    missing_ids = sorted(set(designer_ids) - existing_ids)
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Credited designer not found: {missing_ids[0]}",
        )

    connection.execute(
        "DELETE FROM collection_credits WHERE collection_id = ?",
        (collection_id,),
    )
    connection.executemany(
        """
        INSERT INTO collection_credits (
            collection_id,
            designer_id,
            credit_role,
            credit_order,
            attribution_note
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                collection_id,
                credit["designer_id"],
                credit["role"],
                credit["position"],
                credit["attribution_note"],
            )
            for credit in credit_values
        ],
    )


def sync_collection_media(
    connection,
    collection_id: int,
    payload: CollectionCreate,
) -> None:
    connection.execute(
        "DELETE FROM collection_media WHERE collection_id = ?",
        (collection_id,),
    )

    media = [
        ("source", payload.source_url),
        ("youtube", payload.youtube_video_id),
    ]
    connection.executemany(
        """
        INSERT INTO collection_media (
            collection_id,
            media_type,
            media_value
        )
        VALUES (?, ?, ?)
        """,
        [
            (collection_id, media_type, media_value)
            for media_type, media_value in media
            if media_value is not None
        ],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        details = database_readiness()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready.",
        ) from error
    return {"status": "ready", **details}


@app.get("/operations/metrics", dependencies=[Depends(require_operations_admin)])
def operations_metrics():
    return service_metrics.snapshot()


@app.get("/archive-version")
def archive_version():
    return {"version": current_archive_version()}


@app.get("/auth/session")
def authenticated_session(
    identity: ClerkIdentity = Depends(require_authenticated_user),
):
    return {
        "authenticated": True,
        "user_id": identity.user_id,
    }


@app.get("/me")
def current_user(
    identity: ClerkIdentity = Depends(require_authenticated_user),
):
    enforce_identity_rate_limit(
        "account-sync",
        identity.user_id,
        limit=ACCOUNT_SYNC_LIMIT,
    )
    return sync_clerk_user_profile(identity.user_id)

def pagination_payload(rows, *, page: int, page_size: int, total: int):
    return {
        "items": [dict(row) for row in rows],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        },
    }


def case_insensitive_equality(connection, column: str) -> str:
    if getattr(connection, "_backend", "sqlite") == "mysql":
        return f"{column} = ?"
    return f"{column} COLLATE NOCASE = ?"


def public_designer_aliases(connection, designer_id: int) -> list[dict]:
    return [
        dict(alias)
        for alias in connection.execute(
            """SELECT alias, alias_type, source_url
               FROM designer_aliases
               WHERE designer_id = ?
               ORDER BY alias""",
            (designer_id,),
        ).fetchall()
    ]


@app.get("/designers")
def list_designers(
    search: str = Query(default="", max_length=120),
    nationality: str = Query(default="", max_length=120),
    label: str = Query(default="", max_length=120),
    season: str = Query(default="", max_length=100),
    year: int | None = Query(default=None, ge=1900, le=2100),
    status_filter: Literal["concept", "in-production", "released", "archived"] | None = Query(
        default=None, alias="status"
    ),
    sort: Literal["name", "newest", "oldest", "collections"] = "name",
    direction: Literal["asc", "desc"] | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
):
    connection = connect()

    try:
        clauses = []
        parameters = []
        normalized_search = search.strip()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            normalized_alias_pattern = f"%{normalized_search_name(normalized_search)}%"
            clauses.append(
                "(LOWER(designers.full_name) LIKE LOWER(?) "
                "OR EXISTS (SELECT 1 FROM designer_aliases "
                "WHERE designer_aliases.designer_id = designers.id "
                "AND designer_aliases.normalized_alias LIKE ?) "
                "OR LOWER(COALESCE(designers.nationality, '')) LIKE LOWER(?) "
                "OR LOWER(COALESCE(designers.biography, '')) LIKE LOWER(?) "
                "OR LOWER(collections.label) LIKE LOWER(?) "
                "OR LOWER(COALESCE(collections.name, '')) LIKE LOWER(?) "
                "OR LOWER(collections.season) LIKE LOWER(?) "
                "OR CAST(collections.release_year AS CHAR) LIKE ? "
                "OR LOWER(COALESCE(collections.description, '')) LIKE LOWER(?))"
            )
            parameters.extend([pattern, normalized_alias_pattern, *([pattern] * 7)])
        for value, expression in (
            (
                nationality.strip(),
                case_insensitive_equality(connection, "designers.nationality"),
            ),
            (label.strip(), case_insensitive_equality(connection, "collections.label")),
            (season.strip(), case_insensitive_equality(connection, "collections.season")),
        ):
            if value:
                clauses.append(expression)
                parameters.append(value)
        if year is not None:
            clauses.append("collections.release_year = ?")
            parameters.append(year)
        if status_filter is not None:
            clauses.append("collections.status = ?")
            parameters.append(status_filter)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = connection.execute(
            f"""SELECT COUNT(DISTINCT designers.id)
                FROM designers
                LEFT JOIN collection_credits
                    ON collection_credits.designer_id = designers.id
                LEFT JOIN collections
                    ON collections.id = collection_credits.collection_id
                {where_sql}""",
            parameters,
        ).fetchone()[0]

        sort_expressions = {
            "name": "LOWER(designers.full_name)",
            "newest": "MAX(collections.release_year)",
            "oldest": "MIN(collections.release_year)",
            "collections": "collection_count",
        }
        default_direction = "desc" if sort in {"newest", "collections"} else "asc"
        order_direction = (direction or default_direction).upper()
        order_sql = (
            f"{sort_expressions[sort]} {order_direction}, "
            f"designers.id {order_direction}"
        )
        offset = (page - 1) * page_size
        rows = connection.execute(
            f"""
            SELECT
                designers.id,
                designers.full_name,
                designers.nationality,
                designers.birth_year,
                designers.website,
                designers.biography,
                COALESCE(MAX(collection_stats.collection_count), 0) AS collection_count
            FROM designers
            LEFT JOIN collection_credits
                ON collection_credits.designer_id = designers.id
            LEFT JOIN collections
                ON collections.id = collection_credits.collection_id
            LEFT JOIN (
                SELECT designer_id, COUNT(*) AS collection_count
                FROM collection_credits
                GROUP BY designer_id
            ) AS collection_stats
                ON collection_stats.designer_id = designers.id
            {where_sql}
            GROUP BY designers.id
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            (*parameters, page_size, offset),
        ).fetchall()

        return pagination_payload(rows, page=page, page_size=page_size, total=total)
    finally:
        connection.close()


@app.get("/archive-options/designers")
def designer_options(
    search: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
):
    connection = connect()
    try:
        normalized_search = search.strip()
        rows = connection.execute(
            """SELECT id, full_name, nationality
               FROM designers
               WHERE LOWER(full_name) LIKE LOWER(?)
                  OR LOWER(COALESCE(nationality, '')) LIKE LOWER(?)
                  OR EXISTS (
                      SELECT 1 FROM designer_aliases
                      WHERE designer_aliases.designer_id = designers.id
                        AND designer_aliases.normalized_alias LIKE ?
                  )
               ORDER BY full_name
               LIMIT ?""",
            (
                f"%{normalized_search}%",
                f"%{normalized_search}%",
                f"%{normalized_search_name(normalized_search)}%",
                limit,
            ),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.get("/designers/{designer_id}")
def get_designer(designer_id: int):
    connection = connect()

    try:
        row = connection.execute(
            """
            SELECT
                id,
                full_name,
                nationality,
                birth_year,
                website,
                biography
            FROM designers
            WHERE id = ?
            """,
            (designer_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Designer not found",
            )

        payload = dict(row)
        payload["aliases"] = public_designer_aliases(connection, designer_id)
        payload["provenance"] = public_provenance(connection, "designer", designer_id)
        return payload
    finally:
        connection.close()

@app.get("/designers/{designer_id}/collections")
def list_designer_collections(designer_id: int):
    connection = connect()

    try:
        designer = connection.execute(
            """
            SELECT id
            FROM designers
            WHERE id = ?
            """,
            (designer_id,),
        ).fetchone()

        if designer is None:
            raise HTTPException(
                status_code=404,
                detail="Designer not found",
            )

        rows = connection.execute(
            """
            SELECT
                id,
                designer_id,
                label,
                name,
                season,
                release_year,
                status,
                piece_count,
                description,
                (
                    SELECT media_value
                    FROM collection_media
                    WHERE collection_id = collections.id
                      AND media_type = 'source'
                ) AS source_url,
                (
                    SELECT media_value
                    FROM collection_media
                    WHERE collection_id = collections.id
                      AND media_type = 'youtube'
                ) AS youtube_video_id
            FROM collections
            WHERE EXISTS (
                SELECT 1
                FROM collection_credits
                WHERE collection_credits.collection_id = collections.id
                  AND collection_credits.designer_id = ?
            )
            ORDER BY release_year DESC, season
            """,
            (designer_id,),
        ).fetchall()

        return collection_payloads(connection, rows)
    finally:
        connection.close()

@app.get("/collections/{collection_id}")
def get_collection(collection_id: int):
    connection = connect()

    try:
        return fetch_collection(connection, collection_id)
    finally:
        connection.close()


@app.get("/collections/{collection_id}/related")
def related_collections(
    collection_id: int,
    limit: int = Query(default=4, ge=1, le=12),
):
    connection = connect()

    try:
        target = fetch_collection(connection, collection_id)
        clauses = [
            case_insensitive_equality(connection, "collections.label"),
            case_insensitive_equality(connection, "collections.season"),
            "collections.release_year BETWEEN ? AND ?",
            """EXISTS (
                SELECT 1
                FROM collection_credits AS candidate_credit
                JOIN collection_credits AS target_credit
                    ON target_credit.designer_id = candidate_credit.designer_id
                WHERE candidate_credit.collection_id = collections.id
                  AND target_credit.collection_id = ?
            )""",
        ]
        parameters = [
            target["label"],
            target["season"],
            target["release_year"] - 2,
            target["release_year"] + 2,
            collection_id,
        ]
        for term in sorted(editorial_search_terms(target))[:40]:
            clauses.append(
                "(LOWER(COALESCE(collections.name, '')) LIKE ? "
                "OR LOWER(COALESCE(collections.description, '')) LIKE ?)"
            )
            parameters.extend((f"%{term}%", f"%{term}%"))
        for descriptor in target.get("descriptors", []):
            clauses.append(
                """EXISTS (
                    SELECT 1 FROM collection_descriptors
                    WHERE collection_descriptors.collection_id = collections.id
                      AND collection_descriptors.category = ?
                      AND collection_descriptors.canonical_value = ?
                )"""
            )
            parameters.extend(
                (descriptor["category"], descriptor["canonical_value"])
            )
        ranked = []
        last_id = 0
        batch_size = 200
        while True:
            rows = connection.execute(
                COLLECTION_SELECT
                + " WHERE collections.id != ? AND collections.id > ? AND ("
                + " OR ".join(clauses)
                + ") ORDER BY collections.id LIMIT ?",
                (collection_id, last_id, *parameters, batch_size),
            ).fetchall()
            if not rows:
                break
            candidates = collection_payloads(connection, rows)
            ranked = rank_related_collections(
                target,
                [*ranked, *candidates],
                limit=limit,
            )
            last_id = rows[-1]["id"]
        return ranked
    finally:
        connection.close()

@app.post(
    "/designers",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_archive_admin)],
)
def create_designer(payload: DesignerCreate):
    connection = connect()

    try:
        cursor = connection.execute(
            """
            INSERT INTO designers (
                full_name,
                nationality,
                birth_year,
                website,
                biography
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.full_name,
                payload.nationality,
                payload.birth_year,
                payload.website,
                payload.biography,
            ),
        )

        bump_archive_version(connection)
        connection.commit()

        row = connection.execute(
            """
            SELECT *
            FROM designers
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

        result = dict(row)
        result["aliases"] = public_designer_aliases(connection, result["id"])
        result["provenance"] = public_provenance(
            connection, "designer", result["id"]
        )
        return result

    except DATABASE_INTEGRITY_ERRORS as error:
        connection.rollback()

        if is_unique_violation(error):
            raise HTTPException(
                status_code=409,
                detail="A designer with this name already exists",
            ) from error

        raise HTTPException(
            status_code=400,
            detail="Designer violates a database constraint",
        ) from error

    finally:
        connection.close()

@app.put(
    "/designers/{designer_id}",
    dependencies=[Depends(require_archive_admin)],
)
def update_designer(designer_id: int, payload: DesignerCreate):
    connection = connect()

    try:
        existing_designer = connection.execute(
            """
            SELECT id
            FROM designers
            WHERE id = ?
            """,
            (designer_id,),
        ).fetchone()

        if existing_designer is None:
            raise HTTPException(
                status_code=404,
                detail="Designer not found",
            )

        connection.execute(
            """
            UPDATE designers
            SET
                full_name = ?,
                nationality = ?,
                birth_year = ?,
                website = ?,
                biography = ?
            WHERE id = ?
            """,
            (
                payload.full_name,
                payload.nationality,
                payload.birth_year,
                payload.website,
                payload.biography,
                designer_id,
            ),
        )

        bump_archive_version(connection)
        connection.commit()

        updated_designer = connection.execute(
            """
            SELECT *
            FROM designers
            WHERE id = ?
            """,
            (designer_id,),
        ).fetchone()

        result = dict(updated_designer)
        result["aliases"] = public_designer_aliases(connection, designer_id)
        result["provenance"] = public_provenance(
            connection, "designer", designer_id
        )
        return result

    except DATABASE_INTEGRITY_ERRORS as error:
        connection.rollback()

        if is_unique_violation(error):
            raise HTTPException(
                status_code=409,
                detail="A designer with this name already exists",
            ) from error

        raise HTTPException(
            status_code=400,
            detail="Designer violates a database constraint",
        ) from error

    finally:
        connection.close()

@app.delete(
    "/designers/{designer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_archive_admin)],
)
def delete_designer(designer_id: int):
    connection = connect()

    try:
        existing_designer = connection.execute(
            """
            SELECT id
            FROM designers
            WHERE id = ?
            """,
            (designer_id,),
        ).fetchone()

        if existing_designer is None:
            raise HTTPException(
                status_code=404,
                detail="Designer not found",
            )

        connection.execute(
            """
            DELETE FROM designers
            WHERE id = ?
            """,
            (designer_id,),
        )

        bump_archive_version(connection)
        connection.commit()

        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )
    finally:
        connection.close()

@app.post(
    "/collections",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_archive_admin)],
)
def create_collection(payload: CollectionCreate):
    connection = connect()

    try:
        designer = connection.execute(
            """
            SELECT id
            FROM designers
            WHERE id = ?
            """,
            (payload.designer_id,),
        ).fetchone()

        if designer is None:
            raise HTTPException(
                status_code=404,
                detail="Designer not found",
            )

        cursor = connection.execute(
            """
            INSERT INTO collections (
                designer_id,
                label,
                name,
                season,
                release_year,
                status,
                piece_count,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.designer_id,
                payload.label,
                payload.name,
                payload.season,
                payload.release_year,
                payload.status,
                payload.piece_count,
                payload.description,
            ),
        )

        sync_collection_media(
            connection,
            cursor.lastrowid,
            payload,
        )
        sync_collection_credits(connection, cursor.lastrowid, payload)

        bump_archive_version(connection)
        connection.commit()

        return fetch_collection(connection, cursor.lastrowid)

    except DATABASE_INTEGRITY_ERRORS as error:
        connection.rollback()

        if is_unique_violation(error):
            raise HTTPException(
                status_code=409,
                detail="This collection already exists",
            ) from error

        raise HTTPException(
            status_code=400,
            detail="Collection violates a database constraint",
        ) from error

    finally:
        connection.close()

@app.put(
    "/collections/{collection_id}",
    dependencies=[Depends(require_archive_admin)],
)
def update_collection(
    collection_id: int,
    payload: CollectionCreate,
):
    connection = connect()

    try:
        existing_collection = connection.execute(
            """
            SELECT id
            FROM collections
            WHERE id = ?
            """,
            (collection_id,),
        ).fetchone()

        if existing_collection is None:
            raise HTTPException(
                status_code=404,
                detail="Collection not found",
            )

        designer = connection.execute(
            """
            SELECT id
            FROM designers
            WHERE id = ?
            """,
            (payload.designer_id,),
        ).fetchone()

        if designer is None:
            raise HTTPException(
                status_code=404,
                detail="Designer not found",
            )

        connection.execute(
            """
            UPDATE collections
            SET
                designer_id = ?,
                label = ?,
                name = ?,
                season = ?,
                release_year = ?,
                status = ?,
                piece_count = ?,
                description = ?
            WHERE id = ?
            """,
            (
                payload.designer_id,
                payload.label,
                payload.name,
                payload.season,
                payload.release_year,
                payload.status,
                payload.piece_count,
                payload.description,
                collection_id,
            ),
        )

        sync_collection_media(
            connection,
            collection_id,
            payload,
        )
        sync_collection_credits(connection, collection_id, payload)

        bump_archive_version(connection)
        connection.commit()

        return fetch_collection(connection, collection_id)

    except DATABASE_INTEGRITY_ERRORS as error:
        connection.rollback()

        if is_unique_violation(error):
            raise HTTPException(
                status_code=409,
                detail="This collection already exists",
            ) from error

        raise HTTPException(
            status_code=400,
            detail="Collection violates a database constraint",
        ) from error

    finally:
        connection.close()

@app.delete(
    "/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_archive_admin)],
)
def delete_collection(collection_id: int):
    connection = connect()

    try:
        existing_collection = connection.execute(
            """
            SELECT id
            FROM collections
            WHERE id = ?
            """,
            (collection_id,),
        ).fetchone()

        if existing_collection is None:
            raise HTTPException(
                status_code=404,
                detail="Collection not found",
            )

        connection.execute(
            """
            DELETE FROM collections
            WHERE id = ?
            """,
            (collection_id,),
        )

        bump_archive_version(connection)
        connection.commit()

        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )
    finally:
        connection.close()


@app.get("/collections")
def list_collections(
    search: str = Query(default="", max_length=120),
    designer_id: int | None = Query(default=None, ge=1),
    nationality: str = Query(default="", max_length=120),
    label: str = Query(default="", max_length=120),
    season: str = Query(default="", max_length=100),
    year: int | None = Query(default=None, ge=1900, le=2100),
    status_filter: Literal["concept", "in-production", "released", "archived"] | None = Query(
        default=None, alias="status"
    ),
    sort: Literal["newest", "oldest", "label", "designer"] = "newest",
    direction: Literal["asc", "desc"] | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
):
    connection = connect()

    try:
        clauses = []
        parameters = []
        normalized_search = search.strip()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            clauses.append(
                "(LOWER(designers.full_name) LIKE LOWER(?) "
                "OR LOWER(collections.label) LIKE LOWER(?) "
                "OR LOWER(COALESCE(collections.name, '')) LIKE LOWER(?) "
                "OR LOWER(collections.season) LIKE LOWER(?) "
                "OR CAST(collections.release_year AS CHAR) LIKE ? "
                "OR LOWER(COALESCE(collections.description, '')) LIKE LOWER(?))"
            )
            parameters.extend([pattern] * 6)
        if designer_id is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM collection_credits "
                "WHERE collection_credits.collection_id = collections.id "
                "AND collection_credits.designer_id = ?)"
            )
            parameters.append(designer_id)
        for value, expression in (
            (
                nationality.strip(),
                case_insensitive_equality(connection, "designers.nationality"),
            ),
            (label.strip(), case_insensitive_equality(connection, "collections.label")),
            (season.strip(), case_insensitive_equality(connection, "collections.season")),
        ):
            if value:
                clauses.append(expression)
                parameters.append(value)
        if year is not None:
            clauses.append("collections.release_year = ?")
            parameters.append(year)
        if status_filter is not None:
            clauses.append("collections.status = ?")
            parameters.append(status_filter)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = connection.execute(
            f"""SELECT COUNT(*)
                FROM collections
                JOIN designers ON designers.id = collections.designer_id
                {where_sql}""",
            parameters,
        ).fetchone()[0]
        sort_expressions = {
            "newest": "collections.release_year",
            "oldest": "collections.release_year",
            "label": "LOWER(collections.label)",
            "designer": "LOWER(designers.full_name)",
        }
        order_direction = (direction or ("desc" if sort == "newest" else "asc")).upper()
        order_sql = f"{sort_expressions[sort]} {order_direction}, collections.id {order_direction}"
        offset = (page - 1) * page_size
        rows = connection.execute(
            f"""
            SELECT
                collections.id,
                collections.designer_id,
                designers.full_name AS lead_designer,
                collections.label,
                collections.name,
                collections.season,
                collections.release_year,
                collections.status,
                collections.piece_count,
                collections.description,
                (
                    SELECT media_value
                    FROM collection_media
                    WHERE collection_id = collections.id
                      AND media_type = 'source'
                ) AS source_url,
                (
                    SELECT media_value
                    FROM collection_media
                    WHERE collection_id = collections.id
                      AND media_type = 'youtube'
                ) AS youtube_video_id
            FROM collections
            JOIN designers
                ON designers.id = collections.designer_id
            {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            (*parameters, page_size, offset),
        ).fetchall()

        return pagination_payload(
            collection_payloads(connection, rows),
            page=page,
            page_size=page_size,
            total=total,
        )
    finally:
        connection.close()


@app.get("/archive-options/collections")
def collection_options(
    search: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
):
    connection = connect()
    try:
        pattern = f"%{search.strip()}%"
        rows = connection.execute(
            """SELECT collections.id, collections.designer_id,
                      designers.full_name AS lead_designer,
                      collections.label, collections.name,
                      collections.season, collections.release_year
               FROM collections
               JOIN designers ON designers.id = collections.designer_id
               WHERE LOWER(designers.full_name) LIKE LOWER(?)
                  OR LOWER(collections.label) LIKE LOWER(?)
                  OR LOWER(COALESCE(collections.name, '')) LIKE LOWER(?)
                  OR LOWER(collections.season) LIKE LOWER(?)
                  OR CAST(collections.release_year AS CHAR) LIKE ?
               ORDER BY collections.release_year DESC, collections.label
               LIMIT ?""",
            (pattern, pattern, pattern, pattern, pattern, limit),
        ).fetchall()
        return collection_payloads(connection, rows)
    finally:
        connection.close()


@app.post(
    "/designers/{designer_id}/collections",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_archive_admin)],
)
def create_designer_collection(
    designer_id: int,
    payload: CollectionCreate,
):
    values = payload.model_dump()
    values["designer_id"] = designer_id
    if values["credits"] is not None:
        for credit in values["credits"]:
            if credit["role"] == "lead":
                credit["designer_id"] = designer_id
    payload = CollectionCreate.model_validate(values)
    return create_collection(payload)

app.mount(
    "/",
    StaticFiles(directory="web", html=True),
    name="web",
)
