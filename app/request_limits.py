"""Request-size safeguards for API mutation endpoints."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


MAX_MUTATION_BODY_BYTES = 64 * 1024
MUTATION_METHODS = {"POST", "PUT", "PATCH"}


class RequestSizeLimitMiddleware:
    """Reject oversized mutation bodies before endpoint validation or DB work."""

    def __init__(
        self,
        app: ASGIApp,
        max_body_bytes: int = MAX_MUTATION_BODY_BYTES,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in MUTATION_METHODS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        declared_length = headers.get(b"content-length")
        if declared_length is not None:
            try:
                if int(declared_length) > self.max_body_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                # The ASGI server normally rejects malformed lengths. If one
                # reaches the app, the streamed-byte limit remains authoritative.
                pass

        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_body_bytes:
                await self._reject(scope, receive, send)
                return
            more_body = message.get("more_body", False)

        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body)}
            return await receive()

        await self.app(scope, replay_body, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            {"detail": "Request body too large."},
            status_code=413,
        )
        await response(scope, receive, send)
