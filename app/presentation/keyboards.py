from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.entities import Channel, ChannelCollection
from app.presentation.callbacks import MenuCallback


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Парсить один канал", callback_data=MenuCallback(action="channels").pack())],
            [InlineKeyboardButton(text="Коллекции каналов", callback_data=MenuCallback(action="collections").pack())],
            [
                InlineKeyboardButton(text="Настройки", callback_data=MenuCallback(action="settings").pack()),
                InlineKeyboardButton(text="Помощь", callback_data=MenuCallback(action="help").pack()),
            ],
        ]
    )


def channels_keyboard(channels: list[Channel]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Добавить канал", callback_data=MenuCallback(action="channel_add").pack())]]
    for channel in channels:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Открыть: {channel.title}",
                    callback_data=MenuCallback(action="channel_open", item_id=channel.id).pack(),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="← В меню", callback_data=MenuCallback(action="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_detail_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Запустить парсинг", callback_data=MenuCallback(action="parse_channel", item_id=channel_id).pack())],
            [InlineKeyboardButton(text="Удалить канал", callback_data=MenuCallback(action="channel_delete_confirm", item_id=channel_id).pack())],
            [InlineKeyboardButton(text="← Назад", callback_data=MenuCallback(action="channels").pack())],
        ]
    )


def confirm_delete_keyboard(confirm_action: str, item_id: int) -> InlineKeyboardMarkup:
    back_action = "channels" if confirm_action == "channel_delete" else "collection_open"
    back_item_id = item_id if confirm_action == "collection_delete" else None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, удалить", callback_data=MenuCallback(action=confirm_action, item_id=item_id).pack())],
            [InlineKeyboardButton(text="← Отмена", callback_data=MenuCallback(action=back_action, item_id=back_item_id).pack())],
        ]
    )


def collections_keyboard(collections: list[ChannelCollection]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Создать коллекцию", callback_data=MenuCallback(action="collection_add").pack())]]
    for collection in collections:
        rows.append(
            [
                InlineKeyboardButton(
                    text=collection.name,
                    callback_data=MenuCallback(action="collection_open", item_id=collection.id).pack(),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="← В меню", callback_data=MenuCallback(action="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def collection_detail_keyboard(collection_id: int, channels: list[Channel]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Добавить в коллекцию",
                callback_data=MenuCallback(action="collection_link_channel", item_id=collection_id).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="Запустить парсинг коллекции",
                callback_data=MenuCallback(action="parse_collection", item_id=collection_id).pack(),
            )
        ],
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="Удалить коллекцию",
                callback_data=MenuCallback(action="collection_delete_confirm", item_id=collection_id).pack(),
            )
        ]
    )
    for channel in channels:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Убрать: {channel.title}",
                    callback_data=MenuCallback(
                        action="collection_unlink_channel", item_id=collection_id, extra=str(channel.id)
                    ).pack(),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="← Назад", callback_data=MenuCallback(action="collections").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_limit_keyboard(source_action: str, item_id: int | None = None) -> InlineKeyboardMarkup:
    limits = [5, 10, 20, 50]
    back_callback = _parse_back_callback(source_action, item_id)
    rows = [
        [
            InlineKeyboardButton(
                text=f"{limit} постов",
                callback_data=MenuCallback(action="parse_limit", item_id=item_id, extra=f"{source_action}|{limit}").pack(),
            )
            for limit in limits[:2]
        ],
        [
            InlineKeyboardButton(
                text=f"{limit} постов",
                callback_data=MenuCallback(action="parse_limit", item_id=item_id, extra=f"{source_action}|{limit}").pack(),
            )
            for limit in limits[2:]
        ],
        [InlineKeyboardButton(text="← Назад", callback_data=back_callback)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_period_keyboard(source_action: str, limit: int, item_id: int | None = None) -> InlineKeyboardMarkup:
    options = [
        ("За 24 часа", "24"),
        ("За 3 дня", "72"),
        ("За 7 дней", "168"),
        ("Без периода", "none"),
    ]
    rows = []
    for label, value in options:
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=MenuCallback(
                        action="parse_period",
                        item_id=item_id,
                        extra=f"{source_action}|{limit}|{value}",
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="← Назад",
                callback_data=MenuCallback(action="parse_select_limit", item_id=item_id, extra=source_action).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _parse_back_callback(source_action: str, item_id: int | None) -> str:
    if source_action == "parse_channel":
        return MenuCallback(action="channels").pack()
    if source_action == "parse_collection":
        return MenuCallback(action="collection_open", item_id=item_id).pack()
    return MenuCallback(action="main").pack()


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="← В меню", callback_data=MenuCallback(action="main").pack())]]
    )


def ai_post_keyboard(post_key: str, can_publish: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Обработать через ИИ", callback_data=MenuCallback(action="ai_post", extra=post_key).pack())]]
    if can_publish:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Опубликовать в канал",
                    callback_data=MenuCallback(action="publish_post", extra=post_key).pack(),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="← В меню", callback_data=MenuCallback(action="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)
