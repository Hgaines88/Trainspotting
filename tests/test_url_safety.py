import pytest

from app.url_safety import normalize_public_http_url


def test_public_https_url_is_preserved():
    assert normalize_public_http_url(
        "https://www.vogue.com/fashion-shows?season=fall#review",
        "Source URL",
    ) == "https://www.vogue.com/fashion-shows?season=fall#review"


def test_missing_scheme_can_be_normalized_for_canonical_websites():
    assert normalize_public_http_url(
        "example.com/archive",
        "Website URL",
        add_https_if_missing=True,
    ) == "https://example.com/archive"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://user:password@example.com/archive",
        "https://localhost/archive",
        "https://127.0.0.1/archive",
        "https://10.0.0.4/archive",
        "https://[::1]/archive",
        "https://example.com/unsafe\nheader",
        "https://example.com:invalid/archive",
        "https://invalid_domain.example/archive",
    ],
)
def test_unsafe_or_non_public_links_are_rejected(url):
    with pytest.raises(ValueError):
        normalize_public_http_url(url, "Source URL")
