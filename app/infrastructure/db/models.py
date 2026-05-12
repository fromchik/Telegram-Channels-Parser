from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


collection_channels = Table(
    "collection_channels",
    Base.metadata,
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("channel_id", ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True),
)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    channels: Mapped[list[ChannelModel]] = relationship(back_populates="owner")
    collections: Mapped[list[CollectionModel]] = relationship(back_populates="owner")


class ChannelModel(Base):
    __tablename__ = "channels"
    __table_args__ = (UniqueConstraint("owner_user_id", "normalized_source", name="uq_channels_owner_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(255))
    normalized_source: Mapped[str] = mapped_column(String(255))
    telegram_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    access_hash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    owner: Mapped[UserModel] = relationship(back_populates="channels")
    collections: Mapped[list[CollectionModel]] = relationship(
        secondary=collection_channels,
        back_populates="channels",
    )


class CollectionModel(Base):
    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("owner_user_id", "name", name="uq_collections_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    owner: Mapped[UserModel] = relationship(back_populates="collections")
    channels: Mapped[list[ChannelModel]] = relationship(
        secondary=collection_channels,
        back_populates="collections",
    )


class ProcessedPostModel(Base):
    __tablename__ = "processed_posts"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "channel_id",
            "telegram_message_id",
            name="uq_processed_posts_owner_channel_message",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    telegram_message_id: Mapped[int] = mapped_column(BigInteger)
    parsed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
