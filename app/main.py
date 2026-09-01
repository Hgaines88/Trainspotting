import sqlite3
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Response, status
from app.database import apply_migrations, connect
from app.schemas import CollectionCreate, DesignerCreate
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(_app: FastAPI):
    apply_migrations()
    yield


app = FastAPI(
    title="Trainspotting API",
    description="Structured fashion-history data for designers, labels, and collections.",
    lifespan=lifespan,
)


def require_archive_admin() -> None:
    """Deny archive mutations until Clerk-backed admin roles are available."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Archive changes require administrator access.",
    )


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
    connection: sqlite3.Connection,
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

    return dict(row)


def sync_collection_media(
    connection: sqlite3.Connection,
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

@app.get("/designers")
def list_designers():
    connection = connect()

    try:
        rows = connection.execute(
            """
            SELECT
                designers.id,
                designers.full_name,
                designers.nationality,
                designers.birth_year,
                designers.website,
                designers.biography,
                COUNT(collections.id) AS collection_count
            FROM designers
            LEFT JOIN collections
                ON collections.designer_id = designers.id
            GROUP BY designers.id
            ORDER BY designers.full_name
            """
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

        return dict(row)
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
            WHERE designer_id = ?
            ORDER BY release_year DESC, season
            """,
            (designer_id,),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()

@app.get("/collections/{collection_id}")
def get_collection(collection_id: int):
    connection = connect()

    try:
        return fetch_collection(connection, collection_id)
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

        connection.commit()

        row = connection.execute(
            """
            SELECT *
            FROM designers
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

        return dict(row)

    except sqlite3.IntegrityError as error:
        connection.rollback()

        if "UNIQUE constraint failed: designers.full_name" in str(error):
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

        connection.commit()

        updated_designer = connection.execute(
            """
            SELECT *
            FROM designers
            WHERE id = ?
            """,
            (designer_id,),
        ).fetchone()

        return dict(updated_designer)

    except sqlite3.IntegrityError as error:
        connection.rollback()

        if "UNIQUE constraint failed: designers.full_name" in str(error):
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

        connection.commit()

        return fetch_collection(connection, cursor.lastrowid)

    except sqlite3.IntegrityError as error:
        connection.rollback()

        if "UNIQUE constraint failed" in str(error):
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

        connection.commit()

        return fetch_collection(connection, collection_id)

    except sqlite3.IntegrityError as error:
        connection.rollback()

        if "UNIQUE constraint failed" in str(error):
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

        connection.commit()

        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )
    finally:
        connection.close()


@app.get("/collections")
def list_collections():
    connection = connect()

    try:
        rows = connection.execute(
            """
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
            ORDER BY
                collections.release_year DESC,
                collections.label
            """
        ).fetchall()

        return [dict(row) for row in rows]
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
    payload = payload.model_copy(update={"designer_id": designer_id})
    return create_collection(payload)

app.mount(
    "/",
    StaticFiles(directory="web", html=True),
    name="web",
)
