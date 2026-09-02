import pytest
from pydantic import ValidationError

from app.submission_schemas import (
    submission_draft_adapter,
    submission_for_review_adapter,
)


SOURCE = {"url": "https://example.com/archive", "title": "Archive source"}


def test_incomplete_draft_is_allowed():
    draft = submission_draft_adapter.validate_python({
        "record_type": "collection",
        "submission_type": "addition",
        "proposed_data": {"label": "Example House"},
    })

    assert draft.proposed_data.label == "Example House"
    assert draft.sources == []


def test_review_submission_requires_explanation_and_source():
    with pytest.raises(ValidationError):
        submission_for_review_adapter.validate_python({
            "record_type": "designer",
            "submission_type": "addition",
            "proposed_data": {"full_name": "Example Designer"},
            "explanation": "",
            "sources": [],
        })


def test_designer_addition_requires_full_name():
    with pytest.raises(ValidationError, match="require full_name"):
        submission_for_review_adapter.validate_python({
            "record_type": "designer",
            "submission_type": "addition",
            "proposed_data": {"nationality": "American"},
            "explanation": "Add this documented designer.",
            "sources": [SOURCE],
        })


def test_collection_addition_requires_canonical_fields():
    with pytest.raises(ValidationError, match="Collection additions require"):
        submission_for_review_adapter.validate_python({
            "record_type": "collection",
            "submission_type": "addition",
            "proposed_data": {"label": "Example House"},
            "explanation": "Add this documented collection.",
            "sources": [SOURCE],
        })


def test_complete_collection_addition_is_ready_for_review():
    submission = submission_for_review_adapter.validate_python({
        "record_type": "collection",
        "submission_type": "addition",
        "proposed_data": {
            "designer_id": 1,
            "label": "Example House",
            "season": "Spring/Summer",
            "release_year": 2026,
            "status": "released",
        },
        "explanation": "Add this documented collection.",
        "sources": [SOURCE],
    })

    assert submission.proposed_data.release_year == 2026


def test_correction_requires_target_and_at_least_one_change():
    with pytest.raises(ValidationError):
        submission_for_review_adapter.validate_python({
            "record_type": "designer",
            "submission_type": "correction",
            "proposed_data": {},
            "explanation": "Correct the record.",
            "sources": [SOURCE],
        })


def test_omitted_and_explicitly_cleared_fields_remain_distinct():
    submission = submission_for_review_adapter.validate_python({
        "record_type": "designer",
        "submission_type": "correction",
        "target_id": 7,
        "proposed_data": {"biography": None},
        "explanation": "Remove an unsupported biography.",
        "sources": [SOURCE],
    })

    assert submission.proposed_data.model_fields_set == {"biography"}
    assert submission.proposed_data.biography is None
    assert "nationality" not in submission.proposed_data.model_fields_set


def test_required_canonical_fields_cannot_be_cleared():
    with pytest.raises(ValidationError, match="cannot be cleared"):
        submission_for_review_adapter.validate_python({
            "record_type": "collection",
            "submission_type": "correction",
            "target_id": 4,
            "proposed_data": {"season": None},
            "explanation": "Incorrectly try to erase the season.",
            "sources": [SOURCE],
        })


def test_source_must_use_http_or_https():
    with pytest.raises(ValidationError, match="http:// or https://"):
        submission_for_review_adapter.validate_python({
            "record_type": "designer",
            "submission_type": "addition",
            "proposed_data": {"full_name": "Example Designer"},
            "explanation": "Add this documented designer.",
            "sources": [{"url": "javascript:alert(1)"}],
        })


@pytest.mark.parametrize(
    ("record_type", "proposed_data"),
    [
        ("designer", {"website": "not-a-url"}),
        ("collection", {"source_url": "not-a-url"}),
    ],
)
def test_optional_record_urls_are_validated_in_drafts(record_type, proposed_data):
    with pytest.raises(ValidationError, match="http:// or https://"):
        submission_draft_adapter.validate_python({
            "record_type": record_type,
            "submission_type": "correction",
            "proposed_data": proposed_data,
        })


def test_addition_cannot_target_an_existing_record():
    with pytest.raises(ValidationError, match="cannot identify"):
        submission_for_review_adapter.validate_python({
            "record_type": "designer",
            "submission_type": "addition",
            "target_id": 4,
            "proposed_data": {"full_name": "Example Designer"},
            "explanation": "Add this documented designer.",
            "sources": [SOURCE],
        })


def test_identity_and_role_fields_are_never_accepted_from_clients():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        submission_for_review_adapter.validate_python({
            "record_type": "designer",
            "submission_type": "addition",
            "proposed_data": {"full_name": "Example Designer"},
            "explanation": "Add this documented designer.",
            "sources": [SOURCE],
            "submitter_user_id": 1,
            "role": "admin",
        })
