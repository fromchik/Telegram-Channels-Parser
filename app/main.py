from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.domain.exceptions import ExternalServiceError
from app.infrastructure.config import load_settings
from app.infrastructure.container import build_container
from app.infrastructure.logging import configure_logging, get_logger
from app.presentation.handlers import register_handlers


async def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    container = build_container(settings)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()

    register_handlers(dispatcher, container)

    logger = get_logger(__name__)
    logger.info("bot.starting")

    try:
        async with container.lifespan():
            await dispatcher.start_polling(bot)
    except ExternalServiceError as exc:
        logger.error("bot.startup_failed", error=str(exc))
        raise


if __name__ == "__main__":
    asyncio.run(main())
