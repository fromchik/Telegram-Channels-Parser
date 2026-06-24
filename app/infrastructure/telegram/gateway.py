from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    AuthKeyUnregisteredError,
    ChannelPrivateError,
    FloodWaitError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    UnauthorizedError,
    UserAlreadyParticipantError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)
from telethon.extensions import html
from telethon.sessions import StringSession
from telethon.tl.custom.message import Message
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.types import ChatInviteAlready, MessageMediaDocument, MessageMediaPhoto

from app.domain.entities import MediaAttachment, ParsedPost, ParseRequest
from app.domain.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.infrastructure.telegram.formatter import TelegramHtmlFormatter


class TelethonGateway:
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_string: str,
        session_file: str,
        media_storage_dir: str,
        formatter: TelegramHtmlFormatter,
        flood_sleep_threshold: int,
    ) -> None:
        session = StringSession(session_string) if session_string else session_file
        self._client = TelegramClient(
            session,
            api_id,
            api_hash,
            flood_sleep_threshold=flood_sleep_threshold,
        )
        self._formatter = formatter
        self._media_storage_dir = Path(media_storage_dir)

    @staticmethod
    def _session_error() -> ExternalServiceError:
        return ExternalServiceError(
            "Telethon session is not authorized. Generate a valid TELETHON_SESSION_STRING "
            "and restart the bot."
        ) 
    async def connect(self) -> None:
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise self._session_error()

    async def disconnect(self) -> None:
        await self._client.disconnect()

    async def resolve_channel(self, source: str) -> tuple[str, int | None, int | None]:
        try:
            entity = await self._resolve_entity(source)
            return (
                getattr(entity, "title", source),
                getattr(entity, "id", None),
                getattr(entity, "access_hash", None),
            )
        except (UsernameInvalidError, UsernameNotOccupiedError) as exc:
            raise ValidationError("Channel username or link is invalid") from exc
        except (InviteHashInvalidError, InviteHashExpiredError) as exc:
            raise ValidationError("Telegram invite link is invalid or expired") from exc
        except (AuthKeyUnregisteredError, UnauthorizedError) as exc:
            raise self._session_error() from exc
        except ChannelPrivateError as exc:
            raise ExternalServiceError(
                "Channel is private or unavailable for the current Telethon session"
            ) from exc
        except FloodWaitError as exc:
            raise ExternalServiceError(f"Telegram flood wait: retry after {exc.seconds}s") from exc

    async def fetch_posts(self, source: str, request: ParseRequest) -> list[ParsedPost]:
        try:
            entity = await self._resolve_entity(source)
            messages = await self._client.get_messages(entity, limit=request.limit)
        except (UsernameInvalidError, UsernameNotOccupiedError) as exc:
            raise NotFoundError("Channel not found") from exc
        except (InviteHashInvalidError, InviteHashExpiredError) as exc:
            raise NotFoundError("Invite link is invalid or expired") from exc
        except (AuthKeyUnregisteredError, UnauthorizedError) as exc:
            raise self._session_error() from exc
        except ChannelPrivateError as exc:
            raise ExternalServiceError(
                "Channel is private or unavailable for the current Telethon session"
            ) from exc
        except FloodWaitError as exc:
            raise ExternalServiceError(f"Telegram flood wait: retry after {exc.seconds}s") from exc

        parsed: list[ParsedPost] = []
        cutoff = self._build_cutoff(request)
        for message in reversed(messages):
            if not isinstance(message, Message) or message.id is None or message.date is None:
                continue
            published_at = message.date.astimezone(UTC)
            if cutoff is not None and published_at < cutoff:
                continue
            html_text = self._render_html(message)
            media = await self._extract_media(source, message)
            parsed.append(
                ParsedPost(
                    source_title=getattr(entity, "title", source),
                    source=source,
                    telegram_message_id=message.id,
                    published_at=published_at,
                    html_text=html_text,
                    media=media,
                )
            )
        return parsed

    async def _extract_media(self, source: str, message: Message) -> list[MediaAttachment]:
        media = message.media
        if media is None:
            return []

        if isinstance(media, MessageMediaPhoto):
            file_path = await self._download_media(source, message, suffix=".jpg")
            return [MediaAttachment(kind="photo", file_path=file_path)] if file_path else []

        if isinstance(media, MessageMediaDocument):
            mime_type = getattr(getattr(media, "document", None), "mime_type", "") or ""
            if mime_type.startswith("video/"):
                file_path = await self._download_media(source, message, suffix=".mp4")
                return [MediaAttachment(kind="video", file_path=file_path)] if file_path else []

        return []

    async def _download_media(self, source: str, message: Message, suffix: str) -> str | None:
        source_dir = self._media_storage_dir / self._safe_source_dir(source)
        source_dir.mkdir(parents=True, exist_ok=True)
        file_path = source_dir / f"{message.id}{suffix}"
        if file_path.exists():
            return str(file_path)
        downloaded = await self._client.download_media(message, file=file_path.as_posix())
        return str(downloaded) if downloaded else None

    def _render_html(self, message: Message) -> str:
        text = message.message or ""
        entities = message.entities or []
        if text and entities:
            try:
                return html.unparse(text, entities)
            except Exception:
                return self._formatter.format(text, entities)
        if text:
            return text
        return "<i>Пост без текста</i>"

    @staticmethod
    def _safe_source_dir(source: str) -> str:
        cleaned = re.sub(r'[^A-Za-z0-9._-]+', '_', source).strip('._')
        return cleaned or "unknown_source"

    @staticmethod
    def _build_cutoff(request: ParseRequest) -> datetime | None:
        if request.period_hours is None:
            return None
        return datetime.now(UTC) - timedelta(hours=request.period_hours)

    async def _resolve_entity(self, source: str):
        if not source.startswith("invite:"):
            return await self._client.get_entity(source)

        invite_hash = source.split(":", 1)[1]
        invite = await self._client(CheckChatInviteRequest(invite_hash))
        if isinstance(invite, ChatInviteAlready):
            return invite.chat

        try:
            result = await self._client(ImportChatInviteRequest(invite_hash))
        except UserAlreadyParticipantError:
            invite = await self._client(CheckChatInviteRequest(invite_hash))
            if isinstance(invite, ChatInviteAlready):
                return invite.chat
            raise ValidationError("Unable to resolve invite link") from None

        chats = getattr(result, "chats", None) or []
        if chats:
            return chats[0]
        raise ValidationError("Unable to resolve invite link")
