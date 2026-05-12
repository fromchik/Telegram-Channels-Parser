from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class MediaAttachment:
    kind: str
    file_path: str


@dataclass(slots=True)
class User:
    id: int | None
    telegram_user_id: int
    username: str | None
    full_name: str | None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Channel:
    id: int | None
    owner_user_id: int
    title: str
    source: str
    normalized_source: str
    telegram_channel_id: int | None = None
    access_hash: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ChannelCollection:
    id: int | None
    owner_user_id: int
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ParsedPost:
    source_title: str
    source: str
    telegram_message_id: int
    published_at: datetime
    html_text: str
    media: list[MediaAttachment] = field(default_factory=list)


@dataclass(slots=True)
class ParseRequest:
    limit: int
    period_hours: int | None = None
