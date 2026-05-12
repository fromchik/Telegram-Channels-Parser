from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from app.application.services import normalize_channel_source
from app.application.use_cases import AddChannelUseCase, ParseChannelsUseCase
from app.domain.entities import Channel, MediaAttachment, ParsedPost, ParseRequest
from app.domain.exceptions import DuplicateError


class FakeChannelsRepo:
    def __init__(self) -> None:
        self.items: dict[int, Channel] = {}
        self.by_source: dict[str, Channel] = {}
        self._next_id = 1

    async def add(self, channel: Channel) -> Channel:
        payload = asdict(channel)
        payload["id"] = self._next_id
        saved = Channel(**payload)
        self.items[self._next_id] = saved
        self.by_source[saved.normalized_source] = saved
        self._next_id += 1
        return saved

    async def list_for_user(self, owner_user_id: int):
        return [item for item in self.items.values() if item.owner_user_id == owner_user_id]

    async def get_by_id(self, owner_user_id: int, channel_id: int):
        channel = self.items.get(channel_id)
        if channel and channel.owner_user_id == owner_user_id:
            return channel
        return None

    async def get_by_source(self, owner_user_id: int, normalized_source: str):
        channel = self.by_source.get(normalized_source)
        if channel and channel.owner_user_id == owner_user_id:
            return channel
        return None

    async def delete(self, owner_user_id: int, channel_id: int):
        return False


class FakeProcessedRepo:
    def __init__(self) -> None:
        self.keys: set[tuple[int, int, int]] = set()

    async def is_processed(
        self, owner_user_id: int, channel_id: int, telegram_message_id: int
    ) -> bool:
        return (owner_user_id, channel_id, telegram_message_id) in self.keys

    async def mark_processed(
        self, owner_user_id: int, channel_id: int, telegram_message_id: int
    ) -> None:
        self.keys.add((owner_user_id, channel_id, telegram_message_id))

    async def list_processed_message_ids(
        self,
        owner_user_id: int,
        channel_id: int,
        telegram_message_ids,
    ) -> set[int]:
        return {
            telegram_message_id
            for telegram_message_id in telegram_message_ids
            if (owner_user_id, channel_id, telegram_message_id) in self.keys
        }

    async def mark_many_processed(
        self,
        owner_user_id: int,
        channel_id: int,
        telegram_message_ids,
    ) -> None:
        for telegram_message_id in telegram_message_ids:
            self.keys.add((owner_user_id, channel_id, telegram_message_id))


class FakeUoW(AbstractAsyncContextManager):
    def __init__(self) -> None:
        self.channels = FakeChannelsRepo()
        self.processed_posts = FakeProcessedRepo()
        self.users = None
        self.collections = None
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


class FakeGateway:
    async def resolve_channel(self, source: str):
        return ("Example Channel", 1001, 2002)

    async def fetch_posts(self, source: str, request: ParseRequest):
        return [
            ParsedPost(
                source_title="Example Channel",
                source=source,
                telegram_message_id=1,
                published_at=datetime.now(UTC),
                html_text="<b>Test</b>",
                media=[MediaAttachment(kind="photo", file_path="C:/tmp/test.jpg")],
            )
        ]

@pytest.mark.asyncio
async def test_add_channel_use_case_rejects_duplicates_async() -> None:
    uow = FakeUoW()
    use_case = AddChannelUseCase(lambda: uow, FakeGateway())

    await use_case.execute(1, "@example")
    with pytest.raises(DuplicateError):
        await use_case.execute(1, "https://t.me/example")


@pytest.mark.asyncio
async def test_parse_use_case_marks_duplicates() -> None:
    uow = FakeUoW()
    channel = await uow.channels.add(
        Channel(
            id=None,
            owner_user_id=1,
            title="Example Channel",
            source="@example",
            normalized_source="example",
        )
    )
    use_case = ParseChannelsUseCase(lambda: uow, FakeGateway())

    first = await use_case.execute(1, [channel], ParseRequest(limit=10, period_hours=24))
    second = await use_case.execute(1, [channel], ParseRequest(limit=10, period_hours=24))

    assert len(first.posts) == 1
    assert second.skipped_duplicates == 1
    assert first.posts[0].media[0].kind == "photo"


def test_normalize_channel_source_accepts_telegram_link() -> None:
    assert normalize_channel_source("https://t.me/example_channel/") == "example_channel"
    assert normalize_channel_source("https://t.me/s/example_channel?single") == "example_channel"
    assert normalize_channel_source("https://t.me/+Q46QCA8BwsxhNDIy") == "invite:Q46QCA8BwsxhNDIy"
    assert (
        normalize_channel_source("https://t.me/joinchat/Q46QCA8BwsxhNDIy")
        == "invite:Q46QCA8BwsxhNDIy"
    )
    assert normalize_channel_source("+Q46QCA8BwsxhNDIy") == "invite:Q46QCA8BwsxhNDIy"
