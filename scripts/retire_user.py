"""Retire a non-administrator account while preserving audit provenance."""

from __future__ import annotations

import argparse

from app.database import connect


FORMER_MEMBER_DISPLAY_NAME = "Former member"


class RetirementError(RuntimeError):
    pass


def retire_user(clerk_user_id: str) -> bool:
    """Clear profile data and privileges without deleting referenced history."""
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute(
            """SELECT id, email, display_name, role
               FROM users WHERE clerk_user_id = ?""",
            (clerk_user_id,),
        ).fetchone()
        if user is None:
            raise RetirementError("No synchronized user has that Clerk user ID.")
        if user["role"] == "admin":
            raise RetirementError(
                "Administrators cannot be retired until controlled role recovery "
                "assigns a replacement."
            )

        already_retired = (
            user["email"] is None
            and user["display_name"] == FORMER_MEMBER_DISPLAY_NAME
            and user["role"] == "member"
        )
        if already_retired:
            connection.rollback()
            return False

        connection.execute(
            """UPDATE users
               SET email = NULL, display_name = ?, role = 'member',
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (FORMER_MEMBER_DISPLAY_NAME, user["id"]),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clerk_user_id", help="Immutable Clerk user ID")
    parser.add_argument(
        "--confirm-retire",
        required=True,
        metavar="CLERK_USER_ID",
        help="Repeat the immutable Clerk user ID to confirm",
    )
    arguments = parser.parse_args()
    if arguments.confirm_retire != arguments.clerk_user_id:
        parser.error("--confirm-retire must exactly match clerk_user_id")

    try:
        changed = retire_user(arguments.clerk_user_id)
    except RetirementError as error:
        parser.error(str(error))

    action = "Retired" if changed else "Already retired"
    print(f"{action}: {arguments.clerk_user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
