from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from app.application.auth import AccessPolicy
from app.application.dto import ActorDTO, MediaAttachmentDTO, ParsedPostDTO, ParseResultDTO
from app.application.services import filter_posts_by_period, normalize_channel_source
from app.domain.entities import Channel, ChannelCollection, ParseRequest, User
from app.domain.exceptions import DuplicateError, NotFoundError, ValidationError
from app.domain.ports import TelegramSourceGateway


class EnsureActorUseCase:
    def __init__(self, uow_factory, access_policy: AccessPolicy) -> None:
        self._uow_factory = uow_factory
        self._access_policy = access_policy

    async def execute(self, actor: ActorDTO) -> User:
        self._access_policy.ensure_allowed(actor.telegram_user_id)
        async with self._uow_factory() as uow:
            user = await uow.users.upsert(
                User(
                    id=None,
                    telegram_user_id=actor.telegram_user_id,
                    username=actor.username,
                    full_name=actor.full_name,
                )
            )
            await uow.commit()
            return user


class AddChannelUseCase:
    def __init__(self, uow_factory, gateway: TelegramSourceGateway) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway

    async def execute(self, owner_user_id: int, source: str) -> Channel:
        normalized = normalize_channel_source(source)
        if not normalized:
            raise ValidationError("Channel source is empty")

        title, telegram_channel_id, access_hash = await self._gateway.resolve_channel(normalized)
        async with self._uow_factory() as uow:
            existing = await uow.channels.get_by_source(owner_user_id, normalized)
            if existing is not None:
                raise DuplicateError("Channel already added")

            channel = await uow.channels.add(
                Channel(
                    id=None,
                    owner_user_id=owner_user_id,
                    title=title,
                    source=source.strip(),
                    normalized_source=normalized,
                    telegram_channel_id=telegram_channel_id,
                    access_hash=access_hash,
                )
            )
            await uow.commit()
            return channel


class ListChannelsUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, owner_user_id: int) -> Sequence[Channel]:
        async with self._uow_factory() as uow:
            return await uow.channels.list_for_user(owner_user_id)


class DeleteChannelUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, owner_user_id: int, channel_id: int) -> None:
        async with self._uow_factory() as uow:
            deleted = await uow.channels.delete(owner_user_id, channel_id)
            if not deleted:
                raise NotFoundError("Channel not found")
            await uow.commit()


class CreateCollectionUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, owner_user_id: int, name: str) -> ChannelCollection:
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("Collection name is empty")

        async with self._uow_factory() as uow:
            collection = await uow.collections.create(
                ChannelCollection(id=None, owner_user_id=owner_user_id, name=clean_name)
            )
            await uow.commit()
            return collection


class ListCollectionsUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, owner_user_id: int) -> Sequence[ChannelCollection]:
        async with self._uow_factory() as uow:
            return await uow.collections.list_for_user(owner_user_id)


class DeleteCollectionUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, owner_user_id: int, collection_id: int) -> None:
        async with self._uow_factory() as uow:
            deleted = await uow.collections.delete(owner_user_id, collection_id)
            if not deleted:
                raise NotFoundError("Collection not found")
            await uow.commit()


class AddChannelToCollectionUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, owner_user_id: int, collection_id: int, channel_id: int) -> None:
        async with self._uow_factory() as uow:
            collection = await uow.collections.get_by_id(owner_user_id, collection_id)
            channel = await uow.channels.get_by_id(owner_user_id, channel_id)
            if collection is None:
                raise NotFoundError("Collection not found")
            if channel is None:
                raise NotFoundError("Channel not found")
            await uow.collections.add_channel(owner_user_id, collection_id, channel_id)
            await uow.commit()


class AddChannelSourceToCollectionUseCase:
    def __init__(self, uow_factory, gateway: TelegramSourceGateway) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway

    async def execute(self, owner_user_id: int, collection_id: int, source: str) -> Channel:
        normalized = normalize_channel_source(source)
        if not normalized:
            raise ValidationError("Channel source is empty")

        title, telegram_channel_id, access_hash = await self._gateway.resolve_channel(normalized)
        async with self._uow_factory() as uow:
            collection = await uow.collections.get_by_id(owner_user_id, collection_id)
            if collection is None:
                raise NotFoundError("Collection not found")

            channel = await uow.channels.get_by_source(owner_user_id, normalized)
            if channel is None:
                channel = await uow.channels.add(
                    Channel(
                        id=None,
                        owner_user_id=owner_user_id,
                        title=title,
                        source=source.strip(),
                        normalized_source=normalized,
                        telegram_channel_id=telegram_channel_id,
                        access_hash=access_hash,
                    )
                )

            await uow.collections.add_channel(owner_user_id, collection_id, channel.id)
            await uow.commit()
            return channel


class RemoveChannelFromCollectionUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, owner_user_id: int, collection_id: int, channel_id: int) -> None:
        async with self._uow_factory() as uow:
            await uow.collections.remove_channel(owner_user_id, collection_id, channel_id)
            await uow.commit()


class ListCollectionChannelsUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, owner_user_id: int, collection_id: int) -> Sequence[Channel]:
        async with self._uow_factory() as uow:
            return await uow.collections.list_channels(owner_user_id, collection_id)


class ParseChannelsUseCase:
    def __init__(self, uow_factory, gateway: TelegramSourceGateway) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway

    async def execute(
        self,
        owner_user_id: int,
        channels: Sequence[Channel],
        request: ParseRequest,
        progress: Callable[[int, int, Channel, str], Awaitable[None]] | None = None,
    ) -> ParseResultDTO:
        posts: list[ParsedPostDTO] = []
        skipped_duplicates = 0
        errors: list[str] = []

        total_channels = len(channels)
        for index, channel in enumerate(channels, start=1):
            try:
                if progress is not None:
                    await progress(index, total_channels, channel, "reading")
                fetched = list(await self._gateway.fetch_posts(channel.normalized_source, request))
                fetched = filter_posts_by_period(fetched, request)
                if progress is not None:
                    await progress(index, total_channels, channel, "saving")
                async with self._uow_factory() as uow:
                    fetched_ids = [post.telegram_message_id for post in fetched]
                    processed_ids = await uow.processed_posts.list_processed_message_ids(
                        owner_user_id, channel.id, fetched_ids
                    )
                    new_posts = [
                        post for post in fetched if post.telegram_message_id not in processed_ids
                    ]
                    skipped_duplicates += len(fetched) - len(new_posts)
                    await uow.processed_posts.mark_many_processed(
                        owner_user_id,
                        channel.id,
                        [post.telegram_message_id for post in new_posts],
                    )
                    for post in new_posts:
                        posts.append(
                            ParsedPostDTO(
                                source_title=post.source_title,
                                source=post.source,
                                telegram_message_id=post.telegram_message_id,
                                published_at=post.published_at,
                                html_text=post.html_text,
                                media=[
                                    MediaAttachmentDTO(kind=item.kind, file_path=item.file_path)
                                    for item in post.media
                                ],
                            )
                        )
                    await uow.commit()
            except Exception as exc:
                errors.append(f"{channel.title}: {exc}")
            finally:
                if progress is not None:
                    await progress(index, total_channels, channel, "done")

        posts.sort(key=lambda item: item.published_at)
        return ParseResultDTO(posts=posts, skipped_duplicates=skipped_duplicates, errors=errors)
