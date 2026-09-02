import os

from clerk_backend_api import Clerk

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


def sync_clerk_user_profile(clerk_user_id: str) -> dict:
    """Refresh non-authoritative profile fields from Clerk's backend API."""
    user = get_or_create_user(clerk_user_id)
    secret_key = os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        return user

    try:
        clerk_user = Clerk(bearer_auth=secret_key).users.get(user_id=clerk_user_id)
    except Exception:
        # Authentication has already succeeded. A temporary profile lookup
        # failure must not prevent the local account or archive from loading.
        return user

    primary_email = next(
        (
            address.email_address
            for address in clerk_user.email_addresses
            if address.id == clerk_user.primary_email_address_id
        ),
        None,
    )
    if primary_email is None and clerk_user.email_addresses:
        primary_email = clerk_user.email_addresses[0].email_address

    full_name = " ".join(
        part.strip()
        for part in (clerk_user.first_name, clerk_user.last_name)
        if isinstance(part, str) and part.strip()
    )
    display_name = full_name or clerk_user.username or primary_email

    connection = connect()
    try:
        connection.execute(
            """UPDATE users SET email = ?, display_name = ?,
               updated_at = CURRENT_TIMESTAMP WHERE clerk_user_id = ?""",
            (primary_email, display_name, clerk_user_id),
        )
        connection.commit()
    finally:
        connection.close()
    return get_or_create_user(clerk_user_id)
