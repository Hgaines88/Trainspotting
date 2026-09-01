import argparse

from app.database import connect


class BootstrapError(RuntimeError):
    pass


def bootstrap_admin(clerk_user_id: str) -> bool:
    """Promote the first synchronized Clerk user to administrator.

    Returns True when the user was promoted and False when that user was
    already the administrator. Refuses to replace an existing administrator.
    """
    connection = connect()

    try:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute(
            "SELECT id, role FROM users WHERE clerk_user_id = ?",
            (clerk_user_id,),
        ).fetchone()

        if user is None:
            raise BootstrapError(
                "No synchronized user has that Clerk user ID. Sign in first."
            )

        existing_admin = connection.execute(
            "SELECT clerk_user_id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()

        if existing_admin is not None:
            if existing_admin["clerk_user_id"] == clerk_user_id:
                connection.rollback()
                return False
            raise BootstrapError(
                "An administrator already exists; bootstrap cannot replace it."
            )

        connection.execute(
            """
            UPDATE users
            SET role = 'admin', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user["id"],),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote Trainspotting's first synchronized user to admin."
    )
    parser.add_argument("clerk_user_id", help="Immutable Clerk user ID")
    arguments = parser.parse_args()

    try:
        promoted = bootstrap_admin(arguments.clerk_user_id)
    except BootstrapError as error:
        parser.error(str(error))

    action = "Promoted" if promoted else "Already configured"
    print(f"{action}: {arguments.clerk_user_id} is the Trainspotting admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
