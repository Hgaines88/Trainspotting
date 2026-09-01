import os
from dataclasses import dataclass

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import HTTPException, Request, status


DEFAULT_AUTHORIZED_PARTIES = (
    "http://localhost:5173",
    "http://localhost:8000",
)


@dataclass(frozen=True)
class ClerkIdentity:
    user_id: str
    session_id: str | None


def authorized_parties() -> list[str]:
    configured = os.getenv("CLERK_AUTHORIZED_PARTIES", "")
    parties = [party.strip() for party in configured.split(",") if party.strip()]
    return parties or list(DEFAULT_AUTHORIZED_PARTIES)


def authentication_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_authenticated_user(request: Request) -> ClerkIdentity:
    authorization = request.headers.get("authorization", "")

    if not authorization.startswith("Bearer "):
        raise authentication_error("Authentication required.")

    secret_key = os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )

    clerk = Clerk(bearer_auth=secret_key)

    try:
        request_state = clerk.authenticate_request(
            request,
            AuthenticateRequestOptions(
                authorized_parties=authorized_parties(),
            ),
        )
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from error

    if not request_state.is_signed_in or request_state.payload is None:
        raise authentication_error("Invalid or expired session.")

    user_id = request_state.payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise authentication_error("Session is missing a user identity.")

    session_id = request_state.payload.get("sid")
    return ClerkIdentity(
        user_id=user_id,
        session_id=session_id if isinstance(session_id, str) else None,
    )
