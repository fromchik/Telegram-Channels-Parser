from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.repositories import (
    SqlAlchemyChannelRepository,
    SqlAlchemyCollectionRepository,
    SqlAlchemyProcessedPostRepository,
    SqlAlchemyUserRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        self.users = SqlAlchemyUserRepository(self.session)
        self.channels = SqlAlchemyChannelRepository(self.session)
        self.collections = SqlAlchemyCollectionRepository(self.session)
        self.processed_posts = SqlAlchemyProcessedPostRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc:
            await self.rollback()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
