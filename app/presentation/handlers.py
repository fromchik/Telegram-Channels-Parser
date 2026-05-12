from __future__ import annotations

import asyncio
from html import escape

from aiogram import Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User as TelegramUser,
)

from app.application.ai import AiPostInput
from app.application.html_sanitizer import sanitize_telegram_html
from app.application.dto import ActorDTO
from app.domain.entities import ParseRequest
from app.domain.exceptions import AccessDeniedError, DomainError, ExternalServiceError
from app.infrastructure.container import Container
from app.presentation.callbacks import MenuCallback
from app.presentation.keyboards import (
    back_to_menu_keyboard,
    ai_post_keyboard,
    channel_detail_keyboard,
    channels_keyboard,
    collection_detail_keyboard,
    confirm_delete_keyboard,
    collections_keyboard,
    main_menu_keyboard,
    parse_limit_keyboard,
    parse_period_keyboard,
)
from app.presentation.messages import HELP_MESSAGE, SETTINGS_MESSAGE, START_MESSAGE
from app.presentation.states import ChannelState, CollectionState


def register_handlers(dispatcher: Dispatcher, container: Container) -> None:
    router = Router()
    parsed_post_cache: dict[str, AiPostInput] = {}

    def clean(value: object) -> str:
        return escape(str(value), quote=False)

    async def ensure_actor(telegram_user: TelegramUser) -> int:
        actor = ActorDTO(
            telegram_user_id=telegram_user.id,
            username=telegram_user.username,
            full_name=telegram_user.full_name,
        )
        user = await container.ensure_actor.execute(actor)
        return user.id

    async def render_main(target: Message | CallbackQuery) -> None:
        text = START_MESSAGE
        markup = main_menu_keyboard()
        if isinstance(target, Message):
            await target.answer(text, reply_markup=markup)
        else:
            await safe_edit(target, text, markup)

    async def render_channels(callback: CallbackQuery, user_id: int, note: str | None = None) -> None:
        channels = list(await container.list_channels.execute(user_id))
        body = ["<b>Каналы</b>", "Добавь источник, открой его карточку и запусти парсинг в пару кликов."]
        if note:
            body.append(f"<i>{clean(note)}</i>")
        if channels:
            body.append(f"Подключено каналов: <b>{len(channels)}</b>\nВыбери канал, чтобы открыть действия.")
        else:
            body.append("Список пока пуст. Нажми <b>Добавить канал</b> и отправь username или ссылку.")
        await safe_edit(callback, "\n\n".join(body), channels_keyboard(channels))

    async def render_collection(callback: CallbackQuery, user_id: int, collection_id: int, note: str | None = None) -> None:
        collections = await container.list_collections.execute(user_id)
        collection = next((item for item in collections if item.id == collection_id), None)
        channels = list(await container.list_collection_channels.execute(user_id, collection_id))
        text = [f"<b>Коллекция: {clean(collection.name if collection else collection_id)}</b>"]
        if note:
            text.append(f"<i>{clean(note)}</i>")
        if channels:
            text.append(f"Источников внутри: <b>{len(channels)}</b>")
            text.append("Каналы в запуске:")
            text.extend(f"• {clean(channel.title)} <code>@{clean(channel.normalized_source)}</code>" for channel in channels)
        else:
            text.append("Коллекция пока пустая. Добавь первый канал по ссылке, invite-ссылке или <code>@username</code>.")
        await safe_edit(callback, "\n".join(text), collection_detail_keyboard(collection_id, channels))

    @router.message(CommandStart())
    async def start(message: Message, state: FSMContext) -> None:
        try:
            await ensure_actor(message.from_user)
            await state.clear()
            await render_main(message)
        except AccessDeniedError:
            await message.answer("Доступ запрещен. Добавь свой Telegram ID в BOT_OWNER_IDS.")

    @router.message(Command("publish_debug"))
    async def publish_debug(message: Message) -> None:
        try:
            await ensure_actor(message.from_user)
        except AccessDeniedError:
            await message.answer("Доступ запрещен.")
            return

        target_channel = container.settings.publish_channel_id.strip()
        if not target_channel:
            await message.answer(
                "<b>Publish Debug</b>\n"
                "<code>PUBLISH_CHANNEL_ID</code> не настроен.\n"
                "Укажи username публичного канала или numeric id приватного канала вида <code>-100...</code>."
            )
            return

        bot = message.bot
        me = await bot.get_me()
        lines = [
            "<b>Publish Debug</b>",
            f"Настроенный target: <code>{target_channel}</code>",
            f"Бот: <code>@{me.username or me.id}</code>",
        ]

        try:
            chat = await bot.get_chat(target_channel)
            lines.extend(
                [
                    f"Найден чат: <b>{getattr(chat, 'title', 'Без названия')}</b>",
                    f"chat_id: <code>{chat.id}</code>",
                    f"type: <code>{chat.type}</code>",
                ]
            )
        except TelegramBadRequest as exc:
            lines.append(f"Ошибка getChat: <code>{clean(exc)}</code>")
            lines.append("Проверь, что бот добавлен в канал и <code>PUBLISH_CHANNEL_ID</code> указан правильно.")
            await message.answer("\n".join(lines))
            return

        try:
            member = await bot.get_chat_member(target_channel, me.id)
            lines.extend(
                [
                    f"Статус бота в канале: <code>{member.status}</code>",
                    f"Может публиковать: <code>{'yes' if member.status in {'administrator', 'creator'} else 'no'}</code>",
                ]
            )
        except TelegramBadRequest as exc:
            lines.append(f"Ошибка getChatMember: <code>{clean(exc)}</code>")

        lines.append("Если это приватный канал, используй numeric id вида <code>-100...</code>, а не invite-ссылку.")
        await message.answer("\n".join(lines))

    @router.callback_query(MenuCallback.filter(F.action == "main"))
    async def main_menu(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            await ensure_actor(callback.from_user)
            await state.clear()
            await render_main(callback)
            await callback.answer()
        except AccessDeniedError:
            await callback.answer("Доступ запрещен", show_alert=True)

    @router.callback_query(MenuCallback.filter(F.action == "help"))
    async def help_menu(callback: CallbackQuery) -> None:
        try:
            await ensure_actor(callback.from_user)
            await safe_edit(callback, HELP_MESSAGE, back_to_menu_keyboard())
            await callback.answer()
        except AccessDeniedError:
            await callback.answer("Доступ запрещен", show_alert=True)

    @router.callback_query(MenuCallback.filter(F.action == "settings"))
    async def settings_menu(callback: CallbackQuery) -> None:
        try:
            await ensure_actor(callback.from_user)
            await safe_edit(callback, SETTINGS_MESSAGE, back_to_menu_keyboard())
            await callback.answer()
        except AccessDeniedError:
            await callback.answer("Доступ запрещен", show_alert=True)

    @router.callback_query(MenuCallback.filter(F.action == "channels"))
    async def channels_menu(callback: CallbackQuery) -> None:
        try:
            user_id = await ensure_actor(callback.from_user)
            await render_channels(callback, user_id)
            await callback.answer()
        except AccessDeniedError:
            await callback.answer("Доступ запрещен", show_alert=True)

    @router.callback_query(MenuCallback.filter(F.action == "channel_open"))
    async def channel_open(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        user_id = await ensure_actor(callback.from_user)
        channels = list(await container.list_channels.execute(user_id))
        channel = next((item for item in channels if item.id == callback_data.item_id), None)
        if channel is None:
            await callback.answer("Канал не найден", show_alert=True)
            return
        text = (
            f"<b>{clean(channel.title)}</b>\n"
            f"Источник: <code>@{clean(channel.normalized_source)}</code>\n\n"
            "Можно запустить парсинг, выбрать лимит и период поиска, либо удалить источник из списка."
        )
        await safe_edit(callback, text, channel_detail_keyboard(channel.id))
        await callback.answer()

    @router.callback_query(MenuCallback.filter(F.action == "channel_add"))
    async def add_channel_prompt(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(ChannelState.waiting_for_source)
        await safe_edit(
            callback,
            "Отправь username канала, <code>@username</code>, публичную ссылку <code>https://t.me/channel_name</code> или invite-ссылку <code>https://t.me/+...</code>.",
            back_to_menu_keyboard(),
        )
        await callback.answer()


    @router.message(ChannelState.waiting_for_source)
    async def add_channel(message: Message, state: FSMContext) -> None:
        try:
            user_id = await ensure_actor(message.from_user)
            channel = await container.add_channel.execute(user_id, message.text or "")
            await state.clear()
            channels = list(await container.list_channels.execute(user_id))
            await message.answer(
                (
                    f"<b>Канал добавлен</b>\n"
                    f"{clean(channel.title)}\n"
                    f"Источник: <code>@{clean(channel.normalized_source)}</code>\n\n"
                    "Теперь его можно парсить отдельно или добавить в коллекцию."
                ),
                reply_markup=channels_keyboard(channels),
            )
        except DomainError as exc:
            await message.answer(f"Не удалось добавить канал: {exc}")


    @router.callback_query(MenuCallback.filter(F.action == "channel_delete"))
    async def delete_channel(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        try:
            user_id = await ensure_actor(callback.from_user)
            await container.delete_channel.execute(user_id, callback_data.item_id)
            await render_channels(callback, user_id, note="Канал удален.")
        except DomainError as exc:
            await callback.answer(str(exc), show_alert=True)
        else:
            await callback.answer()

    @router.callback_query(MenuCallback.filter(F.action == "channel_delete_confirm"))
    async def delete_channel_confirm(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        user_id = await ensure_actor(callback.from_user)
        channels = list(await container.list_channels.execute(user_id))
        channel = next((item for item in channels if item.id == callback_data.item_id), None)
        if channel is None:
            await callback.answer("Канал не найден", show_alert=True)
            return
        await safe_edit(
            callback,
            f"<b>Удалить канал?</b>\n{clean(channel.title)}\n\nОн исчезнет из списка источников, но уже отправленные результаты останутся в чате.",
            confirm_delete_keyboard("channel_delete", channel.id),
        )
        await callback.answer()

    @router.callback_query(MenuCallback.filter(F.action == "collections"))
    async def collections_menu(callback: CallbackQuery) -> None:
        try:
            user_id = await ensure_actor(callback.from_user)
            collections = list(await container.list_collections.execute(user_id))
            body = "<b>Коллекции</b>\nСобирай несколько каналов в один запуск и парси их общей пачкой."
            if not collections:
                body = "<b>Коллекции</b>\nКоллекций пока нет. Создай первую, чтобы запускать парсинг сразу по нескольким каналам."
            await safe_edit(callback, body, collections_keyboard(collections))
            await callback.answer()
        except AccessDeniedError:
            await callback.answer("Доступ запрещен", show_alert=True)

    @router.callback_query(MenuCallback.filter(F.action == "collection_add"))
    async def collection_add_prompt(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(CollectionState.waiting_for_name)
        await safe_edit(callback, "Отправь короткое название новой коллекции.", back_to_menu_keyboard())
        await callback.answer()

    @router.message(CollectionState.waiting_for_name)
    async def create_collection(message: Message, state: FSMContext) -> None:
        try:
            user_id = await ensure_actor(message.from_user)
            collection = await container.create_collection.execute(user_id, message.text or "")
            await state.clear()
            channels = list(await container.list_collection_channels.execute(user_id, collection.id))
            await message.answer(
                f"<b>Коллекция создана</b>\n{clean(collection.name)}\n\nТеперь можно добавить каналы и запускать их одной подборкой.",
                reply_markup=collection_detail_keyboard(collection.id, channels),
            )
        except DomainError as exc:
            await message.answer(f"Не удалось создать коллекцию: {exc}")

    @router.callback_query(MenuCallback.filter(F.action == "collection_open"))
    async def collection_open(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        user_id = await ensure_actor(callback.from_user)
        await render_collection(callback, user_id, callback_data.item_id)
        await callback.answer()

    @router.callback_query(MenuCallback.filter(F.action == "collection_link_channel"))
    async def collection_link_prompt(callback: CallbackQuery, callback_data: MenuCallback, state: FSMContext) -> None:
        await state.set_state(CollectionState.waiting_for_channel_source)
        await state.update_data(collection_id=callback_data.item_id)
        await safe_edit(
            callback,
            "Отправь ссылку на канал, invite-ссылку <code>https://t.me/+...</code> или username вида <code>@channel_name</code>. Я добавлю источник в эту коллекцию.",
            back_to_menu_keyboard(),
        )
        await callback.answer()

    @router.message(CollectionState.waiting_for_channel_source)
    async def collection_add_channel_source(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        try:
            collection_id = int(data["collection_id"])
            user_id = await ensure_actor(message.from_user)
            channel = await container.add_channel_source_to_collection.execute(
                user_id, collection_id, message.text or ""
            )
            await state.clear()
            channels = list(await container.list_collection_channels.execute(user_id, collection_id))
            lines = [
                f"<b>Канал добавлен в коллекцию</b>\n{clean(channel.title)}",
                "Текущий список источников:",
            ]
            lines.extend(f"• {clean(item.title)} <code>@{clean(item.normalized_source)}</code>" for item in channels)
            await message.answer("\n".join(lines), reply_markup=collection_detail_keyboard(collection_id, channels))
        except (ValueError, KeyError):
            await message.answer("Не удалось определить коллекцию.", reply_markup=back_to_menu_keyboard())
        except DomainError as exc:
            await message.answer(f"Не удалось добавить канал в коллекцию: {exc}")

    @router.callback_query(MenuCallback.filter(F.action == "collection_unlink_channel"))
    async def collection_unlink_channel(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        try:
            user_id = await ensure_actor(callback.from_user)
            channel_id = int(callback_data.extra)
            await container.remove_channel_from_collection.execute(user_id, callback_data.item_id, channel_id)
            await render_collection(callback, user_id, callback_data.item_id, note="Канал удален из коллекции.")
            await callback.answer()
        except (TypeError, ValueError):
            await callback.answer("Некорректный канал", show_alert=True)
        except DomainError as exc:
            await callback.answer(str(exc), show_alert=True)

    @router.callback_query(MenuCallback.filter(F.action == "collection_delete"))
    async def collection_delete(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        user_id = await ensure_actor(callback.from_user)
        await container.delete_collection.execute(user_id, callback_data.item_id)
        collections = list(await container.list_collections.execute(user_id))
        await safe_edit(callback, "Коллекция удалена.", collections_keyboard(collections))
        await callback.answer()

    @router.callback_query(MenuCallback.filter(F.action == "collection_delete_confirm"))
    async def collection_delete_confirm(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        user_id = await ensure_actor(callback.from_user)
        collections = await container.list_collections.execute(user_id)
        collection = next((item for item in collections if item.id == callback_data.item_id), None)
        if collection is None:
            await callback.answer("Коллекция не найдена", show_alert=True)
            return
        await safe_edit(
            callback,
            f"<b>Удалить коллекцию?</b>\n{clean(collection.name)}\n\nКаналы как источники сохранятся, удалится только сама подборка.",
            confirm_delete_keyboard("collection_delete", collection.id),
        )
        await callback.answer()

    @router.callback_query(MenuCallback.filter(F.action.in_({"parse_channel", "parse_collection", "parse_select_limit"})))
    async def parse_select_limit(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        source_action = callback_data.action
        item_id = callback_data.item_id
        if source_action == "parse_select_limit":
            source_action = callback_data.extra
        await safe_edit(
            callback,
            "<b>Шаг 1/2</b>\nВыбери, сколько последних постов смотреть.",
            parse_limit_keyboard(source_action, item_id),
        )
        await callback.answer()

    @router.callback_query(MenuCallback.filter(F.action == "parse_limit"))
    async def parse_select_period(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        try:
            source_action, limit_raw = (callback_data.extra or "").split("|", 1)
            limit = int(limit_raw)
        except (ValueError, TypeError):
            await callback.answer("Некорректный лимит", show_alert=True)
            return

        await safe_edit(
            callback,
            f"<b>Шаг 2/2</b>\nЛимит: <b>{limit}</b>. Теперь выбери период.",
            parse_period_keyboard(source_action, limit, callback_data.item_id),
        )
        await callback.answer()

    @router.callback_query(MenuCallback.filter(F.action == "parse_period"))
    async def run_parse(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        user_id = await ensure_actor(callback.from_user)
        try:
            source_action, limit_raw, period_raw = (callback_data.extra or "").split("|", 2)
            limit = int(limit_raw)
            period_hours = None if period_raw == "none" else int(period_raw)
        except (ValueError, TypeError):
            await callback.answer("Некорректные параметры парсинга", show_alert=True)
            return
        request = ParseRequest(limit=limit, period_hours=period_hours)

        if source_action == "parse_channel":
            all_channels = list(await container.list_channels.execute(user_id))
            channels = [channel for channel in all_channels if channel.id == callback_data.item_id]
        else:
            channels = list(await container.list_collection_channels.execute(user_id, callback_data.item_id))

        if not channels:
            await callback.answer("Нет каналов для парсинга", show_alert=True)
            return

        await callback.answer("Парсинг запущен...")
        period_label = "без ограничения по времени" if period_hours is None else f"за последние {period_hours} ч"

        async def update_parse_status(text: str) -> None:
            try:
                await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard())
            except TelegramBadRequest:
                pass

        async def track_channel_progress(index: int, total: int, channel, phase: str) -> None:
            phase_labels = {
                "reading": "читаю посты и медиа",
                "saving": "проверяю дубли и сохраняю результат",
                "done": "источник обработан",
            }
            await update_parse_status(
                "\n".join(
                    [
                        "<b>Парсинг запущен</b>",
                        progress_bar(index, total),
                        f"Источник: <b>{clean(channel.title)}</b>",
                        f"Статус: {phase_labels.get(phase, 'работаю')}",
                        "",
                        f"Лимит: <b>{limit}</b>",
                        f"Период: <b>{period_label}</b>",
                    ]
                )
            )

        await safe_edit(
            callback,
            "\n".join(
                [
                    "<b>Парсинг запущен</b>",
                    progress_bar(0, len(channels)),
                    "Подготавливаю источники и подключаюсь к Telegram.",
                    "",
                    f"Каналов в запуске: <b>{len(channels)}</b>",
                    f"Лимит: <b>{limit}</b>",
                    f"Период: <b>{period_label}</b>",
                ]
            ),
            back_to_menu_keyboard(),
        )
        result = await container.parse_channels.execute(user_id, channels, request, progress=track_channel_progress)

        if not result.posts and not result.errors:
            await update_parse_status(
                "\n".join(
                    [
                        "<b>Парсинг завершен</b>",
                        progress_bar(len(channels), len(channels)),
                        "Новых постов не найдено.",
                    ]
                )
            )
            await callback.message.answer(
                f"Новых постов нет. Пропущено дублей: {result.skipped_duplicates}.",
                reply_markup=back_to_menu_keyboard(),
            )
        total_posts = len(result.posts)
        for post_index, post in enumerate(result.posts, start=1):
            await update_parse_status(
                "\n".join(
                    [
                        "<b>Отправляю найденные посты</b>",
                        progress_bar(post_index, total_posts),
                        f"Пост: <b>{post_index}</b> из <b>{total_posts}</b>",
                        f"Источник: <b>{clean(post.source_title)}</b>",
                    ]
                )
            )
            post_key = f"{user_id}_{post.source}_{post.telegram_message_id}".replace(":", "_")
            parsed_post_cache[post_key] = AiPostInput(
                source_title=post.source_title,
                source=post.source,
                html_text=post.html_text,
                media=post.media,
            )
            caption = (
                f"<b>{clean(post.source_title)}</b>\n"
                f"<code>@{clean(post.source)}</code>\n"
                f"{post.published_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"{post.html_text}"
            )
            if post.media:
                first_media = post.media[0]
                media_file = FSInputFile(first_media.file_path)
                try:
                    if first_media.kind == "photo":
                        await callback.message.answer_photo(
                            photo=media_file,
                            caption=caption,
                            reply_markup=ai_post_keyboard(post_key, can_publish=bool(container.settings.publish_channel_id)),
                        )
                    elif first_media.kind == "video":
                        await callback.message.answer_video(
                            video=media_file,
                            caption=caption,
                            reply_markup=ai_post_keyboard(post_key, can_publish=bool(container.settings.publish_channel_id)),
                        )
                    else:
                        await callback.message.answer(
                            caption,
                            disable_web_page_preview=True,
                            reply_markup=ai_post_keyboard(post_key, can_publish=bool(container.settings.publish_channel_id)),
                        )
                except TelegramBadRequest:
                    if first_media.kind == "photo":
                        await callback.message.answer_photo(photo=media_file, caption="Медиа из поста")
                    elif first_media.kind == "video":
                        await callback.message.answer_video(video=media_file, caption="Медиа из поста")
                    await callback.message.answer(
                        (
                            f"Источник: <b>{clean(post.source_title)}</b>\n"
                            f"<code>@{clean(post.source)}</code>\n"
                            f"{post.published_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                            "Текст поста содержит сложное форматирование, поэтому отправлен отдельным сообщением."
                        ),
                        disable_web_page_preview=True,
                    )
                    await callback.message.answer(
                        post.html_text,
                        disable_web_page_preview=True,
                        reply_markup=ai_post_keyboard(post_key, can_publish=bool(container.settings.publish_channel_id)),
                    )
            else:
                await callback.message.answer(
                    caption,
                    disable_web_page_preview=True,
                    reply_markup=ai_post_keyboard(post_key, can_publish=bool(container.settings.publish_channel_id)),
                )

        if result.errors:
            await callback.message.answer(
                "<b>Ошибки во время парсинга</b>\n" + "\n".join(f"• {clean(error)}" for error in result.errors),
                reply_markup=back_to_menu_keyboard(),
            )
        summary_lines = [
            "<b>Парсинг завершен</b>",
            f"• отправлено постов: <b>{len(result.posts)}</b>",
            f"• пропущено дублей: <b>{result.skipped_duplicates}</b>",
        ]
        if result.errors:
            summary_lines.append(f"• ошибок: <b>{len(result.errors)}</b>")
        await update_parse_status(
            "\n".join(
                [
                    "<b>Готово</b>",
                    progress_bar(1, 1),
                    "Все найденные посты отправлены ниже.",
                ]
            )
        )
        await callback.message.answer(
            "\n".join(summary_lines),
            reply_markup=back_to_menu_keyboard(),
        )

    @router.callback_query(MenuCallback.filter(F.action == "ai_post"))
    async def ai_process_post(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        post_key = callback_data.extra or ""
        post = parsed_post_cache.get(post_key)
        can_publish = bool(container.settings.publish_channel_id)
        if post is None:
            await callback.answer("Пост больше не доступен для ИИ-обработки. Запусти парсинг заново.", show_alert=True)
            return

        await callback.answer("ИИ обрабатывает пост...")
        loading_task = asyncio.create_task(
            animate_ai_loading(callback.message, post_key, can_publish)
        )
        try:
            processed = sanitize_telegram_html(await container.ai_post_processor.process(post))
            updated_post = AiPostInput(
                source_title=post.source_title,
                source=post.source,
                html_text=processed,
                media=post.media,
            )
            parsed_post_cache[post_key] = updated_post
        except (DomainError, ExternalServiceError) as exc:
            await stop_ai_loading(callback.message, loading_task, post_key, can_publish)
            await callback.message.answer(f"Не удалось обработать пост через ИИ: {exc}", reply_markup=back_to_menu_keyboard())
            return

        await stop_ai_loading(callback.message, loading_task, post_key, can_publish)

        try:
            await send_post_preview(
                callback.message,
                updated_post,
                reply_markup=ai_post_keyboard(post_key, can_publish=can_publish),
                title="ИИ-версия поста",
            )
        except TelegramBadRequest:
            await callback.message.answer(
                "<b>ИИ-версия поста</b>\n"
                "Telegram не принял часть HTML-разметки, поэтому текст отправлен упрощенно.",
                reply_markup=back_to_menu_keyboard(),
            )
            await callback.message.answer(processed.replace("<", "").replace(">", ""), disable_web_page_preview=True)

    @router.callback_query(MenuCallback.filter(F.action == "publish_post"))
    async def publish_post(callback: CallbackQuery, callback_data: MenuCallback) -> None:
        post_key = callback_data.extra or ""
        post = parsed_post_cache.get(post_key)
        target_channel = container.settings.publish_channel_id.strip()
        if not target_channel:
            await callback.answer("PUBLISH_CHANNEL_ID не настроен", show_alert=True)
            return
        if post is None:
            await callback.answer("Пост больше не доступен. Запусти парсинг заново.", show_alert=True)
            return

        await callback.answer("Публикую пост...")
        try:
            await publish_post_to_channel(callback.message.bot, target_channel, post)
        except TelegramBadRequest as exc:
            error_text = str(exc)
            if "chat not found" in error_text.lower():
                await callback.message.answer(
                    (
                        "<b>Публикация не удалась</b>\n"
                        "Telegram не нашел целевой канал.\n\n"
                        "Проверь настройки:\n"
                        "1. Для приватного канала в <code>PUBLISH_CHANNEL_ID</code> нужен numeric id вида <code>-100...</code>.\n"
                        "2. Бот должен быть администратором канала с правом публикации.\n"
                        "3. После добавления бота в канал опубликуй любой новый тестовый пост и повтори попытку.\n\n"
                        "Для диагностики отправь команду <code>/publish_debug</code>."
                    ),
                    reply_markup=back_to_menu_keyboard(),
                )
            else:
                await callback.message.answer(
                    f"<b>Публикация не удалась</b>\n<code>{clean(exc)}</code>",
                    reply_markup=back_to_menu_keyboard(),
                )
            return

        await callback.message.answer(
            "<b>Пост опубликован</b>\nМатериал отправлен в целевой канал без пересылки.",
            reply_markup=back_to_menu_keyboard(),
        )

    @router.callback_query(MenuCallback.filter(F.action == "ai_post_loading"))
    async def ai_post_loading(callback: CallbackQuery) -> None:
        await callback.answer("ИИ уже обрабатывает этот пост...")

    dispatcher.include_router(router)


async def safe_edit(callback: CallbackQuery, text: str, reply_markup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=reply_markup)


def ai_loading_markup(post_key: str, can_publish: bool, frame: int) -> InlineKeyboardMarkup:
    frames = (
        "ИИ обрабатывает [●○○]",
        "ИИ обрабатывает [○●○]",
        "ИИ обрабатывает [○○●]",
    )
    rows = [
        [
            InlineKeyboardButton(
                text=frames[frame % len(frames)],
                callback_data=MenuCallback(action="ai_post_loading", extra=post_key).pack(),
            )
        ]
    ]
    if can_publish:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Опубликовать в канал",
                    callback_data=MenuCallback(action="publish_post", extra=post_key).pack(),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="← В меню", callback_data=MenuCallback(action="main").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def animate_ai_loading(message: Message, post_key: str, can_publish: bool) -> None:
    frame = 0
    try:
        while True:
            await message.edit_reply_markup(
                reply_markup=ai_loading_markup(post_key, can_publish, frame)
            )
            frame += 1
            await asyncio.sleep(0.7)
    except TelegramBadRequest:
        return
    except asyncio.CancelledError:
        raise


async def stop_ai_loading(
    message: Message,
    loading_task: asyncio.Task,
    post_key: str,
    can_publish: bool,
) -> None:
    loading_task.cancel()
    try:
        await loading_task
    except asyncio.CancelledError:
        pass
    try:
        await message.edit_reply_markup(
            reply_markup=ai_post_keyboard(post_key, can_publish=can_publish)
        )
    except TelegramBadRequest:
        pass


def progress_bar(current: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "[----------] 0%"
    current = max(0, min(current, total))
    filled = round(width * current / total)
    percent = round(100 * current / total)
    return f"[{'#' * filled}{'-' * (width - filled)}] {percent}%"


async def send_post_preview(message: Message, post: AiPostInput, reply_markup, title: str) -> None:
    caption = f"<b>{escape(title, quote=False)}</b>\n<code>@{escape(post.source, quote=False)}</code>\n\n{post.html_text}"
    if post.media:
        first_media = post.media[0]
        media_file = FSInputFile(first_media.file_path)
        if first_media.kind == "photo":
            await message.answer_photo(photo=media_file, caption=caption, reply_markup=reply_markup)
            return
        if first_media.kind == "video":
            await message.answer_video(video=media_file, caption=caption, reply_markup=reply_markup)
            return
    await message.answer(caption, disable_web_page_preview=True, reply_markup=reply_markup)


async def publish_post_to_channel(bot, target_channel: str, post: AiPostInput) -> None:
    if post.media:
        first_media = post.media[0]
        media_file = FSInputFile(first_media.file_path)
        if first_media.kind == "photo":
            await bot.send_photo(chat_id=target_channel, photo=media_file, caption=post.html_text)
            return
        if first_media.kind == "video":
            await bot.send_video(chat_id=target_channel, video=media_file, caption=post.html_text)
            return
    await bot.send_message(chat_id=target_channel, text=post.html_text, disable_web_page_preview=True)

