"""Deterministic normalization for human-readable archive names."""

import unicodedata


def normalized_search_name(value: str) -> str:
    """Return an accent-insensitive, punctuation-neutral lookup value."""
    decomposed = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(
            character.lower()
            if character.isascii() and character.isalnum()
            else ""
            if unicodedata.combining(character)
            else " "
            for character in decomposed
        ).split()
    )
