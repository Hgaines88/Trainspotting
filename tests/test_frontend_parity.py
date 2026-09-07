import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def attribute_values(path: Path, attribute: str) -> set[str]:
    source = path.read_text(encoding="utf-8")
    return set(re.findall(rf'{attribute}="([^"]+)"', source))


def form_control_names(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    return set(
        re.findall(
            r'<(?:input|select|textarea)\b[^>]*\bname="([^"]+)"',
            source,
        )
    )


def test_designer_forms_expose_the_same_fields():
    react = PROJECT_ROOT / "react-ui" / "src" / "pages" / "DesignerForm.jsx"
    vanilla = PROJECT_ROOT / "web" / "designer-form.html"

    assert form_control_names(react) == form_control_names(vanilla) == {
        "full_name",
        "nationality",
        "birth_year",
        "website",
        "biography",
    }


def test_collection_forms_expose_the_same_fields_and_statuses():
    react = PROJECT_ROOT / "react-ui" / "src" / "pages" / "CollectionForm.jsx"
    vanilla = PROJECT_ROOT / "web" / "collection-form.html"

    expected_fields = {
        "label",
        "name",
        "season",
        "release_year",
        "status",
        "piece_count",
        "description",
        "source_url",
        "youtube_video_id",
        "vimeo_video_id",
    }
    expected_statuses = {
        "concept",
        "in-production",
        "released",
        "archived",
    }

    assert form_control_names(react) == form_control_names(vanilla) == (
        expected_fields
    )
    assert attribute_values(react, "value") & expected_statuses == (
        attribute_values(vanilla, "value") & expected_statuses
    ) == expected_statuses


def test_vanilla_pages_share_react_layout_and_detail_features():
    web = PROJECT_ROOT / "web"
    pages = [
        web / "index.html",
        web / "designer.html",
        web / "designer-form.html",
        web / "collection.html",
        web / "collection-form.html",
    ]

    for page in pages:
        source = page.read_text(encoding="utf-8")
        assert "CH. 001" in source
        assert 'class="site-footer"' in source
        assert 'src="/layout.js"' in source

    designer_page = (web / "designer.html").read_text(encoding="utf-8")
    collection_page = (web / "collection.html").read_text(encoding="utf-8")

    assert 'id="collection-count"' in designer_page
    assert 'id="designer-flag"' in designer_page
    assert 'id="collection-label"' in collection_page
    assert 'id="collection-media"' in collection_page


def test_react_mutations_are_only_exposed_through_admin_guards():
    react_app = (PROJECT_ROOT / "react-ui" / "src" / "App.jsx").read_text(
        encoding="utf-8"
    )
    react_pages = "\n".join(
        (
            PROJECT_ROOT / "react-ui" / "src" / "pages" / filename
        ).read_text(encoding="utf-8")
        for filename in (
            "DesignerList.jsx",
            "DesignerDetail.jsx",
            "CollectionDetail.jsx",
        )
    )
    vanilla_pages = "\n".join(
        (PROJECT_ROOT / "web" / filename).read_text(encoding="utf-8")
        for filename in ("index.html", "designer.html", "collection.html")
    )
    vanilla_scripts = "\n".join(
        (PROJECT_ROOT / "web" / filename).read_text(encoding="utf-8")
        for filename in ("app.js", "designer.js", "collection.js")
    )

    assert "DesignerForm" in react_app
    assert "CollectionForm" in react_app
    assert react_app.count("<RequireAdmin>") == 4
    assert "isAdmin &&" in react_pages
    for public_source in (vanilla_pages,):
        assert "Add a designer" not in public_source
        assert "Add a collection" not in public_source
        assert "Edit designer" not in public_source
        assert "Edit collection" not in public_source
        assert "Delete designer" not in public_source
        assert "Delete collection" not in public_source
    assert 'method: "DELETE"' not in vanilla_scripts


def test_collection_page_exposes_explainable_related_collections():
    source = (
        PROJECT_ROOT / "react-ui" / "src" / "pages" / "CollectionDetail.jsx"
    ).read_text(encoding="utf-8")

    assert "Related collections" in source
    assert "Follow the connection" in source
    assert "item.reasons.map" in source
    assert "item.match_strength" in source
    assert "item.score" in source


def test_react_exposes_guarded_collection_enrichment_workflow():
    app_source = (PROJECT_ROOT / "react-ui" / "src" / "App.jsx").read_text(
        encoding="utf-8"
    )
    collection_source = (
        PROJECT_ROOT / "react-ui" / "src" / "pages" / "CollectionDetail.jsx"
    ).read_text(encoding="utf-8")
    form_source = (
        PROJECT_ROOT / "react-ui" / "src" / "pages" / "EnrichmentSubmissionForm.jsx"
    ).read_text(encoding="utf-8")
    queue_source = (
        PROJECT_ROOT / "react-ui" / "src" / "pages" / "ModerationQueue.jsx"
    ).read_text(encoding="utf-8")

    assert 'path="/collections/:collectionId/enrichment/new"' in app_source
    assert 'path="/submissions/:submissionId/enrichment/edit"' in app_source
    assert "<RequireAuthenticated><EnrichmentSubmissionForm" in app_source
    assert "Suggest enrichment" in collection_source
    assert 'proposal_kind: "enrichment"' in form_source
    assert 'authorizedRequest("/editorial-vocabulary")' in form_source
    assert '`/submission-drafts/${submissionId}`' in form_source
    assert '`/submissions/${submissionId}/submit`' in form_source
    assert 'appUser?.role === "admin"' in queue_source
    assert "Administrator approval is required for canonical promotion." in queue_source


def test_react_uses_clerk_without_exposing_the_secret_key():
    main_source = (
        PROJECT_ROOT / "react-ui" / "src" / "main.jsx"
    ).read_text(encoding="utf-8")
    layout_source = (
        PROJECT_ROOT / "react-ui" / "src" / "components" / "Layout.jsx"
    ).read_text(encoding="utf-8")

    assert "ClerkProvider" in main_source
    assert "VITE_CLERK_PUBLISHABLE_KEY" in main_source
    assert "CLERK_SECRET_KEY" not in main_source
    assert '<Show when="signed-out">' in layout_source
    assert '<Show when="signed-in">' in layout_source
    assert "SignInButton" in layout_source
    assert "SignUpButton" in layout_source
    assert "UserButton" in layout_source


def test_signed_in_react_users_sync_with_a_bearer_token():
    sync_source = (
        PROJECT_ROOT
        / "react-ui"
        / "src"
        / "auth"
        / "ApplicationUserContext.jsx"
    ).read_text(encoding="utf-8")

    assert "useAuth" in sync_source
    assert "getToken" in sync_source
    assert 'authorizedRequest("/me")' in sync_source
    assert "Authorization: `Bearer ${token}`" in sync_source


def test_react_archive_writes_use_fresh_clerk_tokens():
    forms = "\n".join(
        (PROJECT_ROOT / "react-ui" / "src" / "pages" / filename).read_text(
            encoding="utf-8"
        )
        for filename in ("DesignerForm.jsx", "CollectionForm.jsx")
    )
    details = "\n".join(
        (PROJECT_ROOT / "react-ui" / "src" / "pages" / filename).read_text(
            encoding="utf-8"
        )
        for filename in ("DesignerDetail.jsx", "CollectionDetail.jsx")
    )

    assert forms.count("authorizedRequest(") == 2
    assert details.count("authorizedRequest(") == 2
    assert 'method: "DELETE"' in details


def test_submission_and_moderation_routes_are_role_guarded():
    app_source = (PROJECT_ROOT / "react-ui" / "src" / "App.jsx").read_text(
        encoding="utf-8"
    )
    submission_source = (
        PROJECT_ROOT / "react-ui" / "src" / "pages" / "SubmissionForm.jsx"
    ).read_text(encoding="utf-8")
    moderation_source = (
        PROJECT_ROOT / "react-ui" / "src" / "pages" / "ModerationQueue.jsx"
    ).read_text(encoding="utf-8")

    assert '<RequireAuthenticated><SubmissionForm />' in app_source
    assert 'path="/submissions/:submissionId/edit"' in app_source
    assert '<RequireAuthenticated><MySubmissions />' in app_source
    assert '<RequireModerator><ModerationQueue />' in app_source
    assert 'authorizedRequest("/submissions"' in submission_source
    assert "authorizedRequest(`/moderation/submissions/${id}/decisions`" in moderation_source
    assert "authorizedRequest(`/moderation/submissions/${id}/rollback`" in moderation_source
    assert 'appUser?.role === "admin"' in moderation_source
    assert "appUser?.clerk_user_id" in moderation_source
