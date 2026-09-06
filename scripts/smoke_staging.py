"""Run non-destructive acceptance checks against a deployed staging origin."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Result:
    status: int
    headers: dict[str, str]
    payload: Any


def request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Result:
    headers = {"Accept": "application/json"}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()

    target = urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))
    prepared = Request(target, data=body, headers=headers, method=method)
    try:
        response = urlopen(prepared, timeout=20)
    except HTTPError as error:
        response = error
    except URLError as error:
        raise RuntimeError(f"Could not reach the staging origin: {error.reason}") from error

    raw = response.read()
    try:
        decoded = json.loads(raw) if raw else None
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{path} did not return JSON") from error

    return Result(
        status=response.status,
        headers={key.lower(): value for key, value in response.headers.items()},
        payload=decoded,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate_base_url(base_url: str, allow_http: bool) -> None:
    parsed = urlparse(base_url)
    require(bool(parsed.netloc), "The staging base URL must include a host")
    require(
        parsed.scheme == "https" or (allow_http and parsed.scheme == "http"),
        "The staging base URL must use HTTPS",
    )
    require(parsed.path in {"", "/"}, "The base URL cannot contain a path")
    require(not parsed.query and not parsed.fragment, "The base URL cannot contain a query")


def run(
    base_url: str,
    token: str | None = None,
    *,
    allow_http: bool = False,
    require_token: bool = False,
) -> None:
    validate_base_url(base_url, allow_http)
    if require_token:
        require(bool(token and token.strip()), "A non-admin smoke token is required")

    health = request(base_url, "/api/health")
    require(health.status == 200 and health.payload == {"status": "ok"}, "Liveness failed")

    ready = request(base_url, "/api/ready")
    require(ready.status == 200, "Readiness failed")
    require(ready.payload.get("status") == "ready", "API is not ready")
    require(ready.payload.get("database") == "mysql", "Staging is not using MySQL")
    require(bool(ready.payload.get("revision")), "Alembic revision is missing")

    archive = request(base_url, "/api/archive-version")
    version = archive.payload.get("version") if archive.status == 200 else None
    require(isinstance(version, int) and version > 0, "Archive version is invalid")

    query = urlencode({"archive_version": version})
    designers = request(base_url, f"/api/designers?{query}")
    designer_items = (
        designers.payload.get("items")
        if isinstance(designers.payload, dict)
        else None
    )
    require(
        designers.status == 200 and isinstance(designer_items, list),
        "Public read failed",
    )
    require(
        designers.headers.get("cache-control")
        == "public, max-age=0, s-maxage=30, stale-while-revalidate=60",
        "Versioned public cache policy is incorrect",
    )

    anonymous_write = request(
        base_url,
        "/api/designers",
        method="POST",
        payload={"full_name": "REL-04 anonymous smoke check"},
    )
    require(anonymous_write.status == 401, "Anonymous mutation was not rejected")

    if token:
        me = request(base_url, "/api/me", token=token)
        require(me.status == 200, "Authenticated identity check failed")
        require(me.payload.get("role") != "admin", "Smoke user must not be an admin")
        member_write = request(
            base_url,
            "/api/designers",
            method="POST",
            token=token,
            payload={"full_name": "REL-04 member smoke check"},
        )
        require(member_write.status == 403, "Member mutation was not rejected")

    checks = 7 if token else 5
    print(
        f"Staging smoke checks passed ({checks} checks; "
        f"database=mysql; revision={ready.payload['revision']})."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("STAGING_BASE_URL"),
        help="Public web origin; defaults to STAGING_BASE_URL",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("STAGING_SMOKE_BEARER_TOKEN"),
        help="Optional short-lived non-admin token",
    )
    parser.add_argument(
        "--require-token",
        action="store_true",
        help="Fail unless an authenticated non-admin token is configured",
    )
    parser.add_argument("--allow-http", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.base_url:
        parser.error("--base-url or STAGING_BASE_URL is required")
    return args


def main() -> None:
    args = parse_args()
    try:
        run(
            args.base_url,
            args.token,
            allow_http=args.allow_http,
            require_token=args.require_token,
        )
    except RuntimeError as error:
        print(f"Staging smoke checks failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
