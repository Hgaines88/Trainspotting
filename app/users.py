from app.database import connect


def get_or_create_user(clerk_user_id: str) -> dict:
    connection = connect()

    try:
        connection.execute(
            """
            INSERT OR IGNORE INTO users (clerk_user_id)
            VALUES (?)
            """,
            (clerk_user_id,),
        )
        connection.commit()

        user = connection.execute(
            """
            SELECT
                id,
                clerk_user_id,
                email,
                display_name,
                role,
                created_at,
                updated_at
            FROM users
            WHERE clerk_user_id = ?
            """,
            (clerk_user_id,),
        ).fetchone()

        if user is None:
            raise RuntimeError("Authenticated user could not be synchronized.")

        return dict(user)
    finally:
        connection.close()
