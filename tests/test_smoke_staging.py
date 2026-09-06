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


def test_automated_release_smoke_can_run_without_persisted_user_token(monkeypatch):
    requested_paths = []

    def fake_request(_base_url, path, **kwargs):
        requested_paths.append((path, kwargs))
        if path == "/api/health":
            return smoke_staging.Result(200, {}, {"status": "ok"})
        if path == "/api/ready":
            return smoke_staging.Result(
                200,
                {},
                {"status": "ready", "database": "mysql", "revision": "0002"},
            )
        if path == "/api/archive-version":
            return smoke_staging.Result(200, {}, {"version": 1})
        if path.startswith("/api/designers?"):
            return smoke_staging.Result(
                200,
                {
                    "cache-control": (
                        "public, max-age=0, s-maxage=30, stale-while-revalidate=60"
                    )
                },
                {
                    "items": [],
                    "pagination": {
                        "page": 1,
                        "page_size": 12,
                        "total": 0,
                        "total_pages": 0,
                    },
                },
            )
        if path == "/api/designers" and kwargs.get("method") == "POST":
            return smoke_staging.Result(401, {}, {"detail": "Not authenticated"})
        pytest.fail(f"Unexpected smoke request: {path}")

    monkeypatch.setattr(smoke_staging, "request", fake_request)

    smoke_staging.run("https://staging.example.com")

    assert all(kwargs.get("token") is None for _, kwargs in requested_paths)
    assert [path for path, _ in requested_paths] == [
        "/api/health",
        "/api/ready",
        "/api/archive-version",
        "/api/designers?archive_version=1",
        "/api/designers",
    ]


def test_release_smoke_rejects_the_legacy_unpaginated_designer_payload(monkeypatch):
    def fake_request(_base_url, path, **kwargs):
        if path == "/api/health":
            return smoke_staging.Result(200, {}, {"status": "ok"})
        if path == "/api/ready":
            return smoke_staging.Result(
                200,
                {},
                {"status": "ready", "database": "mysql", "revision": "0006"},
            )
        if path == "/api/archive-version":
            return smoke_staging.Result(200, {}, {"version": 2})
        if path.startswith("/api/designers?"):
            return smoke_staging.Result(200, {}, [])
        pytest.fail(f"Unexpected smoke request: {path} {kwargs}")

    monkeypatch.setattr(smoke_staging, "request", fake_request)

    with pytest.raises(RuntimeError, match="Public read failed"):
        smoke_staging.run("https://staging.example.com")


def test_release_smoke_rejects_a_designer_payload_without_pagination(monkeypatch):
    def fake_request(_base_url, path, **kwargs):
        if path == "/api/health":
            return smoke_staging.Result(200, {}, {"status": "ok"})
        if path == "/api/ready":
            return smoke_staging.Result(
                200,
                {},
                {"status": "ready", "database": "mysql", "revision": "0006"},
            )
        if path == "/api/archive-version":
            return smoke_staging.Result(200, {}, {"version": 2})
        if path.startswith("/api/designers?"):
            return smoke_staging.Result(200, {}, {"items": []})
        pytest.fail(f"Unexpected smoke request: {path} {kwargs}")

    monkeypatch.setattr(smoke_staging, "request", fake_request)

    with pytest.raises(RuntimeError, match="Public read failed"):
        smoke_staging.run("https://staging.example.com")
