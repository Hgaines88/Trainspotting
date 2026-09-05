from pydantic import BaseModel, Field, field_validator
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
