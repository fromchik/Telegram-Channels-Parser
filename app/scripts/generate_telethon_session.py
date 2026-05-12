from __future__ import annotations

import asyncio

from telethon import TelegramClient

from app.infrastructure.config import load_settings


async def main() -> None:
    settings = load_settings()
    session_file = settings.normalized_telethon_session_file
    client = TelegramClient(session_file, settings.telegram_api_id, settings.telegram_api_hash)

    print(f"Using session file: {session_file}.session")
    print("Telegram will ask for phone, code, and password if needed.")

    async with client:
        await client.start()
        me = await client.get_me()
        print(f"Authorized as: {me.username or me.first_name or me.id}")
        print("Session saved. You can now run: python -m app.main")


if __name__ == "__main__":
    asyncio.run(main())
