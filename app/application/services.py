from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from app.domain.entities import ParseRequest, ParsedPost
from app.domain.exceptions import ValidationError


def normalize_channel_source(source: str) -> str:
    value = source.strip()
    if not value:
        return ""

    if re.match(r"^https?://", value, flags=re.IGNORECASE):
        parsed = urlparse(value)
        host = (parsed.netloc or "").lower()
        if host not in {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}:
            raise ValidationError("Only Telegram channel links are supported")

        path = parsed.path.strip("/")
        parts = [part for part in path.split("/") if part]
        if not parts:
            raise ValidationError("Telegram link does not contain a channel")

        if parts[0].startswith("+"):
            invite_hash = parts[0][1:].strip()
            if not invite_hash:
                raise ValidationError("Telegram invite link is invalid")
            return f"invite:{invite_hash}"

        if parts[0].lower() == "joinchat":
            if len(parts) < 2 or not parts[1].strip():
                raise ValidationError("Telegram invite link is invalid")
            return f"invite:{parts[1].strip()}"

        if parts[0].lower() in {"s", "c"}:
            parts = parts[1:]
        if not parts:
            raise ValidationError("Telegram link does not contain a public channel username")

        value = parts[0]

    value = value.lstrip("@/")
    value = value.split("?", 1)[0].split("#", 1)[0].strip()
    if "/" in value:
        value = value.split("/", 1)[0]

    if value.startswith("+"):
        invite_hash = value[1:].strip()
        if not invite_hash:
            raise ValidationError("Telegram invite link is invalid")
        return f"invite:{invite_hash}"

    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        raise ValidationError("Channel username or link is invalid")
    return value.lower()


def build_cutoff(request: ParseRequest) -> datetime | None:
    if request.period_hours is None:
        return None
    return datetime.now(timezone.utc) - timedelta(hours=request.period_hours)


def filter_posts_by_period(posts: list[ParsedPost], request: ParseRequest) -> list[ParsedPost]:
    cutoff = build_cutoff(request)
    if cutoff is None:
        return posts
    return [post for post in posts if post.published_at >= cutoff]
