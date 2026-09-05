"""Validation for user-supplied links rendered by public archive pages."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit


PUBLIC_HOSTNAME_PATTERN = re.compile(
    r"^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*"
    r"\.[A-Za-z]{2,}$"
)


def normalize_public_http_url(
    value: str | None,
    field_label: str,
    *,
    add_https_if_missing: bool = False,
) -> str | None:
    """Return a safe public HTTP(S) link or raise a validation error."""
    if value is None:
        return None

    cleaned_value = value.strip()
    if not cleaned_value:
        return None
    if any(character.isspace() or ord(character) < 32 for character in cleaned_value):
        raise ValueError(f"{field_label} cannot contain whitespace or control characters")

    parsed = urlsplit(cleaned_value)
    if add_https_if_missing and not parsed.scheme:
        cleaned_value = f"https://{cleaned_value}"
        parsed = urlsplit(cleaned_value)

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{field_label} must use http:// or https://")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_label} cannot contain embedded credentials")

    try:
        parsed.port
    except ValueError as error:
        raise ValueError(f"{field_label} contains an invalid port") from error

    hostname = parsed.hostname
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if not PUBLIC_HOSTNAME_PATTERN.fullmatch(hostname):
            raise ValueError(f"{field_label} must include a valid public domain name")
    else:
        if not address.is_global:
            raise ValueError(f"{field_label} cannot target a private or local address")

    return cleaned_value
