from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities import Channel, ChannelCollection, User
from app.infrastructure.db.models import (
    ChannelModel,
    CollectionModel,
    ProcessedPostModel,
    UserModel,
)


def to_user_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        telegram_user_id=model.telegram_user_id,
        username=model.username,
        full_name=model.full_name,
        is_active=model.is_active,
        created_at=model.created_at,
    )


def to_channel_entity(model: ChannelModel) -> Channel:
    return Channel(
        id=model.id,
        owner_user_id=model.owner_user_id,
        title=model.title,
        source=model.source,
        normalized_source=model.normalized_source,
        telegram_channel_id=model.telegram_channel_id,
        access_hash=model.access_hash,
        created_at=model.created_at,
    )


def to_collection_entity(model: CollectionModel) -> ChannelCollection:
    return ChannelCollection(
        id=model.id,
        owner_user_id=model.owner_user_id,
        name=model.name,
        created_at=model.created_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.telegram_user_id == telegram_user_id)
        )
        model = result.scalar_one_or_none()
        return to_user_entity(model) if model else None

    async def upsert(self, user: User) -> User:
        result = await self._session.execute(
            select(UserModel).where(UserModel.telegram_user_id == user.telegram_user_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = UserModel(
                telegram_user_id=user.telegram_user_id,
                username=user.username,
                full_name=user.full_name,
                is_active=user.is_active,
            )
            self._session.add(model)
            await self._session.flush()
        else:
            model.username = user.username
            model.full_name = user.full_name
            model.is_active = user.is_active
        return to_user_entity(model)


class SqlAlchemyChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, channel: Channel) -> Channel:
        model = ChannelModel(
            owner_user_id=channel.owner_user_id,
            title=channel.title,
            source=channel.source,
            normalized_source=channel.normalized_source,
            telegram_channel_id=channel.telegram_channel_id,
            access_hash=channel.access_hash,
        )
        self._session.add(model)
        await self._session.flush()
        return to_channel_entity(model)

    async def list_for_user(self, owner_user_id: int) -> Sequence[Channel]:
        result = await self._session.execute(
            select(ChannelModel)
            .where(ChannelModel.owner_user_id == owner_user_id)
            .order_by(ChannelModel.id)
        )
        return [to_channel_entity(model) for model in result.scalars().all()]

    async def get_by_id(self, owner_user_id: int, channel_id: int) -> Channel | None:
        result = await self._session.execute(
            select(ChannelModel).where(
                ChannelModel.owner_user_id == owner_user_id,
                ChannelModel.id == channel_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_channel_entity(model) if model else None

    async def get_by_source(self, owner_user_id: int, normalized_source: str) -> Channel | None:
        result = await self._session.execute(
            select(ChannelModel).where(
                ChannelModel.owner_user_id == owner_user_id,
                ChannelModel.normalized_source == normalized_source,
            )
        )
        model = result.scalar_one_or_none()
        return to_channel_entity(model) if model else None

    async def delete(self, owner_user_id: int, channel_id: int) -> bool:
        result = await self._session.execute(
            select(ChannelModel).where(
                ChannelModel.owner_user_id == owner_user_id,
                ChannelModel.id == channel_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True


class SqlAlchemyCollectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, collection: ChannelCollection) -> ChannelCollection:
        model = CollectionModel(owner_user_id=collection.owner_user_id, name=collection.name)
        self._session.add(model)
        await self._session.flush()
        return to_collection_entity(model)

    async def list_for_user(self, owner_user_id: int) -> Sequence[ChannelCollection]:
        result = await self._session.execute(
            select(CollectionModel)
            .where(CollectionModel.owner_user_id == owner_user_id)
            .order_by(CollectionModel.id)
        )
        return [to_collection_entity(model) for model in result.scalars().all()]

    async def get_by_id(self, owner_user_id: int, collection_id: int) -> ChannelCollection | None:
        result = await self._session.execute(
            select(CollectionModel).where(
                CollectionModel.owner_user_id == owner_user_id,
                CollectionModel.id == collection_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_collection_entity(model) if model else None

    async def delete(self, owner_user_id: int, collection_id: int) -> bool:
        result = await self._session.execute(
            select(CollectionModel).where(
                CollectionModel.owner_user_id == owner_user_id,
                CollectionModel.id == collection_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    async def add_channel(self, owner_user_id: int, collection_id: int, channel_id: int) -> None:
        collection_result = await self._session.execute(
            select(CollectionModel)
            .options(selectinload(CollectionModel.channels))
            .where(
                CollectionModel.owner_user_id == owner_user_id,
                CollectionModel.id == collection_id,
            )
        )
        channel_result = await self._session.execute(
            select(ChannelModel).where(
                ChannelModel.owner_user_id == owner_user_id,
                ChannelModel.id == channel_id,
            )
        )
        collection = collection_result.scalar_one()
        channel = channel_result.scalar_one()
        if channel not in collection.channels:
            collection.channels.append(channel)

    async def remove_channel(self, owner_user_id: int, collection_id: int, channel_id: int) -> None:
        collection_result = await self._session.execute(
            select(CollectionModel)
            .options(selectinload(CollectionModel.channels))
            .where(
                CollectionModel.owner_user_id == owner_user_id,
                CollectionModel.id == collection_id,
            )
        )
        collection = collection_result.scalar_one_or_none()
        if collection is None:
            return
        collection.channels = [
            channel for channel in collection.channels if channel.id != channel_id
        ]

    async def list_channels(self, owner_user_id: int, collection_id: int) -> Sequence[Channel]:
        result = await self._session.execute(
            select(CollectionModel)
            .options(selectinload(CollectionModel.channels))
            .where(
                CollectionModel.owner_user_id == owner_user_id,
                CollectionModel.id == collection_id,
            )
        )
        collection = result.scalar_one_or_none()
        if collection is None:
            return []
        return [to_channel_entity(model) for model in collection.channels]


class SqlAlchemyProcessedPostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_processed(
        self, owner_user_id: int, channel_id: int, telegram_message_id: int
    ) -> bool:
        result = await self._session.execute(
            select(ProcessedPostModel.id).where(
                ProcessedPostModel.owner_user_id == owner_user_id,
                ProcessedPostModel.channel_id == channel_id,
                ProcessedPostModel.telegram_message_id == telegram_message_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def mark_processed(
        self, owner_user_id: int, channel_id: int, telegram_message_id: int
    ) -> None:
        self._session.add(
            ProcessedPostModel(
                owner_user_id=owner_user_id,
                channel_id=channel_id,
                telegram_message_id=telegram_message_id,
            )
        )

    async def list_processed_message_ids(
        self,
        owner_user_id: int,
        channel_id: int,
        telegram_message_ids: Sequence[int],
    ) -> set[int]:
        if not telegram_message_ids:
            return set()
        result = await self._session.execute(
            select(ProcessedPostModel.telegram_message_id).where(
                ProcessedPostModel.owner_user_id == owner_user_id,
                ProcessedPostModel.channel_id == channel_id,
                ProcessedPostModel.telegram_message_id.in_(telegram_message_ids),
            )
        )
        return set(result.scalars().all())

    async def mark_many_processed(
        self,
        owner_user_id: int,
        channel_id: int,
        telegram_message_ids: Sequence[int],
    ) -> None:
        if not telegram_message_ids:
            return
        self._session.add_all(
            [
                ProcessedPostModel(
                    owner_user_id=owner_user_id,
                    channel_id=channel_id,
                    telegram_message_id=telegram_message_id,
                )
                for telegram_message_id in telegram_message_ids
            ]
        )
