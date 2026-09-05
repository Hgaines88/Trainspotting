import pytest

from scripts import smoke_staging


@pytest.mark.parametrize("token", [None, "", "   "])
def test_release_smoke_checks_require_an_authenticated_token(monkeypatch, token):
    monkeypatch.setattr(
        smoke_staging,
        "request",
        lambda *_args, **_kwargs: pytest.fail("network request was attempted"),
    )

    with pytest.raises(RuntimeError, match="smoke token is required"):
        smoke_staging.run(
            "https://staging.example.com",
            token,
            require_token=True,
        )
