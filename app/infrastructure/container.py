from __future__ import annotations

from contextlib import asynccontextmanager

from app.application.ai import AiPostProcessor
from app.application.auth import AccessPolicy
from app.application.use_cases import (
    AddChannelSourceToCollectionUseCase,
    AddChannelToCollectionUseCase,
    AddChannelUseCase,
    CreateCollectionUseCase,
    DeleteChannelUseCase,
    DeleteCollectionUseCase,
    EnsureActorUseCase,
    ListChannelsUseCase,
    ListCollectionChannelsUseCase,
    ListCollectionsUseCase,
    ParseChannelsUseCase,
    RemoveChannelFromCollectionUseCase,
)
from app.infrastructure.config import Settings
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.openrouter import OpenRouterClient
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.telegram.formatter import TelegramHtmlFormatter
from app.infrastructure.telegram.gateway import TelethonGateway


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_engine(settings.normalized_database_url)
        self.session_factory = create_session_factory(self.engine)
        self.formatter = TelegramHtmlFormatter()
        self.telegram_gateway = TelethonGateway(
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
            session_string=settings.telethon_session_string,
            session_file=settings.normalized_telethon_session_file,
            media_storage_dir=settings.normalized_media_storage_dir,
            formatter=self.formatter,
            flood_sleep_threshold=settings.flood_sleep_threshold,
        )
        self.openrouter_client = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
        )
        self.ai_post_processor = AiPostProcessor(self.openrouter_client)
        self.access_policy = AccessPolicy(settings.bot_owner_ids)

        self.ensure_actor = EnsureActorUseCase(self.uow_factory, self.access_policy)
        self.add_channel = AddChannelUseCase(self.uow_factory, self.telegram_gateway)
        self.list_channels = ListChannelsUseCase(self.uow_factory)
        self.delete_channel = DeleteChannelUseCase(self.uow_factory)
        self.create_collection = CreateCollectionUseCase(self.uow_factory)
        self.list_collections = ListCollectionsUseCase(self.uow_factory)
        self.delete_collection = DeleteCollectionUseCase(self.uow_factory)
        self.add_channel_to_collection = AddChannelToCollectionUseCase(self.uow_factory)
        self.add_channel_source_to_collection = AddChannelSourceToCollectionUseCase(
            self.uow_factory, self.telegram_gateway
        )
        self.remove_channel_from_collection = RemoveChannelFromCollectionUseCase(self.uow_factory)
        self.list_collection_channels = ListCollectionChannelsUseCase(self.uow_factory)
        self.parse_channels = ParseChannelsUseCase(self.uow_factory, self.telegram_gateway)

    def uow_factory(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    @asynccontextmanager
    async def lifespan(self):
        await self.telegram_gateway.connect()
        try:
            yield self
        finally:
            await self.telegram_gateway.disconnect()
            await self.engine.dispose()


def build_container(settings: Settings) -> Container:
    return Container(settings)
