from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app.schemas import CollectionStatus, normalize_vimeo_video_id
from app.recommendations import EDITORIAL_FACETS
from app.url_safety import normalize_public_http_url


SubmissionKind = Literal["addition", "correction"]


class SubmissionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def normalize_optional_http_url(value: str | None, field_label: str) -> str | None:
    return normalize_public_http_url(value, field_label)


class SubmissionSource(SubmissionModel):
    url: str = Field(max_length=500)
    title: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("url")
    @classmethod
    def source_url_must_be_http(cls, value: str) -> str:
        normalized = normalize_public_http_url(value, "Source URL")
        if normalized is None:
            raise ValueError("Source URL must not be blank")
        return normalized


class DesignerProposal(SubmissionModel):
    full_name: str | None = Field(default=None, max_length=120)
    nationality: str | None = Field(default=None, max_length=120)
    birth_year: int | None = Field(default=None, ge=1800, le=2100)
    website: str | None = Field(default=None, max_length=500)
    biography: str | None = Field(default=None, max_length=10_000)

    @field_validator("full_name")
    @classmethod
    def supplied_name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Full name must not be blank")
        return cleaned_value

    @field_validator("website")
    @classmethod
    def website_must_be_http(cls, value: str | None) -> str | None:
        return normalize_optional_http_url(value, "Website URL")


class CollectionProposal(SubmissionModel):
    designer_id: int | None = Field(default=None, ge=1)
    label: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=120)
    season: str | None = Field(default=None, max_length=40)
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    status: CollectionStatus | None = None
    piece_count: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=10_000)
    source_url: str | None = Field(default=None, max_length=500)
    youtube_video_id: str | None = Field(default=None, max_length=200)
    vimeo_video_id: str | None = Field(default=None, max_length=200)

    @field_validator("label", "season")
    @classmethod
    def supplied_required_text_must_not_be_blank(
        cls, value: str | None
    ) -> str | None:
        if value is None:
            return None
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Value must not be blank")
        return cleaned_value

    @field_validator("source_url")
    @classmethod
    def source_url_must_be_http(cls, value: str | None) -> str | None:
        return normalize_optional_http_url(value, "Source URL")

    @field_validator("vimeo_video_id")
    @classmethod
    def normalize_vimeo_id(cls, value: str | None) -> str | None:
        return normalize_vimeo_video_id(value)


class SubmissionDraftBase(SubmissionModel):
    submission_type: SubmissionKind
    target_id: int | None = Field(default=None, ge=1)
    explanation: str | None = Field(default=None, max_length=2000)
    sources: list[SubmissionSource] = Field(default_factory=list, max_length=20)


class DesignerSubmissionDraft(SubmissionDraftBase):
    record_type: Literal["designer"]
    proposal_kind: Literal["archive_record"] = "archive_record"
    proposed_data: DesignerProposal = Field(default_factory=DesignerProposal)


class CollectionSubmissionDraft(SubmissionDraftBase):
    record_type: Literal["collection"]
    proposal_kind: Literal["archive_record"] = "archive_record"
    proposed_data: CollectionProposal = Field(default_factory=CollectionProposal)


class CollectionEnrichmentProposal(SubmissionModel):
    category: str = Field(max_length=32)
    canonical_value: str = Field(max_length=64)
    strength: Literal["dominant", "supporting"]
    evidence_note: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def descriptor_must_use_controlled_vocabulary(self):
        self.category = self.category.strip().casefold()
        self.canonical_value = self.canonical_value.strip().casefold()
        self.evidence_note = self.evidence_note.strip()
        descriptors = EDITORIAL_FACETS.get(self.category)
        if descriptors is None:
            raise ValueError("Unknown editorial descriptor category")
        if self.canonical_value not in descriptors:
            raise ValueError("Unknown canonical editorial descriptor")
        return self


class CollectionEnrichmentSubmissionDraft(SubmissionDraftBase):
    record_type: Literal["collection"]
    proposal_kind: Literal["enrichment"]
    submission_type: Literal["correction"]
    proposed_data: CollectionEnrichmentProposal


SubmissionDraft = (
    DesignerSubmissionDraft
    | CollectionSubmissionDraft
    | CollectionEnrichmentSubmissionDraft
)
submission_draft_adapter = TypeAdapter(SubmissionDraft)


class ReviewSubmissionBase(SubmissionDraftBase):
    explanation: str = Field(min_length=1, max_length=2000)
    sources: list[SubmissionSource] = Field(min_length=1, max_length=20)

    @field_validator("explanation")
    @classmethod
    def explanation_must_not_be_blank(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Explanation must not be blank")
        return cleaned_value

    @model_validator(mode="after")
    def target_must_match_submission_type(self):
        if self.submission_type == "correction" and self.target_id is None:
            raise ValueError("Corrections must identify a target record")
        if self.submission_type == "addition" and self.target_id is not None:
            raise ValueError("Additions cannot identify an existing target record")
        return self


class DesignerSubmissionForReview(ReviewSubmissionBase):
    record_type: Literal["designer"]
    proposal_kind: Literal["archive_record"] = "archive_record"
    proposed_data: DesignerProposal

    @model_validator(mode="after")
    def validate_proposed_designer(self):
        supplied_fields = self.proposed_data.model_fields_set
        if not supplied_fields:
            raise ValueError("At least one proposed field is required")
        if self.submission_type == "addition" and self.proposed_data.full_name is None:
            raise ValueError("Designer additions require full_name")
        if "full_name" in supplied_fields and self.proposed_data.full_name is None:
            raise ValueError("full_name cannot be cleared")
        return self


class CollectionSubmissionForReview(ReviewSubmissionBase):
    record_type: Literal["collection"]
    proposal_kind: Literal["archive_record"] = "archive_record"
    proposed_data: CollectionProposal

    @model_validator(mode="after")
    def validate_proposed_collection(self):
        supplied_fields = self.proposed_data.model_fields_set
        if not supplied_fields:
            raise ValueError("At least one proposed field is required")

        required_fields = {
            "designer_id", "label", "season", "release_year", "status"
        }
        if self.submission_type == "addition":
            missing = [
                field_name
                for field_name in sorted(required_fields)
                if getattr(self.proposed_data, field_name) is None
            ]
            if missing:
                raise ValueError(
                    "Collection additions require: " + ", ".join(missing)
                )

        cleared_required = [
            field_name
            for field_name in sorted(required_fields & supplied_fields)
            if getattr(self.proposed_data, field_name) is None
        ]
        if cleared_required:
            raise ValueError(
                "Required fields cannot be cleared: " + ", ".join(cleared_required)
            )
        return self


class CollectionEnrichmentSubmissionForReview(ReviewSubmissionBase):
    record_type: Literal["collection"]
    proposal_kind: Literal["enrichment"]
    submission_type: Literal["correction"]
    target_id: int = Field(ge=1)
    proposed_data: CollectionEnrichmentProposal


SubmissionForReview = (
    DesignerSubmissionForReview
    | CollectionSubmissionForReview
    | CollectionEnrichmentSubmissionForReview
)
submission_for_review_adapter = TypeAdapter(SubmissionForReview)


class ReviewDecision(SubmissionModel):
    decision: Literal["approve", "reject", "request_changes"]
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def notes_required_for_non_approval(self):
        if self.decision != "approve" and not (self.notes or "").strip():
            raise ValueError("Review notes are required for this decision")
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class RollbackRequest(SubmissionModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Rollback reason must not be blank")
        return cleaned_value
