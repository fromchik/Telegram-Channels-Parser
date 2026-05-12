from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MediaAttachmentDTO:
    kind: str
    file_path: str


@dataclass(slots=True)
class ActorDTO:
    telegram_user_id: int
    username: str | None
    full_name: str | None


@dataclass(slots=True)
class ParsedPostDTO:
    source_title: str
    source: str
    telegram_message_id: int
    published_at: datetime
    html_text: str
    media: list[MediaAttachmentDTO]


@dataclass(slots=True)
class ParseResultDTO:
    posts: list[ParsedPostDTO]
    skipped_duplicates: int
    errors: list[str]
