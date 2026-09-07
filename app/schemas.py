from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal
from urllib.parse import parse_qs, urlparse
import re

from app.url_safety import normalize_public_http_url

CollectionStatus = Literal[
    "concept",
    "in-production",
    "released",
    "archived",
]

CollectionCreditRole = Literal[
    "lead",
    "co-designer",
    "guest",
    "collaborator",
    "attribution-note",
]


def normalize_vimeo_video_id(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned_value = value.strip()
    if not cleaned_value:
        return None

    video_id = cleaned_value
    if "://" in cleaned_value:
        parsed = urlparse(cleaned_value)
        hostname = (parsed.hostname or "").lower()
        if hostname not in {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}:
            video_id = ""
        else:
            numeric_parts = [part for part in parsed.path.split("/") if part.isdigit()]
            video_id = numeric_parts[-1] if numeric_parts else ""

    if not re.fullmatch(r"[0-9]{6,12}", video_id):
        raise ValueError("Enter an official Vimeo URL or numeric video ID")
    return video_id


class CollectionCredit(BaseModel):
    designer_id: int = Field(ge=1)
    role: CollectionCreditRole
    position: int = Field(ge=1, le=100)
    attribution_note: str | None = Field(default=None, max_length=500)

    @field_validator("attribution_note")
    @classmethod
    def attribution_note_must_not_be_blank(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Attribution note must not be blank")
        return cleaned

class DesignerCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    nationality: str | None = Field(default=None, max_length=120)
    birth_year: int | None = Field(default=None, ge=1800, le=2100)
    website: str | None = Field(default=None, max_length=500)
    biography: str | None = Field(default=None, max_length=10_000)

    @field_validator("full_name")
    @classmethod
    def full_name_must_not_be_blank(cls, value: str) -> str:
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("Full name must not be blank")

        return cleaned_value

    @field_validator("website")
    @classmethod
    def normalize_website_url(
        cls,
        value: str | None,
    ) -> str | None:
        return normalize_public_http_url(
            value,
            "Website URL",
            add_https_if_missing=True,
        )

class CollectionCreate(BaseModel):
    designer_id: int = Field(ge=1)
    label: str = Field(min_length=1, max_length=120)
    name: str | None = Field(default=None, max_length=120)
    season: str = Field(min_length=1, max_length=40)
    release_year: int = Field(ge=1900, le=2100)
    status: CollectionStatus
    piece_count: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=10_000)
    source_url: str | None = Field(default=None, max_length=500)
    youtube_video_id: str | None = Field(default=None, max_length=200)
    vimeo_video_id: str | None = Field(default=None, max_length=200)
    credits: list[CollectionCredit] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def validate_credits(self):
        if self.credits is None:
            return self

        designer_ids = [credit.designer_id for credit in self.credits]
        positions = [credit.position for credit in self.credits]
        leads = [credit for credit in self.credits if credit.role == "lead"]
        if len(set(designer_ids)) != len(designer_ids):
            raise ValueError("A designer may only be credited once")
        if len(set(positions)) != len(positions):
            raise ValueError("Credit positions must be unique")
        if len(leads) != 1 or leads[0].designer_id != self.designer_id:
            raise ValueError(
                "Credits must contain exactly one lead matching designer_id"
            )
        return self

    @field_validator("label", "season")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("Value must not be blank")

        return cleaned_value

    @field_validator("name")
    @classmethod
    def optional_name_must_not_be_blank(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError(
                "Name must be meaningful when provided"
            )

        return cleaned_value

    @field_validator("source_url")
    @classmethod
    def source_url_must_be_http(
        cls,
        value: str | None,
    ) -> str | None:
        return normalize_public_http_url(value, "Source URL")

    @field_validator("youtube_video_id")
    @classmethod
    def normalize_youtube_video_id(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip()
        if not cleaned_value:
            return None

        video_id = cleaned_value
        if "://" in cleaned_value:
            parsed = urlparse(cleaned_value)
            hostname = (parsed.hostname or "").lower()

            if hostname in {"youtu.be", "www.youtu.be"}:
                video_id = parsed.path.strip("/").split("/")[0]
            elif hostname in {
                "youtube.com",
                "www.youtube.com",
                "m.youtube.com",
                "music.youtube.com",
                "youtube-nocookie.com",
                "www.youtube-nocookie.com",
            }:
                if parsed.path == "/watch":
                    video_id = parse_qs(parsed.query).get("v", [""])[0]
                else:
                    path_parts = parsed.path.strip("/").split("/")
                    video_id = path_parts[1] if (
                        len(path_parts) >= 2
                        and path_parts[0] in {"embed", "shorts", "live"}
                    ) else ""
            else:
                video_id = ""

        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError("Enter an official YouTube URL or 11-character video ID")

        return video_id

    @field_validator("vimeo_video_id")
    @classmethod
    def normalize_vimeo_id(cls, value: str | None) -> str | None:
        return normalize_vimeo_video_id(value)
